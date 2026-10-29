# Original workflow alignment - 28 October 2026

- Preserved Node 1 intake/security/decision/history, Node 2 policy/text chat, and Node 3 vision responsibilities.
- Node 2 now executes local text models directly; it no longer depends on Node 3 for policy chat.
- Both inference processes use a shared operating-system file lock, tested for contention and process-exit recovery.
- Return order is verified: Node 3 inspection, then Node 2 policy, then Node 1 decision/history.
- 109 software tests passed. 24 decision fixtures matched the original gateway functions.
- Architecture page and README now describe the aligned roles and distinguish storage/queue/security improvements.
- Live Node 2 chat completed using local qwen2.5:7b, with all three services and the trained classifier healthy.
- Detailed scope and evidence: docs/WORKFLOW_PARITY.md and docs/workflow_parity_results.json.

---

# Hardware training and local integration verification - 28 October 2026

- Trained an auxiliary MobileNetV3 Small hardware classifier on Colab Tesla T4.
- 971 retained original images: 679 training, 147 validation, 145 held-out test.
- Fine-tuned type recognition: 122/145 correct (84.14%); macro F1 0.8301.
- Frozen ImageNet feature/centroid baseline: 75.17%; this is not a Qwen3-VL comparison.
- GPU recall 52.17%, below its baseline recall; no claim of damage or RMA decision improvement.
- ONNX/PyTorch parity passed in Colab; local ONNX matched all 145 Colab predictions.
- 104 software regression tests passed, including corrupt-model fallback, output spoof protection,
  advisory persistence contract, and proof that classifier hints cannot change tier decisions.
- Three local services restarted with an empty active queue; all reported healthy.
- Actual exported ONNX loaded in Node 3, with model and metrics checksums verified.
- A live combined inference using local Qwen3-VL 8B and the trained ONNX model completed successfully.
- Evidence and limitations: training/results/2026-10-28 and training/README.md.

---

# Publication verification — 28 October 2026

The rebuilt application was prepared at the root of `HappyDeswal/SmartRMA_Publish` and verified from a clean publication checkout.

- **96 isolated Python tests passed** on the source and again on the publication checkout.
- `pip check`: no broken requirements.
- Browser application and architecture JavaScript syntax checks passed.
- The README now documents portable setup, all three nodes, local-only model execution, the current no-login local workspace, tier boundaries, operations and data attribution.
- Private runtime databases, credentials, audit keys, virtual environments and generated diagnostic artifacts are excluded from Git. The `tests/artifacts` directory is retained as an empty output location for optional diagnostics.

These publication checks did not rerun live model inference or browser workflows. The dated sections below retain historical results; referenced generated artifacts remain in the development workspace and are not bundled in the public checkout. Software tests do not establish diagnostic accuracy or reproduce the journal benchmarks.

---

# Functional audit and fixes — 27 October 2026

Audited the Python services, local-model transport, deterministic decisions, signed storage, launch/restart behavior and browser workflows. The original project was not changed. The new project's existing history was preserved; four clearly labelled software-audit orders were added using licensed sample photos and synthetic tier values.

## Fixed problems

- Null/malformed model responses crashed vision/chat instead of trying the next supported local model. Invalid inventory rows could also hide usable models. Responses are now validated before use.
- Valid long Unicode conversations expanded into escaped JSON beyond the internal node limit. Prompts now preserve Unicode characters when serializing history.
- A malformed dossier could cause a server error and break filtered history searches. It now produces an integrity conflict; history listing remains usable.
- Current exports could succeed even when an earlier audit event was corrupted. Current exports now verify stored integrity first. Corrupted history/ledger reads return an explicit integrity conflict instead of unverified data or a parser crash.
- Finalization could accept fewer observations than submitted photos. It now requires matching photo, observation and model-result counts before saving an outcome.
- Photo bytes changed after inspection were not checked again before a human approval. Finalization and human decisions now verify the relevant original photos inside their write transaction.
- An ungrounded exclusion flag could increase risk. Only a grounded exclusion can contribute that policy risk adjustment.
- Recently closed TCP connections could make the launcher incorrectly report an occupied port on immediate restart. Port checks now use the server's address-reuse behavior while still rejecting live listeners.
- Animated PNG/WebP files could present frames different from the single inspected frame. Upload validation now requires single-frame photos.
- Non-object internal-node JSON responses could crash gateway consumers. They now produce a controlled unavailable-node result.
- A failed job without a new case revision did not render its Retry button during polling. Rendering now considers job state as well as case revision.
- A slower reply for an earlier selected case could replace a newer selection. Current and historical reads now use request ordering guards.
- Browser Back/Forward and the workspace wordmark changed the URL without reliably changing the visible view. Hash navigation now updates the page; direct `review.html` opens review.
- Refresh could replace a service error with a success message. It now preserves the failure notice.

