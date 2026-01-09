import logging

logger = logging.getLogger(__name__)

class TerRepo:
    def __init__(self, db):
        self.collection = db.ter_snapshot
        self.collection.create_index(
            [("fund_id", 1), ("plan_type", 1), ("as_of_month", 1)],
            unique=True
        )

    def delete_month_data(self, as_of_month: str):
        """
        Deletes all TER records for a specific month. 
        Useful for a fresh ingestion of a month's data.
        """
        result = self.collection.delete_many({"as_of_month": as_of_month})
        if result.deleted_count > 0:
            logger.info("Cleared existing TER data | month=%s | count=%s", as_of_month, result.deleted_count)

    def upsert(self, doc: dict):
        self.collection.update_one(
            {
                "fund_id": doc["fund_id"],
                "plan_type": doc["plan_type"],
                "as_of_month": doc["as_of_month"]
            },
            {"$set": doc},
            upsert=True
        )

        logger.info(
            "Upserted TER | fund_id=%s | plan=%s | month=%s | ter=%s",
            doc["fund_id"], doc["plan_type"], doc["as_of_month"], doc["ter"]
        )
