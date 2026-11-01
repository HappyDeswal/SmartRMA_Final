#!/usr/bin/env python3
"""
SmartRMA - Node 2: Warranty Policy RAG & Decision Engine
Runs as a microservice on Port 8001.
Integrates with local Ollama LLMs and indexes manufacturer warranty PDFs.
Enforces strict politeness, boundary guardrails, representative fallback,
and rigorous perimeter firewall controls.

SECURITY HARDENED:
- StaticFiles dotfile and sensitive directory firewall middleware (blocks .git, .system_generated, .env)
- Prohibits direct downloading of python source files, shell scripts, and audit ledgers
- Prompt injection filter neutralizing forged context delimiters
- Strict Pydantic input field length constraints and type limits
- Defensive HTTP security headers
"""

import os
import json
import re
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
# Support both `python -m node...` and direct script execution.
import sys
from pathlib import Path
if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from node.local_runtime import (LocalAccessMiddleware, ALLOWED_ORIGINS, CHAT_MODELS,
    available_models, local_json, CHAT_REQUEST_SECONDS, record_model_result, model_readiness)
from node.decision_rules import (detect_manufacturer, canonical_manufacturer, damage_evidence, informational_reply)

app = FastAPI(title="SmartRMA Node 2 - Policy RAG Engine", version="2.5.0")

# Security Firewall Middleware: blocks path traversal, dotfiles, and sensitive file downloads
class SecurityFirewallMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        raw_path = request.url.path
        
        # 1. Block directory traversal attempts
        if ".." in raw_path:
            return JSONResponse({"error": "Access forbidden: Directory traversal prohibited."}, status_code=403)

        # 2. Block access to hidden directories and dotfiles (.git, .env, .system_generated, etc.)
        segments = [s.strip() for s in raw_path.split("/") if s.strip()]
        for segment in segments:
            if segment.startswith("."):
                return JSONResponse({"error": "Access forbidden: Hidden resource access prohibited."}, status_code=403)

        # 3. Block access to internal source files, ledgers, and system configurations
        blocked_extensions = {".py", ".pyc", ".sh", ".env", ".key", ".pem", ".log", ".tmp"}
        blocked_filenames = {"audit_ledger.json", "cases_store.json", "pending_transaction.json", "package.json", "package-lock.json"}
        blocked_dirs = {"node", "tests", "working", "invalid_sources", ".git", ".system_generated"}
        if any(seg in blocked_dirs for seg in segments):
            return JSONResponse({"error": "Access forbidden: Restricted system directory."}, status_code=403)
        
        last_segment = segments[-1].lower() if segments else ""
        _, ext = os.path.splitext(last_segment)
        if ext in blocked_extensions or last_segment in blocked_filenames:
            return JSONResponse({"error": "Access forbidden: Restricted system file."}, status_code=403)

        response = await call_next(request)

        # Inherent security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityFirewallMiddleware)
app.add_middleware(LocalAccessMiddleware)

# Enable CORS for browser frontends (e.g. index.html, review.html)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(NODE_DIR)
POLICY_DIR = os.path.join(BASE_DIR, "policy") if not BASE_DIR.endswith("policy") else BASE_DIR
INDEX_FILE = os.path.join(POLICY_DIR, "policy_index.json")

# Load Indexed Policy Chunks
POLICY_DATA = {"metadata": {}, "catalog": [], "chunks": []}
if os.path.exists(INDEX_FILE):
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            POLICY_DATA = json.load(f)
        print(f"[Node 2] Loaded {len(POLICY_DATA.get('chunks', []))} policy chunks from {INDEX_FILE}")
    except Exception as e:
        print(f"[Node 2] Error reading index file: {e}")

# Preferred local Ollama models in order of priority (matching installed models)
MODELS_TO_TRY = CHAT_MODELS

