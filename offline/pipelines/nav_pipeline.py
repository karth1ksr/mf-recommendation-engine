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

    def run(self, fund_ids: list[int]):
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
        logger.info("NAV ingestion completed | inserted=%s", inserted)
