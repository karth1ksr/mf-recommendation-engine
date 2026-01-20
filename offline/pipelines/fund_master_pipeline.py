import logging 
from storage.mongo_client import MongoDBClient
from storage.fund_master_repo import FundMasterRepository
from ingestion.fund_master_ingestion import FundMasterIngestor  

logger = logging.getLogger(__name__)

class FundMasterPipeline:
    def __init__(self, csv_path: str):
        db = MongoDBClient().get_db()
        self.fund_master_repo = FundMasterRepository(db)
        self.fund_master_ingestor = FundMasterIngestor(csv_path)

    def run(self):
        logger.info("Fund master ingestion started")

        df = self.fund_master_ingestor.load_csv()
        records = self.fund_master_ingestor.transform(df)

        for record in records:
            self.fund_master_repo.upsert_fund(record)

        logger.info(
            "Fund master ingestion completed | total_funds=%s",
            len(records)
        )