SYSTEM_PROMPT = """You are the SmartRMA Intelligent Technical & Policy Assistant.
Your tone must ALWAYS be warm, polite, empathetic, conversational, professional, and helpful — like an experienced hardware support specialist.

CRITICAL OPERATIONAL BOUNDARIES & MANDATORY LIMITATIONS:

1. CHAT PURPOSE ONLY (NO IMAGE/FILE PROCESSING):
   - You are solely an informational conversational assistant for answering questions about official manufacturer warranty policies and general technical/hardware details.
   - You CANNOT and MUST NOT receive, inspect, or process image uploads, hardware photos, or file attachments in this chat.
   - If a customer asks to upload photos or asks you to examine an image in chat, politely clarify:
     "I am an informational text assistant and cannot accept or analyze uploaded photos here. To have your hardware inspected and evaluated, please upload your images in the official SmartRMA Return Intake form on the portal."

2. ABSOLUTE PROHIBITION ON RETURN CLAIMS, APPROVALS & OUTCOME GUARANTEES:
   - You MUST NEVER claim, promise, approve, authorize, or guarantee any return, replacement, refund, or warranty claim outcome.
   - NEVER state phrases such as "Your return is approved", "You will get a refund", "We will replace your item", or "Your warranty claim is accepted".
   - You must explicitly maintain that you cannot make binding return determinations.
   - Clarify that official return authorization requires formal submission via the Return Intake form with authentic hardware photos, followed by automated pipeline analysis and human technician review.

3. ACCURATE POLICY TERMS & RETURN PROCESS PREPARATION:
   - Provide accurate manufacturer warranty terms, coverage periods, and exclusions (e.g. Customer Induced Damage / CID, liquid spills, cracked PCBs, burnt pins) based on official indexed policies.
   - When guiding a user on general return preparation, explain the standard preparation steps:
     • Retain proof of purchase (invoice / store receipt) with matching serial number.
     • Verify the hardware is free from physical impact, burns, or liquid corrosion.
     • Safely pack in an anti-static (ESD) protective bag with original accessories.
     • Obtain shipping authorization directly from the manufacturer before shipping; this prototype only records review suggestions.
   - Conclude with: "For official claim submission and return authorization, please submit a return request through the SmartRMA Intake Portal or contact your manufacturer."

4. GENERAL HARDWARE & TECHNICAL TROUBLESHOOTING:
   - Answer general technical questions (e.g., GPU/CPU architectures, thermal paste, artifacting, PCIe lanes, power requirements, troubleshooting steps) informatively, accurately, and politely according to standard engineering knowledge.
   - Do not mention return checklists or policies for purely technical or conceptual hardware questions unless the user asks about returning."""

# Tokens filtered from user input to prevent prompt injection and delimiter hijacking
FORBIDDEN_DELIMITERS = [
    "[OFFICIAL POLICY CONTEXT]",
    "[CUSTOMER QUESTION]",
    "[CUSTOMER QUERY]",
    "ALL CLAIMS ARE APPROVED",
    "100% CASH REFUND",
    "SYSTEM_PROMPT",
    "SYSTEM PROMPT",
    "### System",
    "### Human",
    "### Assistant",
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>"
]

class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., max_length=1000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    manufacturer: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=64)
    history: List[ChatMessage] = Field(default_factory=list, max_length=6)
    model_config = ConfigDict(extra="forbid")

class TriageRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=128)
    manufacturer: str = Field(..., min_length=1, max_length=64)
    serial: Optional[str] = Field("SN-UNKNOWN", max_length=64)
    defect_type: str = Field(..., min_length=1, max_length=64)
    symptoms: str = Field(..., min_length=1, max_length=2000)
    inspection_notes: Optional[str] = Field("", max_length=2000)

detect_manufacturer_from_text = detect_manufacturer

