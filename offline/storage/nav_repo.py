import logging
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

class NavRepo:
    def __init__(self, db):
        # Time-series collections offer better compression and speed for financial data.
        # Note: They do not support unique indexes, so we handle duplicates in Python.
        if "nav_timeseries" not in db.list_collection_names():
            db.create_collection(
                "nav_timeseries",
                timeseries={
                    "timeField": "nav_date",
                    "metaField": "fund_id",
                    "granularity": "hours"
                }
            )
        
        self.collection = db.nav_timeseries
        
        # Regular index for performance (Unique is not supported here)
        self.collection.create_index([("fund_id", 1), ("nav_date", -1)])

    def insert_nav(self, fund_id: int, nav_date, nav_value: float) -> bool:
        # Manual duplicate check since Unique Index isn't available for Time Series
        exists = self.collection.find_one({
            "fund_id": fund_id,
            "nav_date": nav_date
        })
        
        if exists:
            logger.debug("Duplicate NAV skipped | fund_id=%s, date=%s", fund_id, nav_date.date())
            return False

        doc ={
            "fund_id": fund_id,
            "nav_date": nav_date,
            "nav": nav_value
        }

        try:
            self.collection.insert_one(doc)
            logger.info(
                "Inserted NAV | fund_id=%s | date=%s | nav=%s",
                fund_id, nav_date.date(), nav_value,
            )
            
            # Remove the "last document" (anything older than 6 years) for this specific fund
            from datetime import datetime
            import pandas as pd
            cutoff_date = datetime.now() - pd.DateOffset(years=6)
            
            del_result = self.collection.delete_many({
                "fund_id": fund_id,
                "nav_date": {"$lt": cutoff_date}
            })
            if del_result.deleted_count > 0:
                logger.debug("Deleted %s old records for fund_id=%s", del_result.deleted_count, fund_id)

            return True
       
        except DuplicateKeyError:
            logger.debug(
                "Duplicate NAV skipped | fund_id=%s, date=%s",
                fund_id, nav_date.date(),
            )
            return False

    def bulk_insert_nav(self, docs: list[dict]):
        if not docs:
            return
        try:
            self.collection.insert_many(docs, ordered=False)
        except Exception as e:
            logger.error("Bulk insert failed | Error: %s", e)

    def delete_old_nav(self, lookback_years: int = 6):
        """
        Deletes records older than the specified lookback window
        """
        from datetime import datetime
        import pandas as pd
        
        cutoff_date = datetime.now() - pd.DateOffset(years=lookback_years)
        
        result = self.collection.delete_many({
            "nav_date": {"$lt": cutoff_date}
        })
        
        if result.deleted_count > 0:
            logger.info("Cleaned up old NAV data | records_deleted=%s", result.deleted_count)

    def get_nav_series(self, fund_id: int):
        """
        Returns a list of NAV records sorted by date
        """
        return list(self.collection.find({"fund_id": fund_id}).sort("nav_date", 1))

