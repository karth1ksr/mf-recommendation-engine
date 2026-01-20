import logging
from datetime import datetime, timedelta
from storage.mongo_client import MongoDBClient
from utils.string_utils import normalize_name, extract_base_name
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_funds():
    db = MongoDBClient().get_db()
    nav_col = db.nav_timeseries
    master_col = db.fund_master

    logger.info("Starting fund data validation and cleanup...")

    # 1. Aggregate NAV data to get counts and latest dates
    pipeline = [
        {
            "$group": {
                "_id": "$fund_id",
                "nav_count": {"$sum": 1},
                "latest_nav": {"$max": "$nav_date"}
            }
        }
    ]
    
    logger.info("Aggregating NAV record counts per fund...")
    nav_stats = list(nav_col.aggregate(pipeline))
    nav_map = {item["_id"]: item for item in nav_stats}

    # 2. Process all funds in master
    funds = list(master_col.find({}, {"fund_id": 1, "scheme_name": 1}))
    total_funds = len(funds)
    logger.info(f"Processing {total_funds} funds in master list...")

    # Thresholds
    MIN_DAYS_FOR_RECO = 750  # ~3 years of trading days
    MIN_DAYS_FOR_ACTIVE = 60 # ~3 months
    STALE_LIMIT_DAYS = 30    # Consider inactive if no data in last 30 days

    now = datetime.now()
    stale_date = now - timedelta(days=STALE_LIMIT_DAYS)

    updates = []
    stats = {
        "deactivated": 0,
        "made_ineligible": 0,
        "kept_active": 0,
        "missing_nav": 0
    }

    for fund in funds:
        fund_id = fund["fund_id"]
        nav_info = nav_map.get(fund_id)
        scheme_name = fund["scheme_name"]

        is_active = True
        eligible_for_reco = True
        status_note = "Valid"
        
        if not nav_info:
            is_active = False
            eligible_for_reco = False
            status_note = "No NAV data found in database"
            stats["missing_nav"] += 1
            stats["deactivated"] += 1
            stats["made_ineligible"] += 1
        else:
            count = nav_info["nav_count"]
            latest = nav_info["latest_nav"]

            notes = []
            # Criteria 1: Inactivity based on stale data
            if latest < stale_date:
                is_active = False
                notes.append(f"Stale data (Latest: {latest.date()})")
                stats["deactivated"] += 1
            
            # Criteria 2: Insufficient history for metrics
            if count < MIN_DAYS_FOR_RECO:
                eligible_for_reco = False
                notes.append(f"Low history count ({count} days)")
                stats["made_ineligible"] += 1
            
            # Criteria 3: Too little data to even be considered active
            if count < MIN_DAYS_FOR_ACTIVE:
                is_active = False
                if f"Low history count ({count} days)" not in notes:
                    notes.append(f"Insufficient total data ({count} days)")
            
            if notes:
                status_note = " | ".join(notes)
            
            if is_active:
                stats["kept_active"] += 1

        # Update the document
        master_col.update_one(
            {"fund_id": fund_id},
            {
                "$set": {
                    "is_active": is_active,
                    "eligible_for_reco": eligible_for_reco,
                    "last_nav_date": nav_info["latest_nav"] if nav_info else None,
                    "nav_record_count": nav_info["nav_count"] if nav_info else 0,
                    "validation_date": now,
                    "status_note": status_note,
                    "normalized_name": normalize_name(scheme_name),
                    "base_name": normalize_name(extract_base_name(scheme_name))
                }
            }
        )

    logger.info("Cleanup completed!")
    logger.info(f"Total Funds: {total_funds}")
    logger.info(f"Active Funds: {stats['kept_active']}")
    logger.info(f"Deactivated (Stale/No Data): {stats['deactivated']}")
    logger.info(f"Ineligible for Recommendations (<3 yrs data): {stats['made_ineligible']}")
    logger.info(f"Funds with 0 NAV records: {stats['missing_nav']}")

if __name__ == "__main__":
    cleanup_funds()
