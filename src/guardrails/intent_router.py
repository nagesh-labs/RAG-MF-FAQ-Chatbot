"""
Intent Classification, Scheme Entity Extraction, and Refusal Router for Milestone RAG.
Intercepts advisory, comparative, speculative, jailbreak, and out-of-scope prompts
before vector retrieval or LLM generation, ensuring 100% compliance with SEBI facts-only regulations.
"""

from datetime import date
from enum import Enum
import re
from typing import Dict, List, Optional, Tuple
from src.config import TARGET_SCHEMES, EDUCATIONAL_LINKS, FOOTER_TEMPLATE


class IntentType(str, Enum):
    """Enumeration of recognized query intents."""
    FACTUAL = "FACTUAL"
    ADVISORY = "ADVISORY"
    COMPARATIVE_OPINION = "COMPARATIVE_OPINION"
    SPECULATIVE_RETURNS = "SPECULATIVE_RETURNS"
    JAILBREAK = "JAILBREAK"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    COMPETITOR_OR_UNINDEXED = "COMPETITOR_OR_UNINDEXED"


# Pre-compiled Regex Patterns for Guardrail Detection

# Pre-compiled Regex Patterns for Guardrail Detection

# 1. Jailbreak & Prompt Injection Patterns
JAILBREAK_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(an\s+unrestricted|a\s+financial\s+advisor|dan|jailbreak)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+investment\s+consultant|a\s+financial\s+advisor|a\s+broker|an\s+unrestricted)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(rules|constraints|disclaimers)", re.IGNORECASE),
    re.compile(r"hypothetically\b.*?\b(which|what|would\s+you|should\s+i|pick|choose)\b", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+unrestricted|a\s+financial\s+advisor|dan)", re.IGNORECASE),
    re.compile(r"imagine\s+(you\s+are|to\s+be)\b", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(guardrails|safety|rules|restrictions)", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
]

# 2. Comparative Opinion & Rating Patterns (Prioritized before general advisory)
COMPARATIVE_OPINION_PATTERNS = [
    re.compile(r"\bwhich\s+(?:scheme|fund|one)?\s*(?:is\s+)?(better|best|superior|preferable|winner|safer)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+is\s+(the\s+)?(better|best|superior|preferable|winner|safer)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+one\s+should\s+i\s+(pick|choose|buy|invest\s+in)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+one\s+to\s+(pick|choose|buy|invest\s+in)\b", re.IGNORECASE),
    re.compile(r"\bcompare\s+and\s+tell\s+me\s+which\s+(to\s+buy|is\s+better)\b", re.IGNORECASE),
    re.compile(r"\b(rate|rank)\s+(the\s+)?\d*\s*(these\s+|hdfc\s+)?(mutual\s+funds?|schemes?|funds?)\b", re.IGNORECASE),
    re.compile(r"\bis\s+[a-z0-9\s-]+better\s+than\s+[a-z0-9\s-]+", re.IGNORECASE),
    re.compile(r"\b(vs|versus)\b.*?\b(which\s+is\s+better|which\s+to\s+buy|which\s+one\s+to\s+choose)\b", re.IGNORECASE),
    re.compile(r"\bwhy\s+should\s+i\s+(invest\s+in|choose|buy)\b.*?\binstead\s+of\b", re.IGNORECASE),
    re.compile(r"\b(personal\s+opinion|your\s+opinion)\b", re.IGNORECASE),
    re.compile(r"\b(outperform|underperform)\b", re.IGNORECASE),
]

