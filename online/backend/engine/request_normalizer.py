import re
import os
import json
from google import genai
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
            try:
                self.client = genai.Client(api_key=api_key)
                logger.info("Gemini (google-genai) client initialized successfully.")
            except Exception as e:
                self.client = None
                logger.error(f"Failed to initialize Gemini client: {e}")
        else:
            self.client = None
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

    async def _extract_with_llm(self, text: str, history: list[dict] = None, last_recommendations: list[dict] = None) -> dict:
        """
        Uses LLM to extract preferences when deterministic logic might fail 
        or when context from history/recommendations is required.
        """
        if not self.client:
            return {}

        history_context = ""
        if history:
            # Format last 3-4 messages for context
            history_context = "\n".join([f"{m['role']}: {m['content']}" for m in history[-4:]])

        reco_context = ""
        if last_recommendations:
            reco_context = "CONTEXTUAL RECOMMENDATIONS (Previously Suggested):\n" + \
                "\n".join([f"{i+1}. {r['scheme_name']}" for i, r in enumerate(last_recommendations[:5])])

        prompt = f"""
        Extract mutual fund investment preferences from the user's input.
        If history or recommendations are provided, use them to resolve ambiguity (e.g., "the first one").

        CONVERSATION HISTORY:
        {history_context}

        {reco_context}

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
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt
            )
            # Remove markdown code blocks if present
            clean_response = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_response)
        except Exception as e:
            logger.error(f"LLM Parsing failed: {e}")
            return {}

    async def _extract_comparison_indices(self, text: str, last_recommendations: list[dict] = None) -> list[int]:
        """
        Extracts index of funds to compare (1-indexed from user perspective).
        """
        if not self.client or not last_recommendations:
            return []

        prompt = f"""
        Identify which funds the user wants to compare from the following list.
        Provide the result as a list of integers representing the ranks (1-indexed).

        RECOMMENDED FUNDS:
        {"\n".join([f"{i+1}. {r['scheme_name']}" for i, r in enumerate(last_recommendations[:5])])}

        USER INPUT:
        "{text}"

        OUTPUT FORMAT (JSON ONLY):
        {{
            "indices": [index1, index2]
        }}
        
        RULES:
        1. Only return JSON.
        2. If indices cannot be found, return [].
        """

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt
            )
            data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
            return data.get("indices", [])
        except Exception as e:
            logger.error(f"Comparison extraction failed: {e}")
            return []

    async def normalize(self, text: str, history: list[dict] = None, last_recommendations: list[dict] = None) -> dict:
        """
        Main entry point for extraction. Combines deterministic and LLM logic.
        """
        if not text:
            return {"risk_level": None, "investment_horizon_years": None, "categories": [], "comparison_indices": []}

        clean_text = text.lower().strip()
        
        # 1. Deterministic Pass (Fast & Reliable for direct input)
        pref = {
            "risk_level": self._extract_risk_deterministic(clean_text),
            "investment_horizon_years": self._extract_horizon_deterministic(clean_text),
            "categories": self._extract_categories_deterministic(clean_text),
            "comparison_indices": []
        }

        # Handle simple numeric comparison extraction deterministically if possible (e.g. "compare 1 and 2")
        comp_match = re.search(r'compare\s*(\d+)\s*(?:and|&|,|vs)?\s*(\d+)', clean_text)
        if comp_match:
            try:
                pref["comparison_indices"] = [int(comp_match.group(1)), int(comp_match.group(2))]
            except ValueError:
                pass

        # 2. Contextual LLM Pass
        is_ambiguous = len(clean_text.split()) < 4 or history is not None or last_recommendations is not None
        needs_llm = any(v is None or (isinstance(v, list) and not v) for k, v in pref.items() if k != "comparison_indices")

        if self.client and (is_ambiguous or needs_llm):
            logger.debug("Attempting contextual extraction with LLM...")
            llm_pref = await self._extract_with_llm(text, history, last_recommendations)
            
            # Merge
            if llm_pref.get("risk_level") and not pref["risk_level"]:
                pref["risk_level"] = llm_pref["risk_level"]
            if llm_pref.get("investment_horizon_years") and not pref["investment_horizon_years"]:
                pref["investment_horizon_years"] = llm_pref["investment_horizon_years"]
            if llm_pref.get("categories") and not pref["categories"]:
                pref["categories"] = llm_pref["categories"]
        
        # Specific check for comparison indices if intent is likely comparison but deterministic failed
        if "compare" in clean_text and not pref["comparison_indices"] and self.client:
            pref["comparison_indices"] = await self._extract_comparison_indices(text, last_recommendations)

        logger.info(f"Final Normalized Preferences: {pref}")
        return pref
