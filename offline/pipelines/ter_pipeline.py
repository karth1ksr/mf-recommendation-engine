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
        Groups funds by their base name for matching with TER data.
        Example: { "aditya birla sun life banking...": [{"fund_id": 1, "plan_type": "Direct"}, ...] }
        """
        fund_map = {}

        for fund in self.db.fund_master.find(
            {}, {"fund_id": 1, "scheme_name": 1, "plan_type": 1}
        ):
            # Extract base name by splitting on common delimiters and cleaning up
            full_name = fund["scheme_name"]
            
            # Simple heuristic: split by "-" and take the first part
            # Most names are like "Fund Name - Regular Plan - Growth"
            base_name_raw = full_name.split(" - ")[0]
            if " - " not in full_name and "-" in full_name:
                # Handle cases where there might not be spaces around the hyphen
                base_name_raw = full_name.split("-")[0]
            
            key = normalize_name(base_name_raw)
            
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
