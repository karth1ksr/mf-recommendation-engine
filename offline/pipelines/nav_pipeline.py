import logging
from storage.mongo_client import MongoDBClient
from ingestion.nav_ingestion import NavIngestion
from storage.nav_repo import NavRepo

logger = logging.getLogger(__name__)

class NavPipeline:
    def __init__(self):
        db = MongoDBClient().get_db()
        self.nav_repo = NavRepo(db)
        self.nav_ingestion = NavIngestion()

    def run(self, fund_ids: list[int] = None):
        if fund_ids is None:
            logger.info("No fund_ids provided, fetching active fund_ids from master...")
            fund_ids = [
                f["fund_id"] for f in self.nav_repo.collection.database.fund_master.find(
                    {"is_active": True}, {"fund_id": 1}
                )
            ]

        logger.info("NAV ingestion started | fund_count=%s", len(fund_ids))

        inserted = 0

        for fund_id in fund_ids:
            result = self.nav_ingestion.fetch_latest_nav(fund_id)
            if not result:
                continue

            nav_date, nav_value = result
            if nav_date and nav_value:
                self.nav_repo.insert_nav(fund_id, nav_date, nav_value)
                inserted += 1

        # Clean up data older than 6 years
        self.nav_repo.delete_old_nav(lookback_years=6)

        logger.info("NAV ingestion completed | inserted=%s", inserted)

    def run_history(self, fund_ids: list[int] = None):
        if fund_ids is None:
            logger.info("Fetching active fund_ids for historical sync...")
            fund_ids = [
                f["fund_id"] for f in self.nav_repo.collection.database.fund_master.find(
                    {"is_active": True}, {"fund_id": 1}
                )
            ]

        logger.info("Historical NAV ingestion started | fund_count=%s", len(fund_ids))
        for fund_id in fund_ids:
            records = self.nav_ingestion.fetch_history(fund_id)
            if records:
                self.nav_repo.bulk_insert_nav(records)
                logger.debug("Synced history for fund_id=%s | records=%s", fund_id, len(records))

        # Clean up data older than 6 years
        self.nav_repo.delete_old_nav(lookback_years=6)

        logger.info("Historical NAV ingestion completed")
