"""
Groq API client for the Contract Review Agent.
Handles all LLM interactions with intelligent routing.
"""
import logging
import os
import time
import json
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Model routing config
SIMPLE_MODEL = "llama-3.3-70b-versatile"
ADVANCED_MODEL = "llama-3.3-70b-versatile"

class GroqClient:
    """Manages Groq API interactions with CascadeFlow routing."""

    def __init__(self):
        try:
            import streamlit as st
            self.api_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
        except Exception:
            self.api_key = os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            logger.warning("Groq API key not provided. Set GROQ_API_KEY in your .env file.")
            self.client = None
        else:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info("Groq client initialized successfully.")
            except ImportError:
                logger.error("groq package not installed. Run: pip install groq")
                self.client = None
            except Exception as e:
                logger.error("Failed to initialize Groq client: %s", e)
                self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def _route_task(self, task_type: str) -> Tuple[str, str, str]:
        """
        CascadeFlow: Route tasks to appropriate model.
        Returns (model, task_category, reason)
        """
        simple_tasks = {
            "summary": (SIMPLE_MODEL, "Simple", "Contract summarization is structured extraction — fast model sufficient."),
            "clause_extraction": (SIMPLE_MODEL, "Simple", "Clause extraction follows patterns — optimized with fast model."),
            "plain_english": (SIMPLE_MODEL, "Simple", "Language translation is straightforward — fast model handles well."),
            "chat": (SIMPLE_MODEL, "Simple", "Conversational Q&A uses fast model for low latency."),
        }
        advanced_tasks = {
            "risk_analysis": (ADVANCED_MODEL, "Advanced", "Risk analysis requires nuanced legal judgment — advanced model used."),
            "missing_clauses": (ADVANCED_MODEL, "Advanced", "Missing clause detection needs comprehensive legal knowledge — advanced model used."),
            "negotiation": (ADVANCED_MODEL, "Advanced", "Negotiation strategy requires sophisticated reasoning — advanced model used."),
        }

        if task_type in simple_tasks:
            return simple_tasks[task_type]
        elif task_type in advanced_tasks:
            return advanced_tasks[task_type]
        else:
            return (ADVANCED_MODEL, "Advanced", f"Unknown task '{task_type}' — defaulting to advanced model for safety.")

    def complete(self, prompt: str, task_type: str = "chat",
                 system_prompt: str = "", max_tokens: int = 2048,
                 temperature: float = 0.1) -> Tuple[str, Dict]:
        """
        Send a completion request with CascadeFlow routing.
        Returns (response_text, audit_info)
        """
        if not self.is_available():
            return (
                "⚠️ Groq API not available. Please set your GROQ_API_KEY in the .env file.",
                {"task_type": "N/A", "model": "N/A", "reason": "API not configured", "duration_ms": 0, "success": False}
            )

        model, category, reason = self._route_task(task_type)

        default_system = """You are an expert legal contract analyst with 20+ years of experience.
You analyze contracts thoroughly, identify risks clearly, and explain legal concepts in plain English.
Always be precise, structured, and helpful. Format responses clearly using markdown."""

        messages = [
            {"role": "user", "content": prompt}
        ]

        start_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt or default_system},
                    *messages
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            text = response.choices[0].message.content or ""

            audit_info = {
                "task_type": category,
                "task_name": task_type,
                "model": model,
                "reason": reason,
                "duration_ms": duration_ms,
                "success": True,
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
            logger.info("Task '%s' completed in %dms using %s", task_type, duration_ms, model)
            return text, audit_info

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Groq API error for task '%s': %s", task_type, e)
            error_msg = f"⚠️ API Error: {str(e)}"
            audit_info = {
                "task_type": category,
                "task_name": task_type,
                "model": model,
                "reason": reason,
                "duration_ms": duration_ms,
                "success": False
            }
            return error_msg, audit_info

    def analyze_summary(self, contract_text: str) -> Tuple[str, Dict]:
        prompt = f"""Analyze this contract and extract key information.

CONTRACT TEXT:
{contract_text}

Respond in valid JSON format ONLY (no markdown, no explanation):
{{
  "contract_type": "e.g. Service Agreement, NDA, Employment Contract",
  "parties": ["Party 1 name and role", "Party 2 name and role"],
  "duration": "contract duration or term",
  "key_dates": ["date 1 with context", "date 2 with context"],
  "contract_value": "monetary value or compensation details",
  "governing_law": "jurisdiction/governing law"
}}"""
        return self.complete(prompt, task_type="summary", temperature=0.0)

    def extract_clauses(self, contract_text: str) -> Tuple[str, Dict]:
        prompt = f"""Extract specific clauses from this contract.

CONTRACT TEXT:
{contract_text}

Respond in valid JSON format ONLY:
{{
  "payment_terms": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }},
  "confidentiality": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }},
  "termination": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }},
  "liability": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }},
  "intellectual_property": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }},
  "dispute_resolution": {{
    "present": true/false,
    "content": "exact clause text or null",
    "summary": "one sentence summary"
  }}
}}"""
        return self.complete(prompt, task_type="clause_extraction", temperature=0.0)

    def analyze_risks(self, contract_text: str, memory_context: str = "") -> Tuple[str, Dict]:
        memory_section = f"\nUSER HISTORY CONTEXT:\n{memory_context}\n" if memory_context else ""
        prompt = f"""Perform a comprehensive risk analysis of this contract.
{memory_section}
CONTRACT TEXT:
{contract_text}

Respond in valid JSON format ONLY:
{{
  "overall_score": 75,
  "summary": "Overall risk assessment in 2-3 sentences",
  "high_risks": [
    {{
      "clause": "clause name",
      "explanation": "why this is risky",
      "recommendation": "what to do about it"
    }}
  ],
  "medium_risks": [
    {{
      "clause": "clause name",
      "explanation": "why this is concerning",
      "recommendation": "suggested action"
    }}
  ],
  "low_risks": [
    {{
      "clause": "clause name",
      "explanation": "minor concern",
      "recommendation": "optional improvement"
    }}
  ]
}}

Score: 0=no risk, 100=extreme risk. Be thorough and specific."""
        return self.complete(prompt, task_type="risk_analysis", temperature=0.1)

    def detect_missing_clauses(self, contract_text: str) -> Tuple[str, Dict]:
        prompt = f"""Check this contract for missing important clauses.

CONTRACT TEXT:
{contract_text}

Respond in valid JSON format ONLY:
{{
  "missing_clauses": [
    {{
      "name": "Clause Name",
      "importance": "Critical/Important/Recommended",
      "recommendation": "Why needed and what to add"
    }}
  ],
  "present_clauses": ["list of important clauses that ARE present"]
}}

Check for: Confidentiality/NDA, IP Ownership, Termination, Dispute Resolution,
Indemnification, Force Majeure, Limitation of Liability, Governing Law,
Amendment Procedure, Assignment Rights, Warranty, Data Protection."""
        return self.complete(prompt, task_type="missing_clauses", temperature=0.0)

    def translate_to_plain_english(self, contract_text: str) -> Tuple[str, Dict]:
        prompt = f"""Translate this legal contract into plain, simple English that anyone can understand.

CONTRACT TEXT:
{contract_text[:8000]}

Write a clear, friendly explanation covering:
1. What this contract is about
2. What each party must do
3. Key obligations and rights
4. Important restrictions
5. What happens if things go wrong

Use simple language. Avoid legal jargon. Use bullet points where helpful.
Start with: "In simple terms, this contract means..."
"""
        return self.complete(prompt, task_type="plain_english", temperature=0.3, max_tokens=1500)

    def chat(self, question: str, contract_text: str, history: list = None) -> Tuple[str, Dict]:
        history_text = ""
        if history:
            recent = history[-6:]  # Last 3 exchanges
            history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent])

        prompt = f"""You are a helpful contract analyst. Answer questions about this contract.

CONTRACT:
{contract_text[:10000]}

{'CONVERSATION HISTORY:' + history_text if history_text else ''}

USER QUESTION: {question}

Provide a clear, helpful answer based on the contract. Be specific and cite relevant clauses."""
        return self.complete(prompt, task_type="chat", temperature=0.2, max_tokens=1000)

    def get_negotiation_tips(self, contract_text: str, risk_summary: str = "") -> Tuple[str, Dict]:
        prompt = f"""As an experienced contract negotiator, provide specific negotiation advice.

CONTRACT:
{contract_text[:8000]}

{f'RISK SUMMARY: {risk_summary}' if risk_summary else ''}

Provide:
1. **Top 5 negotiation priorities** (most important clauses to push back on)
2. **Specific language improvements** for risky clauses
3. **Clauses to add** that protect the reviewer's interests
4. **Red lines** (terms that should be deal-breakers)
5. **Quick wins** (easy improvements the other party will likely accept)

Be specific and actionable."""
        return self.complete(prompt, task_type="negotiation", temperature=0.2, max_tokens=1500)
