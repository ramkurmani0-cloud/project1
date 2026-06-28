"""
PDF parsing module for the Contract Review Agent.
Supports both pdfplumber and PyPDF2 as fallback.
"""
import logging
import io
import re
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> Tuple[str, str]:
    """
    Extract text from PDF bytes.
    Returns (extracted_text, method_used)
    Tries pdfplumber first, then PyPDF2 as fallback.
    """
    text, method = _try_pdfplumber(file_bytes)
    if text and len(text.strip()) > 100:
        return text, method

    text, method = _try_pypdf2(file_bytes)
    if text and len(text.strip()) > 100:
        return text, method

    return _try_basic_extraction(file_bytes)


def _try_pdfplumber(file_bytes: bytes) -> Tuple[str, str]:
    """Try extracting with pdfplumber."""
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
        full_text = "\n\n".join(pages_text)
        logger.info("pdfplumber extracted %d chars", len(full_text))
        return full_text, "pdfplumber"
    except ImportError:
        logger.warning("pdfplumber not installed")
        return "", "failed"
    except Exception as e:
        logger.warning("pdfplumber failed: %s", e)
        return "", "failed"


def _try_pypdf2(file_bytes: bytes) -> Tuple[str, str]:
    """Try extracting with PyPDF2."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        full_text = "\n\n".join(pages_text)
        logger.info("PyPDF2 extracted %d chars", len(full_text))
        return full_text, "PyPDF2"
    except ImportError:
        logger.warning("PyPDF2 not installed")
        return "", "failed"
    except Exception as e:
        logger.warning("PyPDF2 failed: %s", e)
        return "", "failed"


def _try_basic_extraction(file_bytes: bytes) -> Tuple[str, str]:
    """Last resort: extract printable characters."""
    try:
        text = file_bytes.decode("latin-1", errors="ignore")
        printable = re.sub(r'[^\x20-\x7E\n\r\t]', ' ', text)
        cleaned = re.sub(r' {3,}', ' ', printable)
        cleaned = re.sub(r'\n{4,}', '\n\n', cleaned)
        logger.warning("Used basic extraction, quality may be poor")
        return cleaned, "basic"
    except Exception as e:
        logger.error("Basic extraction failed: %s", e)
        return "Could not extract text from PDF.", "none"


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    # Remove excessive whitespace
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Normalize line endings
    text = re.sub(r'\r\n', '\n', text)
    # Remove excessive blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Remove page number artifacts
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 12000) -> str:
    """
    Return a representative chunk of text for API analysis.
    Prioritizes beginning and end of document where key clauses often appear.
    """
    if len(text) <= max_chars:
        return text

    # Take first 60% and last 40% for better coverage
    first_part = int(max_chars * 0.6)
    last_part = max_chars - first_part

    start = text[:first_part]
    end = text[-last_part:]

    return f"{start}\n\n[... middle section truncated for analysis ...]\n\n{end}"


def get_page_count(file_bytes: bytes) -> int:
    """Get the number of pages in a PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return len(pdf.pages)
    except Exception:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return len(reader.pages)
    except Exception:
        return 0


def get_pdf_metadata(file_bytes: bytes) -> dict:
    """Extract metadata from PDF."""
    metadata = {}
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        info = reader.metadata
        if info:
            metadata = {
                "title": getattr(info, "title", ""),
                "author": getattr(info, "author", ""),
                "subject": getattr(info, "subject", ""),
                "creator": getattr(info, "creator", ""),
            }
    except Exception:
        pass
    return metadata
