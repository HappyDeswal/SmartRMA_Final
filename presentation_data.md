# SmartRMA: Autonomous Hardware Return Authorization & Telemetry Platform
## Presentation Slides & Project Synopsis Data

---

### Slide 1: Introduction
**SmartRMA** is an autonomous, distributed hardware triage and telemetry platform designed to modernize computer hardware returns. By uniting multimodal vision AI, retrieval-augmented manufacturer warranty policies, and cryptographic ledger verification, SmartRMA eliminates manual RMA bottlenecks, detects fraudulent returns, and accelerates decision-making across customer intake and technician review workflows with unmatched precision and speed.

---

### Slide 2: Problem Statement
* **High Operational Latency & Manual Review Costs**: Traditional RMA triage relies on subjective, manual bench inspections, causing multi-week customer turnaround times and ballooning operational labor expenses.
* **Prevalent Return Fraud & Concealed Physical Damage**: Bad actors frequently submit downloaded stock imagery or attempt to return hardware with Customer Induced Damage (CID) such as liquid corrosion, burnt pins, and cracked PCBs.
* **Fragmented & Inconsistently Enforced Warranty Policies**: Hardware manufacturers maintain disparate, complex warranty contracts that human support representatives struggle to parse and apply consistently.

---

### Slide 3: Abstract
This project presents SmartRMA, an intelligent, multi-node architecture for automated electronics return authorization. Combining perceptual image hashing, multimodal vision defect localization, a 1,500-clause manufacturer policy RAG engine, and a tamper-evident SHA-256 audit ledger, the system autonomously classifies hardware defects, prevents fraud, enforces SLA tiers, and guides users with conversational support.

---

### Slide 4: Research Gap
* **Absence of Multi-Angle Visual Defect Localization**: Existing enterprise RMA pipelines evaluate single isolated photos without cross-angle validation or sub-millimeter false-color anomaly heatmap segmentation.
* **Disconnect Between Computer Vision and Legal Policy Clauses**: Prior automated triage solutions classify hardware anomalies purely on visual defects without grounding outcomes in legally binding OEM warranty clauses.
* **Lack of Centralized Immutable Cryptographic Auditability**: Current intake systems rely on mutable relational databases that fail to provide mathematically verifiable, tamper-evident audit trails for fraud prevention.

---

### Slide 5: Objectives
* **Automate Real-Time Hardware Triage & SLA Routing**: Evaluate hardware defects in real time, generate calibrated risk indices (1–100), and dynamically route cases across financial SLA tiers within seconds.
* **Deliver Explainable, Policy-Grounded Decisions**: Index and semantically retrieve clauses from 25+ official manufacturer warranty agreements (Dell, Apple, NVIDIA, ASUS, etc.) to produce legally justified determinations.
* **Guarantee Ledger Tamper-Evident Integrity & Fraud Immunity**: Intercept counterfeit or duplicate image submissions using pHash/EXIF forensics and commit every intake block into an immutable SHA-256 cryptographic ledger.

---

### Slide 6: Dataset & Inputs
* **Multi-Angle Standardized Component Imagery**: 5 required high-resolution inspection angles per hardware unit (Front Shroud, Backplate, PCIe Gold Fingers, 12VHPWR Power Socket, and Serial Barcode Label).
* **Golden Clean Reference Board Baseline**: Curated high-fidelity reference images of factory-perfect GPUs and motherboards utilized for pixel-level comparative anomaly extraction.
* **Indexed Manufacturer Policy Corpus**: Over 1,525 parsed policy chunks extracted from 25+ official OEM warranty and limited service agreements.
* **Intake Metadata & Hardware Telemetry**: Customer order ID, declared retail value (USD), serial number, reported operational symptoms, and camera EXIF header metadata.

---

### Slide 7: Proposed Solution
* **Centralized Master Gateway & Decision Orchestration**: Node 1 serves as the central brain—ingesting dossiers, coordinating worker nodes, verifying cryptographic authenticity, and generating the final verdict.
* **Dedicated Vision Telemetry Return Loop**: Node 3 (Vision LLM Engine) receives image streams from Node 1, localizes defects (PatchCore + Moondream), and routes its findings exclusively back to Node 1.
* **Grounded Policy Evaluation & Conversational Support**: Node 2 (Policy RAG Engine) evaluates warranty terms for Node 1 and powers an interactive, empathetic AI Chatbot dedicated solely to customer queries and return guidance.
* **Cryptographic Block-Chained Audit Ledger**: Every submission, vision score, and decision block is immutably linked with SHA-256 hashes, preventing database tampering and ensuring enterprise-grade auditability.

