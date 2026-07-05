import json
import re
import math
import random
from collections import Counter, defaultdict

# Regex to clean Korean text and isolate core blocks
def clean_korean_text(text):
    # Keep only Korean, English, numbers, and basic punctuation
    return re.sub(r'[^가-힣a-zA-Z0-9\s!\?]', ' ', text)

# Custom Korean Tokenizer to strip common Josa (postpositions) and verb endings
# This allows extracting noun-like stems without heavy JVM-based morph analyzers.
def custom_tokenize(text):
    text = clean_korean_text(text)
    words = text.split()
    tokens = []
    
    # Common Korean postpositions and verb endings
    josa_pattern = re.compile(
        r'(은|는|이|가|을|를|의|에|에서|로|으로|와|과|도|만|고|며|라고|하고|했다|한다|입니다|이다|였다|이며|에도|에서만|보다|까지|처럼|조차|마저|요|으로의|로서|로써|한테|에게|께)$'
    )
    
    for word in words:
        if re.match(r'^[가-힣]+$', word):
            stemmed = josa_pattern.sub('', word)
            # Remove Josa again in case of compound postpositions (e.g. 에서는 -> 에서 -> '')
            stemmed = josa_pattern.sub('', stemmed)
            if len(stemmed) >= 2: # Keep words with length >= 2
                tokens.append(stemmed)
        else:
            # For alphanumeric or mixed words, lowercase and keep if length >= 2
            w_clean = re.sub(r'[^a-zA-Z0-9]', '', word).lower()
            if len(w_clean) >= 2:
                tokens.append(w_clean)
    return tokens

def analyze_statistics(articles):
    total_chars = 0
    total_words = 0
    total_digits = 0
    total_puncs = 0
    
    for art in articles:
        content = art['content']
        total_chars += len(content)
        total_words += len(content.split())
        total_digits += len(re.findall(r'\d', content))
        total_puncs += len(re.findall(r'[!\?]', content))
        
    n = len(articles) if len(articles) > 0 else 1
    return {
        'count': len(articles),
        'avg_chars': round(total_chars / n, 2),
        'avg_words': round(total_words / n, 2),
        'digit_ratio_pct': round((total_digits / (total_chars if total_chars > 0 else 1)) * 100, 3),
        'punc_ratio_pct': round((total_puncs / (total_chars if total_chars > 0 else 1)) * 100, 3)
    }

class NaiveBayesClassifier:
    def __init__(self, alpha=1.0):
        self.alpha = alpha
        self.class_priors = {}
        self.word_counts = defaultdict(lambda: defaultdict(int))
        self.class_word_totals = defaultdict(int)
        self.vocab = set()

    def train(self, X_train, y_train):
        num_docs = len(X_train)
        class_counts = Counter(y_train)
        
        # Calculate class prior probabilities P(c)
        for c, count in class_counts.items():
            self.class_priors[c] = count / num_docs
            
        # Count word frequencies in each class
        for tokens, c in zip(X_train, y_train):
            for token in tokens:
                self.word_counts[c][token] += 1
                self.class_word_totals[c] += 1
                self.vocab.add(token)

    def predict(self, tokens):
        best_class = None
        max_log_post = -float('inf')
        
        vocab_size = len(self.vocab)
        
        # Calculate P(c | d) proportional to P(c) * product(P(w | c))
        # Log space: log P(c) + sum(log P(w | c))
        for c in self.class_priors:
            log_post = math.log(self.class_priors[c])
            
            for token in tokens:
                # Only use tokens that were seen in training to avoid zero-probabilities 
                # (Laplace smoothing handles unseen words that are in the vocab)
                if token in self.vocab:
                    count_w_c = self.word_counts[c][token]
                    prob_w_c = (count_w_c + self.alpha) / (self.class_word_totals[c] + self.alpha * vocab_size)
                    log_post += math.log(prob_w_c)
            
            if log_post > max_log_post:
                max_log_post = log_post
                best_class = c
                
        return best_class

    def get_top_predictive_words(self, target_class=1, top_n=15):
        # Find words where P(w | target_class) / P(w | other_class) is highest
        # For class 1 (Fake News) vs class 0 (Real News)
        other_class = 1 - target_class
        vocab_size = len(self.vocab)
        word_ratios = []
        
        for token in self.vocab:
            p_target = (self.word_counts[target_class][token] + self.alpha) / (self.class_word_totals[target_class] + self.alpha * vocab_size)
            p_other = (self.word_counts[other_class][token] + self.alpha) / (self.class_word_totals[other_class] + self.alpha * vocab_size)
            ratio = p_target / p_other
            word_ratios.append((token, ratio, self.word_counts[target_class][token]))
            
        # Sort by ratio descending
        word_ratios.sort(key=lambda x: x[1], reverse=True)
        return word_ratios[:top_n]

