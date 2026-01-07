import logging.config
from config.logging import *
from pipelines.nav_pipeline import NavPipeline

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    nav_pipeline = NavPipeline()
    nav_pipeline.run() 