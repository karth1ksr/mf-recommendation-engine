import logging.config
from config.logging import *
from pipelines.nav_pipeline import NavPipeline
from pipelines.fund_master_pipeline import FundMasterPipeline
from pipelines.ter_pipeline import TerPipeline

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    
    fund_master_pipeline = FundMasterPipeline(
        csv_path="data/scheme_details.csv"
    )
    nav_pipeline = NavPipeline()
    ter_pipeline = TerPipeline(
        ter_file="data/ter_data.xlsx",
        as_of_month="2026-01"
    ) 

    fund_master_pipeline.run()
    nav_pipeline.run()
    ter_pipeline.run() 