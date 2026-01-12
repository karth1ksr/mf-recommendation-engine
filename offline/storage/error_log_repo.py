import logging
from datetime import datetime

class ErrorLogRepository:
    def __init__(self, db):
        self.collection = db.error_logs
        # Create an index on timestamp for easier querying and cleanup
        self.collection.create_index([("timestamp", -1)])

    def log_error(self, module: str, message: str, error_details: str = None, metadata: dict = None):
        """
        Logs an error to the MongoDB collection
        """
        log_entry = {
            "timestamp": datetime.now(),
            "module": module,
            "message": message,
            "error_details": error_details,
            "metadata": metadata or {},
            "level": "ERROR"
        }
        try:
            self.collection.insert_one(log_entry)
        except Exception as e:
            # Fallback to console if DB logging fails
            print(f"CRITICAL: Failed to log error to MongoDB: {e}")

    def get_recent_errors(self, limit: int = 50):
        return list(self.collection.find().sort("timestamp", -1).limit(limit))

    def clear_old_logs(self, days: int = 30):
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        result = self.collection.delete_many({"timestamp": {"$lt": cutoff}})
        return result.deleted_count
