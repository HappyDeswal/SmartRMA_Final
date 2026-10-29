from dataclasses import dataclass
from pathlib import Path
import os
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / 'var'
    origin: str = 'http://127.0.0.1:8010'
    secure_cookie: bool = False
    start_worker: bool = True
    three_node: bool = False
    bootstrap: bool = True
    local_auto_login: bool = False
    session_hours: int = 8
    max_file_bytes: int = 10 * 1024 * 1024
    max_total_bytes: int = 25 * 1024 * 1024
    max_body_bytes: int = 27 * 1024 * 1024
    max_queued_jobs: int = 20

    def __post_init__(self):
        url = urlsplit(self.origin)
        if url.scheme not in {'http','https'} or not url.hostname or url.username or url.path not in {'','/'} or url.query:
            raise ValueError('HAPPY_ORIGIN must be a single HTTP(S) origin without credentials or paths.')
        if url.hostname not in {'127.0.0.1','localhost','testserver'} and (url.scheme != 'https' or not self.secure_cookie):
            raise ValueError('Remote deployment requires HTTPS and secure cookies.')
        if not 1 <= self.session_hours <= 24:
            raise ValueError('Session lifetime must be 1–24 hours.')

    @classmethod
    def environment(cls):
        return cls(data_dir=Path(os.environ.get('HAPPY_DATA_DIR',str(ROOT/'var'))).resolve(),
                   origin=os.environ.get('HAPPY_ORIGIN','http://127.0.0.1:8010').rstrip('/'),
                   secure_cookie=os.environ.get('HAPPY_SECURE_COOKIE','0')=='1',
                   local_auto_login=os.environ.get('HAPPY_LOCAL_AUTO_LOGIN','1')=='1',
                   three_node=os.environ.get('HAPPY_THREE_NODE','0')=='1')
