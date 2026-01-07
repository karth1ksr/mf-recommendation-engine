import logging.config
from config.logging import LOGGING_CONFIG
from pipelines.nav_pipeline import NavPipeline

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    nav_pipeline = NavPipeline()
    
    # Example fund IDs (e.g., for Quant Small Cap Fund, etc.)
    fund_ids = [120847, 100350] 
    nav_pipeline.run(fund_ids)