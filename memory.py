"""
Hindsight Memory System for Contract Review Agent.
Tracks user preferences, flagged clauses, and patterns across sessions.
"""
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

import database as db

logger = logging.getLogger(__name__)

MEMORY_STORE_DIR = os.path.join(os.path.dirname(__file__), "memory_store")
os.makedirs(MEMORY_STORE_DIR, exist_ok=True)


class HindsightMemory:
    """
    Implements cross-session memory for contract review patterns.
    Remembers user preferences, repeatedly flagged clauses, and risk patterns.
    """

    def __init__(self):
        self.session_flags: List[str] = []
        self.session_preferences: Dict[str, str] = {}
        self._load_preferences()

    def _load_preferences(self):
        """Load stored preferences from database."""
        self.session_preferences = db.get_user_preference("risk_preferences", {})

    def flag_clause(self, clause_name: str, reason: str = "", contract_id: str = ""):
        """Mark a clause as risky/concerning for this session."""
        if clause_name not in self.session_flags:
            self.session_flags.append(clause_name)
        logger.info("Flagged clause: %s", clause_name)

    def save_session(self, contract_id: str, notes: str = ""):
        """Persist current session flags to database."""
        if self.session_flags:
            db.save_memory(
                contract_id=contract_id,
                flagged_clauses=self.session_flags,
                risk_preferences=self.session_preferences,
                notes=notes
            )
            logger.info("Saved session memory for contract %s", contract_id)

    def get_historical_flags(self) -> List[str]:
        """Get all historically flagged clauses across all sessions."""
        return db.get_flagged_clauses_history()

    def get_memory_context(self, current_clauses: List[str] = None) -> str:
        """
        Build a memory context string to inject into prompts.
        Warns about previously flagged clauses.
        """
        historical = self.get_historical_flags()
        if not historical:
            return ""

        context_parts = []

        if historical:
            context_parts.append(
                f"The user has previously flagged these clause types as risky: {', '.join(historical)}. "
                "Mention this history when analyzing similar clauses."
            )

        if current_clauses:
            overlap = [c for c in current_clauses if any(
                h.lower() in c.lower() or c.lower() in h.lower()
                for h in historical
            )]
            if overlap:
                context_parts.append(
                    f"NOTE: This contract contains clauses similar to ones previously flagged: {', '.join(overlap)}. "
                    "Alert the user with: 'You previously flagged similar clauses as high risk.'"
                )

        return " ".join(context_parts)

    def check_for_previously_flagged(self, clause_name: str) -> Optional[str]:
        """
        Check if a clause type was previously flagged.
        Returns a warning message if yes, None if no.
        """
        historical = self.get_historical_flags()
        for flagged in historical:
            if flagged.lower() in clause_name.lower() or clause_name.lower() in flagged.lower():
                return f"⚠️ **Memory Alert:** You previously flagged **{flagged}** clauses as high risk in a past contract review."
        return None

    def set_preference(self, key: str, value: str):
        """Set a user preference."""
        self.session_preferences[key] = value
        db.set_user_preference("risk_preferences", self.session_preferences)

    def get_preference(self, key: str, default: str = "") -> str:
        """Get a user preference."""
        return self.session_preferences.get(key, default)

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of stored memory for display."""
        all_memories = db.get_all_memories()
        historical_flags = self.get_historical_flags()

        return {
            "total_reviews": len(all_memories),
            "historical_flags": historical_flags,
            "risk_preferences": self.session_preferences,
            "recent_notes": [m.get("notes", "") for m in all_memories[-3:] if m.get("notes")],
        }

    def clear_session(self):
        """Clear current session memory."""
        self.session_flags = []

    def get_risk_insight(self, risk_type: str) -> str:
        """
        Return personalized insight based on memory.
        """
        historical = self.get_historical_flags()
        risk_lower = risk_type.lower()

        for flagged in historical:
            if flagged.lower() in risk_lower or risk_lower in flagged.lower():
                return (
                    f"💡 **Hindsight Insight:** Based on your review history, "
                    f"you've consistently flagged **{flagged}** as a concern. "
                    f"Pay close attention to this clause."
                )
        return ""

    def record_contract_pattern(self, contract_type: str, high_risk_clauses: List[str]):
        """Record patterns from a completed review for future reference."""
        patterns = db.get_user_preference("contract_patterns", {})
        if contract_type not in patterns:
            patterns[contract_type] = {"count": 0, "common_risks": []}

        patterns[contract_type]["count"] += 1
        for clause in high_risk_clauses:
            if clause not in patterns[contract_type]["common_risks"]:
                patterns[contract_type]["common_risks"].append(clause)

        db.set_user_preference("contract_patterns", patterns)

    def get_pattern_insight(self, contract_type: str) -> str:
        """Get insights based on past contracts of same type."""
        patterns = db.get_user_preference("contract_patterns", {})
        if contract_type in patterns and patterns[contract_type]["count"] > 0:
            common_risks = patterns[contract_type].get("common_risks", [])
            count = patterns[contract_type]["count"]
            if common_risks:
                return (
                    f"📊 **Pattern Insight:** You've reviewed {count} similar {contract_type}(s) before. "
                    f"Common risks in past reviews: {', '.join(common_risks[:3])}. "
                    f"Watch for these patterns."
                )
        return ""
