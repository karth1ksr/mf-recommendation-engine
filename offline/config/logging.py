LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
        },
        "mongo_error": {
            "class": "utils.mongo_logger.MongoErrorUpdateHandler",
            "level": "ERROR",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "mongo_error"],
    },
}
