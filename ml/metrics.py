"""
Guideline 14 metrics and conformal prediction utilities for AC optimization ML models.
"""
import numpy as np


def cv_rmse(y_true: np.ndarray, y_pred: np.ndarray, p: int = 1) -> float:
    """
    Coefficient of Variation of the Root Mean Square Error (CV-RMSE).
    ASHRAE Guideline 14 formula:
        CV(RMSE) = 100 * [ sqrt( sum((y - y_hat)^2) / (n - p) ) ] / y_mean
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    n = len(y_true)
    if n <= p:
        return 0.0
    mean_val = np.mean(y_true)
    if abs(mean_val) < 1e-6:
        return 0.0
    sse = np.sum((y_true - y_pred) ** 2)
    rmse = np.sqrt(sse / (n - p))
    return float(100.0 * (rmse / mean_val))


def nmbe(y_true: np.ndarray, y_pred: np.ndarray, p: int = 1) -> float:
    """
    Normalized Mean Bias Error (NMBE).
    ASHRAE Guideline 14 formula:
        NMBE = 100 * [ sum(y - y_hat) / ( (n - p) * y_mean ) ]
    Note: A positive NMBE indicates model under-prediction; negative indicates over-prediction.
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)
    n = len(y_true)
    if n <= p:
        return 0.0
    mean_val = np.mean(y_true)
    if abs(mean_val) < 1e-6:
        return 0.0
    error_sum = np.sum(y_true - y_pred)
    return float(100.0 * (error_sum / ((n - p) * mean_val)))


def split_conformal_bounds(
    y_cal: np.ndarray,
    y_cal_pred: np.ndarray,
    coverage: float = 0.80
) -> float:
    """
    Computes split-conformal non-conformity threshold q_hat on calibration set.
    For 80% coverage:
        alpha = 0.20
        q_val = (1 - alpha) * (1 + 1/n) quantile of absolute residuals
    """
    residuals = np.abs(np.asarray(y_cal, dtype=np.float64) - np.asarray(y_cal_pred, dtype=np.float64))
    n = len(residuals)
    if n == 0:
        return 0.1
    alpha = 1.0 - coverage
    k = int(np.ceil((1.0 - alpha) * (n + 1)))
    k = min(n, max(1, k))
    sorted_res = np.sort(residuals)
    return float(sorted_res[k - 1])


def evaluate_conformal_coverage(
    y_true: np.ndarray,
    y_lower: np.ndarray,
    y_upper: np.ndarray
) -> float:
    """Returns fraction of true points falling inside [y_lower, y_upper]."""
    y_true = np.asarray(y_true, dtype=np.float64)
    y_lower = np.asarray(y_lower, dtype=np.float64)
    y_upper = np.asarray(y_upper, dtype=np.float64)
    inside = (y_true >= y_lower) & (y_true <= y_upper)
    return float(np.mean(inside))
