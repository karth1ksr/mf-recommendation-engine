import logging
from datetime import datetime
from storage.mongo_client import MongoDBClient

class MongoErrorUpdateHandler(logging.Handler):
    """
    Custom logging handler that logs ERROR and CRITICAL messages to MongoDB.
    """
    def __init__(self, level=logging.ERROR):
        super().__init__(level)
        try:
            db = MongoDBClient().get_db()
            self.collection = db.error_logs
        except Exception as e:
            self.collection = None
            print(f"Failed to initialize MongoErrorUpdateHandler: {e}")

    def emit(self, record):
        if self.collection is None:
            return

        try:
            log_entry = {
                "timestamp": datetime.now(),
                "level": record.levelname,
                "module": record.module,
                "name": record.name,
                "message": record.getMessage(),
                "line_number": record.lineno,
                "process_name": record.processName
            }
            
            # If there's exception info, format it
            if record.exc_info:
                log_entry["error_details"] = self.format(record)
            
            # Extract fund_id or other metadata if present in the message
            # This is a bit heuristic, but useful for your specific use case
            self.collection.insert_one(log_entry)
        except Exception:
            self.handleError(record)
