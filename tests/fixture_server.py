"""Disposable browser fixture. Explicit fake model, isolated temporary storage only."""
import sys,tempfile,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from app.main import create_app
from app.config import Settings
from test_application import FakeModels
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8111);args=parser.parse_args()
path=Path(tempfile.mkdtemp(prefix='happy-browser-fixture-'))
Path('/tmp/happy-fixture-path').write_text(str(path))
uvicorn.run(create_app(Settings(data_dir=path,origin=f'http://127.0.0.1:{args.port}'),FakeModels()),host='127.0.0.1',port=args.port,log_level='warning')
