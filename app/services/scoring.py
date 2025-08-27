import random

def score_simple(pattern: dict) -> float:
    """Very simple placeholder scoring until features are implemented."""
    base = 0.6 if 'scoring' in pattern else 0.5
    jitter = random.random() * 0.3
    return min(0.99, base + jitter)