import logging.config
from config.logging import *
from pipelines.nav_pipeline import NavPipeline
from pipelines.fund_master_pipeline import FundMasterPipeline
from pipelines.ter_pipeline import TerPipeline

import sys

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Check for --history flag
    is_history_sync = "--history" in sys.argv

    fund_master_pipeline = FundMasterPipeline(
        csv_path="data/scheme_details.csv"
    )
    nav_pipeline = NavPipeline()
    ter_pipeline = TerPipeline(
        ter_file="data/ter_data.xlsx",
        as_of_month="2026-01"
    ) 

    # 1. Update master list
    fund_master_pipeline.run()

    # 2. Sync NAV (History or Latest)
    if is_history_sync:
        logger.info("Running FULL historical NAV sync...")
        nav_pipeline.run_history()
    else:
        logger.info("Running daily incremental NAV sync...")
        nav_pipeline.run()

    # 3. Sync TER
    ter_pipeline.run()