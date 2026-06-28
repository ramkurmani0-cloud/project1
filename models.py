"""
Data models for the Contract Review Agent.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    HIGH = "High Risk"
    MEDIUM = "Medium Risk"
    LOW = "Low Risk"


class TaskType(Enum):
    SIMPLE = "Simple"
    ADVANCED = "Advanced"


@dataclass
class RiskItem:
    level: RiskLevel
    clause: str
    explanation: str
    recommendation: str


@dataclass
class ClauseInfo:
    name: str
    present: bool
    content: Optional[str] = None
    summary: Optional[str] = None


@dataclass
class ContractSummary:
    contract_type: str
    parties: List[str]
    duration: str
    key_dates: List[str]
    contract_value: str
    governing_law: str
    raw_text: str


@dataclass
class ClauseExtraction:
    payment_terms: ClauseInfo
    confidentiality: ClauseInfo
    termination: ClauseInfo
    liability: ClauseInfo
    intellectual_property: ClauseInfo
    dispute_resolution: ClauseInfo


@dataclass
class RiskAnalysis:
    overall_score: float  # 0-100
    high_risks: List[RiskItem]
    medium_risks: List[RiskItem]
    low_risks: List[RiskItem]
    summary: str


@dataclass
class MissingClause:
    name: str
    importance: str
    recommendation: str


@dataclass
class AuditLogEntry:
    timestamp: datetime
    task_type: TaskType
    task_name: str
    model_used: str
    reason: str
    duration_ms: int
    success: bool


@dataclass
class ContractReview:
    contract_id: str
    filename: str
    upload_date: datetime
    summary: Optional[ContractSummary] = None
    clauses: Optional[ClauseExtraction] = None
    risks: Optional[RiskAnalysis] = None
    missing_clauses: List[MissingClause] = field(default_factory=list)
    plain_english: Optional[str] = None
    audit_log: List[AuditLogEntry] = field(default_factory=list)
    full_text: str = ""


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MemoryEntry:
    contract_id: str
    flagged_clauses: List[str]
    risk_preferences: Dict[str, str]
    notes: str
    timestamp: datetime = field(default_factory=datetime.now)
