import pandas as pd
import numpy as np

def calculate_rolling_consistency(nav_series: pd.Series, window_years: int = 3) -> float:
    """
    1. Compute rolling N-year returns.
    2. Measure consistency as the proportion of periods with positive returns.
    """
    if nav_series.empty or len(nav_series) < 2:
        return None

    # Number of days in 3 years roughly (business days vary, using calendar days approximation)
    window_size = window_years * 365
    
    # We'll use shift to get the NAV from 3 years ago for each day
    # This requires daily frequency or reindexing
    # First, ensure daily frequency to make shifting reliable
    daily_nav = nav_series.resample('D').ffill()
    
    if len(daily_nav) <= window_size:
        return None
        
    # NAV_t / NAV_{t-window} - 1
    # Mask zeros to avoid division by zero warning
    shifted_nav = daily_nav.shift(window_size).replace(0, np.nan)
    rolling_returns = (daily_nav / shifted_nav) - 1
    rolling_returns = rolling_returns.dropna()
    
    if rolling_returns.empty:
        return None
        
    positive_periods = (rolling_returns > 0).sum()
    total_periods = len(rolling_returns)
    
    return float(positive_periods / total_periods)

def compute_stability_metrics(nav_df: pd.DataFrame) -> dict:
    nav_series = nav_df['nav']
    return {
        "rolling_3y_consistency": calculate_rolling_consistency(nav_series, 3)
    }
