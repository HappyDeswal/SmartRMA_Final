# SmartRMA

A local prototype for reviewing hardware return merchandise authorization (RMA) claims. SmartRMA connects photo intake, local image inspection, manufacturer policy retrieval, automatic screening and technician review. Each case keeps its evidence, decision reasons and audit history.

The current project uses three FastAPI services on one workstation. The services have separate responsibilities; this is not a peer-to-peer network or blockchain deployment.

## Architecture

| Component | Port | Responsibility |
| --- | --- | --- |
| Gateway | 8000 | Validate intake, gather vision and policy evidence, apply tier rules, store cases and audit events |
| Policy service and frontend | 8001 | Search local warranty documents, provide cited chat explanations, serve the customer and technician interfaces |
| Vision service | 8002 | Inspect uploaded photos with local Ollama models and optionally return an ONNX hardware-type hint |

The gateway collects vision findings before requesting a policy suggestion. The technician workbench displays the original photo, findings, identity status, retrieved policy and decision controls together.

```text
SmartRMA_Final/
├── run.py                    # Launcher and service controls
├── config/
│   ├── requirements.txt      # Core Python dependencies
│   ├── requirements-hardware.txt
│   └── .env.example          # Documented shell settings
├── backend/
│   ├── services/             # Gateway, policy and vision APIs
│   ├── core/                 # Local runtime and decision rules
│   ├── models/               # Optional hardware classifier integration
│   ├── policy/               # Warranty documents, source manifest and index builder
│   ├── evaluation/           # Annotation tools, metrics and retrieval diagnostics
│   └── tools/                # Asset catalogue tooling
├── frontend/
│   ├── pages/                # Intake, technician review and architecture pages
│   ├── js/
│   ├── css/
│   └── assets/
└── tests/                    # Regression tests and separate live smoke checks
```

Runtime data, datasets, weights and generated reports stay outside Git. The application creates `data/` when needed.

## Setup and launch

Use Python 3.10 or later and install Ollama separately. From a new checkout:

