import pandas as pd
import numpy as np

def calculate_daily_returns(nav_series: pd.Series) -> pd.Series:
    """
    Computes daily returns from NAV values.
    """
    returns = nav_series.pct_change()
    # Remove NaNs, infinities, and ensure valid numeric data
    return returns[np.isfinite(returns)].dropna()

def calculate_volatility(daily_returns: pd.Series) -> float:
    """
    Computed as the standard deviation of daily returns.
    """
    if daily_returns.empty:
        return None
    return float(daily_returns.std())

def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """
    1. Compute running maximum of NAV values.
    2. Calculate drawdown as percentage drop from the running maximum.
    3. Maximum drawdown is the minimum value in the drawdown series.
    """
    if nav_series.empty:
        return None
    
    running_max = nav_series.cummax()
    # Mask zeros to avoid division by zero warning
    safe_max = running_max.replace(0, np.nan)
    drawdown = (nav_series - safe_max) / safe_max
    return float(drawdown.min())

def compute_risk_metrics(nav_df: pd.DataFrame) -> dict:
    nav_series = nav_df['nav']
    daily_returns = calculate_daily_returns(nav_series)
    
    return {
        "volatility": calculate_volatility(daily_returns),
        "max_drawdown": calculate_max_drawdown(nav_series)
    }
