"""
Statistical and Energy Modeling Utility Helpers (ASHRAE Guideline 14).
"""
from collections.abc import Sequence

import numpy as np


def cv_rmse(
    y_true: np.ndarray | Sequence[float],
    y_pred: np.ndarray | Sequence[float],
    p: int = 1
) -> float:
    """
    Coefficient of Variation of the Root Mean Square Error (CV-RMSE).
    Defined according to ASHRAE Guideline 14-2014, Clause 4.2.11.2:
      CV(RMSE) = 100 * [ sqrt( sum((y - y_hat)^2) / (n - p) ) ] / y_mean
    
    Parameters:
      y_true: Actual measured values
      y_pred: Predicted / baseline modeled values
      p: Number of parameters in model (default 1 for mean baseline, p degrees of freedom subtracted)
    
    Returns:
      CV(RMSE) percentage (e.g., 18.5 for 18.5%)
    """
    y = np.asarray(y_true, dtype=float)
    y_hat = np.asarray(y_pred, dtype=float)
    n = len(y)
    if n <= p:
        raise ValueError(f"Sample size n={n} must be greater than number of parameters p={p}")
    
    y_mean = np.mean(y)
    if abs(y_mean) < 1e-9:
        raise ValueError("Mean of actual values is zero; CV-RMSE is undefined")
    
    rmse = np.sqrt(np.sum((y - y_hat) ** 2) / (n - p))
    return float(100.0 * (rmse / y_mean))


def nmbe(
    y_true: np.ndarray | Sequence[float],
    y_pred: np.ndarray | Sequence[float],
    p: int = 1
) -> float:
    """
    Normalized Mean Bias Error (NMBE).
    Defined according to ASHRAE Guideline 14-2014, Clause 4.2.11.1:
      NMBE = 100 * [ sum(y - y_hat) / (n - p) ] / y_mean
    
    Sign Convention:
      Positive (+) indicates model under-prediction on average (y > y_hat).
      Negative (-) indicates model over-prediction on average (y < y_hat).
      Note: Some literature writes sum(y_hat - y); here we follow Guideline 14 standard.
    
    Returns:
      NMBE percentage (e.g. +3.2 for +3.2% under-prediction)
    """
    y = np.asarray(y_true, dtype=float)
    y_hat = np.asarray(y_pred, dtype=float)
    n = len(y)
    if n <= p:
        raise ValueError(f"Sample size n={n} must be greater than number of parameters p={p}")
    
    y_mean = np.mean(y)
    if abs(y_mean) < 1e-9:
        raise ValueError("Mean of actual values is zero; NMBE is undefined")
    
    bias_sum = np.sum(y - y_hat)
    return float(100.0 * (bias_sum / (n - p)) / y_mean)
