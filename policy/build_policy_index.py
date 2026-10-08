#!/usr/bin/env python3
"""
SmartRMA - Manufacturer Policy PDF & Document Ingestion Engine (Node 2)
Extracts, structures, and indexes warranty terms, return policies, and exclusions
from all official manufacturer PDF, Markdown, and HTML files.
"""

import os
import glob
import re
import json
from pypdf import PdfReader

POLICY_DIR = os.path.dirname(os.path.abspath(__file__))
if not POLICY_DIR.endswith("policy"):
    POLICY_DIR = os.path.join(POLICY_DIR, "policy")

OUTPUT_INDEX = os.path.join(POLICY_DIR, "policy_index.json")

def detect_manufacturer(filename, text_sample):
    fn = filename.lower()
    ts = text_sample.lower()
    
    if "gigabyte" in fn or "gigabyte" in ts:
        return "GIGABYTE"
    elif "apple" in fn or "mac warranty" in fn or "apple inc" in ts:
        return "Apple"
    elif "dell" in fn or "dell usa" in fn or "dell marketing" in ts:
        return "Dell"
    elif "acer" in fn or "acer official" in fn or "acer india" in ts or "acer global" in ts:
        return "Acer"
    elif "lenovo" in fn or "b4400" in fn or "lenovo limited" in ts:
        return "Lenovo"
    elif "hp.com" in fn or "hewlett-packard" in ts or "hp worldwide" in ts:
        return "HP"
    elif "intel" in fn or "intel xeon" in ts or "intel corporation" in ts:
        return "Intel"
    elif "nvidia" in fn or "geforce" in ts or "nvidia corporation" in ts:
        return "NVIDIA"
    elif "evga" in fn or "evga corp" in ts:
        return "EVGA"
    elif "asus" in fn or "br_graphic card" in fn or "asustek" in ts:
        return "ASUS"
    elif "amd" in fn or "advanced micro devices" in ts:
        return "AMD"
    return "Universal Hardware"

def categorize_clause(text):
    t = text.lower()
    if any(k in t for k in ["customer induced damage", "cid", "abuse", "misuse", "accident", "damage caused by", "void", "crack", "spill", "liquid", "corrosion", "burnt", "burn", "tamper", "unauthorized"]):
        return "exclusion_cid"
    elif any(k in t for k in ["return merchandise authorization", "rma", "how to obtain service", "returning the product", "return procedure", "shipping", "freight"]):
        return "return_rma"
    elif any(k in t for k in ["warranty period", "three (3) years", "3 years", "1 year", "one (1) year", "duration", "coverage period", "90 days"]):
        return "warranty_duration"
    elif any(k in t for k in ["proof of purchase", "original invoice", "receipt", "sales slip", "bill of sale"]):
        return "proof_of_purchase"
    elif any(k in t for k in ["replacement", "repair or replace", "refurbished", "repaired product", "exchange"]):
        return "remedy_replacement"
    return "general_terms"

def clean_text(t):
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def chunk_text(text, max_chars=900, overlap=150):
    chunks = []
    # split into sentences or paragraphs
    sentences = re.split(r'(?<=[.?!])\s+', text)
    curr = ""
    for s in sentences:
        if len(curr) + len(s) > max_chars and len(curr) > 200:
            chunks.append(curr.strip())
            curr = curr[-overlap:] + " " + s
        else:
            curr += " " + s
    if curr.strip() and len(curr.strip()) > 60:
        chunks.append(curr.strip())
    return chunks

def index_all():
    print(f"[*] Scanning policy folder: {POLICY_DIR}")
    chunks_indexed = []
    doc_catalog = []

    # 1. Process all PDFs
    pdf_files = glob.glob(os.path.join(POLICY_DIR, "*.pdf"))
    for pdf_path in sorted(pdf_files):
        fname = os.path.basename(pdf_path)
        try:
            reader = PdfReader(pdf_path)
            num_pages = len(reader.pages)
            full_text = ""
            file_chunks = 0
            
            # Detect manufacturer from filename + first 2 pages
            sample = ""
            for p in reader.pages[:2]:
                sample += (p.extract_text() or "") + " "
            mfg = detect_manufacturer(fname, sample)
            
            for page_idx, page in enumerate(reader.pages):
                raw = page.extract_text() or ""
                cleaned = clean_text(raw)
                if not cleaned or len(cleaned) < 50:
                    continue
                
                full_text += cleaned + "\n"
                page_chunks = chunk_text(cleaned)
                for ch in page_chunks:
                    cat = categorize_clause(ch)
                    chunks_indexed.append({
                        "id": f"{fname}:p{page_idx+1}:{file_chunks}",
                        "manufacturer": mfg,
                        "source_file": fname,
                        "page": page_idx + 1,
                        "total_pages": num_pages,
                        "category": cat,
                        "text": ch
                    })
                    file_chunks += 1
            
            doc_catalog.append({
                "filename": fname,
                "type": "PDF",
                "manufacturer": mfg,
                "pages": num_pages,
                "chunks": file_chunks,
                "bytes": os.path.getsize(pdf_path)
            })
            print(f" [+] [PDF] {fname} ({mfg}) -> {num_pages} pages, {file_chunks} chunks")
        except Exception as e:
            print(f" [!] Error parsing {fname}: {e}")

    # 2. Process Markdown files
    md_files = glob.glob(os.path.join(POLICY_DIR, "*.md"))
    for md_path in sorted(md_files):
        fname = os.path.basename(md_path)
        try:
            with open(md_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            mfg = detect_manufacturer(fname, content[:500])
            sections = re.split(r'\n#{1,4}\s+', content)
            file_chunks = 0
            for sec in sections:
                cleaned = clean_text(sec)
                if len(cleaned) < 60:
                    continue
                for ch in chunk_text(cleaned):
                    chunks_indexed.append({
                        "id": f"{fname}:sec:{file_chunks}",
                        "manufacturer": mfg,
                        "source_file": fname,
                        "page": 1,
                        "total_pages": 1,
                        "category": categorize_clause(ch),
                        "text": ch
                    })
                    file_chunks += 1
            doc_catalog.append({
                "filename": fname,
                "type": "Markdown",
                "manufacturer": mfg,
                "pages": 1,
                "chunks": file_chunks,
                "bytes": os.path.getsize(md_path)
            })
            print(f" [+] [MD]  {fname} ({mfg}) -> {file_chunks} chunks")
        except Exception as e:
            print(f" [!] Error parsing {fname}: {e}")

    # Build manufacturer summary
    mfg_counts = {}
    for c in chunks_indexed:
        m = c["manufacturer"]
        mfg_counts[m] = mfg_counts.get(m, 0) + 1

    payload = {
        "metadata": {
            "version": "2.4.0",
            "indexed_documents": len(doc_catalog),
            "total_chunks": len(chunks_indexed),
            "manufacturers": list(mfg_counts.keys()),
            "distribution": mfg_counts
        },
        "catalog": doc_catalog,
        "chunks": chunks_indexed
    }

    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"\n[OK] Policy indexing complete: {len(doc_catalog)} documents, {len(chunks_indexed)} policy chunks.")
    print(f"[OK] Saved to: {OUTPUT_INDEX}")

if __name__ == "__main__":
    index_all()
