import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MetricsRepo:
    def __init__(self, db):
        self.collection = db.fund_metrics
        self.collection.create_index("fund_id", unique=True)
        self.collection.create_index("last_updated")

    def upsert_metrics(self, fund_metrics: dict):
        """
        Inserts or updates metrics for a specific fund
        """
        fund_metrics["last_updated"] = datetime.now()
        self.collection.update_one(
            {"fund_id": fund_metrics["fund_id"]},
            {"$set": fund_metrics},
            upsert=True
        )

    def bulk_upsert_metrics(self, metrics_list: list[dict]):
        """
        Efficiently updates multiple fund metrics at once
        """
        if not metrics_list:
            return
            
        from pymongo import UpdateOne
        operations = []
        now = datetime.now()
        
        for doc in metrics_list:
            doc["last_updated"] = now
            operations.append(
                UpdateOne(
                    {"fund_id": doc["fund_id"]},
                    {"$set": doc},
                    upsert=True
                )
            )
            
        if operations:
            self.collection.bulk_write(operations, ordered=False)

    def get_metrics(self, fund_id: int):
        return self.collection.find_one({"fund_id": fund_id})

    def get_all_metrics(self):
        return list(self.collection.find())
