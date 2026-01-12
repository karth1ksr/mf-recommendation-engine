import logging
import pandas as pd
from storage.mongo_client import MongoDBClient
from storage.nav_repo import NavRepo
from storage.ter_repo import TerRepo
from storage.metrics_repo import MetricsRepo
from metrics.performance import compute_performance_metrics
from metrics.risk import compute_risk_metrics
from metrics.stability import compute_stability_metrics
from metrics.cost import compute_cost_metrics
from validation.normalization import normalize_by_category
from concurrent.futures import ProcessPoolExecutor
import functools

logger = logging.getLogger(__name__)

def _compute_single_fund_metrics(fund_id, category, nav_records, ter_doc):
    """
    Helper function for multiprocessing.
    Must be standalone (not a class method) to be picklable.
    """
    try:
        if not nav_records:
            return None
            
        # Prepare DataFrame
        df = pd.DataFrame(nav_records)
        df['nav_date'] = pd.to_datetime(df['nav_date'])
        df.set_index('nav_date', inplace=True)
        df.sort_index(inplace=True)
        
        # Compute Metrics
        perf_metrics = compute_performance_metrics(df)
        risk_metrics = compute_risk_metrics(df)
        stability_metrics = compute_stability_metrics(df)
        cost_metrics = compute_cost_metrics(ter_doc)
        
        # Consolidate
        return {
            "fund_id": fund_id,
            "scheme_category": category,
            **perf_metrics,
            **risk_metrics,
            **stability_metrics,
            **cost_metrics
        }
    except Exception as e:
        # We don't log here to avoid issues with multiprocess logging, 
        # return None and handle in main process
        return None

class MetricsPipeline:
    def __init__(self):
        db = MongoDBClient().get_db()
        self.nav_repo = NavRepo(db)
        self.ter_repo = TerRepo(db)
        self.metrics_repo = MetricsRepo(db)
        self.db = db

    def run(self, fund_ids: list[int] = None):
        """
        Runs the metric computation with massive speed optimizations:
        1. Bulk Data Fetching (reduces DB roundtrips)
        2. Multiprocessing (uses all CPU cores)
        """
        # 1. Fetch eligible funds
        query = {"is_active": True, "eligible_for_reco": True}
        if fund_ids:
            query["fund_id"] = {"$in": fund_ids}
            
        logger.info("Fetching eligible funds and historical data...")
        funds_list = list(self.db.fund_master.find(query, {"fund_id": 1, "scheme_category": 1}))
        
        if not funds_list:
            logger.info("No eligible funds found.")
            return

        all_fund_ids = [f["fund_id"] for f in funds_list]
        category_map = {f["fund_id"]: f.get("scheme_category", "Unknown") for f in funds_list}

        # 2. BULK FETCH NAV (The biggest optimization)
        logger.info("Bulk fetching NAV data for %s funds...", len(all_fund_ids))
        nav_cursor = self.db.nav_timeseries.find(
            {"fund_id": {"$in": all_fund_ids}},
            {"fund_id": 1, "nav_date": 1, "nav": 1}
        ).sort([("fund_id", 1), ("nav_date", 1)])
        
        # Group NAV records by fund_id for processing
        from collections import defaultdict
        nav_data_map = defaultdict(list)
        for record in nav_cursor:
            nav_data_map[record["fund_id"]].append(record)

        # 3. BULK FETCH TER
        logger.info("Bulk fetching TER data...")
        # Get latest TER for all these funds using aggregation (faster than 1000 queries)
        ter_pipeline = [
            {"$match": {"fund_id": {"$in": all_fund_ids}}},
            {"$sort": {"as_of_month": -1}},
            {"$group": {"_id": "$fund_id", "doc": {"$first": "$$ROOT"}}}
        ]
        ter_results = list(self.db.ter_snapshot.aggregate(ter_pipeline))
        ter_map = {item["_id"]: item["doc"] for item in ter_results}

        # 4. PARALLEL COMPUTATION
        logger.info("Computing metrics in parallel...")
        all_metrics_data = []
        
        # Prepare arguments for multiprocessing
        tasks = [
            (f_id, category_map[f_id], nav_data_map[f_id], ter_map.get(f_id))
            for f_id in all_fund_ids
        ]

        import os
        num_workers = min(os.cpu_count(), 8) # Avoid overwhelming system
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # map maintains order and returns results as they finish
            results = list(executor.map(
                functools.partial(unwrapper_compute), # helper to unpack tuple
                tasks
            ))
            
        all_metrics_data = [r for r in results if r is not None]

        if not all_metrics_data:
            logger.warning("No metrics were successfully computed.")
            return

        # 5. NORMALIZE (Collective)
        logger.info("Normalizing metrics across all funds...")
        metrics_df = pd.DataFrame(all_metrics_data)
        available_metrics = [
            m for m in ["cagr_3y", "cagr_5y", "volatility", "max_drawdown", "rolling_3y_consistency", "expense_ratio"] 
            if m in metrics_df.columns
        ]
        
        normalized_df = normalize_by_category(metrics_df, available_metrics)
        
        # 6. BULK UPDATE
        logger.info("Saving %s records to database...", len(normalized_df))
        final_records = normalized_df.to_dict(orient="records")
        self.metrics_repo.bulk_upsert_metrics(final_records)

        logger.info("Optimization complete! Metric computation finished.")

def unwrapper_compute(args):
    """Bridge for ProcessPoolExecutor.map with multiple arguments"""
    return _compute_single_fund_metrics(*args)
