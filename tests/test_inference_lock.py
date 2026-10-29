from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from app.inference_lock import InferenceLock
from app.models import LocalModels


class SharedInferenceTests(unittest.TestCase):
    def test_model_readiness_belongs_to_the_node_that_executes_it(self):
        for role,owned,other in [('policy','qwen2.5:7b','qwen3-vl:8b'),('vision','qwen3-vl:8b','qwen2.5:7b')]:
            with patch.dict('os.environ',{'HAPPY_HARDWARE_MODEL_DIR':''}):models=LocalModels(role=role)
            with patch.object(models,'installed',return_value={owned,other}):
                models.record(other,True)
                health=models.health()
                self.assertNotIn(other,health['model_states'])
                self.assertFalse(health['inference_tested'])
                models.record(owned,True)
                self.assertTrue(models.health()['inference_tested'])

    def test_separate_process_cannot_overlap_but_can_acquire_after_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'inference.lock';path.write_bytes(b'0')
            lock=InferenceLock(path)
            self.assertTrue(lock.acquire(timeout=.1))
            code=('from app.inference_lock import InferenceLock; import sys; '
                  'lock=InferenceLock(sys.argv[1]); ok=lock.acquire(timeout=.1); '
                  'print(ok); lock.release() if ok else None')
            try:
                blocked=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,check=True)
                self.assertEqual(blocked.stdout.strip(),'False')
            finally:lock.release()
            ready=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,check=True)
            self.assertEqual(ready.stdout.strip(),'True')

    def test_process_exit_releases_inference_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'inference.lock';path.write_bytes(b'0')
            code='from app.inference_lock import InferenceLock; import sys; lock=InferenceLock(sys.argv[1]); assert lock.acquire(timeout=.1)'
            subprocess.run([sys.executable,'-c',code,str(path)],check=True)
            lock=InferenceLock(path)
            self.assertTrue(lock.acquire(timeout=.1));lock.release()
