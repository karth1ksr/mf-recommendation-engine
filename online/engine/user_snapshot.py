from loguru import logger

"""
[LLD 4.3] Engine - User Snapshot.

This module maintains the state of a user session, holding extracted preferences
and deriving system-level constraints like target fund categories based on risk appetite.
"""

class UserSnapshot:
    """
    Session-state container for user preferences.
    
    Attributes:
        risk_level (str | None): Valid values: 'low', 'moderate', 'high'.
        investment_horizon_years (int | None): Number of years for investment.
        preferred_categories (list[str]): System-derived categories based on risk level.
    """

    def __init__(self):
        self.risk_level: str | None = None
        self.investment_horizon_years: int | None = None
        self.preferred_categories: list[str] = []

    def update_from_preferences(self, pref_dict: dict):
        """
        Updates the snapshot with new preferences extracted from user input.
        
        Args:
            pref_dict (dict): Dictionary containing 'risk_level' and 'investment_horizon_years'.
        """
        if not pref_dict:
            return

        # Update risk level
        new_risk = pref_dict.get("risk_level")
        if new_risk:
            self.risk_level = new_risk
            self._derive_categories()
            logger.debug(f"Snapshot risk_level updated to: {self.risk_level}")

        # Update horizon
        new_horizon = pref_dict.get("investment_horizon_years")
        if new_horizon is not None:
            self.investment_horizon_years = new_horizon
            logger.debug(f"Snapshot investment_horizon_years updated to: {self.investment_horizon_years}")

    def is_complete(self) -> bool:
        """
        Checks if the snapshot has all minimum required data for a recommendation.
        
        Returns:
            bool: True if risk and horizon are captured.
        """
        complete = self.risk_level is not None and self.investment_horizon_years is not None
        logger.info(f"Snapshot completeness check: {complete}")
        return complete

    def _derive_categories(self):
        """
        Private method to map risk levels to fund categories.
        
        Logic:
            - low -> ["debt"]
            - moderate -> ["equity", "hybrid"]
            - high -> ["equity"]
        """
        mapping = {
            "low": ["debt"],
            "moderate": ["equity", "hybrid"],
            "high": ["equity"]
        }
        
        self.preferred_categories = mapping.get(self.risk_level, [])
        logger.debug(f"Derived preferred categories: {self.preferred_categories}")

    def __repr__(self):
        return (f"UserSnapshot(risk={self.risk_level}, "
                f"horizon={self.investment_horizon_years}, "
                f"categories={self.preferred_categories})")
