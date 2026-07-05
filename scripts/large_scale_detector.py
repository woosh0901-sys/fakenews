import csv
import re
import math
import random
import os
import json
import urllib.request
import ssl
from collections import Counter

# Bypass SSL verification to avoid the MSYS64 CA cert chain error
ssl._create_default_https_context = ssl._create_unverified_context

# Multi-repository Fallbacks to ensure raw download doesn't fail on 404
TRUE_URLS = [
    "https://raw.githubusercontent.com/jyojay/MONU_Project_4/master/Resources/True.csv",
    "https://raw.githubusercontent.com/timooo-thy/fake-real-news-classifier/master/True.csv",
    "https://raw.githubusercontent.com/SteffiPeTaffy/machineLearningNotebooks/master/Fake%20News%20Detection/True.csv"
]

FAKE_URLS = [
    "https://raw.githubusercontent.com/jyojay/MONU_Project_4/master/Resources/Fake.csv",
    "https://raw.githubusercontent.com/timooo-thy/fake-real-news-classifier/master/Fake.csv",
    "https://raw.githubusercontent.com/SteffiPeTaffy/machineLearningNotebooks/master/Fake%20News%20Detection/Fake.csv"
]

TRUE_FILE = "True.csv"
FAKE_FILE = "Fake.csv"

