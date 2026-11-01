"""Classifier integration contracts; no hosted AI or real customer mutations."""
import base64,io,json,tempfile,unittest,os
from pathlib import Path
from unittest.mock import patch,MagicMock
from PIL import Image
ISOLATED_DATA = tempfile.TemporaryDirectory(prefix='smartrma-classifier-tests-')
os.environ['SMARTRMA_DATA_DIR'] = ISOLATED_DATA.name
from node.hardware_classifier import HardwareClassifier,HardwareHint
from node import node3_vision as vision,node1_gateway as gateway

class ColabIntegrationTests(unittest.TestCase):
    def request(self):
        b=io.BytesIO();Image.new('RGB',(40,40),'white').save(b,format='PNG')
        return vision.InspectRequest(images=[{'slot':0,'name':'Front','image_b64':base64.b64encode(b.getvalue()).decode()}])
    def observation(self):
        return json.dumps({'hardware_visible':True,'condition':'clean','findings':'The visible board and contacts appear intact.','confidence':.98,'anomaly_score':.02})
    def hint(self):
        return HardwareHint(product_type='ram',score=.9,model_sha256='a'*64)
    def test_local_hint_stays_separate_from_condition(self):
        classifier=MagicMock();classifier.predict.return_value=self.hint()
        with patch.object(vision,'HARDWARE_CLASSIFIER',classifier),patch.object(vision,'call_vision_llm',return_value=(self.observation(),'local-test-fixture')):
            result=vision.inspect_endpoint(self.request())['telemetry']
        self.assertEqual(result['hardware_recognition'][0]['product_type'],'ram')
        self.assertEqual(result['confidence'],.98)
        self.assertEqual(result['anomaly_score'],.02)
        self.assertTrue(result['hardware_recognition'][0]['advisory_only'])
        self.assertEqual(result['view_inspections'][0]['hardware_hint']['score'],.9)
    def test_classifier_failure_does_not_break_condition(self):
        classifier=MagicMock();classifier.predict.side_effect=RuntimeError('bad optional runtime')
        with patch.object(vision,'HARDWARE_CLASSIFIER',classifier),patch.object(vision,'call_vision_llm',return_value=(self.observation(),'local-test-fixture')):
            result=vision.inspect_endpoint(self.request())['telemetry']
        self.assertEqual(result['hardware_recognition'],[]);self.assertTrue(result['all_views_clean'])
    def test_no_llm_success_cannot_be_replaced_by_classifier(self):
        from fastapi import HTTPException
        with patch.object(vision,'call_vision_llm',side_effect=HTTPException(503,'unavailable')):
            with self.assertRaises(HTTPException):vision.inspect_endpoint(self.request())
    def test_health_reports_classifier_independently(self):
        with patch.object(vision,'available_models',return_value=[]):
            health=vision.health()
        self.assertIn('hardware_classifier',health);self.assertFalse(health['inference_ready'])
    def test_absent_or_corrupt_export_is_safe(self):
        self.assertEqual(HardwareClassifier().health()['state'],'disabled')
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'metadata.json').write_text('{}')
            c=HardwareClassifier(tmp);self.assertEqual(c.health()['state'],'unavailable');self.assertIsNone(c.predict(b'broken'))
    def test_every_view_has_its_own_hint(self):
        req=self.request();req.images.append(req.images[0].model_copy(update={'slot':1,'name':'Back'}));classifier=MagicMock();classifier.predict.return_value=self.hint()
        with patch.object(vision,'HARDWARE_CLASSIFIER',classifier),patch.object(vision,'call_vision_llm',return_value=(self.observation(),'local-test-fixture')):
            result=vision.inspect_endpoint(req)['telemetry']
        self.assertEqual(classifier.predict.call_count,2);self.assertEqual([h['slot'] for h in result['hardware_recognition']],[0,1])
    def test_hardware_hint_cannot_change_financial_decision(self):
        v={'assessment_available':True,'evidence_consistent':True,'all_views_clean':True,'conditions':['clean']}
        for tier in ['T1','T2','T3','T4']:
            plain=gateway.decision_result(tier,2,.98,{},v)
            enriched=gateway.decision_result(tier,2,.98,{},dict(v,hardware_recognition=[self.hint().model_dump()]))
            self.assertEqual(plain,enriched)
        self.assertEqual(gateway.decision_result('T4',2,.98,{},v)[0],'ESCALATE')
if __name__=='__main__':unittest.main()
