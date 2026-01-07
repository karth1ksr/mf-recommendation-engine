import logging

logger = logging.getLogger(__name__)

class FundMasterRepository:
    def __init__(self, db):
        self.collection = db.fund_master

    def upsert_fund(self, fund_doc: dict):
        fund_id = fund_doc["fund_id"]

        self.collection.update_one(
            {"fund_id": fund_id},
            {"$set": fund_doc},
            upsert=True,
        )

        logger.debug("Upserted fund | fund_id=%s", fund_id)