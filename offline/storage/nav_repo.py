import logging
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

class NavRepo:
    def __init__(self, db):
        self.collection = db.nav_timeseries
        self.collection.create_index(
            [("fund_id", 1), ("nav_date", -1)],
            unique=True
        )

    def insert_nav(self, fund_id: int, nav_date, nav_value: float) -> bool:
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
            # ordered=False allows the operation to continue even if some documents 
            # fail due to the Unique Index (duplicates)
            self.collection.insert_many(docs, ordered=False)
        except Exception:
            # We catch the exception because we expect potential DuplicateKeyErrors 
            # when re-running historical syncs.
            pass

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

