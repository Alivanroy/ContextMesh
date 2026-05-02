import subprocess
import requests
import time
import json
import sys

MODEL = "llama3:latest"
OLLAMA_URL = "http://localhost:11434/api/generate"

def query_ollama(prompt: str) -> tuple[str, float]:
    start_time = time.time()
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()
        result = response.json().get("response", "")
    except Exception as e:
        result = f"Error querying Ollama: {e}"
    duration = time.time() - start_time
    return result, duration

def main():
    print("===============================================")
    print("ContextMesh Ollama Real-Life Benchmark")
    print("===============================================\n")

    # 1. Gather Raw Context (Baseline)
    with open("demo/src/auth/reset.py", "r") as f:
        raw_source = f.read()
        
    raw_test_run = subprocess.run(
        ["pytest", "demo/tests/auth/test_reset.py"], 
        capture_output=True, text=True
    )
    raw_pytest = raw_test_run.stdout + raw_test_run.stderr

    raw_prompt = f"""You are an expert python debugger. 
Below is the raw source code for a module and the raw pytest output indicating a failure.
Identify the exact line causing the bug and provide the single line of code to fix it. Keep your answer brief.

--- RAW SOURCE CODE ---
{raw_source}

--- RAW PYTEST OUTPUT ---
{raw_pytest}

Bug Fix:"""

    # 2. Gather ContextMesh Context
    from contextmesh.packets.generator import generate_symbol_packets
    from contextmesh.wrappers.test_runner import distill_command_output
    
    symbol_packets = generate_symbol_packets("demo/src/auth/reset.py")
    mesh_source = "\n".join(sp.model_dump_json() for sp in symbol_packets)
    
    packet = distill_command_output(["pytest", "demo/tests/auth/test_reset.py"], raw_test_run.returncode, raw_pytest)
    mesh_pytest = packet.model_dump_json()

    mesh_prompt = f"""You are an expert python debugger. 
Below is the ContextMesh Symbol data for a module and the ContextMesh TestFailure packet indicating a failure.
Identify the exact line causing the bug and provide the single line of code to fix it. Keep your answer brief.

--- CONTEXTMESH SYMBOLS ---
{mesh_source}

--- CONTEXTMESH TEST FAILURE ---
{mesh_pytest}

Bug Fix:"""

    print(f"Executing Baseline Evaluation on {MODEL}...")
    raw_response, raw_time = query_ollama(raw_prompt)
    print(f"\n[BASELINE RESULTS] (Took {raw_time:.2f} seconds)")
    print(raw_response.strip())
    print("\n" + "-"*50 + "\n")

    print(f"Executing ContextMesh Evaluation on {MODEL}...")
    mesh_response, mesh_time = query_ollama(mesh_prompt)
    print(f"\n[CONTEXTMESH RESULTS] (Took {mesh_time:.2f} seconds)")
    print(mesh_response.strip())
    print("\n" + "-"*50 + "\n")

    print("--- SUMMARY ---")
    speedup = ((raw_time - mesh_time) / raw_time) * 100 if raw_time > 0 else 0
    print(f"Baseline Time:    {raw_time:.2f}s")
    print(f"ContextMesh Time: {mesh_time:.2f}s")
    if speedup > 0:
        print(f"ContextMesh was {speedup:.1f}% faster at inference!")
    else:
        print(f"ContextMesh was {-speedup:.1f}% slower at inference.")

if __name__ == "__main__":
    main()
