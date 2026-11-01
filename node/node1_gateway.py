#!/usr/bin/env python3
"""Local SmartRMA gateway: validated evidence, deterministic routing, durable audit.
Run one worker: file storage and locks are scoped to this process.
"""
import hashlib
import copy
import shutil
import re
import json
import os
import tempfile
import threading
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Literal
from PIL import ExifTags
import imagehash
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
# Support both `python -m node...` and direct script execution.
import sys
from pathlib import Path
if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from node.local_runtime import (BASE_DIR, LocalAccessMiddleware, ALLOWED_ORIGINS,
    LOCAL_HTTP, decode_image, safe_image_path, GATEWAY_VISION_SECONDS)

app = FastAPI(title='SmartRMA Node 1 - Gateway & Decision Router', version='3.0.0')
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
                   allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])
app.add_middleware(LocalAccessMiddleware)
DATA_DIR = Path(os.environ.get('SMARTRMA_DATA_DIR', str(BASE_DIR))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_FILE = str(DATA_DIR / 'audit_ledger.json')
CASES_FILE = str(DATA_DIR / 'cases_store.json')
PENDING_FILE = str(DATA_DIR / 'pending_transaction.json')
SNAPSHOT_DIR = DATA_DIR / '.snapshots'
LEDGER_LOCK = threading.RLock()
CASES_LOCK = threading.RLock()
PHASH_LOCK = threading.RLock()
KNOWN_PHASH_DB = {}
STATS = {'total_intakes': 0, 'approved': 0, 'escalated': 0, 'rejected': 0,
         'phash_duplicates_flagged': 0, 'exif_tamper_flagged': 0}
ZERO_HASH = '0' * 64

class LocalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ImageUpload(LocalRequest):
    slot: int = Field(ge=0, le=4)
    name: str = Field('Inspection Angle', max_length=100)
    image_b64: Optional[str] = Field(None, max_length=21_000_100)
    url: Optional[str] = Field(None, max_length=500)

class IntakeRequest(LocalRequest):
    order_id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_\-.]+$')
    serial_number: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_\-.]+$')
    product_value: float = Field(gt=0, le=100_000, allow_inf_nan=False)
    manufacturer: str = Field(min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    symptom_description: str = Field(min_length=1, max_length=2000)
    images: List[ImageUpload] = Field(min_length=1, max_length=5)

    @field_validator('order_id', 'serial_number', 'manufacturer', 'model_name', 'symptom_description', mode='before')
    @classmethod
    def strip_required_text(cls, value):
        if not isinstance(value, str) or not value.strip() or not any(ch.isalnum() for ch in value):
            raise ValueError('A nonblank identifier or description is required.')
        return value.strip()

class DecisionRequest(LocalRequest):
    decision: Literal['Approved', 'Rejected']
    reason: str = Field(min_length=3, max_length=2000)
    operator: Literal['TECH-402'] = 'TECH-402'

resolve_safe_image_path = safe_image_path

def read_records(path):
    if not os.path.exists(path):
        return []
    try:
        data = json.loads(Path(path).read_text())
        if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
            raise ValueError('Expected an array of records')
        return data
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail='Stored records are unreadable; no data was overwritten.') from exc

