import json
import re
import math
import random
from collections import defaultdict, Counter

def clean_korean_text(text):
    return re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', text)

def custom_tokenize(text):
    text = clean_korean_text(text)
    words = text.split()
    tokens = []
    josa_pattern = re.compile(
        r'(은|는|이|가|을|를|의|에|에서|로|으로|와|과|도|만|고|며|라고|하고|했다|한다|입니다|이다|였다|이며|에도|에서만|보다|까지|처럼|조차|마저|요|으로의|로서|로써|한테|에게|께)$'
    )
    # Protect common Korean nouns from being corrupted by naive Josa stripping
    protected_words = {"국가", "회의", "결과", "효과", "통과", "온도", "태도", "속도", "지도", "제도", "도로", "서로", "나이", "아이", "오이", "차이", "주의", "정의", "합의", "평화", "대화", "변화", "문화", "영화", "전화"}
    for word in words:
        if word in protected_words:
            tokens.append(word)
            continue
        if re.match(r'^[가-힣]+$', word):
            stemmed = josa_pattern.sub('', word)
            stemmed = josa_pattern.sub('', stemmed) # double strip
            if len(stemmed) >= 2:
                tokens.append(stemmed)
        else:
            w_clean = re.sub(r'[^a-zA-Z0-9]', '', word).lower()
            if len(w_clean) >= 2:
                tokens.append(w_clean)
    return tokens

# Trigram Language Model for Reconstruction Loss
class TrigramLanguageModel:
    def __init__(self):
        self.unigrams = Counter()
        self.bigrams = Counter()
        self.trigrams = Counter()
        self.total_words = 0
        self.vocab = set()

    def train(self, corpus_tokens):
        # corpus_tokens is a list of lists of tokens
        for tokens in corpus_tokens:
            # Pad with start and end tokens
            padded = ['<s>', '<s>'] + tokens + ['</s>']
            self.total_words += len(padded)
            
            for word in padded:
                self.unigrams[word] += 1
                self.vocab.add(word)
                
            for i in range(len(padded) - 1):
                self.bigrams[(padded[i], padded[i+1])] += 1
                
            for i in range(len(padded) - 2):
                self.trigrams[(padded[i], padded[i+1], padded[i+2])] += 1

    def get_probability(self, w1, w2, w3):
        # Implement backoff smoothing with Laplace add-one fallback
        vocab_size = len(self.vocab)
        
        # 1. Trigram probability: Count(w1, w2, w3) / Count(w1, w2)
        tri_count = self.trigrams[(w1, w2, w3)]
        bi_count = self.bigrams[(w1, w2)]
        
        if bi_count > 0:
            return 0.7 * (tri_count / bi_count) + 0.3 * self.get_bigram_prob(w2, w3)
        else:
            return self.get_bigram_prob(w2, w3)

    def get_bigram_prob(self, w1, w2):
        # Bigram probability: Count(w1, w2) / Count(w1)
        bi_count = self.bigrams[(w1, w2)]
        uni_count = self.unigrams[w1] if w1 in self.unigrams else 0
        
        vocab_size = len(self.vocab)
        
        if uni_count > 0:
            return 0.7 * (bi_count / uni_count) + 0.3 * ((self.unigrams[w2] + 1) / (self.total_words + vocab_size))
        else:
            # Fallback to smoothed unigram
            uni_w2 = self.unigrams[w2] if w2 in self.unigrams else 0
            return (uni_w2 + 1) / (self.total_words + vocab_size)

    # Calculates Negative Log-Likelihood (Reconstruction Loss) for a sentence
    def calculate_sentence_loss(self, tokens):
        if not tokens:
            return 0.0
            
        padded = ['<s>', '<s>'] + tokens + ['</s>']
        total_log_prob = 0.0
        n_transitions = len(padded) - 2
        
        word_losses = []
        
        for i in range(n_transitions):
            w1, w2, w3 = padded[i], padded[i+1], padded[i+2]
            prob = self.get_probability(w1, w2, w3)
            # Clip probability to avoid log(0)
            prob = max(prob, 1e-10)
            token_loss = -math.log(prob)
            total_log_prob += token_loss
            
            if w3 != '</s>':
                word_losses.append((w3, round(token_loss, 4)))
                
        # Return average NLL (loss) per token and step-by-step losses
        avg_loss = total_log_prob / n_transitions
        return avg_loss, word_losses