# 3. Direct Advisory & Recommendation Patterns
ADVISORY_PATTERNS = [
    re.compile(r"\bshould\s+i\s+(invest|buy|put|start\s+sip|choose|sell|redeem|exit|stay\s+invested)\b", re.IGNORECASE),
    re.compile(r"\bis\s+it\s+(good|safe|worth|wise|advisable|recommended)\s+to\s+(invest|buy|start|enter|sell|redeem|exit|switch|move)\b", re.IGNORECASE),
    re.compile(r"\bis\s+[a-z0-9\s-]+\s+(safe|good|advisable)\s+to\s+invest\b", re.IGNORECASE),
    re.compile(r"\ba\s+good\s+(buy|investment|pick|choice)\b", re.IGNORECASE),
    re.compile(r"\b(can\s+you\s+)?recommend\b.*?\b(fund|scheme|investment|portfolio|stock)\b", re.IGNORECASE),
    re.compile(r"\b(suggest|advise)\b.*?\b(fund|scheme|investment|portfolio)\b", re.IGNORECASE),
    re.compile(r"\bwhere\s+should\s+i\s+(invest|put\s+my\s+money)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+am|i'm)\s+\d{2}\s+(years?\s+old|age).*?(where|which|how)\s+to\s+invest\b", re.IGNORECASE),
    re.compile(r"\bportfolio\s+(advice|recommendation|review|allocation|suggestion)\b", re.IGNORECASE),
    re.compile(r"\bhelp\s+me\s+pick\s+(a\s+|the\s+best\s+)?fund\b", re.IGNORECASE),
    re.compile(r"\bis\s+(?:this|[a-z0-9\s-]+)\s+(?:a\s+)?good\s+fund\s+for\b", re.IGNORECASE),
    re.compile(r"\b(best|top)\s+funds?\s+to\s+(invest|buy)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+(?:mutual\s+)?funds?\s+should\s+i\s+(buy|invest\s+in|choose|pick)\b", re.IGNORECASE),
    re.compile(r"\bis\s+it\s+(the\s+)?right\s+time\s+to\s+(invest|enter|buy)\b", re.IGNORECASE),
    re.compile(r"\bshould\s+i\s+stop\s+(my\s+)?sip\b", re.IGNORECASE),
    re.compile(r"\btell\s+me\s+as\s+a\s+friend\b", re.IGNORECASE),
    re.compile(r"\b(financial\s+advice|investment\s+advice)\b", re.IGNORECASE),
    re.compile(r"\ballocating\s+between\b", re.IGNORECASE),
    re.compile(r"\bsuggest\s+(an?\s+)?(?:optimal\s+)?(?:mutual\s+fund\s+)?portfolio\b", re.IGNORECASE),
]

# 4. Return Speculation & Forecasting Patterns
SPECULATIVE_RETURN_PATTERNS = [
    re.compile(r"\bwill\b.*?\b(give|generate|produce|make)\b.*?\d+%\s*(?:returns?)?\b", re.IGNORECASE),
    re.compile(r"\b(?:guaranteed|assured|expected)\b.*?\breturns?\b|\breturns?\b.*?\b(?:guaranteed|assured)\b", re.IGNORECASE),
    re.compile(r"\bcrorepati\b", re.IGNORECASE),
    re.compile(r"\bhow\s+much\s+(profit|money)\s+will\s+i\s+(make|earn)\b", re.IGNORECASE),
    re.compile(r"\bpredict\b.*?\b(returns?|performance|nav)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(will\s+be\s+the\s+nav|returns?\s+can\s+i\s+expect)\b", re.IGNORECASE),
    re.compile(r"\bnav\b.*?\b(?:in|by|next)\b.*?\d{4}\b", re.IGNORECASE),
    re.compile(r"\bguarantee\b.*?\breturns?\b", re.IGNORECASE),
]

# 5. Out-of-Scope Patterns (Crypto, Stocks, Non-Mutual-Funds, Chit-Chat)
OUT_OF_SCOPE_PATTERNS = [
    re.compile(r"\b(bitcoin|crypto|ethereum|dogecoin|binance)\b", re.IGNORECASE),
    re.compile(r"\b(weather|temperature|forecast)\b", re.IGNORECASE),
    re.compile(r"\b(write\s+a\s+poem|tell\s+me\s+a\s+joke|who\s+won\s+the\s+match|cricket|world\s+cup)\b", re.IGNORECASE),
    re.compile(r"\b(buy|sell)\s+(reliance|tcs|infosys|hdfc\s+bank)\s+shares?\b", re.IGNORECASE),
]

# 6. Competitor AMCs & Unindexed Schemes (Outside our 5 verified HDFC schemes corpus)
COMPETITOR_AND_UNINDEXED_PATTERNS = [
    re.compile(
        r"\b(sbi|icici(?:\s+prudential)?|axis|nippon(?:\s+india)?|kotak|mirae(?:\s+asset)?|quant|parag\s+parikh|uti|tata)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhdfc\s+(flexi\s*cap|balanced|hybrid|liquid|overnight|gilt|defence|arbitrage|tax\s*saver|elss|index)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(carbon\s+footprint|esg\s+score|treynor)\b",
        re.IGNORECASE,
    ),
]


def classify_intent(query: str) -> IntentType:
    """
    Classify user query intent using deterministic regex patterns.
    Runs in sub-millisecond time without external LLM calls.
    
    Args:
        query: Inbound sanitized user query.
        
    Returns:
        IntentType classification enum.
    """
    clean_q = query.strip()

    # Priority 1: Jailbreak detection
    for pattern in JAILBREAK_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.JAILBREAK

    # Priority 2: Comparative opinions & ratings
    for pattern in COMPARATIVE_OPINION_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.COMPARATIVE_OPINION

    # Priority 3: Direct advisory detection
    for pattern in ADVISORY_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.ADVISORY

    # Priority 4: Speculative return forecasting
    for pattern in SPECULATIVE_RETURN_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.SPECULATIVE_RETURNS

    # Priority 5: Out of scope (crypto, weather, chit-chat)
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.OUT_OF_SCOPE

    # Priority 6: Competitor AMCs and unindexed schemes
    for pattern in COMPETITOR_AND_UNINDEXED_PATTERNS:
        if pattern.search(clean_q):
            return IntentType.COMPETITOR_OR_UNINDEXED

    # Default: Factual mutual fund query
    return IntentType.FACTUAL