def atomic_write(path, records):
    fd, temp_path = tempfile.mkstemp(dir=Path(path).parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(records, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail='Could not persist records. Action was not confirmed.') from exc

def verify_blocks(ledger):
    previous = ZERO_HASH
    for i, block in enumerate(ledger):
        if i == 0 and block.get('prev_hash') == '0' * 32:
            previous = '0' * 32  # Compatibility with the original genesis format.
        payload = {k: v for k, v in block.items() if k not in {'prev_hash', 'block_hash'}}
        computed = hashlib.sha256((json.dumps(payload, sort_keys=True) + str(block.get('prev_hash', ''))).encode()).hexdigest()
        if block.get('prev_hash') != previous or block.get('block_hash') != computed:
            return {'valid': False, 'status': 'TAMPERED', 'failed_block_index': i}
        previous = block['block_hash']
    return {'valid': True, 'status': 'VERIFIED_AUTHENTIC', 'blocks_verified': len(ledger),
            'tamper_detected': False, 'latest_block_hash': previous if ledger else None}

def record_audit_ledger(entry):
    with LEDGER_LOCK:
        ledger = read_records(LEDGER_FILE)
        if not verify_blocks(ledger)['valid']:
            raise HTTPException(status_code=409, detail='Audit chain failed verification; restore it before recording decisions.')
        previous = ledger[-1]['block_hash'] if ledger else ZERO_HASH
        clean = {k: v for k, v in entry.items() if k not in {'prev_hash', 'block_hash'}}
        digest = hashlib.sha256((json.dumps(clean, sort_keys=True) + previous).encode()).hexdigest()
        ledger.append({**clean, 'prev_hash': previous, 'block_hash': digest})
        # Retain genesis and the entire chain; pruning breaks verification.
        atomic_write(LEDGER_FILE, ledger)
        return digest

def case_payload(case):
    return {key: value for key, value in case.items() if key not in {'ledgerHash', 'resolvedHash'}}


def case_digest(case):
    return hashlib.sha256(json.dumps(case_payload(case), sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_snapshot(digest):
    if not re.fullmatch(r'[a-f0-9]{64}', digest or ''):
        raise HTTPException(status_code=409, detail='Invalid dossier digest.')
    rows = read_records(str(SNAPSHOT_DIR / (digest + '.json')))
    if len(rows) != 1 or case_digest(rows[0]) != digest:
        raise HTTPException(status_code=409, detail='Historical dossier is missing or has been modified.')
    return rows[0]


def dossier_status(case, ledger):
    latest = next((row for row in reversed(ledger) if row.get('case_id') == case.get('id') and row.get('case_hash')), None)
    if not latest:
        return 'LEGACY_UNVERIFIED'
    if case_digest(case) != latest['case_hash']:
        return 'TAMPERED'
    try:
        read_snapshot(latest['case_hash'])
    except HTTPException:
        return 'TAMPERED'
    if latest.get('event_type') == 'TECHNICIAN_DECISION' and case.get('resolvedHash') != latest['block_hash']:
        return 'TAMPERED'
    intake = next((row for row in ledger if row.get('case_id') == case.get('id') and row.get('event_type') == 'INTAKE' and row.get('case_hash')), None)
    if intake and case.get('ledgerHash') != intake['block_hash']:
        return 'TAMPERED'
    return 'VERIFIED'


def register_fingerprints(fingerprints):
    # A new image for the same order/slot must not discard earlier committed fingerprints.
    for key, digest in fingerprints.items():
        root = key.split(':image_', 1)[0]
        KNOWN_PHASH_DB[f'{root}:image_{digest}'] = digest


def recover_pending_transaction():
    """Replay a prepared case/ledger transaction after a crash or interrupted disk write."""
    with CASES_LOCK, PHASH_LOCK, LEDGER_LOCK:
        if not os.path.exists(PENDING_FILE):
            return
        pending = read_records(PENDING_FILE)
        if len(pending) != 2:
            raise HTTPException(status_code=500, detail='Pending transaction is invalid; storage needs repair.')
        block, case = pending
        if block.get('case_hash'):
            if case_digest(case) != block['case_hash']:
                raise HTTPException(status_code=409, detail='Pending dossier does not match its audit digest.')
            read_snapshot(block['case_hash'])
        ledger = read_records(LEDGER_FILE)
        if not any(row.get('block_hash') == block['block_hash'] for row in ledger):
            if block['prev_hash'] != (ledger[-1]['block_hash'] if ledger else ZERO_HASH):
                raise HTTPException(status_code=409, detail='Pending audit transaction conflicts with the ledger.')
            if not verify_blocks(ledger + [block])['valid']:
                raise HTTPException(status_code=409, detail='Pending audit transaction failed verification.')
            atomic_write(LEDGER_FILE, ledger + [block])
        cases = read_records(CASES_FILE)
        cases = [row for row in cases if row.get('id') != case['id']]
        cases.insert(0, case)
        atomic_write(CASES_FILE, cases)
        os.remove(PENDING_FILE)
        register_fingerprints(block.get('image_fingerprints', {}))


def commit_case(case, entry):
    """Prepare once, then persist both files; recovery makes retries idempotent."""
    with CASES_LOCK, PHASH_LOCK, LEDGER_LOCK:
        recover_pending_transaction()
        ledger = read_records(LEDGER_FILE)
        if not verify_blocks(ledger)['valid']:
            raise HTTPException(status_code=409, detail='Audit chain failed verification.')
        snapshot_hash = case_digest(case)
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path = str(SNAPSHOT_DIR / (snapshot_hash + '.json'))
        if os.path.exists(snapshot_path):
            read_snapshot(snapshot_hash)
        else:
            atomic_write(snapshot_path, [case_payload(case)])
        entry = {**entry, 'case_hash': snapshot_hash}
        previous = ledger[-1]['block_hash'] if ledger else ZERO_HASH
        digest = hashlib.sha256((json.dumps(entry, sort_keys=True) + previous).encode()).hexdigest()
        block = {**entry, 'prev_hash': previous, 'block_hash': digest}
        hash_field = 'resolvedHash' if entry.get('event_type') == 'TECHNICIAN_DECISION' else 'ledgerHash'
        case[hash_field] = digest
        atomic_write(PENDING_FILE, [block, case])
        recover_pending_transaction()
        return digest


recover_pending_transaction()

def load_phash_cache():
    with PHASH_LOCK, LEDGER_LOCK:
        for block in read_records(LEDGER_FILE):
            register_fingerprints(block.get('image_fingerprints', {}))

load_phash_cache()

def get_tier(value):
    return 'T1' if value < 300 else 'T2' if value <= 1000 else 'T3' if value <= 2500 else 'T4'

def audit_exif(image):
    metadata = {ExifTags.TAGS.get(k, str(k)): str(v) for k, v in image.getexif().items()}
    software = metadata.get('Software', '')
    flags = [f'Image edited with {editor}' for editor in ['photoshop', 'gimp', 'canva', 'lightroom', 'pixelmator', 'snapseed'] if editor in software.lower()]
    return {'has_exif': bool(metadata), 'camera_make': metadata.get('Make'),
            'camera_model': metadata.get('Model'), 'software': software or None,
            'flags': flags, 'authenticity': 'EDITING_METADATA_PRESENT' if flags else 'NOT_ESTABLISHED'}

def audit_phash(image, image_key):
    fingerprint = str(imagehash.phash(image))
    matched = None
    with PHASH_LOCK:
        for key, stored in KNOWN_PHASH_DB.items():
            if key.rsplit(':slot_', 1)[0] == image_key.rsplit(':slot_', 1)[0]:
                continue  # Retrying a claim is not evidence of another customer's photo reuse.
            if imagehash.hex_to_hash(stored) - imagehash.hex_to_hash(fingerprint) <= 4:
                matched = key
                break
    return {'phash_64': fingerprint, 'is_duplicate': matched is not None, 'matched_reference': matched}

def request_service(url, payload, timeout):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    with LOCAL_HTTP.open(request, timeout=timeout) as response:
        return json.load(response)

def call_node2_policy(mfg, model, serial, defect_type, symptoms):
    try:
        return request_service('http://127.0.0.1:8001/api/triage/evaluate', {
            'manufacturer': mfg, 'model_name': model, 'serial': serial,
            'defect_type': defect_type, 'symptoms': symptoms[:2000]}, 15)
    except Exception:
        return {'determination': 'ESCALATED', 'grounded': False,
                'cited_clause': 'Policy service unavailable; technician review required.',
                'source_doc': None, 'page': None, 'notes': 'No policy determination was made.'}

def call_node3_vision(order_id, serial, images, symptoms, manufacturer, model_name):
    try:
        data = request_service('http://127.0.0.1:8002/api/v1/inspect', {
            'order_id': order_id, 'serial_number': serial, 'manufacturer': manufacturer,
            'model_name': model_name, 'symptom_description': symptoms,
            'images': [image.model_dump() for image in images]}, GATEWAY_VISION_SECONDS)
        telemetry = data['telemetry']
        return {**telemetry, 'anomaly_region': telemetry['flagged_component']}
    except Exception:
        return {'assessment_available': False, 'anomaly_score': 0.5, 'anomaly_region': 'Unassessed',
                'severity': 'UNASSESSED', 'confidence': 0.0, 'model_used': None,
                'visual_findings_text': 'Local vision inspection unavailable. No visual verification was completed.',
                'serial_verification': {'status': 'UNVERIFIED', 'user_serial': serial, 'detected_serial': None,
                                        'details': 'No readable serial was verified.'},
                'model_verification': {'status': 'UNVERIFIED', 'user_model': f'{manufacturer} {model_name}',
                                       'detected_model': None, 'details': 'Model not verified.'},
                'inspection_points': [], 'defect_coordinates': None}

def decision_result(tier, risk, confidence, policy, vision, duplicate=False, edited=False):
    """Image screening: automatic T1–T3, price-mandated human review for T4 only.

    A rejection for insufficient evidence requests a new photo; it does not assert
    physical damage, fraud, or a manufacturer's warranty exclusion.
    """
    if tier == 'T4':
        return 'ESCALATE', ['T4_MANDATORY_REVIEW']
    reasons = []
    if duplicate: reasons.append('SIMILAR_PHOTO_REQUIRES_NEW_EVIDENCE')
    if edited: reasons.append('EDITING_METADATA_REQUIRES_NEW_EVIDENCE')
    if not vision.get('assessment_available'): reasons.append('INSPECTION_UNAVAILABLE_RESUBMIT')
    if vision.get('evidence_consistent') is not True: reasons.append('CONFLICTING_VISUAL_EVIDENCE_RESUBMIT')
    if policy.get('grounded') and policy.get('determination') == 'REJECTED':
        reasons.append('INDEXED_POLICY_EXCLUSION')
    for name in ['serial', 'model', 'manufacturer']:
        if vision.get(name + '_verification', {}).get('status') == 'MISMATCH':
            reasons.append(name.upper() + '_MISMATCH_RESUBMIT')
    conditions = set(vision.get('conditions', []))
    if conditions & {'physical_damage', 'tampered'}:
        reasons.append('VISIBLE_DAMAGE_OR_TAMPERING')
    elif 'cosmetic_wear' in conditions:
        reasons.append('VISIBLE_COSMETIC_WEAR')
    if confidence < (.95 if tier == 'T3' else .85):
        reasons.append('CONFIDENCE_BELOW_TIER_THRESHOLD_RESUBMIT')
    if reasons:
        return 'REJECT', reasons
    if vision.get('all_views_clean') is True and conditions == {'clean'} and risk is not None and risk < 30:
        return 'APPROVE', ['CLEAN_IMAGE_PASSES_TIER_RULES']
    return 'REJECT', ['INSUFFICIENT_OR_HIGH_RISK_EVIDENCE_RESUBMIT']


def route_decision(tier, risk, confidence, policy, vision, duplicate=False, edited=False):
    return decision_result(tier, risk, confidence, policy, vision, duplicate, edited)[0]

@app.get('/health')
def health():
    return {'status': 'ONLINE', 'service': 'SmartRMA Node 1 - Gateway & Decision Router',
            'port': 8000, 'local_only': True, 'indexed_phash_signatures': len(KNOWN_PHASH_DB),
            'max_image_pixels_limit': 25_000_000, 'stats': STATS,
            'temporary_storage': any(DATA_DIR.is_relative_to(Path(root).resolve()) for root in (tempfile.gettempdir(), '/tmp')),
            'security_features': ['decompression_bomb_guard', 'path_traversal_guard', 'cryptographic_sha256_ledger']}

@app.get('/api/v1/stats')
def get_stats():
    return {'stats': STATS, 'active_pHash_fingerprints': len(KNOWN_PHASH_DB)}

@app.get('/api/v1/ledger')
def get_ledger(limit: int = 100):
    with LEDGER_LOCK:
        records = read_records(LEDGER_FILE)
        return {'count': len(records), 'recent_blocks': records[-max(1, min(500, limit)):]}

@app.get('/api/v1/ledger/verify')
def verify_ledger():
    recover_pending_transaction()
    with CASES_LOCK, LEDGER_LOCK:
        ledger = read_records(LEDGER_FILE)
        result = verify_blocks(ledger)
        result['chain_valid'] = result['valid']
        cases = read_records(CASES_FILE)
        statuses = {case['id']: dossier_status(case, ledger) for case in cases}
        broken_snapshots = []
        for block in ledger:
            if block.get('case_hash'):
                try:
                    read_snapshot(block['case_hash'])
                except HTTPException:
                    broken_snapshots.append(block['case_id'])
        missing = sorted({row['case_id'] for row in ledger if row.get('case_hash')} - set(statuses))
        tampered = [key for key, status in statuses.items() if status == 'TAMPERED']
        result.update(dossier_statuses=statuses, tampered_dossiers=tampered,
                      broken_snapshots=broken_snapshots, missing_dossiers=missing,
                      legacy_dossiers=[key for key, status in statuses.items() if status == 'LEGACY_UNVERIFIED'])
        result['dossiers_valid'] = not tampered and not broken_snapshots and not missing
        result['valid'] = result['chain_valid'] and result['dossiers_valid']
        return result

@app.post('/api/v1/ledger/clear')
@app.delete('/api/v1/ledger')
def clear_ledger():
    with PHASH_LOCK, LEDGER_LOCK:
        atomic_write(LEDGER_FILE, [])
        KNOWN_PHASH_DB.clear()
    return {'status': 'SUCCESS'}

@app.get('/api/v1/cases')
def get_cases():
    recover_pending_transaction()
    with CASES_LOCK, LEDGER_LOCK:
        cases = read_records(CASES_FILE)
        ledger = read_records(LEDGER_FILE)
    return {'count': len(cases), 'cases': [{**case, '_integrity': dossier_status(case, ledger)} for case in cases]}

@app.post('/api/v1/cases/clear')
def clear_cases():
    with CASES_LOCK:
        atomic_write(CASES_FILE, [])
    return {'status': 'SUCCESS'}

@app.post('/api/v1/reset')
def reset_workspace():
    recover_pending_transaction()
    # Explicit local development action, never triggered by a URL query parameter.
    with CASES_LOCK, PHASH_LOCK, LEDGER_LOCK:
        atomic_write(CASES_FILE, [])
        atomic_write(LEDGER_FILE, [])
        KNOWN_PHASH_DB.clear()
        shutil.rmtree(SNAPSHOT_DIR, ignore_errors=True)
    return {'status': 'SUCCESS'}

@app.post('/api/v1/cases/{case_id}/decision')
def record_case_decision(case_id: str, payload: DecisionRequest):
    recover_pending_transaction()
    if not payload.reason.strip():
        raise HTTPException(status_code=422, detail='Enter the technician findings.')
    with CASES_LOCK:
        cases = read_records(CASES_FILE)
        case = next((c for c in cases if c.get('id') == case_id), None)
        if case is None:
            raise HTTPException(status_code=404, detail='Case not found.')
        if dossier_status(case, read_records(LEDGER_FILE)) == 'TAMPERED':
            raise HTTPException(status_code=409, detail='Dossier integrity failed; restore the audited version before changing its decision.')
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {'timestamp': timestamp, 'case_id': case_id, 'order_id': case.get('orderId'),
                 'serial_number': case.get('serialNumber'), 'product': case.get('p'),
                 'product_value': case.get('v'), 'tier': case.get('t'),
                 'risk_score': case.get('r'), 'anomaly_score': case.get('a'),
                 'anomaly_region': case.get('rn'), 'operator': payload.operator,
                 'reason': payload.reason.strip(), 'cited_clause': payload.reason.strip(),
                 'disposition': 'APPROVE' if payload.decision == 'Approved' else 'REJECT',
                 'event_type': 'TECHNICIAN_DECISION'}
        case.update(st=payload.decision, resolvedOperator=payload.operator,
                    resolvedReason=payload.reason.strip(), resolvedTime=timestamp)
        digest = commit_case(case, entry)
    return {'status': 'SUCCESS', 'case_id': case_id, 'decision': payload.decision,
            'block_hash': digest, 'case': case}

@app.get('/api/v1/cases/{case_id}/history/{block_hash}')
def historical_case(case_id: str, block_hash: str):
    with LEDGER_LOCK:
        ledger = read_records(LEDGER_FILE)
        if not verify_blocks(ledger)['valid']:
            raise HTTPException(status_code=409, detail='Audit chain failed verification.')
        block = next((row for row in ledger if row.get('case_id') == case_id and row.get('block_hash') == block_hash), None)
        if not block:
            raise HTTPException(status_code=404, detail='Audit event not found.')
        if not block.get('case_hash'):
            raise HTTPException(status_code=409, detail='This legacy event has no verifiable historical dossier.')
        case = read_snapshot(block['case_hash'])
        intake = next((row['block_hash'] for row in ledger if row.get('case_id') == case_id and row.get('event_type') == 'INTAKE'), block_hash)
        return {'case': {**case, 'ledgerHash': intake, 'resolvedHash': block_hash if block.get('event_type') == 'TECHNICIAN_DECISION' else None, '_integrity': 'VERIFIED'},
                'event': block, 'historical': True}

@app.get('/api/v1/cases/{case_id}/export')
def export_case(case_id: str):
    recover_pending_transaction()
    with CASES_LOCK:
        case = next((c for c in read_records(CASES_FILE) if c.get('id') == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail='Case not found.')
    integrity = dossier_status(case, read_records(LEDGER_FILE))
    if integrity == 'TAMPERED':
        raise HTTPException(status_code=409, detail='Dossier integrity failed; export the verified historical record instead.')
    return {'integrity': integrity, 'notice': 'SmartRMA review record; manufacturer shipping authorization must be obtained separately.', 'case': case}

@app.post('/api/v1/intake')
def process_intake(req: IntakeRequest):
    if len({img.slot for img in req.images}) != len(req.images):
        raise HTTPException(status_code=422, detail='Inspection slots must be unique.')
    decoded = [(item, decode_image(item.image_b64, item.url)[0]) for item in req.images]
    audits = []
    for item, image in decoded:
        audits.append({'slot': item.slot, 'name': item.name, 'exif': audit_exif(image),
                       'phash': audit_phash(image, f'{req.order_id}:slot_{item.slot}')})
    vision = call_node3_vision(req.order_id, req.serial_number, req.images, req.symptom_description, req.manufacturer, req.model_name)
    # Policy receives visual observations, after inspection, as well as the complaint.
    policy = call_node2_policy(req.manufacturer, req.model_name, req.serial_number,
                               vision.get('defect_type', 'other'),
                               f"{req.symptom_description}\nVisual findings: {vision.get('visual_findings_text', '')}"[:2000])
    with CASES_LOCK, PHASH_LOCK:
        recover_pending_transaction()
        for (item, image), audit in zip(decoded, audits):
            audit['phash'] = audit_phash(image, f'{req.order_id}:slot_{item.slot}')
        duplicate = any(row['phash']['is_duplicate'] for row in audits)
        edited = any(row['exif']['flags'] for row in audits)
        score = float(vision.get('anomaly_score', 0.5))
        confidence = float(vision.get('confidence', 0))
        if not 0 <= score <= 1 or not 0 <= confidence <= 1:
            raise HTTPException(status_code=502, detail='Vision returned invalid scores.')
        tier = get_tier(req.product_value)
        risk = min(100, round(score * 70 + (20 if policy.get('determination') == 'REJECTED' else 0) + (30 if duplicate or edited else 0)))
        if not vision.get('assessment_available'):
            risk = None
        disposition, decision_reasons = decision_result(tier, risk, confidence, policy, vision, duplicate, edited)
        case_id = 'RMA-' + uuid.uuid4().hex[:16].upper()
        timestamp = datetime.now(timezone.utc).isoformat()
        flags = (['DUPLICATE_PHASH_DETECTED'] if duplicate else []) + (['EXIF_SOFTWARE_MODIFICATION'] if edited else [])
        if vision.get('serial_verification', {}).get('status') == 'MISMATCH':
            flags.append('SERIAL_NUMBER_MISMATCH_DETECTED')
        telemetry = {**vision, 'flagged_region': vision.get('anomaly_region', 'Unassessed'),
                     'visual_findings': vision.get('visual_findings_text', '')}
        grounding = {'node2_verdict': policy.get('determination'), 'verdict': policy.get('determination'),
                     'grounded': policy.get('grounded', False), 'cited_clause': policy.get('cited_clause'),
                     'source_document': policy.get('source_doc'), 'page': policy.get('page'), 'explanation': policy.get('notes')}
        user_images = [{'slot': i.slot, 'name': i.name, 'src': i.image_b64 or i.url} for i in req.images]
        coordinates = vision.get('defect_coordinates')
        case = {'id': case_id, 'orderId': req.order_id, 'serialNumber': req.serial_number,
                'oem': req.manufacturer, 'modelName': req.model_name, 'p': f'{req.manufacturer} {req.model_name}',
                'v': req.product_value, 't': tier, 'r': risk, 'a': score if vision.get('assessment_available') else None, 'conf': round(confidence * 100),
                'rn': telemetry['flagged_region'], 'cl': policy.get('cited_clause'), 'src': policy.get('source_doc'),
                'st': 'Auto-Approved' if disposition == 'APPROVE' else 'Rejected' if disposition == 'REJECT' else 'Pending',
                'subImg': user_images[0]['src'], 'userImages': [i['src'] for i in user_images], 'imageSlots': user_images,
                'at': [coordinates['center_x_pct'], coordinates['center_y_pct']] if coordinates else None,
                'symptom': req.symptom_description, 'submittedAt': timestamp,
                'isAutoApproved': disposition == 'APPROVE', 'resolvedOperator': None,
                'visionTelemetry': telemetry, 'policyGrounding': grounding,
                'decisionMode': 'IMAGE_RULES_V2', 'humanApprovalRequired': tier == 'T4',
                'policyAdvisoryOnly': True, 'decisionReasons': decision_reasons, 'escalationReason': ', '.join(decision_reasons)}
        entry = {'timestamp': timestamp, 'case_id': case_id, 'order_id': req.order_id,
                 'serial_number': req.serial_number, 'product': case['p'], 'product_value': req.product_value,
                 'tier': tier, 'disposition': disposition, 'decision_mode': 'IMAGE_RULES_V2', 'human_approval_required': tier == 'T4', 'risk_score': risk, 'confidence': confidence,
                 'anomaly_score': case['a'], 'anomaly_region': telemetry['flagged_region'],
                 'cited_clause': policy.get('cited_clause'), 'source_doc': policy.get('source_doc'),
                 'page': policy.get('page'), 'fraud_flags': flags, 'event_type': 'INTAKE', 'decision_reasons': decision_reasons,
                 'image_fingerprints': {f'{req.order_id}:slot_{a["slot"]}': a['phash']['phash_64'] for a in audits}}
        digest = commit_case(case, entry)
    STATS['total_intakes'] += 1
    STATS[{'APPROVE': 'approved', 'REJECT': 'rejected', 'ESCALATE': 'escalated'}[disposition]] += 1
    STATS['phash_duplicates_flagged'] += int(duplicate)
    STATS['exif_tamper_flagged'] += int(edited)
    return {'case_id': case_id, 'order_id': req.order_id, 'disposition': disposition, 'tier': tier,
            'risk_index': risk, 'confidence': confidence, 'decision_reasons': decision_reasons, 'case': case,
            'vision_telemetry': telemetry, 'policy_grounding': grounding,
            'security_audit': {'images_verified': len(audits), 'has_duplicate_phash': duplicate,
                               'has_tampered_exif': edited, 'audits': audits},
            'cryptographic_ledger': {'block_hash': digest, 'algorithm': 'SHA-256', 'tamper_evident': True}}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
