import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image

from app.domain import Observation, HardwareHint, aggregate, decide
from app.hardware import HardwareClassifier, LABELS
from app.models import LocalModels


def picture():
    out = BytesIO()
    Image.new('RGB', (300,100), 'white').save(out, format='PNG')
    return out.getvalue()


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        model, metrics = b'controlled-test-model-not-production-weights', b'{}'
        self.meta = {'schema_version':1, 'labels': LABELS, 'task':'hardware_type_classification',
                     'advisory_only':True, 'input_size':224,
                     'preprocessing':'exif_transpose_rgb_white_pad_bilinear_224',
                     'mean':[.485,.456,.406], 'std':[.229,.224,.225], 'temperature':1,
                     'model_sha256':hashlib.sha256(model).hexdigest(),
                     'metrics_sha256':hashlib.sha256(metrics).hexdigest()}
        (self.root/'hardware.onnx').write_bytes(model)
        (self.root/'metrics.json').write_bytes(metrics)
        self.write_meta()
        self.session = MagicMock()
        inp, out = MagicMock(), MagicMock()
        inp.name, inp.shape, inp.type = 'image', ['batch',3,224,224], 'tensor(float)'
        out.name, out.shape = 'logits', ['batch',4]
        self.session.get_inputs.return_value = [inp]
        self.session.get_outputs.return_value = [out]
        self.session.run.return_value = [np.array([[0,0,5,0]],dtype=np.float32)]
        runtime = MagicMock()
        runtime.InferenceSession.return_value = self.session
        self.patch = patch.dict('sys.modules', {'onnxruntime':runtime})
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def write_meta(self):
        (self.root/'metadata.json').write_text(json.dumps(self.meta))

    def test_disabled_does_not_require_runtime_or_files(self):
        model = HardwareClassifier()
        self.assertEqual(model.health()['state'], 'disabled')
        self.assertIsNone(model.predict(picture()))

    def test_local_prediction_preserves_tensor_contract_and_is_advisory(self):
        model = HardwareClassifier(self.root)
        result = model.predict(picture())
        self.assertEqual(result.product_type.value, 'ram')
        self.assertTrue(result.advisory_only)
        batch = self.session.run.call_args.args[1]['image']
        self.assertEqual(batch.shape, (1,3,224,224))
        self.assertEqual(batch.dtype, np.float32)
        expected = (np.ones(3)-[.485,.456,.406])/[.229,.224,.225]
        np.testing.assert_allclose(batch[0,:,0,0], expected, atol=1e-6)

    def test_corrupt_weights_disable_classifier(self):
        (self.root/'hardware.onnx').write_bytes(b'corrupt')
        model = HardwareClassifier(self.root)
        self.assertEqual(model.health()['state'], 'unavailable')
        self.assertIsNone(model.predict(picture()))

    def test_invalid_temperature_cannot_produce_probabilities(self):
        self.meta['temperature'] = float('nan'); self.write_meta()
        self.assertEqual(HardwareClassifier(self.root).health()['state'], 'unavailable')

    def test_nonfinite_prediction_does_not_interrupt_condition_workflow(self):
        model = HardwareClassifier(self.root)
        self.session.run.return_value = [np.array([[0,np.nan,0,0]], dtype=np.float32)]
        self.assertIsNone(model.predict(picture()))

    def test_hint_cannot_change_approval_rejection_or_t4_review(self):
        for condition in ['clean','physical_damage','uncertain']:
            obs = Observation(hardware_visible=True, condition=condition,
                              findings='Controlled condition observation.', confidence=.99,
                              anomaly_score=.05 if condition=='clean' else .9)
            without = aggregate([obs])
            obs.hardware_hint = HardwareHint(product_type='ssd',score=.999,model_sha256='a'*64)
            with_hint = aggregate([obs])
            self.assertEqual(without, with_hint)
            for price in [25000,75000,150000,300000]:
                self.assertEqual(decide(price,without,{}), decide(price,with_hint,{}))
        self.assertTrue(decide(300000,with_hint,{})['human_required'])

    def test_llm_cannot_spoof_the_classifiers_result(self):
        with patch.dict(os.environ, {'HAPPY_HARDWARE_MODEL_DIR': str(self.root)}):
            models = LocalModels()
        response = Observation(hardware_visible=True, condition='clean',
                               findings='Visible components appear clean.', confidence=.95, anomaly_score=.1,
                               hardware_hint=HardwareHint(product_type='ssd',score=1,model_sha256='a'*64))
        with patch.object(models,'installed',return_value={'qwen3-vl:8b'}), patch.object(models,'select_model'), \
                patch.object(models,'http',return_value={'response':response.model_dump_json()}) as http:
            result, _ = models.inspect(picture(), time.monotonic()+30)
        self.assertEqual(result.hardware_hint.product_type.value, 'ram')
        self.assertNotIn('hardware_hint', http.call_args.args[1]['format']['properties'])


class HintHistoryTests(unittest.TestCase):
    def test_advisory_survives_signed_case_history(self):
        import test_application as base
        fixture = base.ApplicationTests()
        fixture.setUp()
        try:
            observation = Observation(hardware_visible=True, condition='clean',
                findings='Controlled software fixture; no live condition inference.', confidence=.99, anomaly_score=.05,
                hardware_hint=HardwareHint(product_type='ram', score=.98, model_sha256='a'*64))
            with patch.object(fixture.models, 'inspect', return_value=(observation,'controlled_fixture')):
                case = fixture.completed()
            self.assertEqual(case['observations'][0]['observation']['hardware_hint']['product_type'], 'ram')
            events = fixture.client.get('/api/cases/'+case['id']+'/history').json()['events']
            historical = fixture.client.get('/api/cases/'+case['id']+'/history/'+events[0]['hash']).json()
            self.assertEqual(historical['snapshot']['observations'][0]['observation']['hardware_hint']['score'], .98)
            self.assertTrue(fixture.app.state.store.verify()['valid'])
            self.assertEqual(case['status'], 'approved')
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
