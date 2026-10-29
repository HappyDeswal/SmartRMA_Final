#!/usr/bin/env python3
"""Supervise three separate local services; one worker owns the SQLite database."""
import argparse,logging,os,secrets,signal,socket,subprocess,sys,threading,time
from pathlib import Path
import httpx,uvicorn
from app.config import Settings
from app.main import create_app
from app.nodes import PORTS

ROOT=Path(__file__).resolve().parent

def health(port):
    try:
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=1) as client:
            response=client.get(f'http://127.0.0.1:{port}/health');response.raise_for_status();return response.json()
    except (httpx.HTTPError,ValueError):return None

def check_port(port):
    with socket.socket() as probe:
        # Match Uvicorn's reuse behavior: recently closed connections must not
        # prevent an immediate supervised restart (TIME_WAIT is not a listener).
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:probe.bind(('127.0.0.1',port))
        except OSError:raise RuntimeError(f'Port {port} is already in use. No existing service was stopped.')

def main():
    parser=argparse.ArgumentParser(description='SmartRMA — three local AI hardware-return nodes')
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8010)
    parser.add_argument('--status',action='store_true',help='Check all three service processes.')
    args=parser.parse_args()
    if not 1<=args.port<=65535 or args.port in {8011,8012}:parser.error('Choose a gateway port other than the internal ports 8011/8012.')
    if args.status:
        statuses=[(role,port,health(port)) for role,port in [('gateway',args.port),('policy',8011),('vision',8012)]]
        for role,port,result in statuses:print(f'{role}: {port} '+('online' if result and result.get('application')=='happy_project' and result.get('role')==role else 'offline'))
        return 0 if all(r and r.get('application')=='happy_project' and r.get('role')==role for role,_,r in statuses) else 1
    if 'HAPPY_ORIGIN' not in os.environ:os.environ['HAPPY_ORIGIN']=f'http://127.0.0.1:{args.port}'
    os.environ['HAPPY_THREE_NODE']='1';os.environ['HAPPY_NODE_TOKEN']=secrets.token_urlsafe(48)
    settings=Settings.environment()
    settings.data_dir.mkdir(parents=True,exist_ok=True)
    lock_path=settings.data_dir/'inference.lock'
    with open(lock_path,'ab') as handle:
        if handle.tell()==0:handle.write(b'0')
    lock_path.chmod(0o600)
    os.environ['HAPPY_INFERENCE_LOCK']=str(lock_path)
    if args.host not in {'127.0.0.1','localhost'} and not settings.secure_cookie:
        parser.error('External listening requires HAPPY_ORIGIN=https://your-host and HAPPY_SECURE_COOKIE=1 behind TLS.')
    try:
        for port in [args.port,8011,8012]:check_port(port)
    except RuntimeError as exc:parser.error(str(exc))
    children=[];stop=threading.Event()
    # Uvicorn replays shutdown signals after restoring prior handlers. Keep those
    # handlers non-terminating until our child-process cleanup has completed.
    previous_handlers={sig:signal.signal(sig,lambda signum,frame:stop.set()) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        for role in ['vision','policy']:
            children.append(subprocess.Popen([sys.executable,'-m','app.service','--role',role],cwd=ROOT,env=os.environ.copy()))
        deadline=time.monotonic()+20
        while True:
            if stop.is_set():return 130
            if any(child.poll() is not None for child in children):raise RuntimeError('An internal node failed to start. Check the service log.')
            if all((result:=health(PORTS[role])) and result.get('role')==role and result.get('application')=='happy_project' for role in ['vision','policy']):break
            if time.monotonic()>=deadline:raise RuntimeError('Internal node startup timed out.')
            time.sleep(.2)
        def monitor():
            while not stop.wait(1):
                if any(child.poll() is not None for child in children):
                    logging.error('An internal node stopped; shutting down the cluster so it can restart consistently.')
                    os.kill(os.getpid(),signal.SIGTERM);return
        threading.Thread(target=monitor,name='happy-node-supervisor',daemon=True).start()
        logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
        print(f'SmartRMA — three nodes\nNode 1 gateway/UI: {settings.origin}\nNode 2 policy/chat: 127.0.0.1:8011\nNode 3 local vision/inference: 127.0.0.1:8012',flush=True)
        uvicorn.run(create_app(settings),host=args.host,port=args.port,workers=1,proxy_headers=False,server_header=False)
    finally:
        stop.set()
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        for sig,handler in previous_handlers.items():signal.signal(sig,handler)
    return 0
if __name__=='__main__':sys.exit(main())
