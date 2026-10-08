# Node 2: Warranty Policy RAG & Local LLM Reasoning Engine

## 1. Overview & Role in the Pipeline
**Node 2** is the legal policy intelligence core of SmartRMA (located in [`node/node2_policy_rag.py`](file:///Users/happydeswal/Downloads/files/node/node2_policy_rag.py) and operating as an active FastAPI microservice on **Port 8001**). Its mission is to parse, index, search, and reason over official manufacturer warranty policies and return terms (from Apple, GIGABYTE, Dell, Acer, ASUS, NVIDIA, EVGA, Lenovo, HP, and Intel).

Node 2 operates in two interconnected modes:
1. **Automated Triage Clause Citation**: Ingests defect symptoms from Node 1, matches them against indexed PDF clauses, and returns deterministic CID/coverage classifications.
2. **Conversational WhatsApp RMA Assistant**: Engages directly with customers in natural language, answering return questions with polite empathy while adhering to strict safety and legal boundaries.

---

## 2. Document Ingestion & Chunking Architecture

```
 [/policy/ Directory: 25 Official Manufacturer PDFs & Terms]
  ├── Dell Limited Hardware Warranty.pdf
  ├── Legal - Mac Warranty Us - Apple.pdf
  ├── Warranty - GIGABYTE Global.pdf
  ├── Warranty - GIGABYTE European Union.pdf
  ├── WY_Acer_NB_EMEA_NC.pdf
  ├── intel_xeon_limited_warranty.pdf
  ├── nvidia_official_geforce_warranty.md
  └── asus_official_warranty_terms.md
                     │
                     ▼
 ┌─────────────────────────────────────────────────────────┐
 │ Node 2 Ingestion Engine (build_policy_index.py)         │
 │                                                         │
 │  • PyPDF text & table extraction                        │
 │  • Text sanitization & whitespace normalization         │
 │  • Sliding window semantic chunking (750 chars + 150 ov)│
 │  • Category labeling:                                   │
 │    - exclusion_cid (Customer Induced Damage)            │
 │    - warranty_duration (1-year, 3-year limited)         │
 │    - return_rma (Shipping, RMA procedure, packaging)    │
 │    - proof_of_purchase (Invoice, authorized reseller)   │
 └─────────────────────────┬───────────────────────────────┘
                           │
                           ▼
 [Structured Vector Index: policy_index.json (1,525 Chunks)]
```

---

## 3. Local LLM Reasoning & Boundary Guardrails

Node 2 integrates with local **Ollama** (`http://localhost:11434`) using the high-performance **`qwen2.5-coder:14b`** model (with automatic fallback to `llama3.2-vision:latest` / `qwen3.5:35b-a3b`).

### Strict System Guardrails Enforced in Node 2:

```
                                [Incoming Customer Inquiry]
                                             │
                                             ▼
                 [Manufacturer & Keyword Retrieval across 1,525 Chunks]
                                             │
                ┌────────────────────────────┴────────────────────────────┐
                ▼                                                         ▼
    [Strong Matching Policy Found]                           [No Matching Policy / Unindexed]
                │                                                         │
 • Synthesize official terms into clean bullet points.     • STRICT RULE: Never hallucinate or assume.
 • Quote official source document, page, and category.     • STRICT RULE: Never make financial promises.
 • Explain exclusions (CID, liquid, burnt) politely.       • Courteous Fallback Triggered:
 • Maintain empathetic, respectful tone.                     "This specific condition or product line is
                                                              not explicitly detailed in our indexed
                                                              manufacturer policy documentation. To ensure
                                                              you receive accurate guidance, our RMA
                                                              representative will review your query shortly."
                                                           • Inject interactive button:
                                                             [🛎️ Connect with Human RMA Representative]
```

### Safety & Persona Guidelines:
1. **Empathy**: Validates the customer's hardware frustration (*"I understand how inconvenient hardware issues can be..."*).
2. **Preliminary Notice**: Always reminds the user that automated triage is preliminary and subject to final physical verification at the depot.
3. **Firm on Exclusions**: Respectfully explains manufacturer CID exclusions without being confrontational or argumentative.
4. **Off-Topic Deflection**: Declines coding requests, roleplay, or general trivia, politely guiding users back to RMA and hardware inspection.

---

## 4. API Endpoints Contract

### Health Check: `GET /health`
```json
{
  "status": "ONLINE",
  "service": "SmartRMA Node 2 - Policy RAG Engine",
  "port": 8001,
  "indexed_chunks": 1525,
  "indexed_documents": 25,
  "manufacturers": ["Dell", "Apple", "GIGABYTE", "Acer", "ASUS", "Lenovo", "HP", "Intel", "EVGA", "NVIDIA"],
  "active_models": ["qwen2.5-coder:14b", "llama3.2-vision:latest", "qwen3.5:35b-a3b"]
}
```

### Conversational Chat: `POST /api/chat`
* **Request**:
  ```json
  {
    "message": "What is the warranty period for a Gigabyte graphics card and is customer induced damage covered?",
    "manufacturer": "GIGABYTE"
  }
  ```
* **Response**:
  ```json
  {
    "reply": "Thank you for your inquiry. According to the GIGABYTE European Union Policy (Page 1), the warranty period for a Gigabyte graphics card is 3 years of limited local warranty (excluding Mining Series cards). Regarding customer induced damage, Section 5 notes that failure resulting from liquid spills, neglect, abuse, or CID is an explicit exclusion.",
    "manufacturer_detected": "GIGABYTE",
    "grounded": true,
    "model_used": "qwen2.5-coder:14b",
    "sources": [
      {
        "manufacturer": "GIGABYTE",
        "document": "Warranty - GIGABYTE European Union.pdf",
        "page": 1,
        "category": "warranty_duration"
      },
      {
        "manufacturer": "GIGABYTE",
        "document": "Warranty - GIGABYTE Global.pdf",
        "page": 5,
        "category": "exclusion_cid"
      }
    ]
  }
  ```

### Triage Evaluation: `POST /api/triage/evaluate`
* **Request**:
  ```json
  {
    "manufacturer": "GIGABYTE",
    "model_name": "RTX 4090 Gaming OC",
    "serial": "GPU-7F3A91",
    "defect_type": "damage",
    "symptoms": "Burnt 12VHPWR connector after system shutdown"
  }
  ```
* **Response**:
  ```json
  {
    "determination": "REJECTED",
    "risk_index": 92,
    "cited_clause": "Physical / Liquid Damage Exclusion (Customer Induced Damage - CID)",
    "source_doc": "Warranty - GIGABYTE Global.pdf",
    "page": 3,
    "notes": "Physical fracture, overvoltage burnout, or liquid contact detected."
  }
  ```