def main():
    # Load scraped datasets
    try:
        with open("real_news.json", "r", encoding="utf-8") as f:
            real_data = json.load(f)
        with open("fake_news.json", "r", encoding="utf-8") as f:
            fake_data = json.load(f)
    except FileNotFoundError as e:
        print(f"Error loading JSON data files: {e}")
        return

    print("Data successfully loaded.")
    
    # 1. basic stats
    real_stats = analyze_statistics(real_data)
    fake_stats = analyze_statistics(fake_data)
    
    # 2. Tokenize and calculate word frequencies
    real_tokens_all = []
    fake_tokens_all = []
    
    dataset = []
    
    for art in real_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        real_tokens_all.extend(tokens)
        dataset.append((tokens, 0)) # Class 0: Real
        
    for art in fake_data:
        tokens = custom_tokenize(art['title'] + " " + art['content'])
        fake_tokens_all.extend(tokens)
        dataset.append((tokens, 1)) # Class 1: Fake
        
    real_counter = Counter(real_tokens_all)
    fake_counter = Counter(fake_tokens_all)
    
    top_real_words = real_counter.most_common(20)
    top_fake_words = fake_counter.most_common(20)
    
    # 3. Naive Bayes Classification Modeling
    # Shuffle and Split (7:3)
    random.seed(42) # Set seed for reproducibility
    random.shuffle(dataset)
    
    split_idx = int(len(dataset) * 0.7)
    train_set = dataset[:split_idx]
    test_set = dataset[split_idx:]
    
    X_train = [x[0] for x in train_set]
    y_train = [x[1] for x in train_set]
    X_test = [x[0] for x in test_set]
    y_test = [x[1] for x in test_set]
    
    clf = NaiveBayesClassifier(alpha=1.0)
    clf.train(X_train, y_train)
    
    # Evaluate
    predictions = [clf.predict(x) for x in X_test]
    
    # Confusion Matrix
    # 0 = Real, 1 = Fake
    tp, fp, tn, fn = 0, 0, 0, 0
    for true, pred in zip(y_test, predictions):
        if true == 1 and pred == 1:
            tp += 1
        elif true == 0 and pred == 1:
            fp += 1
        elif true == 0 and pred == 0:
            tn += 1
        elif true == 1 and pred == 0:
            fn += 1
            
    accuracy = (tp + tn) / len(y_test) if len(y_test) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Top predictive terms for Fake News
    fake_indicators = clf.get_top_predictive_words(target_class=1, top_n=15)
    real_indicators = clf.get_top_predictive_words(target_class=0, top_n=15)
    
    results = {
        'statistics': {
            'real': real_stats,
            'fake': fake_stats
        },
        'top_words': {
            'real': top_real_words,
            'fake': top_fake_words
        },
        'evaluation': {
            'test_size': len(y_test),
            'confusion_matrix': {'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn},
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4)
        },
        'indicators': {
            'fake_news': [(w[0], round(w[1], 2), w[2]) for w in fake_indicators],
            'real_news': [(w[0], round(w[1], 2), w[2]) for w in real_indicators]
        }
    }
    
    # Save analysis results
    with open("analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
        
    print("\n=== ANALYSIS COMPLETE ===")
    print(f"Total processed: Real: {real_stats['count']}, Fake: {fake_stats['count']}")
    print(f"Test Set Accuracy: {accuracy:.4f}")
    print(f"Test Set F1-Score: {f1:.4f}")
    print(f"Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")

if __name__ == "__main__":
    # Prevent stdout encoding errors on Windows terminal
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    main()
