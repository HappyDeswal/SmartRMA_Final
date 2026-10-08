# Node 1: Ingest & Security Gateway + Decision Router

## 1. Overview & Role in the Pipeline
**Node 1** is the enterprise edge entry point and the master decision router of SmartRMA (located in [`node/node1_gateway.py`](file:///Users/happydeswal/Downloads/files/node/node1_gateway.py) and operating on **Port 8000**). It serves two primary functions:
1. **Intake & Anti-Fraud Security Gateway (Inbound)**: Intercepts all incoming return requests, sanitizes payload data, extracts camera EXIF metadata, and calculates cryptographic Perceptual Hashes (pHash) to stop fraudulent, duplicate, or stock web photo submissions.
2. **Deterministic Decision Router (Outbound)**: Synthesizes visual anomaly scores from **Node 3** and legal warranty coverage clauses from **Node 2** into a deterministic Multi-Factor Risk Index (0–100) and resolves the final RMA disposition (**Approve**, **Escalate**, or **Reject**).

---

## 2. Ingest & Anti-Fraud Verification Pipeline

```
 [Customer RMA Submission (Form / Chat)]
                 │
                 ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Node 1: Edge Security & Ingest Gateway (Port 8000)      │
 │                                                         │
 │  [1. Payload Sanitization & Schema Validation]          │
 │      • Order ID, Serial Number, Value, Defect Notes     │
 │                                                         │
 │  [2. Forensic EXIF & Metadata Audit]                    │
 │      • Original camera timestamp vs. return time        │
 │      • Device model, lens focal length, GPS tags        │
 │      • Edited software signatures (Photoshop/GIMP)      │
 │                                                         │
 │  [3. Perceptual Hashing (pHash) Duplicate Filter]       │
 │      • Compute 64-bit DCT perceptual hash               │
 │      • Hamming distance < 5 flag: Reused / Web image    │
 └─────────────────────────┬───────────────────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
  [Pass Security]                        [Fraud Flag]
       │                                       │
       ▼                                       ▼
 Forward to Node 3 & Node 2           Immediate T4 Forensic Escalation
```

### Key Security Algorithms
* **Perceptual Hashing (`imagehash.phash`)**:
  Computes a 64-bit discrete cosine transform (DCT) frequency fingerprint of each of the 5 uploaded camera angles. If the Hamming distance between the submitted image and any known stock web image or past RMA claim is $\le 4$, the claim is flagged for serial recycling fraud.
* **EXIF Consistency Check**:
  Verifies that the camera creation timestamp matches the claim submission timeframe ($\le 48\text{ hours}$) and confirms that all 5 angles were captured by the same physical camera sensor.

---

## 3. Deterministic Decision Router Matrix

SmartRMA strictly avoids "black-box" decision-making for warranty disbursements. Node 1 applies a deterministic boundary matrix based on item value tiers and computed risk scores.

### Multi-Factor Risk Index Formulation
The composite risk score $R \in [0, 100]$ is computed as:
$$R = w_1 \cdot A_{\text{anomaly}} + w_2 \cdot C_{\text{exclusion}} + w_3 \cdot H_{\text{history}} + w_4 \cdot S_{\text{security}}$$
* $A_{\text{anomaly}}$: Vision Anomaly Score from Node 3 ($0.0 \dots 1.0$)
* $C_{\text{exclusion}}$: Policy exclusion factor from Node 2 ($1.0$ if Customer Induced Damage, $0.0$ if manufacturing defect)
* $H_{\text{history}}$: Account return frequency and RMA return velocity
* $S_{\text{security}}$: pHash and EXIF integrity penalty

### Decision Tier Boundaries
| Tier | Product Value | Auto-Approval Criteria | Escalation Criteria | Rejection Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | Under $300 | Risk Score $< 30$ | Risk Score $30 \dots 70$ | Verified CID / Serial mismatch |
| **Tier 2** | $300 – $1,000 | Confidence $\ge 85\%$ & Risk $< 30$ | Confidence $< 85\%$ | Verified CID exclusion from Node 2 |
| **Tier 3** | $1,000 – $2,500 | Confidence $\ge 95\%$ & Risk $< 20$ | Confidence $< 95\%$ | Physical damage / CID verified |
| **Tier 4** | Over $2,500 | **Never Auto-Approved** | **100% Mandatory L2 Tech Teardown** | Verified CID exclusion |

---

## 4. Input & Output Contract

### Inbound POST `/api/v1/intake`
```json
{
  "order_id": "ORD-48213",
  "serial_number": "GPU-7F3A91",
  "product_value": 1240.00,
  "manufacturer": "GIGABYTE",
  "model_name": "RTX 4090 Gaming OC",
  "symptom_description": "Burnt 12VHPWR connector after high load",
  "images": [
    { "slot": 0, "angle": "front_shroud", "image_b64": "..." },
    { "slot": 1, "angle": "backplate", "image_b64": "..." },
    { "slot": 2, "angle": "pcie_pins", "image_b64": "..." },
    { "slot": 3, "angle": "power_socket", "image_b64": "..." },
    { "slot": 4, "angle": "serial_label", "image_b64": "..." }
  ]
}
```

### Outbound POST `/api/v1/decision`
```json
{
  "case_id": "RMA-84920",
  "determination": "REJECT",
  "decision_tier": "T3",
  "risk_index": 92,
  "confidence": 0.94,
  "security_audit": {
    "phash_status": "VERIFIED_UNIQUE",
    "exif_status": "AUTHENTIC_CAMERA_RAW",
    "fraud_flags": []
  },
  "policy_citation": {
    "source_doc": "Warranty - GIGABYTE Global.pdf",
    "page": 5,
    "clause": "Customer Induced Damage (CID) & Overvoltage Exclusion",
    "text": "GIGABYTE will not be responsible for failure caused by liquid spill, neglect, misuse, abuse, and customer induced damage."
  },
  "audit_ledger_hash": "sha256:4a8f9c1b2e3d4f5..."
}
```
