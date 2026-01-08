import logging
from storage.mongo_client import MongoDBClient
from storage.ter_repo import TerRepo
from ingestion.ter_ingestion import TerIngestor, normalize_name

logger = logging.getLogger(__name__)

class TerPipeline:
    def __init__(self, ter_file: str, as_of_month: str):
        db = MongoDBClient().get_db()
        self.repo = TerRepo(db)
        self.ingestor = TerIngestor(ter_file, as_of_month)
        self.db = db

    def build_fund_map(self) -> dict:
        """
        normalized_scheme_name → fund_id
        """
        fund_map = {}

        for fund in self.db.fund_master.find(
            {}, {"fund_id": 1, "scheme_name": 1}
        ):
            key = normalize_name(fund["scheme_name"])
            fund_map[key] = fund["fund_id"]

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
