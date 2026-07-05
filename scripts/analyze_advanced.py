import json
import re
import math
from collections import Counter, defaultdict

# Re-use our custom tokenizer for consistency
def clean_korean_text(text):
    return re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text)

def custom_tokenize(text):
    text = clean_korean_text(text)
    words = text.split()
    tokens = []
    
    josa_pattern = re.compile(
        r'(은|는|이|가|을|를|의|에|에서|로|으로|와|과|도|만|고|며|라고|하고|했다|한다|입니다|이다|였다|이며|에도|에서만|보다|까지|처럼|조차|마저|요|으로의|로서|로써|한테|에게|께)$'
    )
    
    for word in words:
        if re.match(r'^[가-힣]+$', word):
            stemmed = josa_pattern.sub('', word)
            stemmed = josa_pattern.sub('', stemmed) # Double strip for compound postpositions
            if len(stemmed) >= 2:
                tokens.append(stemmed)
        else:
            w_clean = re.sub(r'[^a-zA-Z0-9]', '', word).lower()
            if len(w_clean) >= 2:
                tokens.append(w_clean)
    return tokens

# 1. MSTTR (Mean Segmental Type-Token Ratio) for Lexical Richness
# Measures vocabulary diversity controlling for text length bias.
def calculate_msttr(tokens, segment_size=50):
    if len(tokens) < segment_size:
        # Fallback to simple TTR if shorter than segment
        return len(set(tokens)) / len(tokens) if tokens else 0
        
    num_segments = len(tokens) // segment_size
    ttr_sum = 0
    for i in range(num_segments):
        segment = tokens[i*segment_size : (i+1)*segment_size]
        ttr_sum += len(set(segment)) / segment_size
        
    return round(ttr_sum / num_segments, 4)

# 2. Subjectivity and Sensationalism Lexicon (자극성/감정적 단어 리스트)
SENSATIONAL_WORDS = {
    # Sensational / Emotional nouns and verbs
    '충격', '발칵', '분노', '폭발', '선동', '논란', '참사', '위기', '거짓말', '왜곡', '조작', '폭로', 
    '의혹', '음모', '유출', '비난', '저격', '보복', '참담', '허위', '괴담', '날조', '은폐', '심각',
    '격분', '강타', '경악', '막말', '밀실', '야합', '폭거', '치욕', '망언', '독재', '직격', '압박'
}

def calculate_sensationalism_score(tokens):
    if not tokens:
        return 0
    match_count = sum(1 for token in tokens if token in SENSATIONAL_WORDS)
    # Return count per 1000 tokens to normalize
    return round((match_count / len(tokens)) * 1000, 3)

# 3. Semantic Network Analysis (Word Co-occurrence within a Window)
# Calculates co-occurrence of terms inside a sliding window of size N
def extract_cooccurrences(articles_tokens, window_size=5):
    cooccur = defaultdict(int)
    for tokens in articles_tokens:
        for i in range(len(tokens)):
            # Define window boundary
            start = max(0, i - window_size)
            end = min(len(tokens), i + window_size + 1)
            target = tokens[i]
            
            for j in range(start, end):
                if i != j:
                    neighbor = tokens[j]
                    # Sort to make graph undirected
                    pair = tuple(sorted([target, neighbor]))
                    cooccur[pair] += 1
                    
    # Divide by 2 because undirected pairs are added twice in sliding window scan
    for pair in cooccur:
        cooccur[pair] = cooccur[pair] // 2
        
    sorted_pairs = sorted(cooccur.items(), key=lambda x: x[1], reverse=True)
    return sorted_pairs

def main():
    try:
        with open("real_news.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)
        with open("fake_news.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
    except FileNotFoundError as e:
        print(f"Data files not found: {e}")
        return

    print("Analyzing linguistics at a professional level...")

    real_articles_tokens = []
    fake_articles_tokens = []
    
    real_msttrs = []
    fake_msttrs = []
    
    real_sensational_scores = []
    fake_sensational_scores = []

    # Process Real News
    for art in real_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        real_articles_tokens.append(tokens)
        real_msttrs.append(calculate_msttr(tokens, segment_size=50))
        real_sensational_scores.append(calculate_sensationalism_score(tokens))

    # Process Fake News (Fact-check reports containing the claims)
    for art in fake_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        fake_articles_tokens.append(tokens)
        fake_msttrs.append(calculate_msttr(tokens, segment_size=50))
        fake_sensational_scores.append(calculate_sensationalism_score(tokens))

    # Compute Averages
    avg_real_msttr = sum(real_msttrs) / len(real_msttrs) if real_msttrs else 0
    avg_fake_msttr = sum(fake_msttrs) / len(fake_msttrs) if fake_msttrs else 0
    
    avg_real_sensational = sum(real_sensational_scores) / len(real_sensational_scores) if real_sensational_scores else 0
    avg_fake_sensational = sum(fake_sensational_scores) / len(fake_sensational_scores) if fake_sensational_scores else 0

    # Co-occurrence analysis (Top 15 semantic edges)
    real_cooccur = extract_cooccurrences(real_articles_tokens, window_size=5)
    fake_cooccur = extract_cooccurrences(fake_articles_tokens, window_size=5)

    # Format output results
    advanced_results = {
        'lexical_diversity': {
            'real_msttr': round(avg_real_msttr, 4),
            'fake_msttr': round(avg_fake_msttr, 4),
            'interpretation': "Higher MSTTR means richer vocabulary per segment. Propaganda or sensational claims often reuse limited emotive words, resulting in lower diversity."
        },
        'sensationalism_index': {
            'real_score_per_1k': round(avg_real_sensational, 3),
            'fake_score_per_1k': round(avg_fake_sensational, 3),
            'interpretation': "Sensationalism score represents the density of highly emotional/conflict-inducing words per 1000 words."
        },
        'semantic_network': {
            'real_news_edges': [
                { 'node1': edge[0][0], 'node2': edge[0][1], 'weight': edge[1] }
                for edge in real_cooccur[:15]
            ],
            'fake_news_edges': [
                { 'node1': edge[0][0], 'node2': edge[0][1], 'weight': edge[1] }
                for edge in fake_cooccur[:15]
            ]
        }
    }

    # Save to JSON
    with open("advanced_analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(advanced_results, f, ensure_ascii=False, indent=4)

    print("\n=== ADVANCED LINGUISTIC ANALYSIS COMPLETE ===")
    print(f"Real News Lexical Richness (MSTTR): {avg_real_msttr:.4f}")
    print(f"Fake News Lexical Richness (MSTTR): {avg_fake_msttr:.4f}")
    print(f"Real News Sensationalism Score (per 1k words): {avg_real_sensational:.3f}")
    print(f"Fake News Sensationalism Score (per 1k words): {avg_fake_sensational:.3f}")
    print("Top Co-occurrences extracted.")

if __name__ == "__main__":
    # Prevent console encode crash
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    main()
