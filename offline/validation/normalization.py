import pandas as pd
import numpy as np

# Normalization module
def normalize_by_category(df: pd.DataFrame, metrics_to_normalize: list) -> pd.DataFrame:
    """
    Applies Z-score normalization to specified metrics, grouped by 'scheme_category'.
    z = (x - mean) / std
    """
    if df.empty:
        return df

    # We work on a copy to avoid modifying the original during processing
    result_df = df.copy()

    for metric in metrics_to_normalize:
        norm_col_name = f"norm_{metric}"
        
        # Group by category and apply z-score
        # transform allows us to broadcast the mean/std back to the original index
        result_df[norm_col_name] = df.groupby('scheme_category')[metric].transform(
            lambda x: (x - x.mean()) / x.std() if x.std() > 0 else 0
        )
        
        # Handle cases where std is 0 (all values same) or only one element in category
        result_df[norm_col_name] = result_df[norm_col_name].fillna(0)

    return result_df