def download_file_with_fallbacks(urls, filepath):
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024*1024: # Must be larger than 1MB to be a valid file
        print(f"Using cached file: {filepath}")
        return

    print(f"File {filepath} not found or corrupted. Initiating download...")
    for url in urls:
        print(f"Trying download from: {url}")
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(filepath, 'wb') as out_file:
                    out_file.write(response.read())
            
            # Verify file size
            if os.path.getsize(filepath) > 1024*1024:
                print(f"Successfully downloaded and verified: {filepath}")
                return
            else:
                print(f"Downloaded file too small, probably invalid. Trying next...")
                if os.path.exists(filepath):
                    os.remove(filepath)
        except Exception as e:
            print(f"Download failed from {url}: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            continue
            
    raise RuntimeError(f"All download fallbacks failed for {filepath}")

# Denoise text by removing crawler artifacts (e.g. "WASHINGTON (Reuters) - ")
def clean_and_preprocess_english(text):
    # 1. Strip Reuters bylines (typically at the very beginning of True articles)
    text = re.sub(r'^.*?\(reuters\)\s*-\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^.*?(reuters)\s*', '', text, flags=re.IGNORECASE)
    
    # 2. Lowercase and clean special chars
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    # 3. Tokenize by whitespace and filter short tokens
    tokens = [w for w in text.split() if len(w) >= 2]
    return tokens

# Load CSV files using python's built-in csv module to prevent Pandas dependencies errors
def load_and_preprocess_csv(filepath, target_count=10000, is_real=True):
    articles = []
    print(f"Loading and preprocessing {filepath} (Target: {target_count} articles)...")
    
    # Set field limit safely for Windows (C long max = 2^31 - 1 = 2147483647)
    import sys
    csv.field_size_limit(2147483647)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            title = row.get('title', '')
            text = row.get('text', '')
            
            # Skip empty articles
            if not text.strip():
                continue
                
            tokens = clean_and_preprocess_english(title + " " + text)
            if tokens:
                articles.append(tokens)
                count += 1
                if count >= target_count:
                    break
                    
    print(f"Successfully loaded {len(articles)} articles from {filepath}")
    return articles

class TrigramLanguageModel:
    def __init__(self):
        self.unigrams = Counter()
        self.bigrams = Counter()
        self.trigrams = Counter()
        self.total_words = 0
        self.vocab = set()

    def train(self, corpus_tokens):
        for tokens in corpus_tokens:
            padded = ['<s>', '<s>'] + tokens + ['</s>']
            self.total_words += len(tokens)
            
            for word in tokens:
                self.unigrams[word] += 1
                self.vocab.add(word)
                
            for i in range(len(padded) - 1):
                self.bigrams[(padded[i], padded[i+1])] += 1
                
            for i in range(len(padded) - 2):
                self.trigrams[(padded[i], padded[i+1], padded[i+2])] += 1

    def get_probability(self, w1, w2, w3):
        tri_count = self.trigrams[(w1, w2, w3)]
        bi_count = self.bigrams[(w1, w2)]
        
        vocab_size = len(self.vocab)
        
        if bi_count > 0 and tri_count > 0:
            return 0.75 * (tri_count / bi_count) + 0.25 * self.get_bigram_prob(w2, w3)
        else:
            return self.get_bigram_prob(w2, w3)

    def get_bigram_prob(self, w1, w2):
        bi_count = self.bigrams[(w1, w2)]
        uni_count = self.unigrams[w1] if w1 in self.unigrams else 0
        
        vocab_size = len(self.vocab)
        
        if uni_count > 0:
            return 0.75 * (bi_count / uni_count) + 0.25 * ((self.unigrams[w2] + 1) / (self.total_words + vocab_size))
        else:
            uni_w2 = self.unigrams[w2] if w2 in self.unigrams else 0
            return (uni_w2 + 1) / (self.total_words + vocab_size)

    def calculate_sentence_loss(self, tokens):
        if not tokens:
            return 0.0
            
        padded = ['<s>', '<s>'] + tokens + ['</s>']
        total_log_prob = 0.0
        n_transitions = len(padded) - 2
        
        for i in range(n_transitions):
            w1, w2, w3 = padded[i], padded[i+1], padded[i+2]
            prob = self.get_probability(w1, w2, w3)
            prob = max(prob, 1e-12) # clip
            total_log_prob += -math.log(prob)
            
        return total_log_prob / n_transitions

def main():
    # 1. Download datasets
    print("Step 1: Downloading large-scale datasets with fallbacks...")
    download_file_with_fallbacks(TRUE_URLS, TRUE_FILE)
    download_file_with_fallbacks(FAKE_URLS, FAKE_FILE)
    
    # 2. Load 10,000 articles of each class
    print("\nStep 2: Parsing and cleaning 10,000 articles of each group...")
    real_corpus = load_and_preprocess_csv(TRUE_FILE, target_count=10000, is_real=True)
    fake_corpus = load_and_preprocess_csv(FAKE_FILE, target_count=10000, is_real=False)
    
    # 3. Train/Test split for Real News (Normal standard)
    random.seed(1337)
    random.shuffle(real_corpus)
    random.shuffle(fake_corpus)
    
    train_size = int(len(real_corpus) * 0.7)
    train_real = real_corpus[:train_size]
    test_real = real_corpus[train_size:]
    
    # Balance test set: 3,000 Real vs 3,000 Fake
    test_fake = fake_corpus[:len(test_real)]
    
    # 4. Train the Trigram Model
    print(f"\nStep 3: Training Trigram Language Model on {len(train_real)} Real Articles...")
    lm = TrigramLanguageModel()
    lm.train(train_real)
    print("Training complete.")

    # 5. Evaluate Reconstruction Loss (NLL)
    print("\nStep 4: Scoring reconstruction loss on test articles...")
    real_losses = []
    for idx, tokens in enumerate(test_real):
        if idx % 500 == 0:
            print(f"Scoring Real: {idx}/{len(test_real)}")
        loss = lm.calculate_sentence_loss(tokens)
        real_losses.append(loss)
        
    fake_losses = []
    for idx, tokens in enumerate(test_fake):
        if idx % 500 == 0:
            print(f"Scoring Fake: {idx}/{len(test_fake)}")
        loss = lm.calculate_sentence_loss(tokens)
        fake_losses.append(loss)

    avg_real_loss = sum(real_losses) / len(real_losses)
    avg_fake_loss = sum(fake_losses) / len(fake_losses)
    
    print("\n=== LARGE-SCALE RECONSTRUCTION LOSS RESULTS ===")
    print(f"Total Evaluated: {len(test_real)} Real, {len(test_fake)} Fake (Balanced Test)")
    print(f"Average Real Article Loss: {avg_real_loss:.4f}")
    print(f"Average Fake Article Loss: {avg_fake_loss:.4f}")
    print(f"Loss Ratio (Fake/Real): {avg_fake_loss / avg_real_loss:.2f}x")

    # 6. Evaluation metrics using threshold
    threshold = (avg_real_loss + avg_fake_loss) / 2
    
    tp, fp, tn, fn = 0, 0, 0, 0
    for loss in fake_losses:
        if loss >= threshold:
            tp += 1
        else:
            fn += 1
            
    for loss in real_losses:
        if loss < threshold:
            tn += 1
        else:
            fp += 1
            
    accuracy = (tp + tn) / (tp + fp + tn + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Decision Threshold: {threshold:.4f}")
    print(f"Detection Accuracy: {accuracy * 100:.2f}%")
    print(f"Detection F1-Score: {f1 * 100:.2f}%")
    print(f"Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

    # Save results
    results = {
        'total_trained': len(train_real),
        'total_tested': {
            'real': len(test_real),
            'fake': len(test_fake)
        },
        'avg_loss': {
            'real': round(avg_real_loss, 4),
            'fake': round(avg_fake_loss, 4)
        },
        'threshold': round(threshold, 4),
        'metrics': {
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4)
        },
        'confusion_matrix': {'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn}
    }
    
    with open("large_scale_analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
    print("\nLarge-Scale Analysis completed and results written.")

if __name__ == "__main__":
    main()
