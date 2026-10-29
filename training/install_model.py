"""Validate and install a Colab export into the local advisory model directory."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.hardware import HardwareClassifier


def install(bundle):
    target = ROOT/'var/models/hardware'
    target.parent.mkdir(parents=True, exist_ok=True)
    allowed = {'hardware.onnx','hardware.pt','metadata.json','metrics.json','dataset_report.json',
               'training_manifest.json','test_predictions.json','confusion_matrix.png'}
    with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            entries = archive.infolist()
            if any(e.filename not in allowed or e.file_size > 32*1024*1024 for e in entries):
                raise ValueError('Unexpected files or oversized model in bundle')
            if len({e.filename for e in entries}) != len(entries):
                raise ValueError('Duplicate archive members')
            archive.extractall(stage)
        classifier = HardwareClassifier(stage)
        if classifier.health()['state'] != 'ready':
            raise ValueError('Export validation failed: '+str(classifier.health()['error']))
        if target.exists():
            raise ValueError('A model is already installed; preserve it before replacing it.')
        shutil.copytree(stage, target)
    print(json.dumps({'installed':str(target), 'health':HardwareClassifier(target).health()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle',type=Path)
    install(parser.parse_args().bundle)
