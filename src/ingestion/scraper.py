"""
Web scraper for official Groww mutual fund scheme pages.
Fetches public scheme pages and saves raw snapshots into data/raw/ for offline parsing and reproducibility.
"""

import logging
from pathlib import Path
from typing import Dict, Optional
import requests

from src.config import RAW_DATA_DIR, TARGET_SCHEMES, SchemeMetadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_scheme_html(scheme: SchemeMetadata, timeout: int = 15) -> Optional[str]:
    """
    Fetch raw HTML from the scheme's verified source URL.
    
    Args:
        scheme: SchemeMetadata instance with source_url and scheme_id.
        timeout: Request timeout in seconds.
        
    Returns:
        HTML string if successful, None otherwise.
    """
    logger.info(f"Fetching scheme: {scheme.scheme_name} from {scheme.source_url}")
    try:
        response = requests.get(scheme.source_url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {scheme.scheme_name}: {e}")
        return None


def save_raw_snapshot(scheme_id: str, html_content: str, output_dir: Path = RAW_DATA_DIR) -> Path:
    """Save raw HTML content to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{scheme_id}.html"
    file_path.write_text(html_content, encoding="utf-8")
    logger.info(f"Saved snapshot for {scheme_id} to {file_path}")
    return file_path


def scrape_all_schemes(force: bool = False) -> Dict[str, Path]:
    """
    Scrape all 5 target HDFC mutual fund schemes and persist raw HTML snapshots.
    
    Args:
        force: If True, refetch even if file already exists in data/raw.
        
    Returns:
        Dictionary mapping scheme_id to snapshot file path.
    """
    results = {}
    for scheme_id, scheme in TARGET_SCHEMES.items():
        destination = RAW_DATA_DIR / f"{scheme_id}.html"
        if destination.exists() and not force:
            logger.info(f"Snapshot already exists for {scheme_id}, skipping (use force=True to re-download).")
            results[scheme_id] = destination
            continue

        html = fetch_scheme_html(scheme)
        if html:
            saved_path = save_raw_snapshot(scheme_id, html)
            results[scheme_id] = saved_path
        else:
            logger.warning(f"Could not retrieve snapshot for {scheme_id}")

    return results


if __name__ == "__main__":
    scrape_all_schemes()
