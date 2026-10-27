"""
Post-Generation Compliance Validator for Milestone RAG.
Enforces the 3 non-negotiable output constraints:
1. Length Limit: Maximum 3 sentences in the answer body.
2. Single Citation: Exactly one valid markdown citation link.
3. Mandatory Footer: Must terminate with `Last updated from sources: <YYYY-MM-DD>`.
"""

from datetime import date
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Markdown Link Regex: [Anchor Text](URL)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

# Source line regex e.g. "Source: [HDFC Mid-Cap](url)"
SOURCE_LINE_PATTERN = re.compile(r"^(?:Source|Reference):\s*\[([^\]]+)\]\((https?://[^\s)]+)\)", re.IGNORECASE | re.MULTILINE)

# Footer Pattern: matches "*Last updated from sources: ...*" or "Last updated from sources: ..."
FOOTER_PATTERN = re.compile(r"\*?Last updated from sources:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\*?", re.IGNORECASE)


def tokenize_sentences(text: str) -> List[str]:
    """
    Split text into sentences using NLTK sent_tokenize with regex fallback.
    
    Args:
        text: Input paragraph or sentence string.
        
    Returns:
        List of individual sentence strings.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    try:
        import nltk
        sentences = nltk.sent_tokenize(clean_text)
        if sentences:
            return [s.strip() for s in sentences if s.strip()]
    except Exception as exc:
        logger.debug(f"NLTK tokenization unavailable, falling back to regex: {exc}")

    # Fallback sentence boundary regex (handles ., !, ? followed by space and uppercase)
    raw_splits = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\u20b9])", clean_text)
    return [s.strip() for s in raw_splits if s.strip()]


def trim_to_max_sentences(body_text: str, max_sentences: int = 3) -> str:
    """
    Trim body text so that it contains at most max_sentences.
    Preserves sentences intact without mid-word truncation.
    
    Args:
        body_text: Main narrative text.
        max_sentences: Maximum allowed sentence count (default: 3).
        
    Returns:
        Trimmed body text.
    """
    sentences = tokenize_sentences(body_text)
    if len(sentences) <= max_sentences:
        return body_text.strip()

    trimmed = " ".join(sentences[:max_sentences])
    return trimmed.strip()


def strip_xml_and_html_tags(text: str) -> str:
    """Strip XML/HTML tags (like <div>, </div>, <think>, etc.) from LLM narrative text."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    return text.strip()


def extract_and_enforce_single_citation(
    text: str,
    canonical_url: str,
    canonical_name: str = "Groww Scheme Details",
) -> Tuple[str, str]:
    """
    Ensure the response contains exactly one citation link.
    If multiple links exist, retains the first valid link and removes subsequent ones.
    If no link exists, returns the body and a canonical citation string.
    
    Args:
        text: Input text containing potential links.
        canonical_url: Fallback canonical URL if no link exists.
        canonical_name: Fallback anchor text.
        
    Returns:
        Tuple of (sanitized_body_without_standalone_source_lines, single_citation_markdown).
    """
    # 0. Clean any raw XML or HTML tags
    clean_text = strip_xml_and_html_tags(text)

    # 1. Check for standalone Source line
    source_line_match = SOURCE_LINE_PATTERN.search(clean_text)
    text_without_source_line = SOURCE_LINE_PATTERN.sub("", clean_text).strip()
    # Clean up any trailing broken or unclosed "Source:" or "Reference:" lines
    text_without_source_line = re.sub(r"(?:\n|\r|\s)*(?:Source|Reference):?\s*\[?[^\]\n\r]*$", "", text_without_source_line, flags=re.IGNORECASE).strip()
    text_without_source_line = re.sub(r"(?:Source|Reference):?\s*\[[^\]\)]*$", "", text_without_source_line, flags=re.IGNORECASE).strip()

    # 2. Find all markdown links in the remaining text
    found_links = MARKDOWN_LINK_PATTERN.findall(text_without_source_line)

    if source_line_match:
        # Standalone Source line already exists
        anchor, url = source_line_match.group(1), source_line_match.group(2)
        citation = f"Source: [{anchor}]({url})"

        # If there were also inline links in the body, remove extra links from body
        if found_links:
            # Replace inline markdown links with just their anchor text
            cleaned_body = MARKDOWN_LINK_PATTERN.sub(r"\1", text_without_source_line)
        else:
            cleaned_body = text_without_source_line

        return cleaned_body.strip(), citation

    elif found_links:
        # At least one inline link found in the text
        # Keep the first inline link as the official citation
        first_anchor, first_url = found_links[0]
        citation = f"Source: [{first_anchor}]({first_url})"

        # If more than 1 link, strip secondary markdown links down to plain anchor text
        def replace_excess_links(match: re.Match) -> str:
            anchor_t, url_t = match.group(1), match.group(2)
            if url_t == first_url:
                # Keep first occurrence as plain text in body since citation will be at the bottom
                return anchor_t
            return anchor_t

        cleaned_body = MARKDOWN_LINK_PATTERN.sub(replace_excess_links, text_without_source_line)
        return cleaned_body.strip(), citation

    else:
        # Zero links found: generate citation from canonical parameters
        citation = f"Source: [{canonical_name}]({canonical_url})"
        return text_without_source_line.strip(), citation


