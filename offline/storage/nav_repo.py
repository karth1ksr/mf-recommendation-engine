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
            return True
       
        except DuplicateKeyError:
            logger.debug(
                "Duplicate NAV skipped | fund_id=%s, date=%s",
                fund_id, nav_date.date(),
            )
            return False