## Executed verification

- **96 backend tests passed**, including 14 newly added reproducing/edge-case tests. The initial ten targeted backend tests failed against the prior implementation and pass after these fixes.
- **61 browser checks passed**: 12 general smoke checks, 25 architecture checks, 17 human-review/account/export/archive workflows, and 7 targeted navigation, response-order, failed-job and error-message checks. Human decisions and account changes were exercised only in a disposable fixture database.
- Python compilation, JavaScript syntax and installed dependency consistency checks passed.
- Four fresh uploads were processed across the actual three-node services, with local Ollama only. Original-photo exports were decoded and their SHA-256 hashes verified.
- A consistent private backup was created under `var/backups/audit-20261027` before the final restart. Existing records and the signed audit head were checked again after restart.

| Live case | Product | Tier price | Outcome | Local vision provider |
|---|---|---:|---|---|
| T1 | Graphics card | $250 | Automatic approval | Qwen3-VL 8B |
| T2 | Motherboard | $750 | Evidence-resubmission rejection | Moondream fallback |
| T3 | RAM | $1,500 | Evidence-resubmission rejection | Moondream fallback |
| T4 | SSD | $3,000 | Pending mandatory human decision | Qwen3-VL 8B |

T2/T3 used unstructured fallback descriptions and therefore have zero verified condition confidence. Their rejections request better evidence and do not establish actual damage. T4 was not automatically or artificially approved. Actual local chat used Qwen2.5 7B; photo Q&A used Qwen3-VL 8B. These tests establish functioning software paths, not independently measured diagnostic accuracy. Self-reported model confidence remains uncalibrated.

Evidence: `tests/artifacts/audit-summary.json`, `audit-regression.log`, `audit-live.json`, `browser-audit.json` and `audit-restart.json`. Passing checks cannot establish that every possible input is bug-free or that AI findings are correct; independent labelled-image validation is still required before relying on real-customer automatic decisions.

---

# Architecture page update — 27 October 2026

Added a dedicated `/architecture.html` page and sidebar view, using the old project's workflow-diagram, node-card and rule-table structure with the new implementation's actual ports and behavior. The diagram supports keyboard/click selection and illustrative replay; it is explicitly labelled as a workflow illustration rather than live request telemetry. Node status, queue details, policy-index counts and model readiness come from authenticated gateway endpoints. Offline or failed health requests are displayed as offline/unknown rather than retaining a fake healthy state.

- **25 architecture browser checks passed**: direct URL, sidebar navigation, reload, actual three-node status and index counts, keyboard selection, replay start/stop, light/dark rendering, reduced motion, correct price/failure tables, mocked offline/failed-status handling, responsive layout, no browser JavaScript errors or external requests.
- **82 backend regression checks passed** after the page/route change.
- Light, dark and mobile screenshots are in `tests/artifacts/architecture-*.png`; named browser checks are in `tests/artifacts/architecture-browser.json`.
- No inference, return decisions or existing history were changed by the page's verification.

---

# Three-node verification — 27 October 2026

The new project now runs three separate FastAPI processes, preserving the original responsibilities:

| Node | Address | Responsibility |
|---|---|---|
| 1 | `127.0.0.1:8010` | Gateway/UI, original uploads, durable jobs, decisions, signed history and SQLite |
| 2 | `127.0.0.1:8011` | Policy retrieval, documents, advisory and chat relay |
| 3 | `127.0.0.1:8012` | Local Ollama vision, photo questions and serialized text/model execution |

`python3 run.py` launches the cluster. `python3 run.py --status` checks it. The browser uses Node 1 only; Nodes 2 and 3 require a private launcher-generated token. The same model allowlists, local-only inference, price tiers and local automatic entry are preserved. There was no data migration or case deletion.

## Results

- **82 backend tests passed**, including 13 cross-node checks using separate ASGI service applications and controlled model fixtures.
- **14 live browser/API checks passed** against three real running processes, plus the actual browser upload that created the recorded demo case on the preceding test pass.
- Live processing traversed Node 1 → Node 3 (inspection) and Node 1 → Node 2 (policy), saved a complete signed decision, and exported the review record.
- Chat traversed Node 1 → Node 2 → Node 3 and responded using local Qwen2.5 7B.
- Photo Q&A traversed Node 1 → Node 3 and responded using local Moondream.
- Internal routes rejected browser requests without the private token; local automatic entry still works through the gateway.
- The deliberate internal-node shutdown test passed after a signal-handling fix: the launcher detected the failed child and all three listening ports closed. Restart then restored the saved cases and valid audit chain. Evidence is in `tests/artifacts/three-node-supervisor.json`.
- The System health page shows all three node statuses. `three-node-health.png` was visually reviewed.
- Node 2/3 outages in controlled tests produce a durable failed job without an invented approval; retry succeeds after recovery. The T4 human gate remains intact.

