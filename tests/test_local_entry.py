import tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from test_application import FakeModels

class LocalEntryTests(unittest.TestCase):
    def client(self,directory,peer='127.0.0.1',enabled=True):
        return TestClient(create_app(Settings(data_dir=Path(directory),origin='http://127.0.0.1:8010',local_auto_login=enabled,start_worker=False),FakeModels()),base_url='http://127.0.0.1:8010',client=(peer,1234))
    def test_local_entry_creates_normal_session_and_csrf(self):
        with tempfile.TemporaryDirectory() as d,self.client(d) as c:
            r=c.get('/api/auth/me');self.assertEqual(r.status_code,200);self.assertTrue(r.json()['local_auto_login']);self.assertEqual(r.json()['user']['role'],'admin');self.assertIn('HttpOnly',r.headers['set-cookie'])
            self.assertEqual(c.get('/api/cases').status_code,200)
            self.assertEqual(c.post('/api/auth/logout').status_code,403)
            self.assertEqual(c.post('/api/auth/logout',headers={'X-CSRF-Token':r.json()['csrf']}).status_code,200)
    def test_remote_peer_cannot_bypass_login(self):
        with tempfile.TemporaryDirectory() as d,self.client(d,peer='192.168.1.55') as c:self.assertEqual(c.get('/api/auth/me').status_code,401)
    def test_disabled_mode_requires_login(self):
        with tempfile.TemporaryDirectory() as d,self.client(d,enabled=False) as c:self.assertEqual(c.get('/api/auth/me').status_code,401)
    def test_remote_origin_disables_auto_entry_even_for_proxy_loopback(self):
        with tempfile.TemporaryDirectory() as d:
            settings=Settings(data_dir=Path(d),origin='https://returns.example',secure_cookie=True,local_auto_login=True,start_worker=False)
            with TestClient(create_app(settings,FakeModels()),base_url='https://returns.example',client=('127.0.0.1',1234)) as c:self.assertEqual(c.get('/api/auth/me').status_code,401)
    def test_direct_write_cannot_self_authenticate(self):
        with tempfile.TemporaryDirectory() as d,self.client(d) as c:self.assertEqual(c.post('/api/auth/logout').status_code,401)
    def test_tampered_admin_cannot_be_auto_signed_in(self):
        with tempfile.TemporaryDirectory() as d,self.client(d) as c:
            with c.app.state.store.connect(True) as db:db.execute("UPDATE users SET password='tampered' WHERE username='admin'")
            self.assertEqual(c.get('/api/auth/me').status_code,401)
