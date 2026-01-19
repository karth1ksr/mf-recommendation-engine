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
        
        Args:
            snapshot (UserSnapshot): The current user session state containing preferences.
            top_k (int): Number of recommendations to return. Default is 5.
            
        Returns:
            list[dict]: A sorted list of fund documents with calculated scores.
        """
        if not snapshot.preferred_categories:
            logger.warning("Recommendation requested but no preferred categories found in snapshot.")
            return []

        logger.info(f"Generating top-{top_k} recommendations for categories: {snapshot.preferred_categories}")

        # 1. Fetch filtered funds from MongoDB
        # We filter based on the systems derived categories (equity, debt, hybrid)
        query = {"category": {"$in": snapshot.preferred_categories}}
        
        try:
            cursor = self.db[self.collection_name].find(query)
            # Fetching a reasonable pool size for the specific categories
            funds = await cursor.to_list(length=500)
            
            if not funds:
                logger.warning(f"No funds found in database for categories: {snapshot.preferred_categories}")
                return []

            # 2. Apply Weighting Logic
            scored_funds = []
            for fund in funds:
                # We assume metrics are already normalized (0 to 1 or Z-score) in the DB
                # Higher values always represent a "better" metric in this context
                norm_cagr = fund.get("norm_cagr_5y", 0)
                norm_consistency = fund.get("norm_consistency", 0)
                norm_drawdown = fund.get("norm_max_drawdown", 0)
                norm_expense = fund.get("norm_expense_ratio", 0)
                
                # Weighted formula per LLD 4.5
                score = (
                    0.4 * norm_cagr +
                    0.25 * norm_consistency +
                    0.2 * norm_drawdown +
                    0.15 * norm_expense
                )
                
                fund["recommendation_score"] = round(float(score), 4)
                scored_funds.append(fund)

            # 3. Sort by score descending
            scored_funds.sort(key=lambda x: x["recommendation_score"], reverse=True)
            
            # 4. Return top K
            final_selection = scored_funds[:top_k]
            
            logger.info(f"Successfully ranked {len(scored_funds)} funds. Returning top {len(final_selection)}.")
            return final_selection

        except Exception as e:
            logger.error(f"Critical error during recommendation generation: {str(e)}")
            return []
