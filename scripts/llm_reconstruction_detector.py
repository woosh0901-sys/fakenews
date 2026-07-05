import json
import requests
import math
import random
import time

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "qwen3.5:latest"

# 1. Ask Qwen 3.5 to reconstruct (paraphrase/denoise) the text
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
            "temperature": 0.1, # Low temperature for deterministic reconstruction
            "top_p": 0.9
        }
    }
    
    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            print(f"Ollama Generate API Error: {resp.status_code}")
            return None
    except Exception as e:
        print(f"Failed to call Ollama Generate: {e}")
        return None

# 2. Get text embeddings using Ollama's local embeddings API
def get_ollama_embedding(text):
    # Slice text if too long for embedding context
    truncated_text = text[:1500]
    payload = {
        "model": MODEL_NAME,
        "prompt": truncated_text
    }
    try:
        resp = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
        else:
            print(f"Ollama Embed API Error: {resp.status_code}")
            return None
    except Exception as e:
        print(f"Failed to call Ollama Embed: {e}")
        return None

# Calculate Cosine Similarity between two vectors
def cosine_similarity(v1, v2):
    if not v1 or not v2:
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = math.sqrt(sum(a * a for a in v1))
    norm_v2 = math.sqrt(sum(a * a for a in v2))
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

# Calculate Jaccard Distance (Lexical Overlap Loss)
def calculate_jaccard_distance(text1, text2):
    def get_words(text):
        return set(re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text).split())
        
    import re
    words1 = get_words(text1)
    words2 = get_words(text2)
    
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 1.0
    # Jaccard distance = 1 - Jaccard index
    return round(1.0 - (intersection / union), 4)

def main():
    print(f"Testing local Ollama connection using model: '{MODEL_NAME}'...")
    
    # Load Korean datasets we collected earlier
    try:
        with open("real_news.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)
        with open("fake_news.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
    except FileNotFoundError as e:
        print(f"Lacking Korean datasets. Please run crawler.py first. Error: {e}")
        return
        
    # Sample 15 articles of each class for local CPU/GPU speed constraint
    # (Paraphrasing 30 articles in total)
    sample_size = 15
    random.seed(777)
    sampled_real = random.sample(real_data, min(sample_size, len(real_data)))
    sampled_fake = random.sample(fake_data, min(sample_size, len(fake_data)))
    
    print(f"Loaded datasets. Sampled {len(sampled_real)} Real and {len(sampled_fake)} Fake articles for local LLM run.")

    results_log = []
    
    def process_article(art, is_fake):
        label = "Fake" if is_fake else "Real"
        title = art['title']
        content = art['content'][:1200] # Cap text length to be quick
        original_text = title + "\n" + content
        
        print(f"\nProcessing [{label}] - Title: '{title[:35]}...'")
        
        # 1. Reconstruct using LLM
        start_time = time.time()
        reconstructed_text = llm_reconstruct_text(original_text)
        elapsed = time.time() - start_time
        
        if not reconstructed_text:
            print("Failed to paraphrase article.")
            return None
            
        print(f"LLM Paraphrase complete in {elapsed:.2f}s.")
        
        # 2. Get Embeddings
        emb_orig = get_ollama_embedding(original_text)
        emb_recon = get_ollama_embedding(reconstructed_text)
        
        # 3. Compute Metrics
        cos_sim = cosine_similarity(emb_orig, emb_recon)
        semantic_loss = round(1.0 - cos_sim, 4)
        lexical_loss = calculate_jaccard_distance(original_text, reconstructed_text)
        
        print(f"   -> Semantic Loss (1-CosSim): {semantic_loss:.4f} (Similarity: {cos_sim:.4f})")
        print(f"   -> Lexical Loss (Jaccard Dist): {lexical_loss:.4f}")
        
        return {
            'title': title,
            'class': label,
            'semantic_loss': semantic_loss,
            'lexical_loss': lexical_loss,
            'cos_similarity': cos_sim,
            'reconstructed_preview': reconstructed_text[:120] + "..."
        }

    # Execute
    print("\n--- Running LLM Inference ---")
    processed_count = 0
    
    for art in sampled_real:
        res = process_article(art, is_fake=False)
        if res:
            results_log.append(res)
            processed_count += 1
            
    for art in sampled_fake:
        res = process_article(art, is_fake=True)
        if res:
            results_log.append(res)
            processed_count += 1
            
    # Calculate Averages
    real_semantic_losses = [r['semantic_loss'] for r in results_log if r['class'] == 'Real']
    fake_semantic_losses = [r['semantic_loss'] for r in results_log if r['class'] == 'Fake']
    
    real_lexical_losses = [r['lexical_loss'] for r in results_log if r['class'] == 'Real']
    fake_lexical_losses = [r['lexical_loss'] for r in results_log if r['class'] == 'Fake']
    
    avg_real_sem = sum(real_semantic_losses) / len(real_semantic_losses) if real_semantic_losses else 0
    avg_fake_sem = sum(fake_semantic_losses) / len(fake_semantic_losses) if fake_semantic_losses else 0
    
    avg_real_lex = sum(real_lexical_losses) / len(real_lexical_losses) if real_lexical_losses else 0
    avg_fake_lex = sum(fake_lexical_losses) / len(fake_lexical_losses) if fake_lexical_losses else 0

    print("\n=== HYBRID LLM RECONSTRUCTION LOSS RESULTS ===")
    print(f"Processed: Real={len(real_semantic_losses)}, Fake={len(fake_semantic_losses)}")
    print(f"Average Semantic Loss (Real): {avg_real_sem:.4f}")
    print(f"Average Semantic Loss (Fake): {avg_fake_sem:.4f}")
    print(f"Semantic Loss Ratio (Fake/Real): {avg_fake_sem / (avg_real_sem if avg_real_sem > 0 else 1):.2f}x")
    
    print(f"\nAverage Lexical Loss (Real): {avg_real_lex:.4f}")
    print(f"Average Lexical Loss (Fake): {avg_fake_lex:.4f}")
    print(f"Lexical Loss Ratio (Fake/Real): {avg_fake_lex / (avg_real_lex if avg_real_lex > 0 else 1):.2f}x")

    # Simple classification metric
    threshold = (avg_real_sem + avg_fake_sem) / 2
    tp, fp, tn, fn = 0, 0, 0, 0
    for r in results_log:
        pred_fake = r['semantic_loss'] >= threshold
        true_fake = r['class'] == 'Fake'
        
        if true_fake and pred_fake:
            tp += 1
        elif not true_fake and pred_fake:
            fp += 1
        elif not true_fake and not pred_fake:
            tn += 1
        elif true_fake and not pred_fake:
            fn += 1
            
    accuracy = (tp + tn) / processed_count if processed_count > 0 else 0
    print(f"\nDecision Threshold (Semantic): {threshold:.4f}")
    print(f"LLM Semantic Classification Accuracy: {accuracy * 100:.2f}%")

    # Save results
    output_payload = {
        'averages': {
            'semantic': {'real': round(avg_real_sem, 4), 'fake': round(avg_fake_sem, 4)},
            'lexical': {'real': round(avg_real_lex, 4), 'fake': round(avg_fake_lex, 4)}
        },
        'accuracy': round(accuracy, 4),
        'threshold': round(threshold, 4),
        'raw_log': results_log
    }
    
    with open("llm_reconstruction_results.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=4)
        
    print("\nLLM Reconstruction Analysis completed.")

if __name__ == "__main__":
    main()
