"""
Database operations for the Contract Review Agent using SQLite.
"""
import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "contracts.db")


def get_connection() -> sqlite3.Connection:
    """Get SQLite connection with row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Initialize the database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                upload_date TEXT NOT NULL,
                contract_type TEXT,
                parties TEXT,
                duration TEXT,
                key_dates TEXT,
                contract_value TEXT,
                governing_law TEXT,
                risk_score REAL DEFAULT 0,
                full_text TEXT,
                summary_json TEXT,
                clauses_json TEXT,
                risks_json TEXT,
                missing_clauses_json TEXT,
                plain_english TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                task_name TEXT NOT NULL,
                model_used TEXT NOT NULL,
                reason TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                timestamp TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
            );

            CREATE TABLE IF NOT EXISTS memory_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT NOT NULL,
                flagged_clauses TEXT DEFAULT '[]',
                risk_preferences TEXT DEFAULT '{}',
                notes TEXT DEFAULT '',
                timestamp TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (contract_id) REFERENCES contracts(id)
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_contracts_upload_date ON contracts(upload_date DESC);
            CREATE INDEX IF NOT EXISTS idx_chat_contract ON chat_history(contract_id);
            CREATE INDEX IF NOT EXISTS idx_audit_contract ON audit_log(contract_id);
        """)
    logger.info("Database initialized at %s", DB_PATH)


def save_contract(contract_data: Dict[str, Any]) -> bool:
    """Save or update a contract record."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO contracts (
                    id, filename, upload_date, contract_type, parties,
                    duration, key_dates, contract_value, governing_law,
                    risk_score, full_text, summary_json, clauses_json,
                    risks_json, missing_clauses_json, plain_english
                ) VALUES (
                    :id, :filename, :upload_date, :contract_type, :parties,
                    :duration, :key_dates, :contract_value, :governing_law,
                    :risk_score, :full_text, :summary_json, :clauses_json,
                    :risks_json, :missing_clauses_json, :plain_english
                )
            """, contract_data)
        return True
    except Exception as e:
        logger.error("Error saving contract: %s", e)
        return False


def get_contract(contract_id: str) -> Optional[Dict]:
    """Get a contract by ID."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM contracts WHERE id = ?", (contract_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error("Error fetching contract: %s", e)
        return None


def get_all_contracts() -> List[Dict]:
    """Get all contracts ordered by upload date."""
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT id, filename, upload_date, contract_type,
                       risk_score, parties
                FROM contracts
                ORDER BY upload_date DESC
                LIMIT 50
            """).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("Error fetching contracts: %s", e)
        return []


def save_chat_message(contract_id: str, role: str, content: str) -> bool:
    """Save a chat message."""
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_history (contract_id, role, content) VALUES (?, ?, ?)",
                (contract_id, role, content)
            )
        return True
    except Exception as e:
        logger.error("Error saving chat message: %s", e)
        return False


def get_chat_history(contract_id: str) -> List[Dict]:
    """Get chat history for a contract."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM chat_history WHERE contract_id = ? ORDER BY timestamp",
                (contract_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("Error fetching chat history: %s", e)
        return []


def save_audit_entry(contract_id: str, entry: Dict[str, Any]) -> bool:
    """Save an audit log entry."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO audit_log (contract_id, task_type, task_name, model_used, reason, duration_ms, success)
                VALUES (:contract_id, :task_type, :task_name, :model_used, :reason, :duration_ms, :success)
            """, {**entry, "contract_id": contract_id})
        return True
    except Exception as e:
        logger.error("Error saving audit entry: %s", e)
        return False


def get_audit_log(contract_id: str) -> List[Dict]:
    """Get audit log for a contract."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE contract_id = ? ORDER BY timestamp",
                (contract_id,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error("Error fetching audit log: %s", e)
        return []


def save_memory(contract_id: str, flagged_clauses: List[str],
                risk_preferences: Dict, notes: str) -> bool:
    """Save memory entry for a contract."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO memory_store (contract_id, flagged_clauses, risk_preferences, notes)
                VALUES (?, ?, ?, ?)
            """, (
                contract_id,
                json.dumps(flagged_clauses),
                json.dumps(risk_preferences),
                notes
            ))
        return True
    except Exception as e:
        logger.error("Error saving memory: %s", e)
        return False


def get_all_memories() -> List[Dict]:
    """Get all memory entries."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memory_store ORDER BY timestamp DESC"
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["flagged_clauses"] = json.loads(d.get("flagged_clauses", "[]"))
                d["risk_preferences"] = json.loads(d.get("risk_preferences", "{}"))
                result.append(d)
            return result
    except Exception as e:
        logger.error("Error fetching memories: %s", e)
        return []


def get_user_preference(key: str, default: Any = None) -> Any:
    """Get a user preference value."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?", (key,)
            ).fetchone()
            return json.loads(row["value"]) if row else default
    except Exception as e:
        logger.error("Error fetching preference: %s", e)
        return default


def set_user_preference(key: str, value: Any) -> bool:
    """Set a user preference value."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """, (key, json.dumps(value)))
        return True
    except Exception as e:
        logger.error("Error setting preference: %s", e)
        return False


def delete_contract(contract_id: str) -> bool:
    """Delete a contract and its related data."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM chat_history WHERE contract_id = ?", (contract_id,))
            conn.execute("DELETE FROM audit_log WHERE contract_id = ?", (contract_id,))
            conn.execute("DELETE FROM memory_store WHERE contract_id = ?", (contract_id,))
            conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
        return True
    except Exception as e:
        logger.error("Error deleting contract: %s", e)
        return False


def get_flagged_clauses_history() -> List[str]:
    """Get all historically flagged clauses across sessions."""
    try:
        memories = get_all_memories()
        all_flagged = []
        for m in memories:
            all_flagged.extend(m.get("flagged_clauses", []))
        return list(set(all_flagged))
    except Exception as e:
        logger.error("Error fetching flagged clauses: %s", e)
        return []
