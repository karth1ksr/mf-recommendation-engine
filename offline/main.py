import logging.config
from config.logging import *
from pipelines.nav_pipeline import NavPipeline
from pipelines.fund_master_pipeline import FundMasterPipeline
from pipelines.ter_pipeline import TerPipeline
import logging

import sys

logger = logging.getLogger(__name__)

if __name__=="__main__":
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Check for pipeline flags
    is_history_sync = "--history" in sys.argv
    run_nav = "--nav" in sys.argv
    run_ter = "--ter" in sys.argv
    run_master = "--master" in sys.argv
    clear_ter = "--clear-ter" in sys.argv
    
    # If no specific flags, run all
    if not run_nav and not run_ter and not run_master:
        run_nav = True
        run_ter = True
        run_master = True

    fund_master_pipeline = FundMasterPipeline(
        csv_path="data/scheme_details.csv"
    )
    nav_pipeline = NavPipeline()
    ter_pipeline = TerPipeline(
        ter_file="data/ter_data.xlsx",
        as_of_month="2026-01"
    ) 

    # 1. Update master list
    if run_master:
        fund_master_pipeline.run()

    # 2. Sync NAV (Optional)
    if run_nav:
        if is_history_sync:
            logger.info("Running FULL historical NAV sync...")
            nav_pipeline.run_history()
        else:
            logger.info("Running daily incremental NAV sync...")
            nav_pipeline.run()

    # 3. Sync TER (Optional)
    if run_ter:
        ter_pipeline.run(delete_month=clear_ter)