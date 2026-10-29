import base64,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.service import create_service
from app.nodes import NodeTransport,NodeUnavailable
from test_application import FakeModels,picture

class ThreeNodeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='happy-three-tests-');self.token='test-node-token-'+'x'*40
        self.env=patch.dict(os.environ,{'HAPPY_NODE_TOKEN':self.token});self.env.start();self.models=FakeModels()
        self.policy_models=FakeModels()
        self.vision=TestClient(create_service('vision',self.token,models=self.models));self.policy=TestClient(create_service('policy',self.token,models=self.policy_models));self.vision.__enter__();self.policy.__enter__()
        self.down=set();self.calls=[]
        def route(*args,**kwargs):
            port=httpx.URL(kwargs['base_url']).port
            self.calls.append(port)
            if port in self.down:raise httpx.ConnectError('controlled service outage')
            client={8011:self.policy,8012:self.vision}[port]
            class Context:
                def __enter__(self):return client
                def __exit__(self,*args):pass
            return Context()
        self.transport=patch('app.nodes.httpx.Client',side_effect=route);self.transport.start()
        self.gateway=TestClient(create_app(Settings(data_dir=Path(self.temp.name),origin='http://testserver',start_worker=False,three_node=True)))
        self.gateway.__enter__();credentials=json.loads((Path(self.temp.name)/'first_login.json').read_text())
        result=self.gateway.post('/api/auth/login',json={k:credentials[k] for k in ['username','password']}).json();self.headers={'X-CSRF-Token':result['csrf'],'Idempotency-Key':'three-node-test-001'}
    def tearDown(self):
        self.gateway.__exit__(None,None,None);self.transport.stop();self.policy.__exit__(None,None,None);self.vision.__exit__(None,None,None);self.env.stop();self.temp.cleanup()
    def submit(self,value='750'):
        metadata={'order_id':'THREE-NODE-TEST','product_type':'graphics_card','product_name':'Controlled GPU fixture','manufacturer':'NVIDIA','value':value,'complaint':'Controlled cross-node workflow.','slots':[0]}
        result=self.gateway.post('/api/cases',headers=self.headers,data={'metadata':json.dumps(metadata)},files={'photos':('photo.jpg',picture(),'image/jpeg')});self.assertEqual(result.status_code,202,result.text);return result.json()['case_id']
    def test_full_distributed_intake_and_signed_history(self):
        ident=self.submit();self.gateway.app.state.worker.run_once();case=self.gateway.get('/api/cases/'+ident).json()
        self.assertEqual(case['status'],'approved');self.assertEqual(self.models.calls,1);self.assertIn(8011,self.calls);self.assertIn(8012,self.calls);self.assertTrue(self.gateway.get('/api/audit/verify').json()['valid'])
    def test_t4_still_requires_human_after_both_nodes(self):
        ident=self.submit('3000');self.gateway.app.state.worker.run_once();self.assertEqual(self.gateway.get('/api/cases/'+ident).json()['status'],'needs_review')
    def test_vision_outage_is_failed_job_not_approval(self):
        ident=self.submit();self.down.add(8012);self.gateway.app.state.worker.run_once();case=self.gateway.get('/api/cases/'+ident).json();self.assertEqual(case['job']['status'],'failed');self.assertIsNone(case['decision'])
        self.down.clear();self.assertEqual(self.gateway.post('/api/cases/'+ident+'/retry',headers=self.headers).status_code,200);self.gateway.app.state.worker.run_once();self.assertEqual(self.gateway.get('/api/cases/'+ident).json()['status'],'approved')
    def test_policy_outage_is_failed_job_not_approval(self):
        ident=self.submit();self.down.add(8011);self.gateway.app.state.worker.run_once();case=self.gateway.get('/api/cases/'+ident).json();self.assertEqual(case['job']['status'],'failed');self.assertIsNone(case['decision'])
    def test_chat_executes_on_policy_node_without_vision_node(self):
        self.down.add(8012)
        result=self.gateway.post('/api/chat',headers=self.headers,json={'message':'Explain NVIDIA warranty proof of purchase.'});self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['model'],'test_local_fixture');self.assertIn(8011,self.calls);self.assertNotIn(8012,self.calls)
    def test_return_inspects_before_policy_evaluation(self):
        self.submit();self.calls.clear();self.gateway.app.state.worker.run_once()
        self.assertEqual(self.calls,[8012,8011])
    def test_vision_node_rejects_policy_text_requests(self):
        result=self.vision.post('/text',json={'prompt':'Explain warranty.'},headers={'X-Happy-Node-Token':self.token})
        self.assertEqual(result.status_code,422)
    def test_question_uses_vision_node_and_saved_photo(self):
        ident=self.submit();self.gateway.app.state.worker.run_once();case=self.gateway.get('/api/cases/'+ident).json();result=self.gateway.post('/api/vision/question',headers=self.headers,json={'image_id':case['photos'][0]['id'],'question':'Describe the connector.'});self.assertEqual(result.status_code,200)
    def test_policy_sources_proxy_pdf_and_text(self):
        catalog=self.gateway.get('/api/policies');self.assertEqual(catalog.status_code,200);self.assertEqual(len(catalog.json()['documents']),26)
        r=self.gateway.get('/api/policies/document/nvidia_official_geforce_warranty.md');self.assertEqual(r.status_code,200);self.assertIn('text/plain',r.headers['content-type'])
        self.assertEqual(self.gateway.get('/api/policies/document/missing.pdf').status_code,404)
    def test_system_reports_all_three_nodes_and_outages(self):
        system=self.gateway.get('/api/system').json();self.assertEqual(system['architecture'],'three_node');self.assertEqual(len(system['nodes']),3);self.assertTrue(all(n['reachable'] for n in system['nodes']))
        self.down.add(8012);system=self.gateway.get('/api/system').json();self.assertFalse(system['nodes'][2]['reachable'])
    def test_internal_inspection_requires_private_token(self):
        payload={'image':base64.b64encode(picture()).decode(),'budget':30}
        self.assertEqual(self.vision.post('/inspect',json=payload).status_code,401)
        self.assertEqual(self.vision.post('/inspect',json=payload,headers={'X-Happy-Node-Token':self.token}).status_code,200)
    def test_policy_internal_routes_require_token(self):
        self.assertEqual(self.policy.get('/catalog').status_code,401);self.assertEqual(self.policy.get('/health').status_code,200)
    def test_invalid_base64_never_reaches_model(self):
        result=self.vision.post('/inspect',json={'image':'not a raster','budget':30},headers={'X-Happy-Node-Token':self.token});self.assertEqual(result.status_code,422);self.assertEqual(self.models.calls,0)
    def test_policy_node_rejects_image_chat(self):
        result=self.policy.post('/text',json={'prompt':'test','image':'invalid'},headers={'X-Happy-Node-Token':self.token});self.assertEqual(result.status_code,422)

    def test_long_valid_conversation_fits_internal_text_contract(self):
        result=self.gateway.post('/api/chat',headers=self.headers,json={'message':'NVIDIA warranty '+'x'*1900,'history':[{'role':'user' if i%2==0 else 'assistant','content':'x'*2000} for i in range(8)]})
        self.assertEqual(result.status_code,200,result.text)
