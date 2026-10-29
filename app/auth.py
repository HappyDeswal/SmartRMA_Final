import hashlib,hmac,json,os,secrets,time,uuid
from .storage import now,Conflict

COOKIE='happy_session'
class LoginRateLimit(Conflict):pass

def password_hash(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return salt.hex()+':'+digest.hex()

def password_matches(password,encoded):
    try:
        salt,digest=encoded.split(':')
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32)
        return hmac.compare_digest(actual.hex(),digest)
    except (ValueError,TypeError):return False

class Auth:
    def __init__(self,store):
        self.store=store
        self.dummy=password_hash(secrets.token_urlsafe(24))

    def bootstrap(self):
        with self.store.connect(True) as con:
            if con.execute('SELECT count(*) FROM users').fetchone()[0]:return
            password=secrets.token_urlsafe(24);ident=uuid.uuid4().hex
            user={'id':ident,'username':'admin','password':password_hash(password),'role':'admin','active':1,'created':now()}
            con.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(*user.values(),self.store.user_seal(user)))
            path=self.store.directory/'first_login.json'
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:
                json.dump({'username':'admin','password':password,'note':'Change this password in Account. This owner-only file is removed after admin password rotation.'},f,indent=2)
                f.flush();os.fsync(f.fileno())

    def login(self,username,password,peer):
        key=hashlib.sha256((peer+'|'+username.casefold()).encode()).hexdigest();ip_key=hashlib.sha256(('peer|'+peer).encode()).hexdigest();current=time.time()
        with self.store.connect(True) as con:
            for k,maximum in [(key,8),(ip_key,30)]:
                row=con.execute('SELECT * FROM login_limits WHERE key=?',(k,)).fetchone()
                if row and current-row['window']<900 and row['failures']>=maximum:
                    raise LoginRateLimit('Too many sign-in attempts. Wait 15 minutes before retrying.')
            user=con.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',(username,)).fetchone()
            valid=password_matches(password,user['password'] if user else self.dummy)
            if not valid or not user or not user['active'] or not hmac.compare_digest(user['seal'],self.store.user_seal(user)):
                for k in [key,ip_key]:
                    old=con.execute('SELECT * FROM login_limits WHERE key=?',(k,)).fetchone()
                    count=old['failures']+1 if old and current-old['window']<900 else 1
                    window=old['window'] if old and current-old['window']<900 else current
                    con.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(k,count,window))
                # Failure counts must commit even though credentials are refused.
                return None
            con.execute('DELETE FROM login_limits WHERE key=?',(key,));con.execute('DELETE FROM sessions WHERE expires<?',(current,))
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,current+self.store.settings.session_hours*3600))
            return {'token':token,'csrf':csrf,'user':{'id':user['id'],'username':user['username'],'role':user['role']}}

    def local_session(self):
        """Create a regular CSRF-protected session for the verified local owner."""
        with self.store.connect(True) as con:
            user=con.execute("SELECT * FROM users WHERE username='admin' AND role='admin' AND active=1").fetchone()
            if not user or not hmac.compare_digest(user['seal'],self.store.user_seal(user)):return None
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            con.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,time.time()+self.store.settings.session_hours*3600))
            return token

    def session(self,token):
        if not token or len(token)>256:return None
        with self.store.connect() as con:
            row=con.execute('SELECT s.csrf,s.expires,u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
            return dict(row) if row and hmac.compare_digest(row['seal'],self.store.user_seal(row)) else None

    def logout(self,token):
        with self.store.connect(True) as con:con.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))

    def create_user(self,body):
        with self.store.connect(True) as con:
            if con.execute('SELECT 1 FROM users WHERE username=? COLLATE NOCASE',(body.username,)).fetchone():raise Conflict('Username already exists.')
            ident=uuid.uuid4().hex
            user={'id':ident,'username':body.username,'password':password_hash(body.password),'role':body.role,'active':1,'created':now()}
            con.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(*user.values(),self.store.user_seal(user)))
            return {'id':ident,'username':body.username,'role':body.role}

    def change_password(self,user,old,new):
        with self.store.connect(True) as con:
            row=con.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
            if not password_matches(old,row['password']):return False
            updated={**dict(row),'password':password_hash(new)}
            con.execute('UPDATE users SET password=?,seal=? WHERE id=?',(updated['password'],self.store.user_seal(updated),user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        if user['username']=='admin':
            (self.store.directory/'first_login.json').unlink(missing_ok=True)
        return True
