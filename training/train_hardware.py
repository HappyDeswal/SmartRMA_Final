"""Colab/T4 transfer learning and export. Never trains damage/return labels."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
import time

import numpy as np
from PIL import Image, ImageOps
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
import torchvision
from torchvision import transforms as T
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

LABELS = ['graphics_card', 'motherboard', 'ram', 'ssd']
MEAN, STD = [.485, .456, .406], [.229, .224, .225]


class Photos(Dataset):
    def __init__(self, root, rows, training=False):
        self.root, self.rows = Path(root), rows
        # Pad to a square before resizing: keep complete contacts/board outlines.
        self.augment = T.Compose([T.RandomHorizontalFlip(), T.RandomRotation(15),
                                  T.ColorJitter(.12, .12, .12, .03)]) if training else None
        self.to_tensor = T.Compose([T.ToTensor(), T.Normalize(MEAN, STD)])

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(self.root / row['path']) as opened:
            image = ImageOps.exif_transpose(opened).convert('RGB')
            image = ImageOps.pad(image, (224, 224), method=Image.Resampling.BILINEAR, color=(255,255,255))
            if self.augment:
                image = self.augment(image)
            return self.to_tensor(image), LABELS.index(row['label'])


def metrics(y, predicted):
    return {'accuracy': float(accuracy_score(y, predicted)),
            'macro_f1': float(f1_score(y, predicted, labels=list(range(4)), average='macro', zero_division=0)),
            'confusion_matrix': confusion_matrix(y, predicted, labels=list(range(4))).tolist(),
            'classification_report': classification_report(y, predicted, labels=list(range(4)), target_names=LABELS,
                                                           output_dict=True, zero_division=0)}


def train(root, output, epochs=12):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    torch.set_num_threads(2)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print('Training device:', device, torch.cuda.get_device_name(0) if device.type == 'cuda' else '', flush=True)
    rows = json.loads((root / 'manifest.json').read_text())
    splits = {s: [r for r in rows if r['split'] == s] for s in ['train','val','test']}
    assert len(splits['train']) >= 501, 'Need 501+ original training images'
    for row in rows:
        path = (root / row['path']).resolve()
        assert path.is_relative_to(root.resolve()), 'Manifest path outside data root'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], 'Image changed'
    for key in ['sha256', 'pixel_sha256', 'group_id']:
        sets = {s: {r[key] for r in splits[s]} for s in splits}
        assert not (sets['train'] & sets['val'] or sets['train'] & sets['test'] or sets['val'] & sets['test']), key
    for s in splits:
        assert set(r['label'] for r in splits[s]) == set(LABELS), 'Each split must contain every class'
    generator = torch.Generator().manual_seed(42)
    loaders = {s: DataLoader(Photos(root, splits[s]), batch_size=32, shuffle=False, num_workers=2) for s in splits}
    train_loader = DataLoader(Photos(root, splits['train'], True), batch_size=32,
                              shuffle=True, num_workers=2, generator=generator)
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT).to(device)

    # Honest transfer-learning baseline: frozen ImageNet feature nearest centroids.
    def embeddings(loader):
        model.eval(); vectors, labels = [], []
        with torch.inference_mode():
            for x, y in loader:
                features = model.avgpool(model.features(x.to(device))).flatten(1)
                vectors.append(nn.functional.normalize(features, dim=1).cpu())
                labels.append(y)
        return torch.cat(vectors), torch.cat(labels)

    features, y_train = embeddings(loaders['train'])
    centroids = torch.stack([features[y_train == i].mean(0) for i in range(4)])
    centroids = nn.functional.normalize(centroids, dim=1)
    test_features, y_test = embeddings(loaders['test'])
    baseline_predictions = (test_features @ centroids.T).argmax(1).numpy()
    baseline = metrics(y_test.numpy(), baseline_predictions)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, 4).to(device)
    counts = Counter(r['label'] for r in splits['train'])
    weights = torch.tensor([len(splits['train'])/(4*counts[label]) for label in LABELS], device=device)
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW([
        {'params': model.features.parameters(), 'lr': 1e-4},
        {'params': model.classifier.parameters(), 'lr': 1e-3}], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    best, best_state, best_epoch = -1, None, None
    history, start = [], time.monotonic()

    def logits(loader):
        model.eval(); scores, truths = [], []
        with torch.inference_mode():
            for x, y in loader:
                scores.append(model(x.to(device)).cpu()); truths.append(y)
        return torch.cat(scores), torch.cat(truths)

    for epoch in range(epochs):
        model.train(); total_loss = 0
        for x, y in train_loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x.to(device)), y.to(device))
            loss.backward(); optimizer.step()
            total_loss += float(loss.detach()) * len(y)
        scheduler.step()
        validation_logits, validation_y = logits(loaders['val'])
        score = f1_score(validation_y.numpy(), validation_logits.argmax(1).numpy(), average='macro', zero_division=0)
        history.append({'epoch': epoch+1, 'train_loss': total_loss/len(splits['train']), 'val_macro_f1': float(score)})
        print(json.dumps(history[-1]), flush=True)
        if score > best:
            best, best_epoch = score, epoch+1
            best_state = copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    validation_logits, validation_y = logits(loaders['val'])
    # Fit only a scalar temperature using validation NLL, never test labels.
    temperatures = np.linspace(.5, 4, 71)
    nll = [float(nn.functional.cross_entropy(validation_logits/float(t), validation_y)) for t in temperatures]
    temperature = float(temperatures[int(np.argmin(nll))])
    test_logits, test_y = logits(loaders['test'])
    probabilities = torch.softmax(test_logits/temperature, 1).numpy()
    predictions = probabilities.argmax(1)
    final = metrics(test_y.numpy(), predictions)
    report = {
        'task': 'hardware_type_classification_only', 'architecture': 'mobilenet_v3_small',
        'base_weights': 'torchvision IMAGENET1K_V1', 'labels': LABELS,
        'dataset_counts': {s: dict(Counter(r['label'] for r in splits[s])) for s in splits},
        'split_method': 'seed42 exact-pixel deduplication and pHash<=6 connected visual groups; physical IDs unknown',
        'frozen_imagenet_centroid_baseline_test': baseline, 'fine_tuned_test': final,
        'test_accuracy_delta': final['accuracy']-baseline['accuracy'],
        'best_epoch_by_validation_macro_f1': best_epoch, 'best_validation_macro_f1': float(best),
        'validation_temperature': temperature, 'history': history,
        'training_seconds': time.monotonic()-start,
        'runtime': {'python': sys.version, 'torch': torch.__version__, 'torchvision': torchvision.__version__,
                    'device': str(device), 'gpu': torch.cuda.get_device_name(0) if device.type=='cuda' else None},
        'limitations': json.loads((root/'dataset_report.json').read_text())['limitations'] + [
            'Recognition scores do not measure damage or end-to-end return decision accuracy.',
            'No out-of-distribution rejection guarantee; every image maps onto these four labels.',
            'No same-dataset comparison against Qwen3-VL was run.']}
    (output/'metrics.json').write_text(json.dumps(report, indent=2))
    torch.save({'state_dict': model.cpu().state_dict(), 'labels': LABELS, 'temperature': temperature}, output/'hardware.pt')
    model.eval()
    example = torch.randn(1,3,224,224)
    torch.onnx.export(model, example, str(output/'hardware.onnx'), input_names=['image'], output_names=['logits'],
                      dynamic_axes={'image': {0: 'batch'}, 'logits': {0:'batch'}}, opset_version=17, dynamo=False)
    import onnxruntime as ort
    session = ort.InferenceSession(str(output/'hardware.onnx'), providers=['CPUExecutionProvider'])
    with torch.inference_mode():
        torch_scores = model(example).numpy()
    onnx_scores = session.run(None, {'image': example.numpy()})[0]
    assert np.allclose(torch_scores, onnx_scores, rtol=1e-3, atol=1e-4), 'ONNX export mismatch'
    metadata = {'schema_version': 1, 'task': 'hardware_type_classification', 'architecture': 'mobilenet_v3_small',
        'labels': LABELS, 'input_name': 'image', 'input_size': 224, 'mean': MEAN, 'std': STD,
        'preprocessing': 'exif_transpose_rgb_white_pad_bilinear_224', 'temperature': temperature,
        'confidence_notice': 'Validation temperature scaled; no OOD or condition certainty guarantee.',
        'model_sha256': hashlib.sha256((output/'hardware.onnx').read_bytes()).hexdigest(),
        'metrics_sha256': hashlib.sha256((output/'metrics.json').read_bytes()).hexdigest(),
        'dataset_manifest_sha256': hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),
        'advisory_only': True, 'test_accuracy': final['accuracy'], 'test_macro_f1': final['macro_f1']}
    (output/'metadata.json').write_text(json.dumps(metadata, indent=2))
    shutil.copy2(root/'dataset_report.json', output/'dataset_report.json')
    shutil.copy2(root/'manifest.json', output/'training_manifest.json')
    (output/'test_predictions.json').write_text(json.dumps([
        {'path': row['path'], 'true': row['label'], 'predicted': LABELS[int(pred)], 'probabilities': prob.tolist()}
        for row, pred, prob in zip(splits['test'], predictions, probabilities)], indent=2))
    import matplotlib.pyplot as plt
    from sklearn.metrics import ConfusionMatrixDisplay
    fig, axis = plt.subplots(figsize=(7,6))
    ConfusionMatrixDisplay(np.array(final['confusion_matrix']), display_labels=LABELS).plot(ax=axis, colorbar=False)
    axis.set_title('Held-out hardware recognition (not damage classification)')
    fig.tight_layout(); fig.savefig(output/'confusion_matrix.png', dpi=170); plt.close(fig)
    bundle = shutil.make_archive(str(output.parent/'smartrma_hardware_bundle'), 'zip', output)
    print('RESULT', json.dumps({'baseline_test_accuracy': baseline['accuracy'], 'fine_tuned_test_accuracy': final['accuracy'],
                              'macro_f1': final['macro_f1'], 'bundle': bundle}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('training/data/hardware'))
    parser.add_argument('--output', type=Path, default=Path('training/runs/hardware'))
    parser.add_argument('--epochs', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 100:
        parser.error('epochs must be in 1..100')
    train(args.data, args.output, args.epochs)
