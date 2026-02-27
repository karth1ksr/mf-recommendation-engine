from loguru import logger
from online.backend.engine.user_snapshot import UserSnapshot
from online.backend.engine.recommender import RecommendationEngine

class MutualFundTools:
    def __init__(self, db, session_id: str):
        self.db = db
        self.session_id = session_id
        self.recommender = RecommendationEngine(db)
        self.snapshot = UserSnapshot()
        logger.info(f"MutualFundTools initialized for session {session_id}")

    async def save_snapshot(self):
        """Persists the current snapshot to MongoDB."""
        snapshot_data = {
            "session_id": self.session_id,
            "risk_level": self.snapshot.risk_level,
            "horizon": self.snapshot.investment_horizon_years,
            "preferred_categories": self.snapshot.preferred_categories,
            "updated_at": "now" # In a real app, use datetime.utcnow()
        }
        await self.db.user_sessions.update_one(
            {"session_id": self.session_id},
            {"$set": snapshot_data},
            upsert=True
        )
        logger.info(f"Snapshot saved for {self.session_id}")

    async def load_snapshot(self):
        """Loads the snapshot from MongoDB."""
        data = await self.db.user_sessions.find_one({"session_id": self.session_id})
        if data:
            self.snapshot.risk_level = data.get("risk_level")
            self.snapshot.investment_horizon_years = data.get("horizon")
            self.snapshot.preferred_categories = data.get("preferred_categories")
            logger.info(f"Snapshot loaded for {self.session_id}: {self.snapshot}")

    async def get_recommendations(self, risk_level: str, horizon: int, preferred_categories: list[str] = None):
        """
        Fetches a ranked list of mutual funds based on the user's risk profile and investment horizon.
        
        Args:
            risk_level: The user's risk tolerance (low, moderate, or high).
            horizon: The investment period in years.
            preferred_categories: Optional specific categories to filter (e.g., Equity, Debt).
        """
        logger.info(f"Tool Call: get_recommendations(risk={risk_level}, horizon={horizon}, categories={preferred_categories})")

        # Update snapshot
        self.snapshot.update_from_preferences({
            "risk_level": risk_level,
            "investment_horizon_years": horizon,
            "categories": preferred_categories
        })
        await self.save_snapshot()
        
        if not self.snapshot.is_complete():
            missing = []
            if not self.snapshot.risk_level: missing.append("risk level")
            if not self.snapshot.investment_horizon_years: missing.append("investment horizon")
            return f"I need a bit more information. Please provide your {' and '.join(missing)}."

        # Get recommendations from the engine
        recommendations = await self.recommender.get_recommendations(self.snapshot)
        logger.info(f"Engine returned {len(recommendations) if isinstance(recommendations, list) else 0} recommendations")
        
        # Store for future reference (comparison/explanation)
        self.snapshot.last_recommendations = recommendations
        
        if not recommendations:
            logger.warning("No recommendations found for this Snapshot")
            return "I couldn't find any funds matching those criteria in the database."
            
        return recommendations

    async def compare_funds(self, index1: int, index2: int):
        """
        Compares two funds from the recently suggested list side-by-side.
        
        Args:
            index1: The 1-based index of the first fund (e.g., 1 for the first one).
            index2: The 1-based index of the second fund (e.g., 2 for the second one).
        """
        logger.info(f"Tool Call: compare_funds(index1={index1}, index2={index2})")
        
        if not self.snapshot.last_recommendations:
            return "No funds have been recommended yet. Please ask for recommendations first."
            
        try:
            fund_a = self.snapshot.last_recommendations[index1 - 1]
            fund_b = self.snapshot.last_recommendations[index2 - 1]
            
            # We return the raw data; the LLM will format the comparison.
            return {
                "fund_a": fund_a,
                "fund_b": fund_b,
                "analysis_context": {
                    "risk": self.snapshot.risk_level,
                    "horizon": self.snapshot.investment_horizon_years
                }
            }
        except IndexError:
            return f"Invalid indices. I only have {len(self.snapshot.last_recommendations)} funds in the current list."

    async def get_explanation(self):
        """
        Provides detailed metrics and rationale for the current recommendations when asked by the user.
        """
        logger.info("Tool Call: get_explanation")
        if not self.snapshot.last_recommendations:
            return "No funds have been recommended yet. Please ask for recommendations first."
        
        return {
            "recommendations": self.snapshot.last_recommendations,
            "context": {
                "risk": self.snapshot.risk_level,
                "horizon": self.snapshot.investment_horizon_years
            }
        }

    async def get_snapshot_status(self):
        """Returns the current state of collected user preferences."""
        return str(self.snapshot)
