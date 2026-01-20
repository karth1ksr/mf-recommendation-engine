import logging

logger = logging.getLogger(__name__)

class FundMasterRepository:
    def __init__(self, db):
        self.collection = db.fund_master
        self.collection.create_index("fund_id", unique=True)
        self.collection.create_index("normalized_name")
        self.collection.create_index("base_name")

    def upsert_fund(self, fund_doc: dict):
        fund_id = fund_doc["fund_id"]

        # Preserve fields managed by the cleanup script (don't overwrite them if they exist)
        state_fields = ["is_active", "eligible_for_reco"]
        
        update_data = {k: v for k, v in fund_doc.items() if k not in state_fields}
        insert_data = {k: v for k, v in fund_doc.items() if k in state_fields}

        self.collection.update_one(
            {"fund_id": fund_id},
            {
                "$set": update_data,
                "$setOnInsert": insert_data
            },
            upsert=True,
        )

        logger.debug("Upserted fund | fund_id=%s", fund_id)