# SmartRMA: The "RMA Triangle of Truth" Architecture

## 1. The Core Architectural Philosophy
In high-value consumer electronics and enterprise GPU triage ($300 to $5,000+ per unit), **no single AI model should ever make a unilateral warranty determination**.
* A pure computer vision model cannot read legal terms or understand warranty duration exclusions.
* A pure large language model cannot reliably inspect circuit board solder joints or detect Photoshop manipulations.
* A pure database rule engine cannot interpret natural language customer complaints or evaluate optical sensor photographs.

To achieve enterprise-grade reliability, SmartRMA introduces the **"RMA Triangle of Truth"**: three distinct, specialized microservices arranged in a triangular consensus topology.

![RMA Triangle Workflow Diagram](rma_triangle_workflow_diagram.svg)

---

## 2. The Three Apexes of the Triangle

```
                           [APEX 1: NODE 1]
                    Ingest & Security Gateway + Router
                              (Port :8000)
                              ONLINE ACTIVE
                                   ▲
                                  / \
                                 /   \
                     5 Photo    /     \   Symptoms & Mfg
                     Tensors   /       \  (Returns CID Clause)
                              /         \
                             /           \
                            ▼             ▼
              [APEX 2: NODE 3] ◄────────► [APEX 3: NODE 2]
              Vision Telemetry             Policy RAG & LLM
                (Port :8002)                 (Port :8001)
                ONLINE ACTIVE                ONLINE ACTIVE
```

### Apex 1: Node 1 — The Edge Security & Mathematical Router (Port 8000)
* **Role**: Gateway, Anti-Fraud, and Final Arbiter.
* **Tech**: FastAPI, Pillow, `imagehash` (64-bit DCT pHash), SHA-256 Ledger.
* **Why No LLM?**: Financial and RMA replacement decisions must be 100% mathematically deterministic and reproducible under audit.
* **Responsibilities**:
  1. Computes 64-bit perceptual hashes to detect recycled web photos.
  2. Audits EXIF camera timestamps and software editing tags (Photoshop/GIMP).
  3. Orchestrates calls to Apex 2 (Vision) and Apex 3 (Policy RAG).
  4. Resolves the Multi-Factor Risk Index ($R \in [0, 100]$) and enforces SLA Tier boundaries (T1 to T4).
  5. Cryptographically signs every finalized claim into an append-only audit ledger.

---

### Apex 2: Node 3 — The Visual Telemetry Engine (Port 8002)
* **Role**: Microscopic and Photometric Anomaly Inspector.
* **Tech**: PyTorch, Anomalib, PatchCore ResNet-50, FLIR Thermal, Laser 3D.
* **Responsibilities**:
  1. Evaluates 5 guided inspection bays (Shroud, Backplate, PCIe Pins, 12VHPWR Socket, Serial Label).
  2. Compares patch features against a memory bank of 500+ golden reference clean circuit boards.
  3. Emits an Anomaly Score $A \in [0.0, 1.0]$.
  4. Pinpoints defect centroid coordinates (e.g. Pin 3: $X=62\%, Y=38\%$) and renders false-color JET heatmaps.

---

### Apex 3: Node 2 — The Legal Policy RAG & Language Engine (Port 8001)
* **Role**: Manufacturer Contract Arbiter & Conversational Assistant.
* **Tech**: FastAPI, 25 Manufacturer PDFs (1,525 Chunks), local Ollama (`qwen2.5-coder:14b`).
* **Responsibilities**:
  1. Retrieves official warranty terms from Dell, Apple, Gigabyte, Acer, ASUS, NVIDIA, EVGA, Lenovo, HP, and Intel.
  2. Matches defect symptoms to Customer Induced Damage (CID) exclusion clauses.
  3. Cites exact document filenames, sections, and page numbers.
  4. Enforces strict politeness and a **Zero-Claim Guardrail** (courteously defers to an RMA representative without guessing if an unindexed condition is encountered).
  5. Powers the interactive WhatsApp Business chatbot.

---

## 3. Real-World Consensus Scenarios

### Scenario 1: Scorched 12VHPWR Power Connector on $1,240 GPU
1. **Node 1** validates order `ORD-48213` and computes pHash (verifies unique, non-stock photo). Determines Tier 3 ($95\%$ confidence threshold required).
2. **Node 3** inspects Slot 3, compares against golden socket reference, and flags $A = 0.86$ at Pin 3 ($X=62\%, Y=38\%$) with red JET thermal anomaly.
3. **Node 2** retrieves `Warranty - GIGABYTE Global.pdf (Page 5)` and cites the Customer Induced Damage & Overvoltage exclusion clause.
4. **Node 1 Router** synthesizes:
   $$R = 70 \cdot (0.86) + 20 \cdot (1.0) + 0 = 80/100$$
   Because $R \ge 70$ and CID is verified, the claim is **REJECTED** (or escalated to L2 workbench if disputed).
5. **SHA-256 Ledger** commits block hash `c9918286d9c4df448c625eda61a0eeee...` permanently into `audit_ledger.json`.

---

### Scenario 2: Recycled Stock Web Image Claim
1. **Node 1** computes 64-bit DCT pHash on the uploaded photo and finds a Hamming distance $\le 4$ against an existing forum image.
2. Flag `DUPLICATE_PHASH_DETECTED` is raised immediately.
3. **Node 1 Router** aborts auto-approval and forces **MANDATORY ESCALATION** to the fraud prevention desk, regardless of how clean the product appears.

---

### Scenario 3: High-Value Enterprise Card ($3,150 RTX 6000 Ada)
1. **Node 1** evaluates declared value $>\$2,500$ and locks the decision tier to **Tier 4**.
2. Even if Node 3 reports $A = 0.05$ (pristine) and Node 2 confirms valid warranty, **Tier 4 policy forbids automated approval**.
3. Claim is routed directly to the [Technician Review Workbench](file:///Users/happydeswal/Downloads/files/review.html) for physical disassembly and lead engineer sign-off.
