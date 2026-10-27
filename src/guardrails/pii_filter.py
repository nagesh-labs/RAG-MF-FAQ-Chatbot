"""
PII Sanitization and Redaction Module for Milestone RAG.
Detects and scrubs personal and financial identifiers (PAN, Aadhaar, Phone, Email,
Account/Folio numbers, OTPs) from incoming user queries before logging, vector search, or LLM transit.
"""

import re
from typing import List, Tuple

# Pre-compiled Regex Patterns for Financial & Personal Identifiers

# Permanent Account Number (PAN): 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", re.IGNORECASE)

# Aadhaar Number: 12 digits starting with 2-9, with optional spaces or hyphens (e.g. 2345 6789 0123)
AADHAAR_PATTERN = re.compile(r"\b[2-9]{1}[0-9]{3}[-\s]?[0-9]{4}[-\s]?[0-9]{4}\b")

# Indian Mobile Phone Numbers (+91 or starting with 6-9, 10 digits, formatted or unformatted)
PHONE_PATTERN = re.compile(
    r"(?:\+91[-\s]?)?[6-9]\d{4}[-\s]?\d{5}\b|(?:\+91[-\s]?)?[6-9]\d{9}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"
)

# Email Address
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

# Folio / Mutual Fund Account Number (with indicator keyword)
FOLIO_PATTERN = re.compile(
    r"\b(?:folio(?:\s*(?:no|number)(?:\.|\b)?)?|account\s*(?:no|number)?)\s*(?:is|:|=)?\s*([0-9]{6,12}(?:[/-][0-9]{1,4})?)\b",
    re.IGNORECASE,
)
# Bare folio format (e.g. 9876543/21 or 1234567-89)
FOLIO_BARE_PATTERN = re.compile(r"\b\d{6,10}[/-]\d{1,4}\b")

# One Time Password (OTP) patterns (e.g. "otp is 123456", "my OTP: 489201", "482910 is my OTP")
OTP_PREFIX_PATTERN = re.compile(
    r"\b(?:otp|passcode|verification\s*code|pin)\s*(?:is|:|=)?\s*([0-9]{4,8})\b",
    re.IGNORECASE,
)
OTP_SUFFIX_PATTERN = re.compile(
    r"\b([0-9]{4,8})\s*(?:is\s*(?:my\s*)?)?(?:otp|passcode|verification\s*code|pin)\b",
    re.IGNORECASE,
)


def sanitize_pii(text: str) -> Tuple[str, List[str]]:
    """
    Sanitize personal and financial identifiers from user query text.
    
    Args:
        text: Inbound raw user query.
        
    Returns:
        Tuple containing (sanitized_text, list_of_detected_pii_types).
    """
    if not text:
        return text, []

    detected: List[str] = []
    sanitized = text

    # 1. Redact OTPs
    otp_found = False
    if OTP_PREFIX_PATTERN.search(sanitized):
        sanitized = OTP_PREFIX_PATTERN.sub(
            lambda m: m.group(0).replace(m.group(1), "[REDACTED_OTP]"), sanitized
        )
        otp_found = True
    if OTP_SUFFIX_PATTERN.search(sanitized):
        sanitized = OTP_SUFFIX_PATTERN.sub(
            lambda m: m.group(0).replace(m.group(1), "[REDACTED_OTP]"), sanitized
        )
        otp_found = True
    if otp_found:
        detected.append("OTP")

    # 2. Redact PAN Card Numbers
    if PAN_PATTERN.search(sanitized):
        sanitized = PAN_PATTERN.sub("[REDACTED_PAN]", sanitized)
        detected.append("PAN")

    # 3. Redact Aadhaar Numbers
    if AADHAAR_PATTERN.search(sanitized):
        sanitized = AADHAAR_PATTERN.sub("[REDACTED_AADHAAR]", sanitized)
        detected.append("AADHAAR")

    # 4. Redact Email Addresses
    if EMAIL_PATTERN.search(sanitized):
        sanitized = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
        detected.append("EMAIL")

    # 5. Redact Phone Numbers
    if PHONE_PATTERN.search(sanitized):
        sanitized = PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
        detected.append("PHONE")

    # 6. Redact Folio / Account Numbers
    if FOLIO_PATTERN.search(sanitized):
        sanitized = FOLIO_PATTERN.sub(
            lambda m: m.group(0).replace(m.group(1), "[REDACTED_FOLIO]"), sanitized
        )
        detected.append("FOLIO")
    elif FOLIO_BARE_PATTERN.search(sanitized):
        sanitized = FOLIO_BARE_PATTERN.sub("[REDACTED_FOLIO]", sanitized)
        detected.append("FOLIO")

    return sanitized, detected


def has_pii(text: str) -> bool:
    """Check if any personal or financial identifiers are present in text."""
    _, detected = sanitize_pii(text)
    return len(detected) > 0


def is_otp_or_credential(text: str) -> bool:
    """Check if query contains authentication credentials or OTP tokens."""
    return bool(OTP_PREFIX_PATTERN.search(text) or OTP_SUFFIX_PATTERN.search(text))


def get_otp_security_warning() -> str:
    """Return explicit security advisory if sensitive credentials/OTPs are submitted."""
    return (
        "Security Notice: Never share OTPs, passwords, or confidential account credentials. "
        "This assistant answers public mutual fund scheme queries and does not access personal accounts."
    )
