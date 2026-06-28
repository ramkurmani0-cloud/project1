"""
Risk analysis utilities for Contract Review Agent.
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def get_risk_color(score: float) -> str:
    """Get color code based on risk score."""
    if score >= 70:
        return "#FF4B4B"   # Red - High risk
    elif score >= 40:
        return "#FFA500"   # Orange - Medium risk
    else:
        return "#00C853"   # Green - Low risk


def get_risk_label(score: float) -> str:
    """Get risk label based on score."""
    if score >= 70:
        return "🔴 HIGH RISK"
    elif score >= 40:
        return "🟡 MEDIUM RISK"
    else:
        return "🟢 LOW RISK"


def get_risk_emoji(level: str) -> str:
    """Get emoji for risk level string."""
    level_lower = level.lower()
    if "high" in level_lower:
        return "🔴"
    elif "medium" in level_lower:
        return "🟡"
    elif "low" in level_lower:
        return "🟢"
    return "⚪"


def calculate_composite_score(
    risk_data: Dict[str, Any],
    missing_clauses: List[Dict],
    clauses_data: Dict[str, Any]
) -> float:
    """
    Calculate a composite risk score from multiple factors.
    """
    base_score = float(risk_data.get("overall_score", 50))

    # Penalty for missing critical clauses
    critical_missing = [
        c for c in missing_clauses
        if c.get("importance", "").lower() == "critical"
    ]
    important_missing = [
        c for c in missing_clauses
        if c.get("importance", "").lower() == "important"
    ]

    missing_penalty = len(critical_missing) * 8 + len(important_missing) * 4

    # Factor in clause presence
    high_value_clauses = ["confidentiality", "termination", "dispute_resolution", "liability"]
    missing_high_value = sum(
        1 for k in high_value_clauses
        if not clauses_data.get(k, {}).get("present", True)
    )
    clause_penalty = missing_high_value * 5

    # High risk items count
    high_risk_count = len(risk_data.get("high_risks", []))
    risk_count_bonus = high_risk_count * 3

    composite = base_score + missing_penalty + clause_penalty + risk_count_bonus
    return min(100.0, max(0.0, composite))


def generate_risk_badge(score: float) -> Dict[str, str]:
    """Generate risk badge display info."""
    if score >= 70:
        return {
            "label": "HIGH RISK",
            "color": "#FF4B4B",
            "bg": "#FFF0F0",
            "icon": "🔴"
        }
    elif score >= 40:
        return {
            "label": "MEDIUM RISK",
            "color": "#FF8C00",
            "bg": "#FFF8F0",
            "icon": "🟡"
        }
    else:
        return {
            "label": "LOW RISK",
            "color": "#00C853",
            "bg": "#F0FFF4",
            "icon": "🟢"
        }


def prioritize_risks(risk_data: Dict[str, Any]) -> List[Dict]:
    """Return all risks sorted by severity."""
    all_risks = []

    for risk in risk_data.get("high_risks", []):
        all_risks.append({**risk, "level": "High", "priority": 1})

    for risk in risk_data.get("medium_risks", []):
        all_risks.append({**risk, "level": "Medium", "priority": 2})

    for risk in risk_data.get("low_risks", []):
        all_risks.append({**risk, "level": "Low", "priority": 3})

    return sorted(all_risks, key=lambda x: x["priority"])


def get_quick_stats(risk_data: Dict[str, Any], missing_data: Dict[str, Any]) -> Dict[str, int]:
    """Get quick statistics for dashboard display."""
    return {
        "high_risks": len(risk_data.get("high_risks", [])),
        "medium_risks": len(risk_data.get("medium_risks", [])),
        "low_risks": len(risk_data.get("low_risks", [])),
        "missing_critical": len([
            c for c in missing_data.get("missing_clauses", [])
            if c.get("importance", "").lower() == "critical"
        ]),
        "missing_important": len([
            c for c in missing_data.get("missing_clauses", [])
            if c.get("importance", "").lower() == "important"
        ]),
    }


def format_risk_summary_for_chat(risk_data: Dict, score: float) -> str:
    """Format risk data as a readable chat message."""
    badge = generate_risk_badge(score)
    lines = [
        f"**{badge['icon']} Overall Risk Score: {score:.0f}/100 ({badge['label']})**",
        "",
        risk_data.get("summary", ""),
        "",
    ]

    highs = risk_data.get("high_risks", [])
    if highs:
        lines.append("**🔴 High Risk Issues:**")
        for r in highs:
            lines.append(f"- **{r['clause']}**: {r['explanation']}")
        lines.append("")

    meds = risk_data.get("medium_risks", [])
    if meds:
        lines.append("**🟡 Medium Risk Issues:**")
        for r in meds:
            lines.append(f"- **{r['clause']}**: {r['explanation']}")
        lines.append("")

    lows = risk_data.get("low_risks", [])
    if lows:
        lines.append("**🟢 Low Risk Issues:**")
        for r in lows:
            lines.append(f"- **{r['clause']}**: {r['explanation']}")

    return "\n".join(lines)