def search_policy_chunks(query: str, target_mfg: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
    chunks = POLICY_DATA.get("chunks", [])
    if not chunks:
        return []

    detected_mfg = target_mfg or detect_manufacturer_from_text(query)
    query_scope = "graphics" if re.search(r"\b(?:radeon|rtx|geforce|graphics|gpu)\b", query, re.I) else "processor" if re.search(r"\b(?:ryzen|xeon|processor|cpu)\b", query, re.I) else None
    
    # Filter by manufacturer if identified
    candidates = []
    for c in chunks:
        if query_scope and c.get("product_scope") and c["product_scope"] != query_scope:
            continue
        if detected_mfg and canonical_manufacturer(detected_mfg).casefold() == canonical_manufacturer(c.get("manufacturer", "")).casefold():
            candidates.append(c)
    
    if not candidates:
        if detected_mfg:
            return []
        candidates = [c for c in chunks if not query_scope or not c.get("product_scope") or c["product_scope"] == query_scope]

    # Keyword scoring
    keywords = [w.lower() for w in re.findall(r'\b[a-zA-Z0-9_\-]{3,}\b', query)]
    stopwords = {"the", "and", "for", "with", "that", "this", "what", "how", "can", "will", "does", "have", "are", "about", "your", "warranty", "policy"}
    keywords = [w for w in keywords if w not in stopwords]

    scored = []
    for c in candidates:
        txt = c.get("text", "").lower()
        score = 0
        for kw in keywords:
            if kw in txt:
                score += 3
        # Category bonus
        if any(term in query.lower() for term in ["burnt", "crack", "physical", "damage", "spill", "water", "void"]) and c.get("category") == "exclusion_cid":
            score += 5
        if any(term in query.lower() for term in ["return", "rma", "send", "ship", "box"]) and c.get("category") == "return_rma":
            score += 4
        if any(term in query.lower() for term in ["how long", "years", "duration", "period", "expire"]) and c.get("category") == "warranty_duration":
            score += 4

        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k]]

def is_warranty_or_rma_query(text: str) -> bool:
    t = text.lower()
    warranty_terms = [
        "warranty", "rma", "return", "refund", "replace", "replacement",
        "coverage", "guarantee", "covered", "void", "cid", "policy", "claim",
        "depot", "eligibility", "send back", "send it back", "exchange",
        "exclusion", "customer induced damage", "process", "status", "guide",
        "steps", "how to return"
    ]
    return any(re.search(rf"\b{term}\b", t) for term in warranty_terms)

def call_ollama(messages, preferred_model=None):
    if preferred_model and preferred_model not in MODELS_TO_TRY:
        raise HTTPException(status_code=422, detail="Select a configured local chat model.")
    models = available_models([preferred_model] if preferred_model else MODELS_TO_TRY)
    deadline = time.monotonic() + CHAT_REQUEST_SECONDS
    for model in models:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            data = local_json('/api/chat', {
                'model': model, 'messages': messages, 'stream': False, 'think': False,
                'options': {'temperature': 0.1, 'num_predict': 350, 'num_ctx': 4096}
            }, timeout=min(90, remaining))
            reply = data.get('message', {}).get('content', '').strip()
            if reply:
                record_model_result(model, True)
                return reply, model
            record_model_result(model, False, 'Empty local response')
        except Exception as exc:
            record_model_result(model, False, type(exc).__name__)
            continue
    raise HTTPException(status_code=503, detail="Local chat model unavailable. Start Ollama and install qwen2.5:7b.")

@app.get('/health')
def health():
    models = available_models(MODELS_TO_TRY)
    return {
        'status': 'ONLINE', 'service': 'SmartRMA Node 2 - Policy RAG Engine',
        'port': 8001, 'inference_provider': 'local_ollama', 'local_only': True,
        'indexed_chunks': len(POLICY_DATA.get('chunks', [])),
        'indexed_documents': len(POLICY_DATA.get('catalog', [])),
        'manufacturers': POLICY_DATA.get('metadata', {}).get('manufacturers', []),
        'active_models': models, **model_readiness(models),
        'retrieval_method': 'manufacturer_filtered_keyword_search',
        'security_features': ['firewall_dotfile_traversal_blocking', 'pydantic_input_bounds']
    }