def extract_scheme_entity(query: str) -> Optional[str]:
    """
    Identify and extract which specific target HDFC scheme is referenced in the query.
    Normalizes hyphens and checks aliases across all 5 target schemes.
    
    Args:
        query: User query text.
        
    Returns:
        Canonical scheme_id if matched, None otherwise.
    """
    q_lower = query.lower()
    q_norm = re.sub(r"[-_]", " ", q_lower)

    # Exact and normalized alias matching across the 5 target schemes
    for scheme_id, scheme in TARGET_SCHEMES.items():
        # Check canonical scheme name
        if scheme.scheme_name.lower() in q_lower or scheme.scheme_name.lower().replace("-", " ") in q_norm:
            return scheme_id

        # Check aliases
        for alias in scheme.aliases:
            alias_lower = alias.lower()
            if re.search(r"\b" + re.escape(alias_lower) + r"\b", q_lower):
                return scheme_id
            if re.search(r"\b" + re.escape(alias_lower.replace("-", " ")) + r"\b", q_norm):
                return scheme_id

    # Secondary heuristic match for key category terms on normalized text
    if "silver" in q_norm:
        return "hdfc-silver-etf-fof-direct-growth"
    if "small cap" in q_norm or "smallcap" in q_norm:
        return "hdfc-small-cap-fund-direct-growth"
    if "mid cap" in q_norm or "midcap" in q_norm:
        return "hdfc-mid-cap-fund-direct-growth"
    if "multi cap" in q_norm or "multicap" in q_norm:
        return "hdfc-multi-cap-fund-direct-growth"
    if "large cap" in q_norm or "top 100" in q_norm:
        return "hdfc-large-cap-fund-direct-growth"

    return None


def generate_refusal_response(intent: IntentType, query: str = "") -> str:
    """
    Generate a compliant, polite, deterministic refusal message with verified educational links.
    Strictly complies with the 3-sentence maximum limit and mandatory timestamp footer.
    
    Args:
        intent: Detected non-factual IntentType.
        query: Original user query.
        
    Returns:
        Formatted refusal string.
    """
    today_str = str(date.today())
    amfi_link = EDUCATIONAL_LINKS["AMFI"]
    sebi_link = EDUCATIONAL_LINKS["SEBI_INVESTOR"]

    if intent in (IntentType.ADVISORY, IntentType.JAILBREAK):
        body = (
            "I am a facts-only assistant and cannot provide investment advice or scheme recommendations. "
            f"Please consult a SEBI-registered financial advisor or explore investor educational guides on [AMFI India]({amfi_link}) "
            f"and [SEBI Investor Education]({sebi_link})."
        )

    elif intent == IntentType.COMPARATIVE_OPINION:
        body = (
            "I cannot provide opinions, ratings, or comparative recommendations between mutual fund schemes. "
            f"You can review objective scheme parameters, factsheets, and investor education at [AMFI India]({amfi_link}) "
            f"and [SEBI Investor Education]({sebi_link})."
        )

    elif intent == IntentType.SPECULATIVE_RETURNS:
        body = (
            "Mutual fund investments are subject to market risks, and I cannot project or guarantee future returns. "
            f"Statutory disclosures and investor education resources are available on [AMFI India]({amfi_link}) "
            f"and [SEBI Investor Education]({sebi_link})."
        )

    elif intent == IntentType.COMPETITOR_OR_UNINDEXED:
        body = (
            "This assistant's verified corpus is currently limited to 5 specific HDFC Mutual Fund schemes. "
            f"Information on competitor funds or unindexed schemes can be explored on [Groww Mutual Funds]({EDUCATIONAL_LINKS['GROWW_MF']}) "
            f"as well as official guides on [AMFI India]({amfi_link}) and [SEBI Investor Education]({sebi_link})."
        )

    elif intent == IntentType.OUT_OF_SCOPE:
        body = (
            "I am a mutual fund FAQ assistant dedicated exclusively to objective mutual fund scheme queries. "
            f"For general investor guidance, please refer to official resources at [AMFI India]({amfi_link}) "
            f"and [SEBI Investor Education]({sebi_link})."
        )

    else:
        body = (
            "I can only assist with verified, factual queries regarding mutual fund scheme parameters. "
            f"Please review official investor resources on [AMFI India]({amfi_link}) "
            f"and [SEBI Investor Education]({sebi_link})."
        )

    footer = FOOTER_TEMPLATE.format(date=today_str)
    return f"{body}\n\n{footer}"
