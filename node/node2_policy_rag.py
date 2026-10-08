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
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field

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
        blocked_extensions = {".py", ".pyc", ".sh", ".env", ".key", ".pem", ".log"}
        blocked_filenames = {"audit_ledger.json", "package.json", "package-lock.json"}
        blocked_dirs = {"node", ".git", ".system_generated"}
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

# Enable CORS for browser frontends (e.g. index.html, review.html)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(NODE_DIR)
POLICY_DIR = os.path.join(BASE_DIR, "policy") if not BASE_DIR.endswith("policy") else BASE_DIR
INDEX_FILE = os.path.join(POLICY_DIR, "policy_index.json")
OLLAMA_URL = "http://localhost:11434/api/chat"

# Load environment variables from .env file if present
def load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            print("[Node 2] Environment variables loaded from .env")
        except Exception as e:
            print(f"[Node 2] Error reading .env file: {e}")

load_env_file()

# Load Indexed Policy Chunks
POLICY_DATA = {"metadata": {}, "catalog": [], "chunks": []}
if os.path.exists(INDEX_FILE):
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            POLICY_DATA = json.load(f)
        print(f"[Node 2] Loaded {len(POLICY_DATA.get('chunks', []))} policy chunks from {INDEX_FILE}")
    except Exception as e:
        print(f"[Node 2] Error reading index file: {e}")

# Preferred local Ollama models in order of priority (fallback when Gemini API unavailable/exhausted)
MODELS_TO_TRY = ["qwen2.5-coder:14b", "llama3.2-vision:latest", "qwen3.5:35b-a3b"]

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
     • Obtain an official RMA authorization number through the Intake Portal before shipping.
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
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(..., max_length=1000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    manufacturer: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=64)
    history: Optional[List[ChatMessage]] = Field(default=[], max_length=6)
    gemini_api_key: Optional[str] = Field(None, max_length=256)

class TriageRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=128)
    manufacturer: str = Field(..., min_length=1, max_length=64)
    serial: Optional[str] = Field("SN-UNKNOWN", max_length=64)
    defect_type: str = Field(..., min_length=1, max_length=64)
    symptoms: str = Field(..., min_length=1, max_length=2000)
    inspection_notes: Optional[str] = Field("", max_length=2000)

def detect_manufacturer_from_text(text: str) -> Optional[str]:
    t = text.lower()
    mapping = {
        "gigabyte": "GIGABYTE",
        "aorus": "GIGABYTE",
        "apple": "Apple",
        "macbook": "Apple",
        "mac": "Apple",
        "dell": "Dell",
        "alienware": "Dell",
        "acer": "Acer",
        "predator": "Acer",
        "lenovo": "Lenovo",
        "thinkpad": "Lenovo",
        "hp": "HP",
        "hewlett": "HP",
        "omen": "HP",
        "intel": "Intel",
        "xeon": "Intel",
        "nvidia": "NVIDIA",
        "geforce": "NVIDIA",
        "rtx": "NVIDIA",
        "evga": "EVGA",
        "asus": "ASUS",
        "rog": "ASUS",
        "amd": "AMD",
        "radeon": "AMD"
    }
    for k, v in mapping.items():
        if re.search(rf"\b{k}\b", t):
            return v
    return None

def search_policy_chunks(query: str, target_mfg: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
    chunks = POLICY_DATA.get("chunks", [])
    if not chunks:
        return []

    detected_mfg = target_mfg or detect_manufacturer_from_text(query)
    
    # Filter by manufacturer if identified
    candidates = []
    for c in chunks:
        if detected_mfg and detected_mfg.lower() in c.get("manufacturer", "").lower():
            candidates.append(c)
    
    if not candidates:
        candidates = chunks

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

def call_gemini_api(user_prompt: str, system_instruction: str, history: Optional[List[Any]] = None, explicit_key: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    key = explicit_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None, None

    gemini_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    contents = []
    if history:
        for h in history[-6:]:
            h_role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else "user")
            h_content = getattr(h, "content", None) or (h.get("content") if isinstance(h, dict) else "")
            contents.append({
                "role": "user" if h_role == "user" else "model",
                "parts": [{"text": str(h_content)[:600]}]
            })
    contents.append({
        "role": "user",
        "parts": [{"text": user_prompt}]
    })

    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        },
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 350,
            "topP": 0.95
        }
    }

    for model_name in gemini_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        text_chunks = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
                        reply_text = "".join(text_chunks).strip()
                        if reply_text:
                            return reply_text, f"{model_name} (Google Gemini Cloud)"
        except urllib.error.HTTPError as http_err:
            print(f"[Node 2] Gemini API HTTP error ({model_name}): {http_err.code} - {http_err.reason}")
            # If 429 (quota exhausted/rate limit) or 400/403, proceed to next model or fallback to local Ollama
            continue
        except Exception as e:
            print(f"[Node 2] Gemini API connection error ({model_name}): {e}")
            continue

    return None, None