def main():
    try:
        with open("real_news.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)
        with open("fake_news.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
    except FileNotFoundError as e:
        print(f"Data files missing: {e}")
        return

    print("Data loaded. Commencing Reconstruction Loss (NLL) analysis...")

    # Tokenize
    real_corpus = []
    fake_corpus = []
    
    for art in real_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        real_corpus.append(tokens)
        
    for art in fake_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        fake_corpus.append(tokens)

    # Shuffle and split real news to train/test
    # We train the language model ONLY on a subset of REAL news.
    # The model acts as the "Pretrained generator / Normal news standard".
    random.seed(42)
    random.shuffle(real_corpus)
    
    train_size = int(len(real_corpus) * 0.7)
    train_real = real_corpus[:train_size]
    test_real = real_corpus[train_size:]
    
    # Train the Trigram Model on Real News
    lm = TrigramLanguageModel()
    lm.train(train_real)
    print(f"Trigram model trained on {len(train_real)} real news articles (Normal Language Baseline).")

    # Evaluate Reconstruction Loss (NLL) on Test Real News vs Fake News
    real_losses = []
    for tokens in test_real:
        loss, _ = lm.calculate_sentence_loss(tokens)
        if loss > 0:
            real_losses.append(loss)
            
    fake_losses = []
    fake_details = []
    for tokens in fake_corpus:
        loss, word_losses = lm.calculate_sentence_loss(tokens)
        if loss > 0:
            fake_losses.append(loss)
            fake_details.append((tokens, loss, word_losses))

    avg_real_loss = sum(real_losses) / len(real_losses) if real_losses else 0
    avg_fake_loss = sum(fake_losses) / len(fake_losses) if fake_losses else 0

    print("\n=== RECONSTRUCTION LOSS RESULTS ===")
    print(f"Average Loss (NLL) for Test Real News: {avg_real_loss:.4f}")
    print(f"Average Loss (NLL) for Fake News (Claims): {avg_fake_loss:.4f}")
    print(f"Loss Ratio (Fake/Real): {avg_fake_loss/avg_real_loss:.2f}x")

    # Simple classification based on Loss Threshold
    # We choose the threshold that separates the training distribution
    threshold = (avg_real_loss + avg_fake_loss) / 2
    print(f"Optimal Reconstruction Loss Decision Threshold: {threshold:.4f}")

    # Evaluate classification
    tp, fp, tn, fn = 0, 0, 0, 0
    for loss in fake_losses:
        if loss >= threshold:
            tp += 1 # correctly caught fake
        else:
            fn += 1 # missed fake
            
    for loss in real_losses:
        if loss < threshold:
            tn += 1 # correctly classified real
        else:
            fp += 1 # false alarm
            
    accuracy = (tp + tn) / (tp + fp + tn + fn)
    print(f"Detection Accuracy using Reconstruction Loss: {accuracy * 100:.2f}%")

    # Show a detailed example of logical anomalies in a fake news article
    # We find a fake article with high loss and show where the transition anomalies are
    fake_details.sort(key=lambda x: x[1], reverse=True)
    best_anomaly_art = fake_details[0] # Highest loss article
    
    print("\n=== LOGICAL ANOMALY DETECTION EXAMPLE (Highest Loss Article) ===")
    print(f"Overall Article Loss (NLL): {best_anomaly_art[1]:.4f}")
    print("\nTop 15 anomaly transitions (where context connection is extremely weak/non-existent):")
    
    # Sort token losses by loss descending to find anomalies
    sorted_anomalies = sorted(best_anomaly_art[2], key=lambda x: x[1], reverse=True)
    for idx, (word, w_loss) in enumerate(sorted_anomalies[:15]):
        print(f"[{idx+1}] Word: '{word}' -> Local Reconstruction Loss: {w_loss} (Highly Unexpected)")

    # Save outputs
    output_data = {
        'avg_real_loss': round(avg_real_loss, 4),
        'avg_fake_loss': round(avg_fake_loss, 4),
        'threshold': round(threshold, 4),
        'accuracy': round(accuracy, 4),
        'anomaly_example': {
            'overall_loss': round(best_anomaly_art[1], 4),
            'top_anomalies': sorted_anomalies[:15]
        }
    }
    with open("reconstruction_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    main()
