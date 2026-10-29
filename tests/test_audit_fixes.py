import json,time,unittest
from unittest.mock import patch
import test_application as base
import test_three_nodes as three
from app.domain import Observation,aggregate,decide
from app.models import LocalModels
from app.storage import Conflict,IntegrityFailure

class StorageAuditTests(unittest.TestCase):
    setUp=base.ApplicationTests.setUp
    tearDown=base.ApplicationTests.tearDown
    signin=base.ApplicationTests.signin
    headers=base.ApplicationTests.headers
    metadata=base.ApplicationTests.metadata
    submit=base.ApplicationTests.submit
    completed=base.ApplicationTests.completed
    def test_malformed_case_is_integrity_conflict_not_server_error(self):
        c=self.completed()
        with self.app.state.store.connect(True) as db:db.execute("UPDATE cases SET data_json='{' WHERE id=?",(c['id'],))
        self.assertEqual(self.client.get('/api/cases/'+c['id']).status_code,409)
        r=self.client.get('/api/cases?search=Test');self.assertEqual(r.status_code,200);self.assertTrue(self.client.get('/api/cases').json()['items'])
    def test_current_export_refuses_a_broken_earlier_audit_event(self):
        c=self.completed()
        with self.app.state.store.connect(True) as db:
            db.execute('DROP TRIGGER audit_no_update');db.execute("UPDATE audit SET entry_json='{}' WHERE seq=1")
        self.assertEqual(self.client.get('/api/cases/'+c['id']+'/export').status_code,409)
    def test_history_tamper_is_reported_not_raw_or_server_error(self):
        c=self.completed()
        with self.app.state.store.connect(True) as db:
            db.execute('DROP TRIGGER audit_no_update');db.execute("UPDATE audit SET entry_json='{' WHERE seq=1")
        self.assertEqual(self.client.get('/api/cases/'+c['id']+'/history').status_code,409)
        self.assertEqual(self.client.get('/api/audit').status_code,409)
    def test_each_photo_needs_an_observation_before_finalization(self):
        metadata=self.metadata(slots=[0,1]);result=self.client.post('/api/cases',data={'metadata':json.dumps(metadata)},files=[('photos',('a.jpg',base.picture(),'image/jpeg')),('photos',('b.jpg',base.picture('red'),'image/jpeg'))],headers=self.headers())
        self.assertEqual(result.status_code,202);job=self.app.state.store.claim_job()
        with self.assertRaises(Conflict):self.app.state.store.finalize(job['id'],[self.models.inspect(base.picture(),time.monotonic()+1)[0]],['test_local_fixture'],{})
        self.assertEqual(self.client.get('/api/cases/'+result.json()['case_id']).json()['status'],'queued')
    def test_image_changed_after_inspection_cannot_be_human_approved(self):
        c=self.completed('3000')
        with self.app.state.store.connect(True) as db:
            db.execute('DROP TRIGGER image_no_update');db.execute('UPDATE images SET data=?',(b'corrupted image',))
        r=self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json={'decision':'approved','revision':c['revision'],'reason':'Actual review of the uploaded item.'});self.assertEqual(r.status_code,409)

class ModelAuditTests(unittest.TestCase):
    def test_null_model_response_uses_next_local_model(self):
        models=LocalModels();obs=Observation(hardware_visible=True,condition='clean',findings='Visible components appear clean.',confidence=.99,anomaly_score=.05)
        with patch.object(models,'installed',return_value={'qwen3-vl:8b','llama3.2-vision:latest'}),patch.object(models,'select_model'),patch.object(models,'http',side_effect=[{'response':None},{'response':obs.model_dump_json()}]):
            result,name=models.inspect(base.picture(),time.monotonic()+30)
        self.assertEqual(name,'llama3.2-vision:latest');self.assertEqual(result.condition,'clean')
    def test_null_chat_response_uses_next_local_model(self):
        models=LocalModels()
        with patch.object(models,'installed',return_value={'qwen2.5:7b','llama3.1:8b'}),patch.object(models,'select_model'),patch.object(models,'http',side_effect=[{'response':None},{'response':'Photos cannot prove electrical function.'}]):
            result,name=models.text('Can a photo establish function?')
        self.assertEqual(name,'llama3.1:8b')
    def test_malformed_inventory_does_not_hide_valid_installed_models(self):
        models=LocalModels()
        with patch.object(models,'http',return_value={'models':[None,{}, {'name':'moondream:latest'}]}):self.assertEqual(models.installed(),{'moondream:latest'})
    def test_ungrounded_exclusion_cannot_add_risk(self):
        evidence=aggregate([Observation(hardware_visible=True,condition='clean',findings='Visible components appear clean.',confidence=.99,anomaly_score=.2)])
        self.assertEqual(decide(75000,evidence,{'grounded':False,'excluded':True})['status'],'approved')

class CrossNodeAuditTests(unittest.TestCase):
    setUp=three.ThreeNodeTests.setUp
    tearDown=three.ThreeNodeTests.tearDown
    submit=three.ThreeNodeTests.submit
    def test_valid_unicode_history_crosses_nodes_without_expanding_past_limit(self):
        result=self.gateway.post('/api/chat',headers=self.headers,json={'message':'NVIDIA warranty','history':[{'role':'user' if i%2==0 else 'assistant','content':'硬件'*1000} for i in range(8)]})
        self.assertEqual(result.status_code,200)

class LauncherAuditTests(unittest.TestCase):
    def test_recently_closed_connection_does_not_block_restart(self):
        import socket
        from run import check_port
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind(('127.0.0.1',0));server.listen();port=server.getsockname()[1]
            with socket.create_connection(('127.0.0.1',port)) as client:
                peer,_=server.accept();peer.shutdown(socket.SHUT_WR);peer.close();self.assertEqual(client.recv(1),b'')
        check_port(port)
    def test_live_listener_is_still_a_port_conflict(self):
        import socket
        from run import check_port
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind(('127.0.0.1',0));server.listen()
            with self.assertRaises(RuntimeError):check_port(server.getsockname()[1])

class PhotoAndTransportAuditTests(unittest.TestCase):
    def test_animated_photo_cannot_hide_a_second_uninspected_frame(self):
        import io
        from PIL import Image
        from app.images import validate_photo
        out=io.BytesIO();Image.new('RGB',(64,64),'white').save(out,format='PNG',save_all=True,append_images=[Image.new('RGB',(64,64),'red')],duration=100,loop=0)
        with self.assertRaises(ValueError):validate_photo(out.getvalue(),0,'animated.png',10*1024*1024)
    def test_non_object_node_response_is_unavailable_not_a_gateway_crash(self):
        import httpx
        from app.nodes import NodeTransport,NodeUnavailable
        response=httpx.Response(200,json=[],request=httpx.Request('GET','http://127.0.0.1:8012/models'))
        with patch('app.nodes.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value=response
            with self.assertRaises(NodeUnavailable):NodeTransport('vision','x'*40).call('/models')
