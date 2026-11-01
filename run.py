#!/usr/bin/env python3
"""
SmartRMA - Unified Master Launcher & Orchestrator
Single-file command to boot the entire distributed SmartRMA ecosystem:
  - Ollama Local LLM Server & Model Verification (moondream:latest, qwen2.5-coder:14b)
  - Node 1: Ingest & Security Gateway + Decision Router (Port 8000)
  - Node 2: Warranty Policy RAG & Web Static Server (Port 8001)
  - Node 3: Vision Telemetry & Multimodal Vision LLM (Port 8002)
  - Automatic Browser Launch (Intake Portal, Technician Workbench, Architecture)
  - Clean Signal Handling (SIGINT / Ctrl+C) with Zero-Dangling-Process Termination
"""

import os
import sys
import time
import json
import signal
import socket
import shutil
import argparse
import webbrowser
import subprocess
import urllib.request
import urllib.error
from node.local_runtime import CHAT_MODELS, VISION_MODELS

# ANSI Terminal Styling
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_BLUE = "\033[94m"
C_DIM = "\033[2m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NODE_DIR = os.path.join(BASE_DIR, "node")

NODE1_SCRIPT = os.path.join(NODE_DIR, "node1_gateway.py")
NODE2_SCRIPT = os.path.join(NODE_DIR, "node2_policy_rag.py")
NODE3_SCRIPT = os.path.join(NODE_DIR, "node3_vision.py")
TEST_SCRIPT = os.path.join(BASE_DIR, "test_security_audit.py")

OLLAMA_URL = "http://localhost:11434"
NODE1_HEALTH = "http://127.0.0.1:8000/health"
NODE2_HEALTH = "http://127.0.0.1:8001/health"
NODE3_HEALTH = "http://127.0.0.1:8002/health"
FRONTEND_URL = "http://127.0.0.1:8001/index.html"

# Global Process Registry for Graceful Teardown
CHILD_PROCESSES = []

def print_banner():
    banner = f"""{C_CYAN}{C_BOLD}
  ╔═══════════════════════════════════════════════════════════════════════════╗
  ║                           S M A R T  R M A                                ║
  ║         Autonomous Distributed Hardware Triage & Telemetry Platform        ║
  ╚═══════════════════════════════════════════════════════════════════════════╝{C_RESET}
  {C_DIM}Root Workspace: {BASE_DIR}{C_RESET}
  {C_DIM}Microservices : {NODE_DIR}{C_RESET}
"""
    print(banner)

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def kill_process_on_port(port: int):
    """Finds and kills any stale process listening on the specified port."""
    try:
        out = subprocess.check_output(["lsof", f"-tiTCP:{port}", "-sTCP:LISTEN"]).decode().strip()
        pids = [p for p in out.split("\n") if p.strip()]
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
                time.sleep(0.3)
                print(f"  {C_YELLOW}[Port Reclaim]{C_RESET} Terminated stale PID {pid} on port {port}")
            except (ProcessLookupError, PermissionError):
                pass
    except subprocess.CalledProcessError:
        pass

