# SmartRMA: Combined Distributed Pipeline Architecture

## 1. System Master Blueprint
SmartRMA connects three microservice nodes into an end-to-end automated hardware warranty intake, triage, and audit platform.

```
                           [Customer Intake / WhatsApp Chat (index.html)]
                                                 │
                                                 ▼
             ┌────────────────────────────────────────────────────────────────────────┐
             │ Node 1: Ingest & Security Gateway (Port 8000)                          │
             │   • EXIF Camera Sensor Audit & Timestamp Correlation                   │
             │   • Perceptual Hash (pHash) 64-bit Duplicate Image Prevention          │
             │   • CRM / Order Verification & Anti-Fraud History                      │
             └───────────────────┬────────────────────────────────┬───────────────────┘
                                 │                                │
                     [5 Inspection Images]               [Symptom Description]
                                 │                                │
                                 ▼                                ▼
  ┌──────────────────────────────────────────────┐ ┌──────────────────────────────────────────────┐
  │ Node 3: Vision Telemetry Engine (Port 8002)  │ │ Node 2: Policy RAG Engine (Port 8001)        │
  │   • PatchCore ResNet-50 Anomaly Inference    │ │   • BM25 + Semantic Search (1,525 Chunks)    │
  │   • Memory Bank Golden Sample Distance       │ │   • Local Ollama LLM (Qwen2.5-Coder)         │
  │   • Sub-millimeter False-Color Heatmaps      │ │   • Strict Politeness & Representative Fall- │
  │   • Outputs Anomaly Score A ∈ [0.0, 1.0]     │ │     back Guardrails (Zero False Claims)      │
  └──────────────────────┬───────────────────────┘ └──────────────────────┬───────────────────────┘
                         │                                                │
                         └───────────────────────┬────────────────────────┘
                                                 │
                                                 ▼
             ┌────────────────────────────────────────────────────────────────────────┐
             │ Node 1: Deterministic Decision Router                                  │
             │   • Multi-Factor Risk Index Calculation (R ∈ [0, 100])                  │
             │   • Tier Boundary SLA Enforcement (T1: <$300, T2, T3, T4: >$2,500)     │
             └───────────────────┬───────────────────┬────────────────────┬───────────┘
                                 │                   │                    │
                   ┌─────────────┘                   │                    └─────────────┐
                   ▼                                 ▼                                  ▼
         ┌──────────────────┐              ┌──────────────────┐               ┌──────────────────┐
         │     APPROVE      │              │     ESCALATE     │               │      REJECT      │
         │  Risk < 30 / T1  │              │  L2 Tech Review  │               │ Verified CID /   │
         │ Auto-Print Label │              │  (review.html)   │               │   Exclusion      │
         └─────────┬────────┘              └─────────┬────────┘               └─────────┬────────┘
                   │                                 │                                  │
                   └─────────────────────────────────┼──────────────────────────────────┘
                                                     ▼
             ┌────────────────────────────────────────────────────────────────────────┐
             │ Cryptographic Append-Only Audit Ledger                                 │
             │   • SHA-256 Merkle root hash linking photos, decision, and cited clause │
             │   • Immutable, tamper-evident audit trail for regulatory compliance    │
             └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End Lifecycle of an RMA Claim

### Step 1: Customer Intake (UI & WhatsApp Chatbot)
1. The customer loads [index.html](file:///Users/happydeswal/Downloads/files/index.html) and enters Order Reference, Serial ID, Declared Value, and Manufacturer.
2. The customer uploads 5 guided diagnostic photos:
   * Front Shroud, Backplate, PCIe Gold Fingers, 12VHPWR Power Socket, Serial Barcode.
3. The customer can ask questions in the real-time **WhatsApp Business Chatbot** (*"Is a burnt connector covered under Gigabyte policy?"*).

---

### Step 2: Edge Security & Ingest (Node 1)
1. **Perceptual Hashing (pHash)**: Converts each image into a 64-bit DCT hash. Calculates Hamming distance against known web images and past claims.
2. **Forensic EXIF Verification**: Confirms photo timestamps are within 48 hours of claim filing and checks for photo editing software signatures.
3. **Order Match**: Validates product serial number against the merchant's ERP database.

---

### Step 3: Parallel Telemetry Execution (Nodes 2 & 3)
* **Node 3 (Computer Vision)**:
  * Resizes photo tensors and extracts deep patch features via ResNet-50.
  * Compares features against 500+ golden reference clean circuit boards in memory bank.
  * Emits an **Anomaly Score ($A = 0.86$)** and locates the defect coordinates ($X=62\%, Y=38\%$, 12VHPWR pin 3).
  * Generates a JET false-color heatmap overlay highlighting localized heat stress.
* **Node 2 (Policy RAG & Local LLM)**:
  * Retrieves relevant clauses from the 25 official manufacturer PDFs in `policy/`.
  * Matches the burnt pin to the **Customer Induced Damage (CID) & Overvoltage Exclusion Clause**.
  * Formulates a polite, policy-grounded justification citing `Warranty - GIGABYTE Global.pdf (Page 5)`.

---

### Step 4: Decision Matrix & Boundary Routing (Node 1)
1. Node 1 merges:
   * Item Value: $\$1,240$ $\rightarrow$ **Tier 3** ($95\%$ confidence threshold required).
   * Vision Anomaly: $0.86$ (Critical electrical burn).
   * Policy Clause: Explicit exclusion under CID.
2. Formulates Composite Risk Score: $92/100$.
3. **Verdict: REJECT** (or **ESCALATE** to L2 Workbench if disputed).

---

### Step 5: Tri-Branch Outcome Execution
1. **Branch A (Approve)**: Generates prepaid return shipping label and packing slip.
2. **Branch B (Escalate)**: Routes claim directly to the **Technician Review Workbench** ([review.html](file:///Users/happydeswal/Downloads/files/review.html)) with dual-viewport golden comparator and override reason chips.
3. **Branch C (Reject)**: Delivers formal PDF Policy Exclusion Notice directly into the customer's WhatsApp chat stream, citing exact manufacturer terms.

---

### Step 6: Immutable Cryptographic Audit Ledger
Every completed RMA decision is signed into an append-only cryptographic ledger:
```json
{
  "timestamp": "2026-10-07T18:25:00Z",
  "case_id": "RMA-84920",
  "disposition": "REJECT",
  "risk_score": 92,
  "cited_policy": "GIGABYTE Global Policy, Section 5 (CID)",
  "vision_anomaly_score": 0.86,
  "ledger_hash": "sha256:7b92f4c1e8d9a04..."
}
```

---

## 3. Current Live Status of All Nodes (Located in `node/` Directory)

| Microservice | Port | File Path | Current Status | Engine Details |
| :--- | :--- | :--- | :--- | :--- |
| **Node 1: Gateway & Decision Router** | `:8000` | `node/node1_gateway.py` | **ONLINE ACTIVE** | EXIF camera metadata audit, 64-bit pHash anti-tamper, deterministic SLA routing, SHA-256 cryptographic ledger. |
| **Node 2: Policy RAG & LLM Engine** | `:8001` | `node/node2_policy_rag.py` | **ONLINE ACTIVE** | Live FastAPI service connected to local Ollama (`qwen2.5-coder:14b`) with 1,525 indexed PDF clauses & perimeter firewall. |
| **Node 3: Vision Telemetry Engine** | `:8002` | `node/node3_vision.py` | **ONLINE ACTIVE** | Multimodal Vision LLM (`moondream:latest`) hardware defect analysis and downstream cross-node text data transmission. |

---

## 4. Directory Structure

All three microservice implementations are consolidated in the dedicated `node/` folder:
- `node/node1_gateway.py`: Port 8000
- `node/node2_policy_rag.py`: Port 8001
- `node/node3_vision.py`: Port 8002
