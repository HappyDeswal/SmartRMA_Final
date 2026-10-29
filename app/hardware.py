"""Optional local ONNX hardware recognition. Advisory only; never decides returns."""
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import threading

from PIL import Image, ImageOps

from .domain import HardwareHint

LABELS = ['graphics_card', 'motherboard', 'ram', 'ssd']


class HardwareClassifier:
    def __init__(self, directory=None):
        self.session = None
        self.metadata = None
        self.lock = threading.Lock()
        self.state = 'disabled'
        self.error = None
        if not directory:
            return
        try:
            directory = Path(directory).resolve(strict=True)
            metadata = json.loads((directory/'metadata.json').read_text())
            if (metadata.get('schema_version') != 1 or metadata.get('labels') != LABELS
                    or metadata.get('task') != 'hardware_type_classification'
                    or metadata.get('advisory_only') is not True
                    or metadata.get('preprocessing') != 'exif_transpose_rgb_white_pad_bilinear_224'
                    or metadata.get('input_size') != 224
                    or metadata.get('mean') != [.485,.456,.406]
                    or metadata.get('std') != [.229,.224,.225]
                    or not isinstance(metadata.get('temperature'), (int,float))
                    or not math.isfinite(metadata['temperature'])
                    or not .1 <= metadata['temperature'] <= 10):
                raise ValueError('Invalid classifier metadata')
            model = (directory/'hardware.onnx').read_bytes()
            if len(model) > 32*1024*1024:
                raise ValueError('Model exceeds expected size')
            if hashlib.sha256(model).hexdigest() != metadata.get('model_sha256'):
                raise ValueError('Model checksum mismatch')
            metrics = (directory/'metrics.json').read_bytes()
            if hashlib.sha256(metrics).hexdigest() != metadata.get('metrics_sha256'):
                raise ValueError('Metrics checksum mismatch')
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(model, sess_options=options, providers=['CPUExecutionProvider'])
            inputs, outputs = session.get_inputs(), session.get_outputs()
            if (len(inputs) != 1 or inputs[0].name != 'image' or inputs[0].shape[1:] != [3,224,224]
                    or inputs[0].type != 'tensor(float)' or len(outputs) != 1
                    or outputs[0].name != 'logits' or outputs[0].shape[-1] != 4):
                raise ValueError('Unsupported classifier interface')
            self.metadata, self.session, self.state = metadata, session, 'ready'
        except Exception as exc:
            self.state, self.error = 'unavailable', type(exc).__name__

    @classmethod
    def environment(cls):
        default = Path(__file__).resolve().parent.parent/'var/models/hardware'
        directory = os.environ.get('HAPPY_HARDWARE_MODEL_DIR', str(default) if (default/'metadata.json').is_file() else '')
        return cls(directory)

    def health(self):
        return {'state': self.state, 'provider': 'local_onnx', 'task': 'hardware_type_classification',
                'advisory_only': True, 'model_sha256': (self.metadata or {}).get('model_sha256'),
                'error': self.error}

    def predict(self, raw):
        if self.session is None:
            return None
        try:
            import numpy as np
            with Image.open(BytesIO(raw)) as opened:
                image = ImageOps.exif_transpose(opened).convert('RGB')
                image = ImageOps.pad(image, (224,224), method=Image.Resampling.BILINEAR, color=(255,255,255))
                data = np.asarray(image, dtype=np.float32)/255
                data = (data - np.array([.485,.456,.406], dtype=np.float32))/np.array([.229,.224,.225], dtype=np.float32)
                batch = np.ascontiguousarray(data.transpose(2,0,1)[None])
            with self.lock:
                logits = self.session.run(['logits'], {'image': batch})[0]
            if logits.shape != (1,4) or not np.isfinite(logits).all():
                raise ValueError('Invalid classifier output')
            scores = logits[0].astype(np.float64)/self.metadata['temperature']
            scores = np.exp(scores-scores.max()); scores /= scores.sum()
            index = int(scores.argmax())
            return HardwareHint(product_type=LABELS[index], score=float(scores[index]),
                                model_sha256=self.metadata['model_sha256'])
        except Exception as exc:
            # Auxiliary failures cannot change a condition assessment or decision.
            self.error = type(exc).__name__
            return None
