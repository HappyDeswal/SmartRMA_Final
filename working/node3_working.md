# Node 3: Vision Telemetry & Multimodal Vision LLM Inspection Engine

## 1. Overview & Role in the Pipeline
**Node 3** is the deep learning computer vision inference microservice of SmartRMA (located in [`node/node3_vision.py`](file:///Users/happydeswal/Downloads/files/node/node3_vision.py) and operating **ONLINE** on **Port 8002**). Its role is to subject hardware return photographs to microscopic structural inspection using an integrated local multimodal **Vision LLM (`moondream:latest`)** running directly via Ollama.

Rather than simple static bounding boxes, Node 3 performs natural visual understanding:
1. It analyzes the hardware photograph to identify the exact component (e.g. 12VHPWR connector, PCIe Gen4 fingers, GPU silicon die, VRM MOSFETs, cooling fans).
2. It detects physical and thermal defects (e.g. scorched/burnt pin terminals, melted plastic housings, arcing, liquid residues, cracks, cold solder joints, or factory-pristine conditions).
3. It extracts deterministic visual telemetry:
   - Anomaly Score ($A \in [0.0, 1.0]$)
   - Flagged component region and normalized coordinates `[X%, Y%]`
   - Severity level (`CRITICAL`, `MODERATE`, `CLEAN`)
   - Natural language diagnostic findings report (`visual_findings_text`)
4. **Cross-Node Transmission**: It packages these textual findings and transmits them directly to:
   - **Node 2** (`http://127.0.0.1:8001/api/triage/evaluate`) for official manufacturer warranty policy citation.
   - **Node 1** (`http://127.0.0.1:8000/api/v1/intake`) for deterministic SLA tier determination ($T_1 - T_4$) and SHA-256 cryptographic audit ledger commitment.

---

## 2. Multimodal Vision Pipeline & Flow

```
                      [Customer Hardware Photograph]
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Ingestion & Security Perimeter Sanitization             │
       │  • Image.MAX_IMAGE_PIXELS = 25,000,000 bomb guard       │
       │  • Canonical path traversal isolation                   │
       │  • Base64 decode & memory-bounded buffer                │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Multimodal Vision LLM Inference (Ollama)                │
       │  • Primary Model: moondream:latest (1.6B Vision)        │
       │  • Fallback: llama3.2-vision:latest / Local CV Matrix   │
       │  • Generates rich empirical physical inspection text    │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │ Deterministic Telemetry & Severity Classifier           │
       │  • Anomaly Score A ∈ [0.0, 1.0]                         │
       │  • Defect Centroid Coordinates [X%, Y%]                 │
       │  • Severity: CRITICAL / MODERATE / CLEAN                │
       └──────────────────────┬───────────┬──────────────────────┘
                              │           │
           ┌──────────────────┘           └──────────────────┐
           ▼                                                 ▼
┌───────────────────────────────┐         ┌────────────────────────────────┐
│ Transmission to Node 2        │         │ Transmission to Node 1         │
│ (Policy RAG Bridge)           │         │ (Decision Router & Ledger)     │
│  • Matches vision findings    │         │  • Calculates Risk Score R     │
│    against 25 manufacturer    │         │  • Enforces SLA Tier Matrix    │
│    PDF policies (CID vs Mfg)  │         │  • Commits SHA-256 Block       │
└───────────────────────────────┘         └────────────────────────────────┘
```

---

## 3. Five Diagnostic Inspection Bays & Modalities

| Inspection Slot | Component Target | Typical Detected Anomalies | Vision Modality |
| :--- | :--- | :--- | :--- |
| **Slot 0** | Front Shroud & Fans | Cracked fan blades, bearing seizure, missing screws | Multimodal Optical RGB |
| **Slot 1** | Backplate & Retention | Warped PCB, stripped screws, thermal pad leakage | Laser 3D / Isometric Optical |
| **Slot 2** | PCIe Gold Fingers | Severed traces, gouges, missing retention teeth | Macro Optical RGB |
| **Slot 3** | 12VHPWR Power Socket | Scorched pins 3 & 4, melted plastic housing, arc pitting | Thermal FLIR / Macro Optical |
| **Slot 4** | Serial Barcode Label | Peeling tamper tape, altered barcode, missing sticker | Macro Optical |

---

## 4. API Endpoints

### 1. `GET /health`
Returns service status, active vision model (`moondream:latest`), and inspection statistics.

### 2. `POST /api/v1/inspect`
Inspects submitted hardware photographs and returns structured visual telemetry:
```json
{
  "order_id": "ORD-48213",
  "serial_number": "SN-RTX4090-OC",
  "images": [
    { "slot": 3, "name": "12VHPWR Power Connector", "url": "assets/gpu_damaged.jpg" }
  ],
  "symptom_description": "Card smoked and pin 3 on power connector blackened"
}
```

**Response**:
```json
{
  "model_used": "moondream:latest",
  "flagged_slot_name": "12VHPWR Power Connector",
  "telemetry": {
    "anomaly_score": 0.88,
    "severity": "CRITICAL",
    "defect_type": "damage",
    "flagged_component": "12VHPWR Power Socket (Pins 3 & 4)",
    "defect_coordinates": { "center_x_pct": 62, "center_y_pct": 38 },
    "confidence": 0.94,
    "recommended_action": "REJECT_CID_EXCLUSION_OR_L2_TEARDOWN",
    "visual_findings_text": "The image shows a person using a ruler to measure a component on a circuit board next to a burnt component that has been damaged..."
  }
}
```

### 3. `POST /api/v1/analyze_and_route`
Analyzes the image and immediately **transmits** the visual diagnostic text to both **Node 2** (Policy RAG) and **Node 1** (Decision Router) for downstream execution:
```json
{
  "status": "SUCCESS_MULTI_NODE_PIPELINE_COMPLETE",
  "pipeline_stages": {
    "node3_vision": {
      "model_used": "moondream:latest",
      "anomaly_score": 0.88,
      "severity": "CRITICAL",
      "flagged_component": "12VHPWR Power Socket (Pins 3 & 4)"
    },
    "node2_policy_rag": {
      "transmitted_findings": true,
      "determination": "REJECTED",
      "cited_clause": "Physical / Liquid Damage Exclusion (Customer Induced Damage - CID)",
      "source_doc": "nvidia_hardware_warranty_policy.md"
    },
    "node1_gateway_ledger": {
      "transmitted_findings": true,
      "disposition": "ESCALATE",
      "tier": "T3",
      "risk_index": 82,
      "block_hash": "241f35da8127bfeae59d4f2a35471472ca092633e6123406837062c25bee56ac"
    }
  }
}
```

### 4. `POST /api/v1/vision/chat`
Allows operators and customers to ask targeted questions about hardware photos (e.g. *"Are the gold fingers scratched in this image?"*).

---

## 5. Security & Operational Hardening
* **Decompression Bomb Protection**: Enforced `Image.MAX_IMAGE_PIXELS = 25_000_000` with strict warning filter.
* **Path Traversal Immunity**: Strict canonical path validation (`resolve_safe_image_path`).
* **HTTP Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`.