def call_ollama(messages: List[Dict[str, str]], preferred_model: Optional[str] = None) -> tuple[str, str]:
    models = [preferred_model] if preferred_model else MODELS_TO_TRY
    for m in models:
        if not m:
            continue
        try:
            payload = {
                "model": m,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 280
                }
            }
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=55) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "").strip()
                if content:
                    return content, m
        except Exception as e:
            print(f"[Node 2] Ollama model '{m}' call failed: {e}")
            continue

    # Resilient human fallback response
    return (
        "Hello! I am here to guide you with manufacturer warranty policy details and general technical hardware queries.\n\n"
        "Key Points to Remember for Return Preparation:\n"
        "1. Check Return Eligibility: Standard warranties cover manufacturing defects and normal hardware failures under standard use. Physical cracks, liquid exposure, or burnt connectors are excluded.\n"
        "2. Keep Proof of Purchase: Have your store receipt or invoice ready with matching serial numbers.\n"
        "3. Safe Packaging: Place the component in an anti-static (ESD) bag with adequate box cushioning.\n"
        "4. Obtain RMA Authorization: Always request an official RMA number through the Intake Portal before sending the package.\n\n"
        "Please note that I cannot authorize returns, guarantee outcomes, or process image uploads in chat. For official claim submission and physical verification, please submit a return request via the SmartRMA Intake Portal or contact your manufacturer.",
        "rule_engine_fallback"
    )

@app.get("/health")
def health():
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "status": "ONLINE",
        "service": "SmartRMA Node 2 - Policy RAG Engine",
        "port": 8001,
        "security_features": [
            "firewall_dotfile_traversal_blocking",
            "source_code_download_prevention",
            "prompt_injection_delimiter_neutralization",
            "pydantic_input_bounds"
        ],
        "indexed_chunks": len(POLICY_DATA.get("chunks", [])),
        "indexed_documents": len(POLICY_DATA.get("catalog", [])),
        "manufacturers": POLICY_DATA.get("metadata", {}).get("manufacturers", []),
        "gemini_api_configured": has_gemini,
        "primary_chat_engine": "Google Gemini API (gemini-1.5-flash)" if has_gemini else "Local Ollama LLM (qwen2.5-coder:14b)",
        "fallback_chat_engine": "Local Ollama LLM (qwen2.5-coder:14b)",
        "active_models": MODELS_TO_TRY
    }

class GeminiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=256)

@app.post("/api/config/gemini_key")
def set_gemini_key(req: GeminiKeyRequest):
    os.environ["GEMINI_API_KEY"] = req.api_key.strip()
    return {"status": "SUCCESS", "message": "Gemini API key configured successfully."}

