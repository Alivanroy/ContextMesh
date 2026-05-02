import subprocess
import tiktoken
import json
import os
from contextmesh.packets.generator import generate_symbol_packets
from contextmesh.wrappers.test_runner import distill_command_output

def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def main():
    print("Running Real-Life Benchmark on ContextMesh...\n")
    
    # 1. Compare Source Code Tokens vs Symbol Packets
    target_file = "contextmesh/indexer/tree_sitter_parser.py"
    with open(target_file, 'r') as f:
        raw_source = f.read()
        
    raw_source_tokens = count_tokens(raw_source)
    
    symbol_packets = generate_symbol_packets(target_file)
    symbol_json = "\n".join(sp.model_dump_json() for sp in symbol_packets)
    optimized_source_tokens = count_tokens(symbol_json)
    
    print(f"--- File Indexing Optimization ({target_file}) ---")
    print(f"Raw Source Code Tokens: {raw_source_tokens}")
    print(f"Symbol Packets Tokens:  {optimized_source_tokens}")
    print(f"Token Reduction:        {raw_source_tokens - optimized_source_tokens} tokens ({((raw_source_tokens - optimized_source_tokens)/raw_source_tokens)*100:.1f}%)\n")

    # 2. Compare Pytest Traceback vs Distilled Packet
    # We will introduce a bug by modifying the file temporarily
    bug_source = raw_source.replace('"import_statement"', '"broken_import"')
    with open(target_file, 'w') as f:
        f.write(bug_source)
        
    try:
        # Run raw pytest
        print("Running raw pytest (will intentionally fail)...")
        result_raw = subprocess.run(
            ["pytest", "tests/test_indexer.py"], 
            capture_output=True, text=True
        )
        raw_pytest_output = result_raw.stdout + result_raw.stderr
        raw_pytest_tokens = count_tokens(raw_pytest_output)
        
        # Run ContextMesh wrapper (using test_runner distill_command_output directly for speed)
        packet = distill_command_output(["pytest", "tests/test_indexer.py"], result_raw.returncode, raw_pytest_output)
        optimized_pytest_tokens = count_tokens(packet.model_dump_json())
        
        print(f"--- Test Failure Output Optimization ---")
        print(f"Raw Pytest Output Tokens: {raw_pytest_tokens}")
        print(f"ContextMesh Packet Tokens: {optimized_pytest_tokens}")
        print(f"Token Reduction:           {raw_pytest_tokens - optimized_pytest_tokens} tokens ({((raw_pytest_tokens - optimized_pytest_tokens)/raw_pytest_tokens)*100:.1f}%)\n")

        print("\n--- Overall Token Savings Per Turn ---")
        total_raw = raw_source_tokens + raw_pytest_tokens
        total_opt = optimized_source_tokens + optimized_pytest_tokens
        print(f"Raw Workflow:        {total_raw} tokens")
        print(f"ContextMesh Workflow: {total_opt} tokens")
        print(f"TOTAL SAVINGS:       {total_raw - total_opt} tokens ({((total_raw - total_opt)/total_raw)*100:.1f}%)")
        print("===========================================")

    finally:
        # Restore original source
        with open(target_file, 'w') as f:
            f.write(raw_source)

if __name__ == "__main__":
    main()
