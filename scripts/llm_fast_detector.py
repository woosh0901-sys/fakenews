import json
import requests
import math
import random
import time
import re
import traceback

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "qwen3.5:latest"

def llm_reconstruct_text(text):
    prompt = (
        "다음 뉴스 기사를 문법적으로 가장 자연스럽고 논리적 흐름이 매끄럽게 재작성(Paraphrase)해주세요. "
        "핵심 의미는 완전히 유지하되, 어색하거나 비논리적인 서술이 있다면 자연스럽게 고치십시오. "
        "설명이나 마크다운 블록, 다른 인사말은 일체 덧붙이지 말고, 오직 재작성된 한국어 텍스트 본문만 출력하세요.\n\n"
        f"기사:\n{text}"
    )
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9
        }
    }
    try:
        # Increase timeout to 180 seconds to allow slow local CPU/GPU generations
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=180)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            print(f"Ollama API Error Status: {resp.status_code}")
    except Exception as e:
        print(f"Ollama API Connection Error: {e}")
    return None

def get_ollama_embedding(text):
    payload = {
        "model": MODEL_NAME,
        "prompt": text
    }
    try:
        resp = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
    except Exception as e:
        print(f"Embedding Generation Error: {e}")
    return None

def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(a * a for a in v2))
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

def calculate_jaccard_distance(text1, text2):
    words1 = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text1).split())
    words2 = set(re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text2).split())
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return round(1.0 - (intersection / union) if union > 0 else 1.0, 4)

def main():
    try:
        with open("real_news.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)
        with open("fake_news.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}")
        return

    # Sample 5 Real vs 5 Fake
    sample_size = 5
    random.seed(42)
    sampled_real = random.sample(real_data, sample_size)
    sampled_fake = random.sample(fake_data, sample_size)

    results = []

    def analyze(art, is_fake):
        label = "Fake" if is_fake else "Real"
        title = art['title']
        # EXTREMELY IMPORTANT: Cap lead context to 150 chars to speed up local LLM processing 10x
        content = art['content'][:150] 
        orig = title + "\n" + content
        
        # Log basic debug text safely
        print(f"\nProcessing [{label}] Article...")
        
        start_time = time.time()
        recon = llm_reconstruct_text(orig)
        if not recon:
            print(f"-> Skip: Failed to generate paraphrase.")
            return None
            
        elapsed = time.time() - start_time
        print(f"-> Paraphrased in {elapsed:.2f}s.")
        
        v_orig = get_ollama_embedding(orig)
        v_recon = get_ollama_embedding(recon)
        
        if not v_orig or not v_recon:
            print("-> Skip: Failed to retrieve embeddings.")
            return None
            
        sim = cosine_similarity(v_orig, v_recon)
        sem_loss = round(1.0 - sim, 4)
        lex_loss = calculate_jaccard_distance(orig, recon)
        
        print(f"   Semantic Loss: {sem_loss:.4f} | Lexical Loss: {lex_loss:.4f}")
        
        return {
            'class': label,
            'title': title,
            'sem_loss': sem_loss,
            'lex_loss': lex_loss,
            'cos_sim': sim
        }

    for art in sampled_real:
        res = analyze(art, is_fake=False)
        if res: results.append(res)
        
    for art in sampled_fake:
        res = analyze(art, is_fake=True)
        if res: results.append(res)

    real_sems = [r['sem_loss'] for r in results if r['class'] == 'Real']
    fake_sems = [r['sem_loss'] for r in results if r['class'] == 'Fake']
    real_lexs = [r['lex_loss'] for r in results if r['class'] == 'Real']
    fake_lexs = [r['lex_loss'] for r in results if r['class'] == 'Fake']

    if not results:
        print("\n!!! ERROR: All articles skipped. Check Ollama server state. !!!")
        return

    avg_real_sem = sum(real_sems)/len(real_sems) if real_sems else 0
    avg_fake_sem = sum(fake_sems)/len(fake_sems) if fake_sems else 0
    avg_real_lex = sum(real_lexs)/len(real_lexs) if real_lexs else 0
    avg_fake_lex = sum(fake_lexs)/len(fake_lexs) if fake_lexs else 0

    output = {
        'avg_real_sem': avg_real_sem,
        'avg_fake_sem': avg_fake_sem,
        'avg_real_lex': avg_real_lex,
        'avg_fake_lex': avg_fake_lex,
        'details': results
    }
    
    with open("llm_fast_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
        
    print("\n=== FAST LLM ANALYSIS RESULTS ===")
    print(f"Processed: {len(results)}/10 articles.")
    print(f"Avg Semantic Loss - Real: {avg_real_sem:.4f} | Fake: {avg_fake_sem:.4f}")
    print(f"Avg Lexical Loss  - Real: {avg_real_lex:.4f} | Fake: {avg_fake_lex:.4f}")

if __name__ == "__main__":
    main()
