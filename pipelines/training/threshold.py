import numpy as np
from sklearn.metrics import precision_recall_curve

DEFAULT_THRESHOLD = 0.5


def choose_threshold(y_true: np.ndarray, scores: np.ndarray, min_precision: float = 0.9) -> float:
    """Lowest score threshold whose precision stays at or above `min_precision`, which gives the
    highest recall the business accepts. Falls back to 0.5 when no threshold reaches it."""
    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    reachable = np.flatnonzero(precision[:-1] >= min_precision)
    if reachable.size == 0:
        return DEFAULT_THRESHOLD
    best = reachable[np.argmax(recall[:-1][reachable])]
    return float(thresholds[best])