## Actual model limitations observed

Ollama was initially stopped. That submission was retained as an inconclusive evidence rejection; it was not a successful inference test. Ollama was then started on loopback with cloud disabled and the upload was repeated as `HAPPY-THREE-NODE-02`.

The repeat case used the Moondream fallback, which supplies a description rather than validated condition confidence, so its final result was **rejected for evidence resubmission**. It is not a confirmed damage diagnosis. Qwen3-VL's attempt failed validation/inference on this run. The architectural split does not claim to improve model accuracy or eliminate fallback/timeouts. The unchanged T4 example still requires a real human decision.

Evidence: `tests/artifacts/three-node-live.json`, `three-node-regression.log`, `three-node-health.png` and the final integrity/status snapshots. Earlier baseline results below describe the initial build before its three-node split.

---

# Verification report — 27 October 2026

Fresh build in `happy_project`; the original project's code and history were not migrated or modified. This is a local workstation deployment with production-oriented safeguards, not a certification of zero defects or diagnostic accuracy.

## Executed checks

| Check | Result |
|---|---|
| Clean virtual environment installation from `requirements.lock` | Passed; 23 pinned runtime packages |
| `pip check` | No broken requirements |
| Isolated Python integration/rule/operations tests | **63 passed** |
| Live-app browser checks in Chrome | **12 passed**, no JavaScript errors or external requests |
| Disposable browser workflow checks with controlled model fixtures | **17 passed**, no JavaScript errors |
| Python compilation / browser JavaScript syntax | Passed |
| Restart persistence of four live cases | Passed |
| Signed audit, current records, photo bytes and SQLite verification | Passed; 4 cases, 8 events, 4 original images |
| All 26 indexed source documents open through authenticated routes | Passed, including 18 PDFs and 8 Markdown/plain-text sources |
| Backup and restore with matching audit key | Passed in isolated tests |

Tests cover tier boundaries, clean approval thresholds, damage/uncertain outcomes, contradictory multiple views, advisory missing identity/policy, failed/queued/recovered work, local-model contention, transaction rollback, concurrent idempotency, input/file/body/pixel limits, CSRF/Origin/Host protection, password rotation, roles, last-administrator protection, rate limits, private files, tampered records/images/fingerprints/accounts/events, historical snapshots and downloads, archive/unarchive, retries and source indexing failures. Real API inference is separate from controlled rule testing.

## Actual local model run

These are four clearly labelled demonstration orders with user-approved synthetic tier prices and existing attributed hardware photos. Source descriptions were not passed to vision. Results are software-flow observations, not independently scored diagnoses.

| Demo | Hardware | Value | Local observation provider | Saved outcome |
|---|---|---:|---|---|
| HAPPY-LIVE-T1 | Graphics card | $250 | Qwen3-VL 8B | Automatic approval |
| HAPPY-LIVE-T2 | Motherboard | $750 | Moondream fallback | Evidence-resubmission rejection |
| HAPPY-LIVE-T3 | RAM | $1,500 | Qwen3-VL 8B | Automatic approval |
| HAPPY-LIVE-T4 | SSD | $3,000 | Qwen3-VL 8B | Pending mandatory human decision |

The T2 result retained an unstructured fallback description with zero verified condition confidence, so the application rejected insufficient evidence rather than asserting damage. The live T4 case was **not** approved by the test runner. Human approve/reject and later re-evaluation were exercised only on a disposable fixture, as were role changes and password rotation.

A real local chat response came from Qwen2.5 7B; selected-photo Q&A responded through Moondream after the structured model attempt failed/timed out. Local fallbacks work, but availability and latency still depend on model memory, image complexity and other Ollama users. This run did not re-evaluate all 20 sample images, calibrate confidence, benchmark accuracy, or validate every listed model variant; only installed successful providers are identified above.

## Evidence

- `tests/artifacts/regression.log`: full disposable regression output.
- `tests/artifacts/browser.json` and `browser-workflows.json`: named browser checks.
- `tests/artifacts/live.json`: actual local observations, decisions, chat and Q&A.
- `tests/artifacts/integrity.json`: live database verification.
- `tests/artifacts/desktop.png` and `mobile.png`: visually reviewed responsive interface.

## Deployment acceptance still required

Independent condition labels and technician review are needed before relying on automatic outcomes for real customer claims. Photos cannot prove electrical function, purchase eligibility, authenticity or hidden defects; confidence is self-reported and uncalibrated. Indexed policies need current region/product/date review. Operational acceptance includes TLS configuration for remote access, encrypted backups, storage monitoring, retention rules and security review appropriate to the deployment. No payment, manufacturer authorization or shipping integration is implemented, matching the original workflow's boundaries.
