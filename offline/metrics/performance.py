import pandas as pd
import numpy as np

def calculate_cagr(nav_series: pd.Series, years: int) -> float:
    """
    Calculates CAGR for a given number of years.
    Formula: (NAV_end / NAV_start) ^ (1 / years) - 1
    """
    if nav_series.empty or len(nav_series) < 2:
        return None
    
    end_date = nav_series.index.max()
    start_date = end_date - pd.DateOffset(years=years)
    
    # Get the NAV closest to the start date
    closest_start_idx = nav_series.index.get_indexer([start_date], method='nearest')[0]
    nav_start = nav_series.iloc[closest_start_idx]
    nav_end = nav_series.iloc[-1]
    
    # Ensure the actual time difference is close to the requested years
    actual_years = (nav_series.index[-1] - nav_series.index[closest_start_idx]).days / 365.25
    
    if actual_years < (years - 0.1): # Allow 0.1 year buffer
        return None
        
    # Safety check: avoid division by zero or invalid values for powers
    if pd.isna(nav_start) or pd.isna(nav_end) or nav_start <= 0 or nav_end <= 0:
        return None
        
    return float((nav_end / nav_start) ** (1 / years) - 1)

def compute_performance_metrics(nav_df: pd.DataFrame) -> dict:
    """
    Computes 3Y and 5Y CAGR
    """
    # Assuming nav_df has DatetimeIndex and 'nav' column
    nav_series = nav_df['nav']
    
    return {
        "cagr_3y": calculate_cagr(nav_series, 3),
        "cagr_5y": calculate_cagr(nav_series, 5)
    }
