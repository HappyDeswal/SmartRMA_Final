#!/usr/bin/env python3
"""Local owner administration. Never print passwords in terminal output."""
import argparse,json,os,secrets,sys
from app.config import Settings,ROOT
from app.storage import Store
from app.auth import password_hash

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('verify');backup=sub.add_parser('backup');backup.add_argument('destination')
    sub.add_parser('reset-admin',help='Stop server first; creates a new private first_login.json.')
    sub.add_parser('rebuild-policies',help='Rebuild local text index atomically. Restart server afterwards.')
    args=parser.parse_args()
    if args.command=='rebuild-policies':
        from app.indexing import rebuild
        print(json.dumps(rebuild(ROOT/'resources/policies'),indent=2));return 0
    store=Store(Settings.environment())
    if args.command=='verify':
        report=store.verify();print(json.dumps(report,indent=2));return 0 if report['valid'] else 1
    if args.command=='backup':
        path=store.backup(args.destination);print('Consistent database and matching audit key backed up to',path);return 0
    if args.command=='reset-admin':
        store.acquire()
        try:
            with store.connect(True) as con:
                store._guard(con)
                row=con.execute("SELECT * FROM users WHERE username='admin'").fetchone()
                if not row:raise RuntimeError('Bootstrap administrator does not exist.')
                password=secrets.token_urlsafe(24);user={**dict(row),'password':password_hash(password),'active':1,'role':'admin'}
                path=store.directory/'first_login.json';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                with os.fdopen(fd,'w') as f:json.dump({'username':'admin','password':password,'note':'Change in Account after login.'},f);f.flush();os.fsync(f.fileno())
                con.execute('UPDATE users SET password=?,active=1,role=?,seal=? WHERE id=?',(user['password'],user['role'],store.user_seal(user),row['id']))
                con.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            print('Administrator reset. Read the private file:',path)
        finally:store.release()
        return 0
if __name__=='__main__':sys.exit(main())