def format_and_validate_response(
    raw_response: str,
    canonical_url: str,
    canonical_name: str = "Groww Scheme Details",
    date_str: Optional[str] = None,
) -> str:
    """
    Format and validate any generated response against the strict 3 constraints:
    1. Maximum 3 sentences in the narrative body.
    2. Exactly one citation link formatted as `Source: [<Name>](<URL>)`.
    3. Mandatory timestamp footer `*Last updated from sources: <YYYY-MM-DD>*`.
    
    Args:
        raw_response: Raw response string from LLM or synthesizer.
        canonical_url: Verified Groww source URL for the scheme.
        canonical_name: Verified display name for the scheme.
        date_str: Optional ISO date string (defaults to today).
        
    Returns:
        Compliant, fully validated response string.
    """
    if not date_str:
        date_str = str(date.today())

    # Step 1: Strip existing timestamp footers if present to avoid duplication
    cleaned = FOOTER_PATTERN.sub("", raw_response).strip()

    # Step 2: Separate narrative body from citation link
    body, citation = extract_and_enforce_single_citation(
        cleaned,
        canonical_url=canonical_url,
        canonical_name=canonical_name,
    )

    # Step 3: Trim narrative body to at most 3 sentences
    trimmed_body = trim_to_max_sentences(body, max_sentences=3)

    # Step 4: Assemble compliant output
    footer = f"*Last updated from sources: {date_str}*"
    formatted_output = f"{trimmed_body}\n\n{citation}\n{footer}"

    return formatted_output


def verify_compliance(text: str) -> Dict[str, Any]:
    """
    Check if a response strictly adheres to all compliance requirements.
    
    Args:
        text: Formatted response string.
        
    Returns:
        Dictionary with granular pass/fail checks and sentence/link counts.
    """
    # 1. Check footer
    footer_match = FOOTER_PATTERN.search(text)
    has_footer = bool(footer_match)

    # 2. Check citation count
    links = MARKDOWN_LINK_PATTERN.findall(text)
    link_count = len(links)
    exact_single_citation = (link_count == 1)

    # 3. Check sentence count in main body
    # Extract body by removing source line and footer
    body = SOURCE_LINE_PATTERN.sub("", text)
    body = FOOTER_PATTERN.sub("", body).strip()
    sentences = tokenize_sentences(body)
    sentence_count = len(sentences)
    max_sentences_pass = (sentence_count <= 3)

    is_compliant = has_footer and exact_single_citation and max_sentences_pass

    return {
        "is_compliant": is_compliant,
        "sentence_count": sentence_count,
        "max_sentences_pass": max_sentences_pass,
        "link_count": link_count,
        "exact_single_citation": exact_single_citation,
        "has_footer": has_footer,
    }
