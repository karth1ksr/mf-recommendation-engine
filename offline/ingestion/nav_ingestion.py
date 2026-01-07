import logging
from datetime import datetime
from mftool import Mftool
import pandas as pd

logger = logging.getLogger(__name__)

class NavIngestion:
    def __init__(self):
        self.mf = Mftool()

    def fetch_latest_nav(self, fund_id: int):
        """
        Returns (nav_date, nav_value) or None
        """
        try:
            # Fetch historical NAV as DataFrame
            df = self.mf.get_scheme_historical_nav(fund_id, as_Dataframe=True)

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
