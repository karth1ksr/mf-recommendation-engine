import re

def normalize_name(name: str) -> str:
    """
    Standardizes fund names for matching across different data sources.
    - Lowers case
    - Replaces '&' with 'and'
    - Replaces '-' with ' '
    - Removes multiple spaces
    - Trims whitespace
    """
    if not name:
        return ""
    
    name = name.lower()
    name = name.replace("&", "and")
    name = name.replace("-", " ")
    
    # Remove multiple spaces
    name = re.sub(r"\s+", " ", name)
    
    return name.strip()

def extract_base_name(full_name: str) -> str:
    """
    Extracts the core fund name by removing plan and option details.
    Example: "Axis Bluechip Fund - Direct Plan - Growth" -> "Axis Bluechip Fund"
    """
    # Common delimiters for plan/option parts
    delimiters = [" - ", " (", " – "]
    
    base_name = full_name
    for d in delimiters:
        if d in base_name:
            base_name = base_name.split(d)[0]
            
    # Also handle hyphens without spaces if needed
    if " - " not in base_name and "-" in base_name:
        # But be careful not to split names like "ICICI-Prudential"
        # Usually, plan info starts with "- Direct" or "- Regular"
        parts = base_name.split("-")
        if len(parts) > 1:
            # Check if the second part looks like a plan
            second_part = parts[1].strip().lower()
            if any(p in second_part for p in ["direct", "regular", "plan"]):
                base_name = parts[0]
                
    return base_name.strip()