```sh
git clone https://github.com/HappyDeswal/SmartRMA_Final.git
cd SmartRMA_Final
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r config/requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

Start Ollama with cloud features disabled:

```sh
OLLAMA_NO_CLOUD=1 ollama serve
```

In another terminal, install the models you want to use, then launch the application from the project root:

```sh
ollama pull qwen3-vl:8b-instruct
ollama pull qwen2.5:7b
python run.py
```

Model downloads require network access and sufficient disk and memory. Once installed, application inference uses local models. The launcher can start or reuse local Ollama, but does not download missing models.

| Interface | Address |
| --- | --- |
| Customer intake | http://127.0.0.1:8001/index.html |
| Technician review | http://127.0.0.1:8001/review.html |
| Architecture and health | http://127.0.0.1:8001/architecture.html |

Launcher controls:

```sh
python run.py --no-browser
python run.py --status
python run.py --stop
```

`--stop` targets recognized SmartRMA services. Use one worker per service because storage coordination is process-local. Services can also run individually with `python -m backend.services.node1_gateway`, `node2_policy_rag` or `node3_vision`.

Supported vision candidates, in preference order, are `qwen3-vl:8b-instruct`, `qwen3-vl:8b`, `llama3.2-vision:latest` and `moondream:latest`. Chat candidates are `qwen2.5:7b`, `qwen2.5-coder:14b`, `ornith:35b` and `llama3.1:8b`. Selection uses the installed local inventory. An installed model remains untested until inference succeeds; service health and model readiness are reported separately.

Settings in [config/.env.example](config/.env.example) are examples for the invoking shell. The application does not load this file automatically. Model requests are restricted to loopback, bypass proxies and reject remote/cloud model aliases.

## Screening and review rules

The active preset is `IMAGE_RULES_V2`. Intake accepts a positive finite declared value, product details, a complaint and one to five distinct photo slots for graphics cards, motherboards, RAM or SSDs.

| Tier | Declared value in US dollars | Route |
| --- | --- | --- |
| T1 | Below 300 | Automatic screening; clean approval requires at least 85% condition confidence |
| T2 | 300 through 1,000 | Automatic screening; clean approval requires at least 85% condition confidence |
| T3 | Above 1,000 through 2,500 | Automatic screening; clean approval requires at least 95% condition confidence |
| T4 | Above 2,500 | Mandatory human approval or rejection |

Automatic approval also requires assessable clean views, consistent evidence and risk below 30. Damage, wear, tampering, actual identifier mismatches, similarity/editing flags or a grounded policy exclusion can reject a lower-tier request. Unavailable inspection, conflicting findings, low confidence and high risk also reject with an explicit request for better evidence. Such a rejection does not prove damage, fraud or legal warranty ineligibility.

Unreadable identities and absent policy sources remain advisory and unverified. They do not create additional mandatory human gates under this rule version. A technician can optionally re-evaluate an automatic result. Confidence is model-reported and has not been independently calibrated.

The system records application screening decisions. It does not issue manufacturer RMA numbers, pay refunds, book couriers or create shipping labels.

## Image inspection and policy retrieval

- Original image information is retained for EXIF screening; inference uses an oriented, resized copy. Input limits and canonical path checks constrain image processing.
- Perceptual hashing compares durably committed local photo fingerprints. It does not search internet images. EXIF and similarity flags are evidence signals, not proof of authenticity or deception.
- Multi-view results retain individual observations and uncertainty. Clearly readable serial/model/manufacturer text is optional visual evidence; missing or uncertain text stays unverified. Moondream descriptions remain inconclusive because reliable structured output and OCR were not established for that fallback.
- Policy retrieval uses manufacturer-filtered keyword scores and category bonuses. It is not a dense-vector or hybrid retriever. Explicit board manufacturers take precedence over chip-family terms, and unsupported brands do not borrow another manufacturer's terms.
- The retained policy index contains 26 readable documents and 1,423 chunks. Regional scope, purchase channel, dates and ownership still need review. Chat returns sources but cannot authorize claims or change a stored decision.
- The asset tools include synthetic thermal, laser and X-ray illustrations. These are not sensor measurements or validated localization evidence.

Rebuild the local policy index from the project root:

```sh
python -m backend.policy.build_policy_index
```

Source information is retained in `backend/policy/source_manifest.json`. The AMD boxed-processor terms are processor-specific and must not be applied to Radeon graphics claims.

## Case storage and audit history

By default, `data/` holds `cases_store.json`, `audit_ledger.json`, a pending transaction journal and private dossier snapshots. Set `SMARTRMA_DATA_DIR` to use another directory. File locks, atomic replacement and journal recovery protect writes in the supported single-worker setup. Do not manually discard a pending transaction journal.

SHA-256 links events and binds dossier versions. Verification checks event hashes, predecessor links and current/historical dossier digests. Historical views and JSON exports retain the evidence and disposition for the selected event. Legacy records without bindings remain unverified.

The ledger is tamper-evident within these storage limits. Someone who can rewrite every record can recompute the chain; tail removal also needs an independent checkpoint or record count to detect. Stronger deployment needs protected storage and external or signed checkpoints.

The UI reset requires confirmation and clears saved cases, audit events, fingerprints and snapshots. Use isolated storage for demonstrations and live smoke tests.

## Optional hardware-type classifier

```sh
python -m pip install -r config/requirements-hardware.txt
```

Place `hardware.onnx`, `metadata.json` and `metrics.json` from a compatible Colab export in `backend/models/hardware/`, or set `SMARTRMA_HARDWARE_MODEL_DIR` to the export directory. An empty setting disables recognition. Missing dependencies, invalid metadata or checksum failures disable the advisory safely.

The MobileNetV3 Small model recognizes graphics cards, motherboards, RAM and SSDs. Its hardware hint and score do not replace condition evidence, change risk or determine routing. Node 3 reports classifier readiness separately from Ollama readiness.

The archived experiment used 971 images: 679 training, 147 validation and 145 test images. It recorded 122/145 correct predictions, 84.14% hardware-type accuracy and macro F1 of 0.8301. Graphics-card recall was 52.17%. These are product-recognition results, not damage-detection or RMA-decision accuracy. Physical-item independence and out-of-distribution rejection were not established. Weights are excluded from Git.

## Verification and evaluation

Run the isolated regression suite without booting the services:

```sh
python -m unittest discover -s tests -p 'test_*.py'
# Equivalent test runner:
python tests/test_security_audit.py
```

Tests use temporary storage and controlled inference outputs to check routing, validation, persistence, concurrency, tampering, historical snapshots and recovery. Passing tests does not establish diagnostic accuracy.

For live checks, first launch a separate instance with temporary storage:

```sh
SMARTRMA_DATA_DIR=/tmp/smartrma-verification-data python run.py --no-browser
# In another terminal:
python tests/live_local_smoke.py
```

`tests/browser_smoke.cjs` additionally requires Playwright and installed Chrome. It refuses to reset normal workspace storage. `python run.py --test` runs the isolated regression suite and exits without launching services.

See [backend/evaluation/README.md](backend/evaluation/README.md) for review-pool preparation, metric functions and retrieval timing. Damage and policy-relevance labels remain pending until independent review. Historical journal graphs are not reproducible accuracy evidence for the current code. Datasets, review annotations and generated evaluation outputs are excluded from source publication.

## Deployment limits

SmartRMA is a trusted local, single-user prototype. `TECH-402` identifies the workstation operator; it is not an authenticated technician account. Production use needs authenticated roles, stronger transactional storage, protected audit checkpoints, reviewed policy applicability and independent evaluation of image and decision quality.

## Runtime checks

Use the explicit `qwen3-vl:8b-instruct` tag for structured inspections. Thinking variants can consume the generation budget before completing their JSON. The service discards token-truncated responses and validates each completed observation. A successful image description alone does not validate condition accuracy.

The web service exposes only explicit frontend and policy routes; the workspace root, reports, configuration and datasets are not public static roots. Ledger verification reports overall dossier integrity separately from chain-only checks. Missing snapshots must be recovered from content that matches the pre-existing recorded digest; never recreate unknown history or alter audit hashes to make verification pass.
