import logging.config
from config.logging import *
from pipelines.nav_pipeline import NavPipeline
from pipelines.fund_master_pipeline import FundMasterPipeline

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    
    fund_master_pipeline = FundMasterPipeline(
        csv_path="data/fund_master.csv"
    )
    nav_pipeline = NavPipeline()
    
    fund_master_pipeline.run()
    nav_pipeline.run() 