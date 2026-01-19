import re
import os
import json
import google.generativeai as genai
from loguru import logger
from online.backend.core.config import get_settings

"""
[LLD 4.2] Interaction Layer - Request Normalizer.

This module handles the extraction of structured financial preferences from natural language input.
It uses a hybrid approach:
1. Deterministic keyword/regex logic for speed and high-confidence matches.
2. LLM-based contextual extraction for handling ambiguous or history-dependent phrases.
"""

class RequestNormalizer:
    """
    Extracts specific mutual fund preferences from raw user text.
    
    Fields extracted:
        - risk_level: 'low', 'moderate', or 'high'
        - investment_horizon_years: Integer representing the number of years
        - categories: list of ['equity', 'debt', 'hybrid']
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
        
        # Initialize Gemini for contextual parsing using central settings
        settings = get_settings()
        api_key = settings.GEMINI_API_KEY
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY not found in settings. LLM parsing will be disabled.")

    def _extract_risk_deterministic(self, text: str) -> str | None:
        """Determines risk level based on keyword presence."""
        for level, keywords in self.risk_map.items():
            if any(kw in text for kw in keywords):
                return level
        return None

    def _extract_categories_deterministic(self, text: str) -> list[str]:
        """Identifies all categories present in the text."""
        found_categories = []
        for cat, keywords in self.category_map.items():
            if any(kw in text for kw in keywords):
                found_categories.append(cat)
        return found_categories

    def _extract_horizon_deterministic(self, text: str) -> int | None:
        """Extracts duration in years using regular expressions."""
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

    async def _extract_with_llm(self, text: str, history: list[dict] = None) -> dict:
        """
        Uses LLM to extract preferences when deterministic logic might fail 
        or when context from history is required.
        """
        if not self.model:
            return {}

        history_context = ""
        if history:
            # Format last 3-4 messages for context
            history_context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])

        prompt = f"""
        Extract mutual fund investment preferences from the user's input.
        If history is provided, use it to resolve ambiguity (e.g., "the first one").

        CONVERSATION HISTORY:
        {history_context}

        USER INPUT:
        "{text}"

        OUTPUT FORMAT (JSON ONLY):
        {{
            "risk_level": "low" | "moderate" | "high" | null,
            "investment_horizon_years": integer | null,
            "categories": ["equity", "debt", "hybrid"] | []
        }}

        RULES:
        1. Only return the JSON. No conversation.
        2. If a value is not found or ambiguous, use null or [].
        3. Convert relative time (e.g., "5 years") to integers.
        """

        try:
            response = self.model.generate_content(prompt)
            # Remove markdown code blocks if present
            clean_response = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_response)
        except Exception as e:
            logger.error(f"LLM Parsing failed: {e}")
            return {}

    async def normalize(self, text: str, history: list[dict] = None) -> dict:
        """
        Main entry point for extraction. Combines deterministic and LLM logic.
        """
        if not text:
            return {"risk_level": None, "investment_horizon_years": None, "categories": []}

        clean_text = text.lower().strip()
        
        # 1. Deterministic Pass (Fast & Reliable for direct input)
        pref = {
            "risk_level": self._extract_risk_deterministic(clean_text),
            "investment_horizon_years": self._extract_horizon_deterministic(clean_text),
            "categories": self._extract_categories_deterministic(clean_text)
        }

        # 2. Contextual LLM Pass (If any field is missing AND we have a model/history)
        # Or if the input is short/ambiguous (e.g., "yes", "the first one", "moderate")
        is_ambiguous = len(clean_text.split()) < 4 or history is not None
        needs_llm = any(v is None or (isinstance(v, list) and not v) for v in pref.values())

        if self.model and (is_ambiguous or needs_llm):
            logger.debug("Attempting contextual extraction with LLM...")
            llm_pref = await self._extract_with_llm(text, history)
            
            # Merge: LLM only fills what deterministic logic missed
            if llm_pref.get("risk_level") and not pref["risk_level"]:
                pref["risk_level"] = llm_pref["risk_level"]
            if llm_pref.get("investment_horizon_years") and not pref["investment_horizon_years"]:
                pref["investment_horizon_years"] = llm_pref["investment_horizon_years"]
            if llm_pref.get("categories") and not pref["categories"]:
                pref["categories"] = llm_pref["categories"]

        logger.info(f"Final Normalized Preferences: {pref}")
        return pref
