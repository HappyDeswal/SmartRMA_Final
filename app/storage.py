"""Transactional case storage, durable jobs and HMAC-sealed audit snapshots."""
import fcntl,hashlib,hmac,json,os,secrets,sqlite3,time,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from .images import similar_hash
from .domain import aggregate,decide,tier

ZERO='0'*64
class Conflict(Exception): pass
class IntegrityFailure(Exception): pass
class NotFound(Exception): pass

def now(): return datetime.now(timezone.utc).isoformat()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(value): return hashlib.sha256(value).hexdigest()

def patched_sqlite(version):
    return version>=(3,51,3) or (version[:2]==(3,50) and version>=(3,50,7)) or (version[:2]==(3,44) and version>=(3,44,6))

class Store:
    def __init__(self,settings):
        self.settings=settings;self.directory=settings.data_dir.resolve();self.directory.mkdir(parents=True,exist_ok=True)
        marker=self.directory/'.happy_data'
        if not marker.exists() and any(self.directory.iterdir()):
            raise RuntimeError('Use a dedicated empty HAPPY_DATA_DIR, or an existing Happy Project data directory.')
        marker.touch(mode=0o600,exist_ok=True);os.chmod(self.directory,0o700)
        self.path=self.directory/'happy.sqlite3';self.key_path=self.directory/'audit.key';self.lock=None
        if not self.key_path.exists():
            if self.path.exists() and self.path.stat().st_size: raise RuntimeError('Audit key missing. Restore the database and its matching key from backup.')
            fd=os.open(self.key_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32));f.flush();os.fsync(f.fileno())
        self.key=self.key_path.read_bytes()
        if len(self.key)!=32: raise RuntimeError('Invalid audit key.')
        os.chmod(self.key_path,0o600)
        with self.connect() as con:
            version=con.execute('PRAGMA user_version').fetchone()[0]
            if version not in {0,1}: raise RuntimeError('Unsupported database schema version; no data was changed.')
            journal='WAL' if patched_sqlite(sqlite3.sqlite_version_info) else 'DELETE'
            con.execute('PRAGMA journal_mode='+journal)
            if version==0:
                con.executescript('''BEGIN IMMEDIATE;
                CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT NOT NULL UNIQUE COLLATE NOCASE,password TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','reviewer','viewer')),active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL,seal TEXT NOT NULL);
                CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
                CREATE INDEX session_expiry ON sessions(expires);
                CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,window REAL NOT NULL);
                CREATE TABLE images(id TEXT PRIMARY KEY,data BLOB NOT NULL,mime TEXT NOT NULL,phash TEXT NOT NULL,width INTEGER NOT NULL,height INTEGER NOT NULL,software TEXT NOT NULL,edited INTEGER NOT NULL);
                CREATE TABLE cases(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,status TEXT NOT NULL,tier TEXT NOT NULL,value_cents INTEGER NOT NULL,revision INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL,updated TEXT NOT NULL,data_json TEXT NOT NULL,event_hash TEXT NOT NULL);
                CREATE INDEX cases_queue ON cases(archived,status,created DESC);
                CREATE INDEX cases_order ON cases(order_id);
                CREATE TABLE case_images(case_id TEXT NOT NULL REFERENCES cases(id),image_id TEXT NOT NULL REFERENCES images(id),slot INTEGER NOT NULL,PRIMARY KEY(case_id,slot));
                CREATE TABLE audit(seq INTEGER PRIMARY KEY,case_id TEXT NOT NULL REFERENCES cases(id),entry_json TEXT NOT NULL,prev_hash TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,seal TEXT NOT NULL,created TEXT NOT NULL);
                CREATE INDEX audit_case ON audit(case_id,seq DESC);
                CREATE TABLE jobs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL UNIQUE REFERENCES cases(id),status TEXT NOT NULL,stage TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);
                CREATE INDEX jobs_queue ON jobs(status,created);
                CREATE TABLE idempotency(user_id TEXT NOT NULL REFERENCES users(id),key TEXT NOT NULL,fingerprint TEXT NOT NULL,case_id TEXT NOT NULL REFERENCES cases(id),job_id TEXT NOT NULL REFERENCES jobs(id),PRIMARY KEY(user_id,key));
                CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Audit events cannot be updated'); END;
                CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Audit events cannot be deleted'); END;
                CREATE TRIGGER image_no_update BEFORE UPDATE ON images BEGIN SELECT RAISE(ABORT,'Image bytes are immutable'); END;
                CREATE TRIGGER image_no_delete BEFORE DELETE ON images BEGIN SELECT RAISE(ABORT,'Image bytes are immutable'); END;
                PRAGMA user_version=1; COMMIT;''')
        os.chmod(self.path,0o600)

    @contextmanager
    def connect(self,write=False):
        con=sqlite3.connect(self.path,timeout=8,isolation_level=None);con.row_factory=sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON');con.execute('PRAGMA busy_timeout=8000');con.execute('PRAGMA synchronous=FULL')
        try:
            if write:con.execute('BEGIN IMMEDIATE')
            yield con
            if write:con.commit()
        except BaseException:
            if write:con.rollback()
            raise
        finally:con.close()

    def acquire(self):
        self.lock=open(self.directory/'service.lock','a+b');os.chmod(self.directory/'service.lock',0o600)
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock.close();self.lock=None;raise RuntimeError('Another Happy Project server already owns this data directory. Run one application worker.')
    def release(self):
        if self.lock:fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close();self.lock=None

    def _event(self,con,case,kind,actor):
        previous=con.execute('SELECT seq,hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        seq=previous['seq']+1 if previous else 1;parent=previous['hash'] if previous else ZERO
        entry={'seq':seq,'case_id':case['id'],'kind':kind,'actor':actor,'at':now(),
               'snapshot_hash':sha(canonical(case).encode()),'snapshot':case}
        text=canonical(entry);digest=sha((parent+text).encode());seal=hmac.new(self.key,digest.encode(),'sha256').hexdigest()
        con.execute('INSERT INTO audit VALUES(?,?,?,?,?,?,?)',(seq,case['id'],text,parent,digest,seal,entry['at']))
        con.execute('UPDATE cases SET status=?,tier=?,value_cents=?,revision=?,archived=?,updated=?,data_json=?,event_hash=? WHERE id=?',
                    (case['status'],case['tier'],case['value_cents'],case['revision'],int(case['archived']),case['updated'],canonical(case),digest,case['id']))
        return digest

    def user_seal(self,user):
        data={k:user[k] for k in ['id','username','password','role','active','created']}
        return hmac.new(self.key,canonical(data).encode(),'sha256').hexdigest()

    def _verify(self,con,blobs=False,check_cases=True):
        errors=[];previous=ZERO;latest={};seq=0
        for account in con.execute('SELECT * FROM users'):
            if not hmac.compare_digest(account['seal'],self.user_seal(account)):
                errors.append('Account record failed verification.')
        for row in con.execute('SELECT * FROM audit ORDER BY seq'):
            seq+=1
            try:
                entry=json.loads(row['entry_json']);digest=sha((row['prev_hash']+canonical(entry)).encode())
                seal=hmac.new(self.key,digest.encode(),'sha256').hexdigest()
                if row['seq']!=seq or entry['seq']!=seq or entry['case_id']!=row['case_id'] or entry['at']!=row['created'] or row['prev_hash']!=previous or digest!=row['hash'] or not hmac.compare_digest(seal,row['seal']) or entry['snapshot_hash']!=sha(canonical(entry['snapshot']).encode()):
                    errors.append(f'Audit event {row["seq"]} failed verification.')
                latest[row['case_id']]=(entry['snapshot'],row['hash'])
            except (ValueError,KeyError,TypeError):errors.append(f'Audit event {row["seq"]} is invalid.')
            previous=row['hash']
        found=set()
        for row in (con.execute('SELECT * FROM cases') if check_cases else []):
            found.add(row['id'])
            try:
                case=json.loads(row['data_json']);expected=latest.get(row['id'])
                links=[(r['slot'],r['image_id']) for r in con.execute('SELECT slot,image_id FROM case_images WHERE case_id=? ORDER BY slot',(row['id'],))]
                declared=sorted((p['slot'],p['id']) for p in case['photos'])
                for photo in case['photos']:
                    original=con.execute('SELECT mime,phash,width,height,software,edited FROM images WHERE id=?',(photo['id'],)).fetchone()
                    if not original or any(original[k]!=photo[k] for k in ['mime','phash','width','height','software','edited']):errors.append('Image metadata failed verification for '+photo['id'])
                if not expected or canonical(case)!=canonical(expected[0]) or row['event_hash']!=expected[1] or links!=declared or any(row[k]!=case[k] for k in ['order_id','status','tier','value_cents','revision','created','updated']) or bool(row['archived'])!=case['archived']:
                    errors.append('Dossier '+row['id']+' failed verification.')
            except (ValueError,KeyError,TypeError):errors.append('Dossier '+row['id']+' is invalid.')
        if check_cases:
            for missing in set(latest)-found:errors.append('Missing dossier '+missing)
        checked=0
        if blobs:
            for row in con.execute('SELECT id,data FROM images'):
                checked+=1
                if sha(row['data'])!=row['id']:errors.append('Image '+row['id']+' failed verification.')
        return {'valid':not errors,'events':seq,'cases':len(found),'images_checked':checked,'head':previous,'errors':errors}

    def verify(self):
        with self.connect() as con:
            con.execute('BEGIN')
            report=self._verify(con,True);report['database_ok']=con.execute('PRAGMA quick_check').fetchone()[0]=='ok'
            report['valid']=report['valid'] and report['database_ok'];return report

    def _guard(self,con):
        if not self._verify(con)['valid']:raise IntegrityFailure('Audit or dossier verification failed. Restore a verified backup before changing records.')

    def submit(self,user,intake,photos,key):
        meta=intake.model_dump(mode='json');meta['value']=format(intake.value,'.2f');meta['slots']=sorted(meta['slots']);photos=sorted(photos,key=lambda p:p['slot'])
        fingerprint=sha(canonical({'intake':meta,'photos':[(p['slot'],p['id']) for p in photos]}).encode())
        with self.connect(True) as con:
            existing=con.execute('SELECT * FROM idempotency WHERE user_id=? AND key=?',(user['id'],key)).fetchone()
            if existing:
                if existing['fingerprint']!=fingerprint:raise Conflict('This idempotency key was already used for different input.')
                return {'case_id':existing['case_id'],'job_id':existing['job_id'],'reused':True}
            self._guard(con)
            if con.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]>=self.settings.max_queued_jobs:
                raise Conflict('The local inspection queue is full. Try again after current work completes.')
            ident='RMA-'+uuid.uuid4().hex[:20].upper();job=uuid.uuid4().hex;timestamp=now()
            descriptors=[]
            for p in photos:
                old=con.execute('SELECT data FROM images WHERE id=?',(p['id'],)).fetchone()
                if old and sha(old['data'])!=p['id']:raise IntegrityFailure('Stored image integrity failed.')
                con.execute('INSERT OR IGNORE INTO images VALUES(?,?,?,?,?,?,?,?)',(p['id'],p['raw'],p['mime'],p['phash'],p['width'],p['height'],p['software'],int(p['edited'])))
                descriptors.append({k:v for k,v in p.items() if k not in {'raw'}})
            case={'id':ident,'order_id':intake.order_id,'product_type':intake.product_type.value,'product_name':intake.product_name,
                  'manufacturer':intake.manufacturer,'serial':intake.serial,'identity_status':'not_verified',
                  'value_cents':intake.cents,'tier':tier(intake.cents),'complaint':intake.complaint,'photos':descriptors,
                  'status':'queued','revision':1,'archived':False,'created':timestamp,'updated':timestamp,
                  'submitted_by':user['username'],'decision':None,'evidence':None,'policy':None,'observations':[]}
            con.execute('INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?)',(ident,intake.order_id,'queued',case['tier'],intake.cents,1,0,timestamp,timestamp,canonical(case),''))
            for p in photos:con.execute('INSERT INTO case_images VALUES(?,?,?)',(ident,p['id'],p['slot']))
            self._event(con,case,'SUBMITTED',user['username'])
            con.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,ident,'queued','Waiting for local inspection',0,None,timestamp,timestamp))
            con.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(user['id'],key,fingerprint,ident,job))
            return {'case_id':ident,'job_id':job,'reused':False}

    def get_case(self,ident):
        with self.connect() as con:
            row=con.execute('SELECT * FROM cases WHERE id=?',(ident,)).fetchone()
            if not row:raise NotFound('Case not found.')
            event=con.execute('SELECT * FROM audit WHERE case_id=? ORDER BY seq DESC LIMIT 1',(ident,)).fetchone()
            try:
                case=json.loads(row['data_json'])
                entry=json.loads(event['entry_json']);digest=sha((event['prev_hash']+canonical(entry)).encode())
                valid=(case==entry['snapshot'] and sha(canonical(case).encode())==entry['snapshot_hash'] and digest==event['hash']==row['event_hash'] and hmac.compare_digest(event['seal'],hmac.new(self.key,digest.encode(),'sha256').hexdigest()) and all(row[k]==case[k] for k in ['order_id','status','tier','value_cents','revision','created','updated']) and bool(row['archived'])==case['archived'])
            except (ValueError,KeyError,TypeError):valid=False
            if not valid:raise IntegrityFailure('This dossier failed verification; open a verified historical event or restore a backup.')
            job=con.execute('SELECT id,status,stage,error,attempts FROM jobs WHERE case_id=?',(ident,)).fetchone()
            return {**case,'integrity':'verified','event_hash':row['event_hash'],'job':dict(job) if job else None}

    def list_cases(self,status='',search='',product='',level='',archived=False,limit=25,offset=0):
        clauses=['archived=?'];params=[int(archived)]
        if status:clauses.append('status=?');params.append(status)
        if level:clauses.append('tier=?');params.append(level)
        if search:
            escaped=search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            clauses.append("(id LIKE ? ESCAPE '\\' OR order_id LIKE ? ESCAPE '\\' OR json_extract(CASE WHEN json_valid(data_json) THEN data_json ELSE '{}' END,'$.product_name') LIKE ? ESCAPE '\\')");params.extend(['%'+escaped+'%']*3)
        if product:clauses.append("json_extract(CASE WHEN json_valid(data_json) THEN data_json ELSE '{}' END,'$.product_type')=?");params.append(product)
        where=' AND '.join(clauses)
        with self.connect() as con:
            total=con.execute('SELECT count(*) FROM cases WHERE '+where,params).fetchone()[0]
            ids=[r['id'] for r in con.execute('SELECT id FROM cases WHERE '+where+' ORDER BY created DESC,id DESC LIMIT ? OFFSET ?',params+[limit,offset])]
            items=[]
            for ident in ids:
                try:
                    c=self.get_case(ident);items.append({k:c[k] for k in ['id','order_id','product_type','product_name','value_cents','tier','status','revision','created','decision','integrity','job','archived']})
                except IntegrityFailure:items.append({'id':ident,'status':'integrity_failure','integrity':'failed'})
            counts={r['status']:r['n'] for r in con.execute('SELECT status,count(*) n FROM cases WHERE archived=0 GROUP BY status')}
            return {'items':items,'total':total,'limit':limit,'offset':offset,'counts':counts}

    def image(self,ident):
        with self.connect() as con:
            row=con.execute('SELECT * FROM images WHERE id=?',(ident,)).fetchone()
            if not row or not con.execute('SELECT 1 FROM case_images WHERE image_id=? LIMIT 1',(ident,)).fetchone():raise NotFound('Image not found.')
            if sha(row['data'])!=ident or row['mime'] not in {'image/jpeg','image/png','image/webp','image/bmp'}:raise IntegrityFailure('Image bytes or metadata failed verification.')
            return dict(row)

    def history(self,ident):
        with self.connect() as con:
            con.execute('BEGIN')
            if not self._verify(con,check_cases=False)['valid']:raise IntegrityFailure('Audit verification failed.')
            if not con.execute('SELECT 1 FROM cases WHERE id=?',(ident,)).fetchone():raise NotFound('Case not found.')
            return [{'seq':r['seq'],'hash':r['hash'],**json.loads(r['entry_json'])} for r in con.execute('SELECT * FROM audit WHERE case_id=? ORDER BY seq DESC',(ident,))]

    def historical(self,ident,event_hash):
        with self.connect() as con:
            con.execute('BEGIN')
            if not self._verify(con,check_cases=False)['valid']:raise IntegrityFailure('Audit verification failed.')
            row=con.execute('SELECT * FROM audit WHERE case_id=? AND hash=?',(ident,event_hash)).fetchone()
            if not row:raise NotFound('Historical event not found.')
            return {'event_hash':row['hash'],'historical':True,'integrity':'verified',**json.loads(row['entry_json'])}

    def audit_page(self,limit,offset):
        with self.connect() as con:
            con.execute('BEGIN')
            if not self._verify(con,check_cases=False)['valid']:raise IntegrityFailure('Audit verification failed.')
            rows=con.execute('SELECT seq,case_id,hash,entry_json FROM audit ORDER BY seq DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
            return {'total':con.execute('SELECT count(*) FROM audit').fetchone()[0],
                    'items':[{'seq':r['seq'],'case_id':r['case_id'],'hash':r['hash'],**{k:v for k,v in json.loads(r['entry_json']).items() if k in {'kind','actor','at'}}} for r in rows]}

    def recover_jobs(self):
        with self.connect(True) as con:
            con.execute("UPDATE jobs SET status='queued',stage='Resumed after restart',updated=? WHERE status='running'",(now(),))

    def claim_job(self):
        with self.connect(True) as con:
            row=con.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created,id LIMIT 1").fetchone()
            if not row:return None
            con.execute("UPDATE jobs SET status='running',attempts=attempts+1,stage='Inspecting uploaded photos',updated=? WHERE id=?",(now(),row['id']))
            return dict(row)

    def progress(self,job,stage):
        with self.connect(True) as con:con.execute('UPDATE jobs SET stage=?,updated=? WHERE id=? AND status=?',(stage[:160],now(),job,'running'))

    def _check_case_photos(self,con,case):
        for photo in case['photos']:
            row=con.execute('SELECT * FROM images WHERE id=?',(photo['id'],)).fetchone()
            if not row or sha(row['data'])!=photo['id'] or any(row[k]!=photo[k] for k in ['mime','phash','width','height','software','edited']):
                raise IntegrityFailure('Original photo bytes or metadata failed verification.')

    def finalize(self,job,observations,model_names,policy):
        with self.connect(True) as con:
            self._guard(con)
            row=con.execute('SELECT * FROM jobs WHERE id=?',(job,)).fetchone()
            if not row or row['status']!='running':raise Conflict('Job is no longer running.')
            c=json.loads(con.execute('SELECT data_json FROM cases WHERE id=?',(row['case_id'],)).fetchone()[0])
            if len(observations)!=len(c['photos']) or len(model_names)!=len(c['photos']):raise Conflict('Every submitted photo requires an inspection result before finalization.')
            self._check_case_photos(con,c)
            evidence=aggregate(observations)
            similar=[]
            known=con.execute("SELECT i.phash,c.id,c.order_id FROM case_images ci JOIN images i ON i.id=ci.image_id JOIN cases c ON c.id=ci.case_id WHERE c.status IN ('approved','rejected','needs_review') AND c.id<>? AND c.order_id<>?",(c['id'],c['order_id'])).fetchall()
            for p in c['photos']:
                match=next((r['id'] for r in known if similar_hash(p['phash'],r['phash'])),None)
                if match:similar.append({'slot':p['slot'],'matched_case':match})
            decision=decide(c['value_cents'],evidence,policy,bool(similar),any(p['edited'] for p in c['photos']))
            c.update(status=decision['status'],decision=decision,evidence=evidence,policy=policy,
                     observations=[{'slot':p['slot'],'model':model,'observation':o.model_dump()} for p,model,o in zip(c['photos'],model_names,observations)],
                     similar_images=similar,revision=c['revision']+1,updated=now())
            self._event(con,c,'AUTOMATIC_DECISION','local_ai_rules')
            con.execute("UPDATE jobs SET status='complete',stage='Evaluation saved',error=NULL,updated=? WHERE id=?",(now(),job))
            return c

    def requeue_busy(self,ident):
        with self.connect(True) as con:
            con.execute("UPDATE jobs SET status='queued',stage='Waiting for the local model',attempts=max(0,attempts-1),updated=? WHERE id=? AND status='running'",(now(),ident))

    def fail_job(self,job,error):
        with self.connect(True) as con:
            con.execute("UPDATE jobs SET status='failed',stage='Processing failed; retry required',error=?,updated=? WHERE id=?",(error[:120],now(),job))

    def human_decision(self,ident,body,user):
        with self.connect(True) as con:
            self._guard(con)
            row=con.execute('SELECT data_json FROM cases WHERE id=?',(ident,)).fetchone()
            if not row:raise NotFound('Case not found.')
            c=json.loads(row[0])
            if c['revision']!=body.revision:raise Conflict('This case changed. Refresh before deciding.')
            if c['archived'] or c['status']=='queued':raise Conflict('Finish processing and unarchive the case before deciding.')
            self._check_case_photos(con,c)
            c.update(status=body.decision,updated=now(),revision=c['revision']+1,
                     decision={'status':body.decision,'source':'human','human_required':False,'reviewer':user['username'],
                               'reason_codes':['HUMAN_REVIEW'],'reasons':[body.reason],'tier':c['tier'],'risk':(c.get('decision') or {}).get('risk'),'rejection_kind':None})
            self._event(con,c,'HUMAN_DECISION',user['username']);return c

    def archive(self,ident,archived,revision,user):
        with self.connect(True) as con:
            self._guard(con);row=con.execute('SELECT data_json FROM cases WHERE id=?',(ident,)).fetchone()
            if not row:raise NotFound('Case not found.')
            c=json.loads(row[0])
            if c['revision']!=revision:raise Conflict('This case changed. Refresh first.')
            if c['status']=='queued':raise Conflict('Processing cases cannot be archived.')
            c.update(archived=archived,revision=c['revision']+1,updated=now())
            self._event(con,c,'ARCHIVED' if archived else 'UNARCHIVED',user['username']);return c

    def retry(self,ident,user):
        with self.connect(True) as con:
            self._guard(con);row=con.execute('SELECT * FROM jobs WHERE case_id=?',(ident,)).fetchone()
            if not row:raise NotFound('Case not found.')
            if row['status']!='failed':raise Conflict('Only failed processing jobs can be retried. A rejected request needs a new submission.')
            if row['attempts']>=3:raise Conflict('Retry limit reached; inspect service health before submitting a new request.')
            con.execute("UPDATE jobs SET status='queued',stage='Retry queued',error=NULL,updated=? WHERE id=?",(now(),row['id']))
            c=json.loads(con.execute('SELECT data_json FROM cases WHERE id=?',(ident,)).fetchone()[0]);c.update(updated=now(),revision=c['revision']+1)
            self._event(con,c,'PROCESSING_RETRY',user['username']);return row['id']

    def backup(self,destination):
        destination=Path(destination)
        if destination.exists():raise Conflict('Backup destination already exists.')
        destination.mkdir(parents=True,mode=0o700);os.chmod(destination,0o700)
        target=destination/'happy.sqlite3'
        with self.connect() as source:
            output=sqlite3.connect(target)
            try:source.backup(output)
            finally:output.close()
        os.chmod(target,0o600)
        fd=os.open(destination/'audit.key',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(self.key)
        (destination/'.happy_data').touch(mode=0o600)
        return destination