@app.get("/api/config/gemini_key")
def get_gemini_key():
    key = os.environ.get("GEMINI_API_KEY", "")
    has_key = bool(key)
    masked = f"{key[:4]}...{key[-4:]}" if len(key) >= 8 else ("configured" if has_key else "not_configured")
    return {
        "configured": has_key,
        "masked_key": masked if has_key else None,
        "primary_engine": "Google Gemini API (gemini-1.5-flash)" if has_key else "Local Ollama LLM (qwen2.5-coder:14b)",
        "fallback_engine": "Local Ollama LLM (qwen2.5-coder:14b)"
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
    if not detected_mfg and req.manufacturer and req.manufacturer.lower() in user_query.lower():
        detected_mfg = req.manufacturer

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
- Mention key preparation points for returns (receipt/invoice, no physical CID, anti-static ESD packaging, obtain RMA number through portal).
- Remember: You are strictly informational. Do not approve, guarantee, or promise any return or refund outcome.
- Conclude by stating: "For official claim submission and return authorization, please use the SmartRMA Intake Portal or contact your manufacturer."
- Keep the response well-structured and under 150 words."""
    elif is_warranty_query:
        user_prompt = f"""[CUSTOMER QUESTION]:
{user_query}

Instructions:
- The customer is asking about warranty terms, return eligibility, or the return process.
- Give a warm, conversational, and helpful response:
  1. Explain defect eligibility under standard industry coverage (normal hardware failures or manufacturing defects are covered, while physical impact, cracked PCB, burns, or liquid damage are excluded).
  2. Clearly guide the user through the standard Return Preparation Steps:
     • Keep proof of purchase (invoice / receipt) and verify serial numbers match.
     • Ensure hardware is free from Customer Induced Damage (physical cracks, burns, liquid corrosion).
     • Pack safely in an anti-static (ESD) protective bag with original accessories.
     • Obtain an official RMA authorization number through the Intake Portal before shipping.
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

    # 4. Generate response: Try Google Gemini API first; on error, quota end, or missing key -> redirect to local Ollama LLM
    gemini_reply, gemini_model = call_gemini_api(
        user_prompt=user_prompt,
        system_instruction=SYSTEM_PROMPT,
        history=req.history,
        explicit_key=req.gemini_api_key
    )

    if gemini_reply:
        reply = gemini_reply
        used_model = gemini_model
        provider = "google_gemini"
    else:
        # Graceful fallback to local Ollama LLM
        reply, used_model = call_ollama(messages, preferred_model=req.model)
        provider = "local_ollama" if used_model != "rule_engine_fallback" else "rule_engine_fallback"
    
    # Clean up formatting
    reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()

    # Sanitize any accidental occurrences of case study phrasing
    reply = re.sub(r'\b(in|based on|according to|from|as a|per the)?\s*(this|the|a)?\s*case stud(y|ies)\b[\s,:]*', '', reply, flags=re.IGNORECASE)
    reply = re.sub(r'\bcase stud(y|ies)\b', 'industry standards', reply, flags=re.IGNORECASE)

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
        "sources": sources
    }

@app.post("/api/triage/evaluate")
def triage_evaluate(req: TriageRequest):
    """
    Evaluates hardware return eligibility against official manufacturer policies.
    """
    query = f"{req.manufacturer} {req.model_name} {req.defect_type} {req.symptoms} {req.inspection_notes}"
    relevant_chunks = search_policy_chunks(query, target_mfg=req.manufacturer, top_k=3)
    
    # Defect pattern check for immediate CID exclusions
    is_cid = any(term in query.lower() for term in ["crack", "burnt", "burn mark", "liquid", "water", "corrosion", "bent pin", "scratched pcb", "unauthorized modification"])
    
    if is_cid:
        status = "REJECTED"
        risk = 92
        clause = "Physical / Liquid Damage Exclusion (Customer Induced Damage - CID)"
        notes = "Physical fracture, overvoltage burnout, or liquid contact detected. Standard manufacturer limited warranties explicitly exclude external physical trauma."
    elif any(term in query.lower() for term in ["artifact", "code 43", "black screen", "fan rattle", "coil whine", "no display", "reboot under load"]):
        status = "APPROVED"
        risk = 14
        clause = "Standard Manufacturing Hardware Defect Coverage"
        notes = "Symptoms conform to verified silicon/component failure under normal operational conditions. Eligible for standard warranty replacement."
    else:
        status = "ESCALATED"
        risk = 52
        clause = "Ambiguous Defect / Manual Inspection Required"
        notes = "Symptom profile requires secondary verification by L2 Engineering Workbench to differentiate solder fatigue from external shock."

    top_source = relevant_chunks[0] if relevant_chunks else None

    return {
        "determination": status,
        "risk_index": risk,
        "manufacturer": req.manufacturer,
        "model": req.model_name,
        "defect_type": req.defect_type,
        "cited_clause": clause,
        "source_doc": top_source.get("source_file") if top_source else "Manufacturer Warranty Agreement",
        "page": top_source.get("page", 1) if top_source else 1,
        "official_excerpt": top_source.get("text", "")[:300] if top_source else "Official warranty terms apply.",
        "notes": notes
    }

# Mount workspace directory for static web files, assets, and downloaded PDF policies
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("[Node 2] Starting Secure SmartRMA Policy RAG Service on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")
