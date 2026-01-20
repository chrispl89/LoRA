"""
Guardrails for content filtering - MVP implementation.
Blocks keywords related to children and NSFW content.
"""
from typing import List, Set
import re


# Keywords related to children (case-insensitive)
CHILD_KEYWORDS: Set[str] = {
    "child", "children", "kid", "kids", "minor", "minors",
    "teenager", "teen", "teenage", "adolescent", "youth",
    "youngster", "baby", "babies", "infant", "toddler",
    "underage", "under-aged", "nieletni", "dziecko", "dzieci"
}

# NSFW keywords (basic MVP list)
NSFW_KEYWORDS: Set[str] = {
    "nude", "naked", "nudity", "porn", "pornography",
    "explicit", "sexual", "sex", "xxx", "nsfw",
    "erotic", "adult content"
}


def check_prompt_safety(prompt: str, negative_prompt: str = "") -> tuple[bool, List[str]]:
    """
    Check if prompt contains blocked keywords.
    
    Returns:
        (is_safe, violations)
    """
    violations: List[str] = []
    text = f"{prompt} {negative_prompt}".lower()
    
    # Check for child-related keywords
    for keyword in CHILD_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
            violations.append(f"Blocked keyword related to children: '{keyword}'")
    
    # Check for NSFW keywords
    for keyword in NSFW_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", text, re.IGNORECASE):
            violations.append(f"Blocked NSFW keyword: '{keyword}'")
    
    return len(violations) == 0, violations


def validate_consent(consent_confirmed: bool, subject_is_adult: bool) -> tuple[bool, str]:
    """
    Validate consent requirements.
    
    Returns:
        (is_valid, error_message)
    """
    if not consent_confirmed:
        return False, "consent_confirmed must be true"
    if not subject_is_adult:
        return False, "subject_is_adult must be true"
    return True, ""
