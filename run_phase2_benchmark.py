import os
import subprocess
import time

import tiktoken


def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def get_directory_tokens(path: str) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath) as f:
                        total += count_tokens(f.read())
                except Exception:
                    pass
    return total

def main():
    print("===============================================")
    print("ContextMesh Phase 2: Massive Scale Benchmark")
    print("Target Repository: psf/requests")
    print("===============================================\n")
    
    requests_dir = "benchmarks/requests"
    if not os.path.exists(requests_dir):
        print("Error: requests repo not found in benchmarks/")
        return

    # 1. Count Raw Tokens
    print("Counting raw source tokens...")
    raw_tokens = get_directory_tokens(requests_dir)
    print(f"Total raw Python tokens in requests: {raw_tokens:,}\n")
    
    # 2. Benchmark Indexing
    print("Running ContextMesh export-context...")
    start_time = time.time()
    result = subprocess.run(
        ["python3", "-m", "contextmesh.cli.main", "export-context", "--path", requests_dir, "--task", "benchmark"], 
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."}
    )
    duration = time.time() - start_time
    
    mesh_tokens = count_tokens(result.stdout)
    print(f"Indexing completed in {duration:.2f} seconds.")
    print(f"ContextMesh Packet Tokens: {mesh_tokens:,}")
    savings = ((raw_tokens - mesh_tokens) / raw_tokens) * 100
    print(f"Token Reduction: {savings:.1f}%\n")
    
    # 3. Test Expand Symbol
    print("Testing Expand Symbol Tool...")
    # We'll expand 'request' function from src/requests/api.py
    expand_result = subprocess.run(
        ["python3", "-m", "contextmesh.cli.main", "expand", f"{requests_dir}/src/requests/api.py", "request"],
        capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."}
    )
    print("Output of 'contextmesh expand benchmarks/requests/src/requests/api.py request':")
    print("-" * 40)
    print(expand_result.stdout.strip())
    print("-" * 40)

if __name__ == "__main__":
    main()