def check_http_endpoint(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartRMA-Runner/1.0"})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def wait_for_endpoint(name: str, url: str, timeout: float = 20.0) -> bool:
    start_time = time.time()
    sys.stdout.write(f"  {C_BLUE}-->{C_RESET} Awaiting {name} ({url})... ")
    sys.stdout.flush()
    while time.time() - start_time < timeout:
        if check_http_endpoint(url):
            sys.stdout.write(f"{C_GREEN}ONLINE{C_RESET}\n")
            sys.stdout.flush()
            return True
        time.sleep(0.5)
    sys.stdout.write(f"{C_RED}TIMED OUT{C_RESET}\n")
    sys.stdout.flush()
    return False

def check_or_start_ollama() -> bool:
    """Verifies that the Ollama engine is running and required models are pulled."""
    print(f"\n{C_BOLD}[1/4] Checking Ollama Local LLM Engine...{C_RESET}")
    
    # 1. Check if Ollama daemon is already active
    if check_http_endpoint(f"{OLLAMA_URL}/api/tags", timeout=1.5):
        print(f"  {C_GREEN}✔{C_RESET} Ollama daemon active at {OLLAMA_URL}")
    else:
        ollama_bin = shutil.which("ollama")
        if not ollama_bin:
            print(f"  {C_RED}✖{C_RESET} 'ollama' CLI not found in PATH! LLM features will report unavailable until local Ollama is installed.")
            return False
        
        print(f"  {C_YELLOW}⚠{C_RESET} Ollama daemon not running. Launching 'ollama serve' in background...")
        proc = subprocess.Popen(
            [ollama_bin, "serve"],
            env={**os.environ, "OLLAMA_NO_CLOUD": "1"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None
        )
        CHILD_PROCESSES.append(("Ollama Daemon", proc))
        
        if not wait_for_endpoint("Ollama Daemon", f"{OLLAMA_URL}/api/tags", timeout=10.0):
            print(f"  {C_RED}✖{C_RESET} Failed to start Ollama server.")
            return False

    # 2. Check installed models
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode())
            installed = [m.get("name") for m in data.get("models", [])]
            
            print(f"  {C_CYAN}Installed Models ({len(installed)}):{C_RESET} {', '.join(installed[:5])}")
            
            # Check Vision LLM
            local_models = {m.get("name") for m in data.get("models", []) if not m.get("remote_host") and ":cloud" not in m.get("name", "")}
            has_vision = bool(local_models.intersection(VISION_MODELS))
            if has_vision:
                print(f"  {C_GREEN}✔{C_RESET} Vision candidates installed; inference is verified on first use")
            else:
                print(f"  {C_YELLOW}⚠{C_RESET} No supported local vision model installed. Recommended: qwen3-vl:8b")
                
            # Check Policy LLM
            has_policy = bool(local_models.intersection(CHAT_MODELS))
            if has_policy:
                print(f"  {C_GREEN}✔{C_RESET} Chat candidates installed; inference is verified on first use")
            else:
                print(f"  {C_YELLOW}⚠{C_RESET} Recommend running 'ollama pull qwen2.5:7b' for full policy reasoning.")
    except Exception as e:
        print(f"  {C_YELLOW}⚠{C_RESET} Could not inspect model list: {e}")

    return True

def is_smartrma_service(port):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            health = json.load(response)
            return health.get('port') == port and health.get('local_only') is True and health.get('service', '').startswith('SmartRMA ')
    except Exception:
        return False

def start_microservices():
    """Starts Node 1, Node 2, and Node 3 as supervised child subprocesses."""
    print(f"\n{C_BOLD}[2/4] Starting Microservice Cluster...{C_RESET}")

    services = [
        ("Node 2 (Policy RAG & Web Server)", NODE2_SCRIPT, 8001, NODE2_HEALTH),
        ("Node 3 (Vision LLM Telemetry)", NODE3_SCRIPT, 8002, NODE3_HEALTH),
        ("Node 1 (Gateway & Decision Router)", NODE1_SCRIPT, 8000, NODE1_HEALTH),
    ]

    for name, script_path, port, health_url in services:
        if not os.path.exists(script_path):
            print(f"  {C_RED}✖{C_RESET} Script missing: {script_path}")
            sys.exit(1)

        # Check if already running from another session
        if is_port_in_use(port):
            if is_smartrma_service(port):
                print(f"  {C_GREEN}✔{C_RESET} {name} is already alive on port {port}.")
                continue
            else:
                raise RuntimeError(f"Port {port} is occupied. Stop the conflicting application explicitly before launching SmartRMA.")

        # Launch node subprocess
        proc = subprocess.Popen(
            [sys.executable, "-m", "node." + os.path.basename(script_path)[:-3]],
            cwd=BASE_DIR,
            stdout=None,
            stderr=None,
            text=True,
            bufsize=1
        )
        CHILD_PROCESSES.append((name, proc))
        print(f"  {C_CYAN}▶{C_RESET} Launched {name} (PID: {proc.pid}) on port {port}")

    # Wait for all health checks to succeed
    print(f"\n{C_BOLD}[3/4] Verifying Cluster Readiness...{C_RESET}")
    n2_ok = wait_for_endpoint("Node 2 (:8001)", NODE2_HEALTH, timeout=15.0)
    n3_ok = wait_for_endpoint("Node 3 (:8002)", NODE3_HEALTH, timeout=15.0)
    n1_ok = wait_for_endpoint("Node 1 (:8000)", NODE1_HEALTH, timeout=15.0)

    if not (n1_ok and n2_ok and n3_ok):
        print(f"\n{C_RED}{C_BOLD}✖ Failed to start all microservices cleanly.{C_RESET}")
        sys.exit(1)

    print(f"\n{C_GREEN}{C_BOLD}✔ All microservices are ONLINE and operational!{C_RESET}")

def print_status_dashboard():
    dashboard = f"""
  {C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}
  {C_BOLD}{C_GREEN}                   SMARTRMA SYSTEM ONLINE & OPERATIONAL{C_RESET}
  {C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}

  {C_BOLD}🌐 FRONTEND WEB PORTALS:{C_RESET}
    • Customer Intake & Triage Portal  : {C_CYAN}{FRONTEND_URL}{C_RESET}
    • Technician Review Workbench      : {C_CYAN}http://127.0.0.1:8001/review.html{C_RESET}
    • System Architecture & Topology   : {C_CYAN}http://127.0.0.1:8001/architecture.html{C_RESET}

  {C_BOLD}⚡ BACKEND MICROSERVICES:{C_RESET}
    • Node 1 (Ingest & Decision Router): {C_MAGENTA}http://127.0.0.1:8000{C_RESET}  (EXIF, pHash, Ledger, SLA)
    • Node 2 (Policy RAG & Web Host)  : {C_MAGENTA}http://127.0.0.1:8001{C_RESET}  (Local policy index and Ollama chatbot)
    • Node 3 (Vision LLM Telemetry)    : {C_MAGENTA}http://127.0.0.1:8002{C_RESET}  (Installed local vision models; fallback may require review)
    • Local LLM Engine (Ollama)        : {C_MAGENTA}http://localhost:11434{C_RESET}  (Local Model Inference)

  {C_BOLD}🔒 SECURITY & LEDGER:{C_RESET}
    • Cryptographic Audit Ledger       : {C_DIM}{os.path.join(os.environ.get("SMARTRMA_DATA_DIR", BASE_DIR), "audit_ledger.json")}{C_RESET}
    • Perimeter Firewall Guard         : {C_GREEN}Active{C_RESET} (Blocks .py downloads, dotfiles)

  {C_BOLD}⌨️  CONTROLS:{C_RESET}
    • Press {C_YELLOW}{C_BOLD}Ctrl+C{C_RESET} at any time to gracefully shut down the entire system.
  {C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C_RESET}
"""
    print(dashboard)

def run_tests():
    """Runs the test_security_audit.py test suite."""
    print(f"\n{C_BOLD}[Audit Mode] Running comprehensive security & integration test suite...{C_RESET}\n")
    if not os.path.exists(TEST_SCRIPT):
        print(f"{C_RED}✖ Test script not found: {TEST_SCRIPT}{C_RESET}")
        return
    res = subprocess.run([sys.executable, TEST_SCRIPT], cwd=BASE_DIR)
    if res.returncode == 0:
        print(f"\n{C_GREEN}{C_BOLD}✔ All test suite assertions passed successfully.{C_RESET}")
    else:
        raise RuntimeError(f"Test suite failed (exit code {res.returncode}).")

def stop_all_services():
    """Kills all SmartRMA services on ports 8000, 8001, and 8002."""
    print(f"\n{C_YELLOW}{C_BOLD}Stopping all SmartRMA services on ports 8000, 8001, 8002...{C_RESET}")
    for p in [8000, 8001, 8002]:
        if is_smartrma_service(p):
            kill_process_on_port(p)
        elif is_port_in_use(p):
            print(f"  Port {p} belongs to an unrecognized service; left running.")
    print(f"{C_GREEN}✔ All ports cleared.{C_RESET}")

def shutdown(signum=None, frame=None):
    """Graceful teardown signal handler."""
    print(f"\n\n{C_YELLOW}{C_BOLD}Received shutdown signal. Stopping SmartRMA services...{C_RESET}")
    
    for name, proc in CHILD_PROCESSES:
        if proc.poll() is None:
            print(f"  {C_DIM}Terminating {name} (PID: {proc.pid})...{C_RESET}")
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    
    print(f"{C_GREEN}✔ All microservices stopped cleanly. Goodbye!{C_RESET}\n")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description="SmartRMA - Unified Master Launcher & Orchestrator")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    parser.add_argument("--test", "--audit", action="store_true", help="Run full security audit test suite after boot")
    parser.add_argument("--stop", action="store_true", help="Stop all SmartRMA services and exit")
    parser.add_argument("--status", action="store_true", help="Display cluster status without launching")
    args = parser.parse_args()

    # Register Clean Shutdown Signals
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print_banner()

    if args.stop:
        stop_all_services()
        return

    if args.status:
        print(f"{C_BOLD}Checking Cluster Status:{C_RESET}")
        print(f"  • Ollama (11434) : {'ONLINE' if check_http_endpoint(f'{OLLAMA_URL}/api/tags') else 'OFFLINE'}")
        print(f"  • Node 1 (8000)  : {'ONLINE' if check_http_endpoint(NODE1_HEALTH) else 'OFFLINE'}")
        print(f"  • Node 2 (8001)  : {'ONLINE' if check_http_endpoint(NODE2_HEALTH) else 'OFFLINE'}")
        print(f"  • Node 3 (8002)  : {'ONLINE' if check_http_endpoint(NODE3_HEALTH) else 'OFFLINE'}")
        return

    if args.test:
        run_tests()
        return

    # 1. Ollama verification & auto-start
    check_or_start_ollama()

    # 2. Start all microservices in node/
    start_microservices()

    # 3. Print system dashboard
    print_status_dashboard()

    # 4. Optional: run test suite
    if args.test:
        run_tests()

    # 5. Launch browser
    if not args.no_browser and not args.test:
        print(f"{C_BOLD}[4/4] Opening Web Application in Browser...{C_RESET}")
        try:
            webbrowser.open(FRONTEND_URL)
        except Exception:
            pass

    print(f"\n{C_CYAN}SmartRMA is running actively. Press Ctrl+C to terminate.{C_RESET}\n")

    # Keep master runner process alive and monitor child health
    try:
        while True:
            time.sleep(2.0)
            # Check child process health
            for item in list(CHILD_PROCESSES):
                name, proc = item
                ret = proc.poll()
                if ret is not None:
                    if name == "Ollama Daemon":
                        if check_http_endpoint(f"{OLLAMA_URL}/api/tags", timeout=2.5):
                            CHILD_PROCESSES.remove(item)
                            continue
                        print(f"\n{C_YELLOW}⚠ Ollama daemon process ended (code {ret}). Microservices remain active.{C_RESET}")
                        CHILD_PROCESSES.remove(item)
                        continue
                    print(f"\n{C_RED}✖ Process '{name}' terminated unexpectedly with code {ret}.{C_RESET}")
                    shutdown()
    except KeyboardInterrupt:
        shutdown()

if __name__ == "__main__":
    try:
        main()
    finally:
        for _, process in CHILD_PROCESSES:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
