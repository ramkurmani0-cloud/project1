"""
Clause extraction module for Contract Review Agent.
Handles parsing and structuring of extracted clause data.
"""
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

IMPORTANT_CLAUSES = [
    "Confidentiality / NDA",
    "Intellectual Property Ownership",
    "Termination",
    "Dispute Resolution",
    "Indemnification",
    "Limitation of Liability",
    "Force Majeure",
    "Governing Law",
    "Non-Compete",
    "Data Protection / Privacy",
    "Assignment",
    "Warranties",
]


def parse_summary_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON response from summary analysis."""
    try:
        cleaned = _clean_json_response(response_text)
        data = json.loads(cleaned)
        return {
            "contract_type": data.get("contract_type", "Unknown"),
            "parties": data.get("parties", []),
            "duration": data.get("duration", "Not specified"),
            "key_dates": data.get("key_dates", []),
            "contract_value": data.get("contract_value", "Not specified"),
            "governing_law": data.get("governing_law", "Not specified"),
        }
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse summary JSON: %s", e)
        return _extract_summary_fallback(response_text)


def parse_clauses_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON response from clause extraction."""
    try:
        cleaned = _clean_json_response(response_text)
        data = json.loads(cleaned)

        clause_keys = [
            "payment_terms", "confidentiality", "termination",
            "liability", "intellectual_property", "dispute_resolution"
        ]

        result = {}
        for key in clause_keys:
            clause = data.get(key, {})
            result[key] = {
                "present": bool(clause.get("present", False)),
                "content": clause.get("content") or "Not found in contract",
                "summary": clause.get("summary") or "Not available"
            }
        return result
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse clauses JSON: %s", e)
        return _default_clauses()


def parse_risk_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON response from risk analysis."""
    try:
        cleaned = _clean_json_response(response_text)
        data = json.loads(cleaned)
        return {
            "overall_score": float(data.get("overall_score", 50)),
            "summary": data.get("summary", "Risk analysis completed."),
            "high_risks": _normalize_risks(data.get("high_risks", [])),
            "medium_risks": _normalize_risks(data.get("medium_risks", [])),
            "low_risks": _normalize_risks(data.get("low_risks", [])),
        }
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse risk JSON: %s", e)
        return {
            "overall_score": 50,
            "summary": response_text[:500],
            "high_risks": [],
            "medium_risks": [],
            "low_risks": [],
        }


def parse_missing_clauses_response(response_text: str) -> Dict[str, Any]:
    """Parse the JSON response from missing clause detection."""
    try:
        cleaned = _clean_json_response(response_text)
        data = json.loads(cleaned)
        return {
            "missing_clauses": data.get("missing_clauses", []),
            "present_clauses": data.get("present_clauses", []),
        }
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse missing clauses JSON: %s", e)
        return {"missing_clauses": [], "present_clauses": []}


def _normalize_risks(risks: list) -> list:
    """Normalize risk items to consistent format."""
    normalized = []
    for r in risks:
        if isinstance(r, dict):
            normalized.append({
                "clause": r.get("clause", "Unknown clause"),
                "explanation": r.get("explanation", "No explanation provided"),
                "recommendation": r.get("recommendation", "Review with legal counsel"),
            })
    return normalized


def _clean_json_response(text: str) -> str:
    """Remove markdown code blocks and clean up JSON response."""
    # Remove ```json ... ``` blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]

    return text


def _extract_summary_fallback(text: str) -> Dict[str, Any]:
    """Fallback extraction when JSON parsing fails."""
    return {
        "contract_type": _extract_pattern(text, r'contract.type[:\s]+([^\n]+)', "Unknown"),
        "parties": [],
        "duration": _extract_pattern(text, r'duration[:\s]+([^\n]+)', "Not specified"),
        "key_dates": [],
        "contract_value": _extract_pattern(text, r'value[:\s]+([^\n]+)', "Not specified"),
        "governing_law": _extract_pattern(text, r'governing.law[:\s]+([^\n]+)', "Not specified"),
    }


def _extract_pattern(text: str, pattern: str, default: str) -> str:
    """Extract text using regex pattern with default fallback."""
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def _default_clauses() -> Dict[str, Any]:
    """Return default clause structure when parsing fails."""
    default_clause = {"present": False, "content": "Could not extract", "summary": "Analysis unavailable"}
    return {
        "payment_terms": default_clause.copy(),
        "confidentiality": default_clause.copy(),
        "termination": default_clause.copy(),
        "liability": default_clause.copy(),
        "intellectual_property": default_clause.copy(),
        "dispute_resolution": default_clause.copy(),
    }


def get_clause_display_name(key: str) -> str:
    """Convert clause key to display name."""
    names = {
        "payment_terms": "💰 Payment Terms",
        "confidentiality": "🔒 Confidentiality",
        "termination": "🚪 Termination",
        "liability": "⚖️ Liability",
        "intellectual_property": "💡 Intellectual Property",
        "dispute_resolution": "🏛️ Dispute Resolution",
    }
    return names.get(key, key.replace("_", " ").title())


def assess_clause_risk(clause_key: str, clause_data: Dict) -> str:
    """Assess risk level of a clause."""
    if not clause_data.get("present", False):
        high_risk_if_missing = ["confidentiality", "termination", "dispute_resolution", "liability"]
        if clause_key in high_risk_if_missing:
            return "HIGH"
        return "MEDIUM"
    return "OK"
