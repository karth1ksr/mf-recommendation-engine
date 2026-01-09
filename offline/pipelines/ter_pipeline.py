import logging
from storage.mongo_client import MongoDBClient
from storage.ter_repo import TerRepo
from ingestion.ter_ingestion import TerIngestor
from utils.string_utils import normalize_name

logger = logging.getLogger(__name__)

class TerPipeline:
    def __init__(self, ter_file: str, as_of_month: str):
        db = MongoDBClient().get_db()
        self.repo = TerRepo(db)
        self.ingestor = TerIngestor(ter_file, as_of_month)
        self.db = db

    def build_fund_map(self) -> dict:
        """
        Groups funds by their stored base name for matching with TER data.
        """
        fund_map = {}

        for fund in self.db.fund_master.find(
            {}, {"fund_id": 1, "base_name": 1, "plan_type": 1}
        ):
            key = fund.get("base_name")
            if not key:
                continue
            
            if key not in fund_map:
                fund_map[key] = []
            
            fund_map[key].append({
                "fund_id": fund["fund_id"],
                "plan_type": fund.get("plan_type", "Regular")
            })

        return fund_map

    def run(self):
        logger.info("TER ingestion started")

        df = self.ingestor.load()
        fund_map = self.build_fund_map()

        records = self.ingestor.transform(df, fund_map)

        for rec in records:
            self.repo.upsert(rec)

        logger.info(
            "TER ingestion completed | inserted_or_updated=%s",
            len(records)
        )
