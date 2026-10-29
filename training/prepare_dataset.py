"""Download versioned public hardware photographs; audit and group before splitting.

Product recognition labels ONLY. No damage/functional/return eligibility labels.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import time
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import zipfile

from PIL import Image, ImageOps
import imagehash

KAGGLE = 'https://www.kaggle.com/datasets/asaniczka/pc-parts-images-dataset-classification'
MENDELEY = 'https://data.mendeley.com/datasets/pwctygncrj/4'
ARCHIVE_SHA = '9404d2f13991d0803185fc29919b4709180c68817cf08060264f0b2c98b8cea6'
RAW_FOLDERS = {
    'motherboard': '9fa92373-7bd8-4644-bc3b-d1a4fdba2812',
    'ram': 'e866026f-21b3-4cf1-adfa-1d5948949025',
    'ssd': '9f39e795-2989-48e3-9be7-161220e5a1e4',
}


def fetch(url):
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'SmartRMA-research/1.0'}), timeout=60) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def prepare(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    cache = root / 'sources'
    cache.mkdir(exist_ok=True)
    archive = cache / 'pc-parts-v1.zip'
    if not archive.exists():
        archive.write_bytes(fetch('https://www.kaggle.com/api/v1/datasets/download/'
                                 'asaniczka/pc-parts-images-dataset-classification?datasetVersionNumber=1'))
    if digest(archive.read_bytes()) != ARCHIVE_SHA:
        raise ValueError('Public archive changed: inspect the dataset version before using it.')
    candidates = []
    with zipfile.ZipFile(archive) as zipped:
        for name in sorted(zipped.namelist()):
            bits = name.split('/')
            if len(bits) == 3 and bits[1] in {'gpu', 'motherboard', 'ram'}:
                candidates.append(('graphics_card' if bits[1] == 'gpu' else bits[1],
                                   'kaggle_pc_parts_v1', name, zipped.read(name), KAGGLE,
                                   'ODC-By (database); underlying image rights remain with original owners'))
    # Include laptop RAM and motherboards too, so an SSD is not the only class
    # with the academic dataset's photography background.
    pending = []
    for label, folder in RAW_FOLDERS.items():
        url = 'https://data.mendeley.com/public-api/datasets/pwctygncrj/files?' + urlencode({
            'folder_id': folder, 'version': 4, '$start': 0, '$limit': 1000})
        entries = json.loads(fetch(url))
        if len(entries) != 140:
            raise ValueError(f'Expected 140 original {label} photographs, got {len(entries)}')
        (cache / f'mendeley-{label}-v4.json').write_text(json.dumps(entries, indent=2))
        pending.extend((label, entry) for entry in entries)

    def download(item):
        label, entry = item
        dest = cache / (entry['id'] + '.jpg')
        raw = dest.read_bytes() if dest.exists() else fetch(entry['content_details']['download_url'])
        if digest(raw) != entry['content_details']['sha256_hash']:
            raise ValueError('Academic source checksum mismatch: ' + entry['id'])
        dest.write_bytes(raw)
        return (label, 'mendeley_laptop_v4_raw', entry['filename'], raw, MENDELEY, 'CC BY 4.0')

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, row in enumerate(pool.map(download, pending), 1):
            candidates.append(row)
            if i % 50 == 0:
                print(f'Downloaded {i}/{len(pending)} academic images', flush=True)
    rows, excluded, seen, conflicts = [], [], {}, set()
    for label, source, name, raw, source_url, license_name in candidates:
        sha = digest(raw)
        try:
            with Image.open(BytesIO(raw)) as image:
                image.load()
                image = ImageOps.exif_transpose(image).convert('RGB')
                if min(image.size) < 64:
                    raise ValueError('image too small')
                pixel_sha = digest(str(image.size).encode() + image.tobytes())
                phash = str(imagehash.phash(image))
                width, height = image.size
        except Exception as exc:
            excluded.append({'source': source, 'name': name, 'reason': type(exc).__name__})
            continue
        if pixel_sha in seen:
            if seen[pixel_sha]['label'] != label:
                conflicts.add(pixel_sha)
                excluded.append({'source': source, 'name': name, 'reason': 'conflicting_pixel_labels',
                                 'also_excluded': seen[pixel_sha]['path']})
                continue
            excluded.append({'source': source, 'name': name, 'reason': 'exact_pixel_duplicate',
                             'duplicate_of': seen[pixel_sha]['sha256']})
            continue
        path = Path('images') / label / (sha + '.jpg')
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        row = {'path': path.as_posix(), 'label': label, 'condition': 'unlabeled',
               'sha256': sha, 'pixel_sha256': pixel_sha, 'phash': phash,
               'width': width, 'height': height, 'source': source,
               'source_filename': name, 'source_url': source_url, 'license': license_name}
        seen[pixel_sha] = row
        rows.append(row)
    rows = [r for r in rows if r['pixel_sha256'] not in conflicts]
    # Connected components of near-duplicates, including cross-source matches.
    # This cannot discover all views of the same physical unit; identifiers absent.
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    hashes = [int(row['phash'], 16) for row in rows]
    conflicting_near = set()
    for i in range(len(rows)):
        for j in range(i):
            if (hashes[i] ^ hashes[j]).bit_count() <= 6:
                if rows[i]['label'] != rows[j]['label']:
                    conflicting_near.update([i, j])
                parents[find(i)] = find(j)
    bad_groups = {find(i) for i in conflicting_near}
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        if find(i) in bad_groups:
            excluded.append({'source': row['source'], 'name': row['source_filename'],
                             'reason': 'conflicting_near_duplicate_group'})
            continue
        group = rows[find(i)]['sha256']
        row['group_id'] = group
        groups[row['label'], group].append(row)
    rows = [row for group in groups.values() for row in group]
    # Quarantine excluded files already written during auditing, rather than
    # counting them as usable class images or silently choosing a label.
    usable = {row['path'] for row in rows}
    for path in (root/'images').glob('*/*.jpg'):
        if path.relative_to(root).as_posix() not in usable:
            dest = root/'quarantine'/path.parent.name/path.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.replace(dest)
    rng = random.Random(42)
    for label in sorted({row['label'] for row in rows}):
        grouped = [group for (key, _), group in groups.items() if key == label]
        rng.shuffle(grouped)
        if len(grouped) < 10:
            raise ValueError(f'Not enough independent visual groups for {label}: {len(grouped)}')
        targets = {'train': .7, 'val': .15, 'test': .15}
        assigned = Counter()
        total = sum(map(len, grouped))
        # Ensure each split has groups before filling relative target deficits.
        for i, group in enumerate(sorted(grouped, key=len, reverse=True)):
            split = list(targets)[i] if i < 3 else max(targets, key=lambda s: targets[s] - assigned[s]/total)
            for row in group:
                row['split'] = split
            assigned[split] += len(group)
    rows.sort(key=lambda row: row['path'])
    assert len(rows) >= 501, 'Need at least 501 original images after deduplication'
    assert sum(row['split'] == 'train' for row in rows) >= 501, 'Need 501+ training images'
    (root / 'manifest.json').write_text(json.dumps(rows, indent=2))
    report = {'schema_version': 1, 'task': 'hardware_type_classification', 'seed': 42,
              'condition_labels_available': False, 'unique_original_images': len(rows),
              'counts': dict(Counter(row['label'] for row in rows)),
              'split_counts': {s: dict(Counter(r['label'] for r in rows if r['split'] == s)) for s in ['train','val','test']},
              'visual_groups': len(groups), 'excluded': excluded,
              'limitations': ['No damage, function, authenticity or warranty labels.',
                  'Physical unit IDs absent: repeated item views can remain across splits.',
                  'SSD source has limited device diversity; per-source/domain testing required.',
                  'Kaggle web images can contain labels or backgrounds that act as shortcuts.',
                  'Near-duplicate grouping uses pHash <= 6; it is not proof of unit independence.']}
    (root / 'dataset_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ['unique_original_images', 'counts', 'split_counts', 'visual_groups']}, indent=2), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('training/data/hardware'))
    prepare(parser.parse_args().output)
