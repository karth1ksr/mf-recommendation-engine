import time
from datetime import datetime
from mftool import Mftool
import pandas as pd

logger = logging.getLogger(__name__)

class NavIngestion:
    def __init__(self):
        self.mf = Mftool()

    def _with_retries(self, func, *args, max_retries=3, initial_wait=2, **kwargs):
        """Helper to retry API calls with exponential backoff"""
        for i in range(max_retries):
            try:
                # Politeness delay to avoid rate limiting
                time.sleep(0.5) 
                return func(*args, **kwargs)
            except Exception as e:
                wait_time = initial_wait * (2 ** i)
                logger.warning(
                    "API failure (attempt %s/%s). Retrying in %ss... | Error: %s",
                    i + 1, max_retries, wait_time, e
                )
                time.sleep(wait_time)
        return None

    def fetch_history(self, fund_id: int, lookback_years: int = 6) -> list[dict]:
        """
        Returns a list of {nav_date, nav_value} for the last N years
        """
        try:
            df = self._with_retries(self.mf.get_scheme_historical_nav, fund_id, as_Dataframe=True)
            if df is None or df.empty:
                return []

            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, format="%d-%m-%Y")

            # Calculate the cutoff date
            cutoff_date = datetime.now() - pd.DateOffset(years=lookback_years)
            df = df[df.index >= cutoff_date]

            records = []
            for date, row in df.iterrows():
                records.append({
                    "fund_id": fund_id,
                    "nav_date": date,
                    "nav": float(row["nav"])
                })
            return records

        except Exception as exc:
            logger.exception("Failed to fetch history | fund_id=%s", fund_id)
            return []

    def fetch_latest_nav(self, fund_id: int):
        """
        Returns (nav_date, nav_value) or None
        """
        try:
            # Fetch historical NAV as DataFrame
            df = self._with_retries(self.mf.get_scheme_historical_nav, fund_id, as_Dataframe=True)

            if df is None or df.empty:
                logger.warning("No NAV data returned | fund_id=%s", fund_id)
                return None

            # Ensure index is datetime
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index, format="%d-%m-%Y")
            
            # Get latest NAV date
            nav_date = df.index.max()
            nav_value = float(df.loc[nav_date, "nav"])  

            logger.info(
                "Fetched latest NAV | fund_id=%s | date%s | nav=%s",
                fund_id,
                nav_date.date(),
                nav_value
            )

            return nav_date, nav_value

        except Exception as exc:
            logger.exception(
                "NAV fetch failed | fund_id=%s | error=%s",
                fund_id, exc
            )
            return None
