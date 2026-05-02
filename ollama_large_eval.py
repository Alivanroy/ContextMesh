import time

import requests
import tiktoken

from contextmesh.packets.generator import generate_symbol_packets

MODEL = "llama3:latest"
OLLAMA_URL = "http://localhost:11434/api/generate"

def count_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def query_ollama(prompt: str) -> tuple[str, float]:
    start_time = time.time()
    try:
        # Set a massive 40k context window to fit the data
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL, 
                "prompt": prompt, 
                "stream": False, 
                "options": {"num_ctx": 40000}
            }
        )
        response.raise_for_status()
        result = response.json().get("response", "")
    except Exception as e:
        result = f"Error querying Ollama: {e}"
    duration = time.time() - start_time
    return result, duration

def main():
    print("===============================================")
    print("ContextMesh Scale Benchmark vs Ollama (llama3)")
    print("===============================================\n")

    # We will pick a few core files from requests to make up ~15k raw tokens
    target_files = [
        "benchmarks/requests/src/requests/api.py",
        "benchmarks/requests/src/requests/sessions.py",
        "benchmarks/requests/src/requests/models.py",
        "benchmarks/requests/src/requests/adapters.py"
    ]
    
    raw_source = ""
    for tf in target_files:
        with open(tf) as f:
            raw_source += f"--- FILE: {tf} ---\n{f.read()}\n"
            
    raw_tokens = count_tokens(raw_source)
    
    mesh_source = ""
    for tf in target_files:
        packets = generate_symbol_packets(tf)
        mesh_source += "\n".join(p.model_dump_json() for p in packets) + "\n"
        
    mesh_tokens = count_tokens(mesh_source)
    
    print(f"Raw Payload Tokens: {raw_tokens}")
    print(f"ContextMesh Payload Tokens: {mesh_tokens}")
    print(f"Token Reduction: {((raw_tokens - mesh_tokens)/raw_tokens)*100:.1f}%\n")

    question = "Which file and class is responsible for sending HTTP requests and handling the connection pooling, and what is its main method for doing so?"
    print(f"Question for LLM: '{question}'\n")

    raw_prompt = f"""You are an expert system architect analyzing a large python library.
Analyze the following raw source code and answer the question.

--- SOURCE CODE ---
{raw_source}

--- QUESTION ---
{question}

Keep your answer under 3 sentences."""

    mesh_prompt = f"""You are an expert system architect analyzing a large python library.
Analyze the following ContextMesh architectural symbol packets and answer the question.

--- CONTEXTMESH PACKETS ---
{mesh_source}

--- QUESTION ---
{question}

Keep your answer under 3 sentences."""

    print("Executing ContextMesh Evaluation on Ollama...")
    mesh_response, mesh_time = query_ollama(mesh_prompt)
    print(f"[CONTEXTMESH RESULTS] (Took {mesh_time:.2f} seconds)")
    print(mesh_response.strip())
    print("\n" + "-"*50 + "\n")

    print("Executing Raw Baseline Evaluation on Ollama (This might take a long time or OOM)...")
    raw_response, raw_time = query_ollama(raw_prompt)
    print(f"[BASELINE RESULTS] (Took {raw_time:.2f} seconds)")
    print(raw_response.strip())
    print("\n" + "-"*50 + "\n")

if __name__ == "__main__":
    main()
