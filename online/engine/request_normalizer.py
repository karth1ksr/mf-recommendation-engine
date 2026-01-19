import re
from loguru import logger

"""
[LLD 4.2] Interaction Layer - Request Normalizer.

This module handles the extraction of structured financial preferences from natural language input.
It uses deterministic keyword mapping and regular expressions to identify risk appetite, 
investment duration, and asset class preferences.
"""

class RequestNormalizer:
    """
    Extracts specific mutual fund preferences from raw user text using rule-based logic.
    
    Fields extracted:
        - risk_level: 'low', 'moderate', or 'high'
        - investment_horizon_years: Integer representing the number of years
        - category: 'equity', 'debt', or 'hybrid'
    """

    def __init__(self):
        # Keyword mappings for risk levels
        self.risk_map = {
            "low": ["low", "conservative", "safe", "stable", "minimum risk"],
            "moderate": ["moderate", "medium", "balanced", "stable growth"],
            "high": ["high", "aggressive", "risky", "maximum returns"]
        }
        
        # Keyword mappings for categories
        self.category_map = {
            "equity": ["equity", "stock", "shares", "growth"],
            "debt": ["debt", "bond", "fixed income", "safe"],
            "hybrid": ["hybrid", "balanced", "mixed"]
        }

    def _extract_risk(self, text: str) -> str | None:
        """Determines risk level based on keyword presence."""
        for level, keywords in self.risk_map.items():
            if any(kw in text for kw in keywords):
                return level
        return None

    def _extract_category(self, text: str) -> str | None:
        """Determines fund category based on keyword presence."""
        for cat, keywords in self.category_map.items():
            if any(kw in text for kw in keywords):
                return cat
        return None

    def _extract_horizon(self, text: str) -> int | None:
        """
        Extracts duration in years using regular expressions.
        Example: "for 5 years", "3 yr", "10 year horizon"
        """
        # Patterns like "5 years", "3 yr", "10yr"
        patterns = [
            r'(\d+)\s*(?:year|yr|yrs|years)',
            r'for\s*(\d+)',
            r'horizon\s*(?:of)?\s*(\d+)'
        ]
        
        for p in patterns:
            match = re.search(p, text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    def normalize(self, text: str) -> dict:
        """
        Normalizes raw text into a structured preference dictionary.
        
        Example Input: "I want to invest in high risk equity funds for 5 years"
        Example Output: {
            "risk_level": "high",
            "investment_horizon_years": 5,
            "category": "equity"
        }
        
        Args:
            text (str): Raw input from the user.
            
        Returns:
            dict: Structured preferences with keys 'risk_level', 
                  'investment_horizon_years', and 'category'.
        """
        if not text or not isinstance(text, str):
            logger.warning("Normalizer received empty or non-string input.")
            return {
                "risk_level": None,
                "investment_horizon_years": None,
                "category": None
            }

        clean_text = text.lower().strip()
        logger.debug(f"Normalizing text: '{clean_text}'")

        preferences = {
            "risk_level": self._extract_risk(clean_text),
            "investment_horizon_years": self._extract_horizon(clean_text),
            "category": self._extract_category(clean_text)
        }

        logger.info(f"Extracted preferences: {preferences}")
        return preferences
