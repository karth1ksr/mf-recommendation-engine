from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

"""
[LLD 4.5] Engine - Recommendation Engine.

This module implements the deterministic core of the recommendation system.
It fetches precomputed fund metrics from MongoDB, applies user preference filters,
and calculates a weighted score to rank the top mutual funds.
"""

class RecommendationEngine:
    """
    Deterministic engine for ranking mutual funds based on weighted metrics.
    
    The scoring formula is predefined to Ensure explainability and consistency:
    Score = 0.4*CAGR + 0.25*Consistency + 0.2*MaxDrawdown + 0.15*ExpenseRatio
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initializes the engine with a database connection.
        
        Args:
            db (AsyncIOMotorDatabase): The asynchronous MongoDB database instance.
        """
        self.db = db
        self.collection_name = "fund_metrics"

    async def get_recommendations(self, snapshot, top_k: int = 5) -> list:
        """
        Generates a ranked list of mutual funds based on user snapshot.
        """
        # 1. Determine asset class patterns
        input_categories = snapshot.preferred_categories
        
        if not input_categories:
            # Fallback mapping if user didn't specify categories
            mapping = {
                "low": ["Debt"],
                "moderate": ["Equity", "Hybrid"],
                "high": ["Equity"]
            }
            input_categories = mapping.get(snapshot.risk_level, [])
            logger.info(f"Using derived asset classes for risk '{snapshot.risk_level}': {input_categories}")

        if not input_categories:
            logger.warning("No asset classes could be determined.")
            return []

        # 2. Build Aggregation Pipeline
        # We need to find funds in fund_master that match the category, 
        # then join with fund_metrics to get the precomputed scores.
        
        # Regex to match categories starting with or containing the asset class
        regex_pattern = "|".join(input_categories)
        
        pipeline = [
            # Step A: Filter fund_master by category (case-insensitive regex)
            {
                "$match": {
                    "scheme_category": {"$regex": f".*({regex_pattern}).*", "$options": "i"},
                    "eligible_for_reco": True
                }
            },
            # Step B: Join with fund_metrics
            {
                "$lookup": {
                    "from": "fund_metrics",
                    "localField": "fund_id",
                    "foreignField": "fund_id",
                    "as": "metrics"
                }
            },
            # Step C: Remove funds without metrics
            {"$unwind": "$metrics"},
            # Step D: Project necessary fields
            {
                "$project": {
                    "fund_id": 1,
                    "scheme_name": 1,
                    "scheme_category": 1,
                    "metrics": 1
                }
            }
        ]

        try:
            logger.info(f"Running recommendation aggregation for patterns: {regex_pattern}")
            cursor = self.db["fund_master"].aggregate(pipeline)
            funds_data = await cursor.to_list(length=1000)
            
            if not funds_data:
                logger.warning(f"No funds joined for patterns: {regex_pattern}")
                return []

            # 3. Apply Weighting Logic in Python
            scored_funds = []
            for item in funds_data:
                metrics = item["metrics"]
                
                norm_cagr = metrics.get("norm_cagr_5y", 0)
                norm_consistency = metrics.get("norm_consistency", 0)
                norm_drawdown = metrics.get("norm_max_drawdown", 0)
                norm_expense = metrics.get("norm_expense_ratio", 0)
                
                score = (
                    0.4 * norm_cagr +
                    0.25 * norm_consistency +
                    0.2 * norm_drawdown +
                    0.15 * norm_expense
                )
                
                # Flatten the response
                result = {
                    "fund_id": item["fund_id"],
                    "scheme_name": item["scheme_name"],
                    "category": item["scheme_category"],
                    "recommendation_score": round(float(score), 4),
                    "norm_cagr_5y": norm_cagr,
                    "norm_consistency": norm_consistency,
                    "norm_max_drawdown": norm_drawdown,
                    "norm_expense_ratio": norm_expense
                }
                scored_funds.append(result)

            # 4. Sort and return
            scored_funds.sort(key=lambda x: x["recommendation_score"], reverse=True)
            final_selection = scored_funds[:top_k]
            
            logger.info(f"Successfully ranked {len(scored_funds)} funds. Returning top {len(final_selection)}.")
            return final_selection

        except Exception as e:
            logger.error(f"Critical error during aggregation: {str(e)}")
            return []