---

### Slide 8: Methodology
1. **Intake & Authenticity Forensics**: 
   The customer submits case metadata and hardware photos through the Customer Intake Portal to Node 1. Node 1 analyzes EXIF camera signatures and calculates 64-bit perceptual hashes (pHash) to intercept duplicate or stock photo fraud.
2. **Vision Defect Delegation & Return to Node 1**:
   Node 1 delegates the 5-angle image package to Node 3. Node 3 processes the images using Moondream Vision LLM, generates false-color anomaly heatmaps, calculates a normalized defect risk score ($0.0 \le \text{Anomaly} \le 1.0$), and returns its visual defect results **exclusively back to Node 1**.
3. **Policy Evaluation Query & Return to Node 1**:
   Node 1 queries Node 2 for policy verification. Node 2 matches the observed defect against 1,525 vector-indexed OEM clauses (identifying coverage or Customer Induced Damage exclusions) and returns the policy determination **back to Node 1**.
4. **Value-Based SLA Tier Synthesis**:
   Node 1 synthesizes the vision score, policy citations, and declared dollar value across SLA financial governance tiers:
   - **Tier 1 (< $300)**: Rapid auto-approval for low anomaly scores.
   - **Tier 2 ($300 – $1,000)**: Autonomous decision if model confidence $\ge 85\%$.
   - **Tier 3 ($1,000 – $2,500)**: Stringent $95\%$ confidence threshold required.
   - **Tier 4 (> $2,500)**: Mandatory human bench teardown inspection.
5. **Ledger Committal & Final Output Dispatch**:
   Node 1 writes the complete synthesized determination into the tamper-evident SHA-256 blockchain ledger and delivers the **final output** to the Customer Intake Portal and Technician Review Workbench. The AI Chatbot functions as a dedicated query interface connected to Node 2 for customer assistance.

---

### Slide 9: Technology Stack
* **Backend Microservices**: Python 3.14, FastAPI, Uvicorn (Asynchronous REST microservice cluster).
* **Machine Learning & Local Inference**: Ollama Local Server, High-Performance Cloud Technical LLM, Qwen 2.5 Coder (14B parameter Policy LLM), Llama 3.2 Vision (11B multimodal Vision LLM).
* **Computer Vision & Image Forensics**: Pillow (PIL), OpenCV, Perceptual Hashing (`imagehash`), EXIF metadata inspection.
* **Frontend Web Portals**: Semantic HTML5, Vanilla CSS3 (glassmorphic dark UI, micro-animations), JavaScript ES6+ (Fetch API, responsive DOM).
* **Data Storage & Cryptography**: JSON Document Database, In-Memory Vector Search Index, SHA-256 Cryptographic Block Ledger.
* **Security Guardrails**: Perimeter Traversal Firewall, Decompression Bomb Interceptors, Prompt Injection Delimiter Sanitizers, Chat-Only Non-Binding Guardrails.

---

### Slide 10: System Architecture

![SmartRMA System Architecture](system_architecture_diagram.jpg)

#### Architecture Data & Control Flow:
* **Client Web Interface**:
  - **Customer Intake Portal** (`index.html`): Submits multi-angle photos and hardware dossiers directly to Node 1.
  - **Technician Review Workbench** (`review.html`): Receives final triage outcomes, false-color heatmaps, and audit telemetry from Node 1.
  - **Interactive AI Chatbot**: Dedicated conversational interface for answering user queries based on official policies and general details (powered by Local Ollama LLM; strictly text-based, cannot approve returns or process photos).
* **Node 1: Master Gateway & Central Decision Engine (:8000)**:
  - Validates EXIF metadata, checks pHash uniqueness, and applies SLA financial tier matrices.
  - Delegates image analysis to Node 3 and queries policy eligibility from Node 2.
  - **Aggregates findings from Node 2 and Node 3**, executes final decision logic, logs the tamper-evident SHA-256 ledger block, and emits the **final determination output**.
* **Node 3: Vision LLM Engine (:8002)**:
  - Executes Llama 3.2 Vision multimodal visual inspection and false-color heatmap generation.
  - **Returns its visual defect results exclusively to Node 1**.
* **Node 2: Policy RAG Engine (:8001)**:
  - Indexes 1,525 OEM warranty clauses and returns legal eligibility citations **back to Node 1**.
  - Handles customer queries from the interactive AI Chatbot via Local Ollama LLM with strict policy RAG grounding.
* **Local Ollama LLM Runtime (:11434)**:
  - Provides private, on-premise local inference for Node 2 and Node 3 without third-party cloud data transmission.