@app.get("/api/policies")
def get_policies():
    return {
        "metadata": POLICY_DATA.get("metadata", {}),
        "catalog": POLICY_DATA.get("catalog", [])
    }

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    user_query = req.message.strip()

    # Neutralize prompt injection tokens & delimiter hijacking
    for delim in FORBIDDEN_DELIMITERS:
        user_query = re.sub(re.escape(delim), "[SANITIZED_DELIMITER]", user_query, flags=re.IGNORECASE)

    text_mfg = detect_manufacturer_from_text(user_query)
    # Only assign a manufacturer if explicitly present in the user query text or confirmed in request
    detected_mfg = text_mfg
    if not detected_mfg and req.manufacturer:
        detected_mfg = canonical_manufacturer(req.manufacturer)

    is_warranty_query = is_warranty_or_rma_query(user_query)
    
    # 1. Retrieve brand-specific policy documents only if the user EXPLICITLY specified or named a brand
    relevant_chunks = []
    if detected_mfg and is_warranty_query:
        relevant_chunks = search_policy_chunks(user_query, target_mfg=detected_mfg, top_k=3)
    has_grounding = len(relevant_chunks) > 0
    
    # 2. Build Context Prompt
    if has_grounding and detected_mfg and is_warranty_query:
        context_parts = []
        for i, c in enumerate(relevant_chunks, 1):
            src = c.get("source_file", "Official Terms")
            pg = c.get("page", 1)
            mfg = c.get("manufacturer", "Manufacturer")
            context_parts.append(f"[{mfg} Policy Document: {src} (Page {pg})]:\n{c.get('text', '')}")
        context_str = "\n\n".join(context_parts)
        user_prompt = f"""[OFFICIAL POLICY CONTEXT FOR {detected_mfg}]:
{context_str}

[CUSTOMER QUESTION]:
{user_query}

Instructions:
- Explain the warranty coverage and terms based on the official {detected_mfg} documentation above.
- Mention key preparation points for returns (receipt/invoice, no physical CID, anti-static ESD packaging, obtain manufacturer shipping authorization).
- Remember: You are strictly informational. Do not approve, guarantee, or promise any return or refund outcome.
- Conclude by stating: "For official claim submission and return authorization, please use the SmartRMA Intake Portal or contact your manufacturer."
- Keep the response well-structured and under 150 words."""
    elif is_warranty_query:
        user_prompt = f"""No applicable indexed manufacturer clause was retrieved. Explicitly state this limitation. Do not invent coverage periods, exclusions, section numbers, or eligibility.
[CUSTOMER QUESTION]:
{user_query}

Instructions:
- The customer is asking about warranty terms, return eligibility, or the return process.
- Give a warm, conversational, and helpful response:
  1. Explain that eligibility cannot be determined without an applicable manufacturer policy. Ask for the manufacturer and region; do not assert blanket exclusions.
  2. Clearly guide the user through the standard Return Preparation Steps:
     • Keep proof of purchase (invoice / receipt) and verify serial numbers match.
     • Ensure hardware is free from Customer Induced Damage (physical cracks, burns, liquid corrosion).
     • Pack safely in an anti-static (ESD) protective bag with original accessories.
     • Obtain shipping authorization directly from the manufacturer before shipping; this prototype only records review suggestions.
  3. Remember: You cannot approve, promise, or guarantee any return outcome or process images in chat.
  4. Conclude with: "For official claim submission and return authorization, please use the SmartRMA Intake Portal or contact your manufacturer."
- Keep the response warm, natural, human-sounding, well-structured, and under 160 words."""
    else:
        user_prompt = f"""[CUSTOMER QUESTION]:
{user_query}

Instructions:
- The customer is asking a general technical, hardware, or conversational question.
- Tell the general information according to your own extensive hardware knowledge.
- Answer directly, helpfully, accurately, and politely (under 120 words).
- Do not mention warranty checklists or return steps unless specifically asked."""

    # 3. Construct Ollama Messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Include recent history if provided (sanitized)
    if req.history:
        for h in req.history[-6:]:
            hist_content = h.content[:500]
            for delim in FORBIDDEN_DELIMITERS:
                hist_content = re.sub(re.escape(delim), "[SANITIZED_DELIMITER]", hist_content, flags=re.IGNORECASE)
            messages.append({"role": "user" if h.role == "user" else "assistant", "content": hist_content})

    messages.append({"role": "user", "content": user_prompt})

    # Only local Ollama is allowed. No cloud credentials or remote inference routes.
    reply, used_model = call_ollama(messages, preferred_model=req.model)
    provider = 'local_ollama'

    # Clean up formatting
    reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()

    # Sanitize any accidental occurrences of case study phrasing
    reply = re.sub(r'\b(in|based on|according to|from|as a|per the)?\s*(this|the|a)?\s*case stud(y|ies)\b[\s,:]*', '', reply, flags=re.IGNORECASE)
    reply = re.sub(r'\bcase stud(y|ies)\b', 'industry standards', reply, flags=re.IGNORECASE)

    reply, guardrail_applied = informational_reply(reply)

    sources = []
    for c in relevant_chunks:
        sources.append({
            "manufacturer": c.get("manufacturer"),
            "document": c.get("source_file"),
            "page": c.get("page"),
            "category": c.get("category"),
            "excerpt": c.get("text")[:180] + "..."
        })

    return {
        "reply": reply,
        "manufacturer_detected": detected_mfg,
        "grounded": has_grounding,
        "model_used": used_model,
        "provider": provider,
        "guardrail_applied": guardrail_applied,
        "sources": sources
    }

