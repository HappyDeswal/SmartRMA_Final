# Original and rebuilt workflow alignment

The rebuilt application preserves the original project's functional three-node
architecture, local models, supported hardware, price tiers and return workflow.
It is a rewritten implementation of that design, not a different RMA architecture.

| Responsibility | Original project | Rebuilt project |
|---|---|---|
| Node 1 | Intake/security, EXIF, pHash, orchestration, deterministic tier decisions and audit history | Same functional responsibilities, plus durable jobs and transaction-backed storage |
| Node 2 | Manufacturer-scoped lexical policy retrieval, cited policy advisory and its own local text-model chat | Same responsibilities; text inference executes on Node 2 rather than being relayed to Node 3 |
| Node 3 | Local vision inspection, per-view findings, estimated confidence/anomaly scores and photo Q&A | Same responsibilities, plus the trained advisory hardware-type classifier |
| LLMs | Local Ollama vision/text allowlists | Same model families and local-only allowlists |
| Return order | Node 1 intake → Node 3 vision → Node 1 → Node 2 policy → Node 1 decision/history | Same |
| Policy chat | Node 1 → Node 2 → local Ollama text model | Same |
| Photo questions | Node 1 → Node 3 → local Ollama vision model | Same |
| Price routing | T1 < $300; T2 $300–$1,000; T3 > $1,000–$2,500; T4 > $2,500 | Same boundaries |
| Human decision | Mandatory for T4 only; lower-tier re-evaluation optional | Same |
| Clean approval | T1/T2 confidence >= 85%; T3 >= 95%; risk < 30; usable, consistent evidence and no rejection flags | Same core gates |

Node 2 and Node 3 remain separate services but share one operating-system
inference lock. This prevents text and vision requests from loading competing
models simultaneously. The original design did not require a fourth node;
neither does the rebuilt design. Ollama is the local model runtime.

## Verification

- The distributed workflow test verifies the exact inspection call order:
  Node 3 first, then Node 2; Node 1 records the result.
- The chat routing test makes Node 3 unavailable and confirms that Node 2
  still answers through its injected text provider without contacting Node 3.
  This is a routing test using controlled providers, not a model-accuracy result.
- Separate-process lock tests verify exclusion, release and recovery on exit.
- [Decision comparison results](workflow_parity_results.json) compare the original
  gateway's actual `get_tier` and `decision_result` functions with the rebuilt
  rules for 24 price-boundary, confidence, condition, policy and evidence fixtures.
  All 24 matched. The original functions were extracted from their syntax tree
  without starting the original server or loading its case history.

## Implementation improvements to describe honestly in the report

Functional parity does not mean identical source files or storage formats.
The original service ports are 8000/8001/8002; the rebuilt ports are
8010/8011/8012 so both projects can coexist. The original uses JSON dossiers and
SHA-256 snapshot files; the rebuilt version uses SQLite transactions and
HMAC-signed snapshots, durable queues, authenticated internal requests and
CSRF-protected sessions. The trained ONNX classifier is an added advisory and
does not change the price rules or replace the vision LLM's condition assessment.

The old code retains optional identifier-comparison and coordinate fields, but
its current inspection prompt requests only five compact condition fields and
explicitly excludes serials and coordinates. Neither report should claim proven
OCR authentication, calibrated measurements, PatchCore localization or electrical
diagnosis from this active inspection flow. The decision fixtures do not prove
complete identity-field or legacy API compatibility.

The report should use the same functional architecture and node responsibilities
in both versions, while identifying the actual implementation improvements.
Journal-reported benchmark results remain separate from reproduced project tests.
