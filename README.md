# SmartRMA — local-only hardware return review

SmartRMA runs three FastAPI services and uses installed local Ollama models only.
No cloud credentials are read. Inference is fixed to loopback, bypasses proxies, rejects external
redirects, and excludes remote/cloud model aliases. The browser uses local assets and system fonts.

## Run

Use Python 3.10+ and the packages listed in `requirements.txt`:

```sh
python3 -m pip install -r requirements.txt
OLLAMA_NO_CLOUD=1 ollama serve
```

In a second terminal, from this project folder:

```sh
python3 run.py
```

Supported vision models, in order: `qwen3-vl:8b`, `llama3.2-vision:latest`, `moondream:latest`.
Supported chat models: `qwen2.5:7b`, `qwen2.5-coder:14b`, `ornith:35b`, `llama3.1:8b`.
Only installed local models are selected; the launcher does not download models.
Installation and inference readiness are reported separately. Until a successful request, a model
is **untested**, not ready. Failed inference is reported; a local fallback may still be usable.

Open `http://127.0.0.1:8001/index.html` for intake, `review.html` for technician review,
and `architecture.html` for service health. `--no-browser` suppresses browser opening, `--status`
checks services, and `--stop` stops recognized SmartRMA services only. Individual services also run
with `python3 -m node.node1_gateway` (or `node2_policy_rag`, `node3_vision`).
Use one worker per service: storage coordination is process-local.

## Automatic decision rules

The current user preset is **IMAGE_RULES_V2**: local AI evaluates uploaded photos of graphics cards, motherboards, RAM and SSDs. T1–T3 receive an automatic approval or rejection. Only T4 (declared value above $2,500) requires a human decision.

Approval requires an assessed clean image, consistent evidence, risk below 30, and confidence at least 85% (T1/T2) or 95% (T3). Damage, tampering, cosmetic wear, actual identifier mismatches, similarity/editing flags, or a grounded policy exclusion reject the request. Unavailable/uncertain inspection, conflicting observations, low confidence or high risk also reject, with an explicit **resubmit evidence** reason. An evidence rejection does not claim the product is damaged, fraudulent or legally ineligible for warranty service.

Unreadable serial/model/OEM and absent policy sources are advisory, not mandatory-human-review gates. They remain unverified in the dossier. No identity or manufacturer authorization is fabricated. A known grounded policy exclusion can reject automatically; unknown policy does not become an invented approval clause.

| Tier | Declared value | Workflow |
|---|---|---|
| T1 | Below $300 | Automatic approval/rejection; clean approval needs ≥85% confidence |
| T2 | $300–$1,000 | Automatic approval/rejection; clean approval needs ≥85% confidence |
| T3 | Above $1,000–$2,500 | Automatic approval/rejection; clean approval needs ≥95% confidence |
| T4 | Above $2,500 | Mandatory human approval/rejection |

These are application return-screening decisions. They do not issue external manufacturer RMA numbers, payments or shipping labels. Confidence is self-reported and uncalibrated. Technicians may optionally re-evaluate a lower-tier automatic result, but it is not held pending for them.

The vision request now asks for compact condition evidence, not unneeded serial/coordinate fields, to reduce truncated structured responses. Optional identifiers remain null instead of being invented. The fallback model is unloaded after use to limit local memory pressure.

## Inspection and policy behavior

- Supply 1–5 distinct photo slots. All supplied views are inspected under one total deadline.
- Original uploads retain EXIF for the gateway; the vision copy applies EXIF orientation and resizing.
- Similarity checks use only durably committed photos, including previous images for resubmitted slots.
  A failed uncommitted request does not create a duplicate-photo/fraud record.
- EXIF is evidence, not proof of authenticity; pHash is not an Internet image search.
- Unknown/missing/conflicting OCR remains unverified. The model is not given a serial to copy into its findings.
- Moondream descriptions are retained as inconclusive because reliable structured OCR was not established.
- Policy search uses manufacturer-filtered keyword scoring, not vector RAG. Explicit board brands take
  precedence over `RTX`/chip-family names. Unsupported brands never borrow another manufacturer's terms.
- Scoped negation and burn-in/cooling terminology are handled before classifying damage. Ambiguous
  language remains flagged in the policy advisory. Chat cannot authorize claims; output checks filter personal outcome promises.
- Timeouts are coordinated: 240 seconds total vision budget, 255 seconds gateway vision wait,
  285 seconds route wait, and 330 seconds browser allowance. Each model attempt is also bounded.
  Chat has a total 180-second budget and a 210-second browser allowance.

## Policy sources

The rebuilt index contains **26 readable documents and 1,423 chunks**, at most 900 characters per chunk.
`python3 policy/build_policy_index.py` rebuilds it atomically and reports ingestion failures.
The invalid AMD HTML download was preserved under `policy/invalid_sources/` and replaced in the corpus
with a validated [official AMD boxed-processor warranty PDF](https://www.amd.com/content/dam/amd/en/documents/products/processors/general/processor-warranty-update.pdf).
Its source URL, retrieval time, SHA-256, and processor-only scope are recorded in `policy/source_manifest.json`.
These processor terms are not applied to Radeon graphics claims. Regional/purchase-date applicability
still requires technician verification; indexing a source is not proof of claim eligibility.

## Storage, historical evidence, and recovery

`cases_store.json` stores current dossiers. `audit_ledger.json` stores the complete SHA-256 chain.
New audit blocks bind a hash of the full dossier, including photo data, model findings, and decision reasons.
The corresponding version is saved in the private `.snapshots/` directory. `pending_transaction.json`
recovers interrupted dossier/audit writes. Do not manually remove a pending journal.

Verification checks chain links, current dossier content/stamps, and historical snapshot hashes.
Modified dossiers cannot be signed off or exported as verified records. Historical audit clicks open
read-only versions; historical JSON downloads retain the old disposition after later re-evaluation.

Existing historical data is preserved. Legacy dossiers without a recorded binding are explicitly marked
unverified; no claim of retroactive authentication is made. The ledger is tamper-evident, not immutable
against someone who can rewrite all local files and recompute every hash.

The UI reset requires confirmation and clears cases, ledger, fingerprints, and private snapshots.
URL query parameters never reset data. Individual case/ledger clear endpoints are local maintenance
operations; use full reset to remove both together.

## Verification

```sh
python3 run.py --test
# or:
python3 test_security_audit.py
```

Tests use temporary storage and controlled inference outputs, including positive automatic decisions,
negative cases, concurrent commits, tampering, snapshot history, and crash recovery.

For live model/browser checks, start a separate app with temporary storage:

```sh
SMARTRMA_DATA_DIR=/tmp/smartrma-verification-data python3 run.py --no-browser
# In another terminal:
python3 tests/live_local_smoke.py
```

`tests/browser_smoke.cjs` requires Playwright and installed Chrome. It refuses to reset normal workspace
storage. Model checks use the actual configured inventory rather than historical hardcoded names.
See `working/pc20_run_20261027_021918/REPORT.md` for the current 20-case image-screening workflow and verification. Earlier audit reports describe historical rule versions.

## Remaining product boundaries

This is a trusted local, single-user prototype. `TECH-402` is a workstation identity, not an authenticated
multi-user login. There is no external order/invoice database, human ticketing, manufacturer RMA-number,
shipping, or refund integration. JSON exports are review records. Generated thermal/laser/X-ray assets
are labeled synthetic; they are not sensor measurements. Legacy research tables are not reproducible
accuracy evidence for the current code.
