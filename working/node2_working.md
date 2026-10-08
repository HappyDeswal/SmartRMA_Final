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

## 3. Dual-Engine LLM Architecture & Boundary Guardrails

Node 2 implements a resilient **Dual-Engine Architecture** for conversational chat:
1. **Primary Cloud Engine**: High-Performance Cloud AI via API key.
2. **Resilient Local Fallback**: When cloud key is unset, rate-limited, or quota is exhausted (HTTP 429), Node 2 automatically redirects to the local Ollama LLM (`qwen2.5-coder:14b` with fallback to `llama3.2-vision:latest`).

### Strict System Guardrails & Limitations Enforced in Node 2:

```
                                [Incoming Customer Inquiry]
                                             │
                                             ▼
                 [Manufacturer & Keyword Retrieval across 1,525 Chunks]
                                             │
                                ┌────────────┴────────────┐
                                ▼                         ▼
                     [Cloud AI Engine]             [Cloud 429 / Unset]
                    (Primary Cloud LLM)                   │
                                │                         ▼
                                │                [Local Ollama LLM]
                                │               (qwen2.5-coder:14b)
                                └────────────┬────────────┘
                                             │
                                             ▼
                        [Strict Safety Boundary Filter]
  • CHAT PURPOSE ONLY: Never accepts image uploads or photo attachments in chat.
  • NO RETURN GUARANTEES: Never promises, approves, or claims returns/refunds.
  • INFORMATIONAL ONLY: Clarifies official returns require formal Intake submission.
  • POLICY GROUNDING: Synthesizes indexed clauses into clean preparation steps.
```

### Safety & Operational Limitations:
1. **Chat Purpose Only**: The assistant is strictly for answering questions about policies and general hardware details. Image uploads and file attachments are prohibited in chat; hardware inspection requires filing a claim in the Return Intake portal.
2. **No Return Approvals or Claims**: The chatbot never states or guarantees that a return or refund will be accepted. Official determinations require formal intake with verified photos and technician review.
3. **Policy Grounding**: Synthesizes verified clauses into step-by-step preparation guidance (receipt verification, anti-static ESD packaging, no CID, official RMA authorization).
4. **General Technical Guidance**: Accurately explains hardware concepts (PCIe lanes, thermal paste, artifacting, architecture) without hallucination.

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
  "cloud_api_configured": true,
  "primary_chat_engine": "High-Performance Cloud AI",
  "fallback_chat_engine": "Local Ollama LLM (qwen2.5-coder:14b)",
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
