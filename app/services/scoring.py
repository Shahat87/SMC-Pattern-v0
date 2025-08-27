import random
from pathlib import Path
from typing import Literal, Optional

import numpy as np

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency at runtime
    Image = None  # type: ignore


def score_simple(pattern: dict) -> float:
    """Very simple placeholder scoring until features are implemented."""
    base = 0.6 if 'scoring' in pattern else 0.5
    jitter = random.random() * 0.3
    return min(0.99, base + jitter)


def _load_grayscale(path: Path, size: int = 256) -> Optional[np.ndarray]:
    if Image is None:
        return None
    img = Image.open(path).convert('L').resize((size, size))
    arr = np.asarray(img, dtype=np.float32)
    # normalize to zero-mean unit-variance
    arr = arr - arr.mean()
    std = arr.std() if arr.std() > 1e-6 else 1.0
    arr = arr / std
    return arr


def similarity_score(
    a_path: str,
    b_path: str,
    method: Literal['ncc', 'mse', 'cosine'] = 'ncc',
) -> Optional[float]:
    """Compute a simple similarity score between two images.

    - ncc: normalized cross-correlation in [0,1]
    - mse: mean squared error mapped to [0,1] via 1/(1+MSE)
    - cosine: cosine similarity of flattened vectors in [0,1]

    Returns None if Pillow is unavailable or images can't be processed.
    """
    try:
        a = _load_grayscale(Path(a_path))
        b = _load_grayscale(Path(b_path))
        if a is None or b is None:
            return None
        if a.shape != b.shape:
            # resize mismatch should not occur due to loader; safety check
            m = min(a.shape[0], b.shape[0])
            a = a[:m, :m]
            b = b[:m, :m]

        if method == 'ncc':
            # normalized cross-correlation equivalent to cosine on flattened
            v1 = a.ravel()
            v2 = b.ravel()
            num = float(np.dot(v1, v2))
            denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
            sim = num / denom if denom > 1e-6 else 0.0
            # map [-1,1] -> [0,1]
            return max(0.0, min(1.0, 0.5 * (sim + 1.0)))
        elif method == 'mse':
            mse = float(np.mean((a - b) ** 2))
            return 1.0 / (1.0 + mse)
        else:  # cosine
            v1 = a.ravel()
            v2 = b.ravel()
            num = float(np.dot(v1, v2))
            denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
            sim = num / denom if denom > 1e-6 else 0.0
            return max(0.0, min(1.0, 0.5 * (sim + 1.0)))
    except Exception:
        return None