@app.post("/api/triage/evaluate")
def triage_evaluate(req: TriageRequest):
    """
    Evaluates hardware return eligibility against official manufacturer policies.
    """
    query = f"{req.manufacturer} {req.model_name} {req.defect_type} {req.symptoms} {req.inspection_notes}"
    relevant_chunks = search_policy_chunks(query, target_mfg=req.manufacturer, top_k=3)
    
    # Rules suggest a disposition; citations must come from the same manufacturer.
    # Never infer coverage for unindexed brands or substitute another brand's terms.
    text = f"{req.symptoms} {req.inspection_notes}".lower()
    evidence = damage_evidence(text)
    is_cid = evidence['damage_asserted']
    category = 'exclusion_cid' if is_cid else 'general_terms'
    sources = search_policy_chunks(
        f"{req.manufacturer} {req.model_name} {req.symptoms} {req.inspection_notes} {'physical damage' if is_cid else 'manufacturing defect replacement'}",
        target_mfg=req.manufacturer, top_k=len(POLICY_DATA.get('chunks', [])))
    source = next((c for c in sources if c.get('category') == category), None)
    if source is None and not is_cid:
        source = next((c for c in sources if c.get('category') in {'remedy_replacement', 'general_terms'}), None)
    grounded = source is not None
    status = 'ESCALATED' if evidence['ambiguous'] else 'REJECTED' if grounded and is_cid else 'APPROVED' if grounded and any(
        word in text for word in ['artifact', 'code 43', 'black screen', 'fan rattle', 'coil whine',
                                  'no display', 'crash', 'freeze', 'dead']) else 'ESCALATED'
    return {
        'determination': status, 'risk_index': 92 if status == 'REJECTED' else 14 if status == 'APPROVED' else 52,
        'manufacturer': req.manufacturer, 'model': req.model_name, 'defect_type': req.defect_type,
        'damage_evidence': evidence, 'grounded': grounded, 'cited_clause': source['text'] if source else 'No applicable indexed clause found.',
        'source_doc': source['source_file'] if source else None,
        'page': source['page'] if source else None,
        'official_excerpt': source['text'] if source else '',
        'notes': 'Rule-based policy suggestion; purchase date, regional terms, and eligibility require technician verification.'
    }

# Mount workspace directory for static web files, assets, and downloaded PDF policies
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("[Node 2] Starting Secure SmartRMA Policy RAG Service on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
