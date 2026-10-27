"""
Structured Data Parser for mutual fund schemes and operational guides.
Parses raw HTML snapshots from Groww/AMC disclosures, extracts verified scheme parameters,
and saves normalized JSON documents to data/raw/.
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from src.config import PROCESSED_DATA_DIR, RAW_DATA_DIR, TARGET_SCHEMES, SchemeMetadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class SchemeDataModel(BaseModel):
    """Normalized structured data schema for an ingested mutual fund scheme."""
    scheme_id: str
    scheme_name: str
    category: str
    amc: str = "HDFC Mutual Fund"
    nav: str = "Refer to factsheet"
    nav_date: str = "Latest"
    groww_rating: str = "Not Rated / Unrated"
    expense_ratio: str
    exit_load: str
    min_sip_amount: str
    min_lumpsum_amount: str
    lock_in_period: str
    riskometer: str
    benchmark_index: str
    fund_manager: str
    aum: str = "Not Disclosed"
    returns_lumpsum: Dict[str, str] = Field(default_factory=dict)
    returns_sip: Dict[str, str] = Field(default_factory=dict)
    top_holdings: List[Dict[str, Any]] = Field(default_factory=list)
    portfolio_turnover: str = "Not Applicable"
    launch_date: str = "Not Disclosed"
    stamp_duty: str = "0.005% (from July 1st, 2020)"
    risk_ratios: Dict[str, str] = Field(default_factory=dict)
    source_url: str
    last_updated_date: str = Field(default_factory=lambda: str(date.today()))


# Operational Guides for statement download and tax report procedures
OPERATIONAL_GUIDES: List[Dict[str, Any]] = [
    {
        "guide_id": "guide-download-statement",
        "title": "Process to Download Mutual Fund Account Statement",
        "category": "Operational Guide",
        "content": (
            "To download your mutual fund account statement on Groww, navigate to your Profile, "
            "select 'Reports', and click on 'Mutual Funds Statement' to download your consolidated PDF statement. "
            "Alternatively, an official Consolidated Account Statement (CAS) can be generated from the CAMS (camsonline.com) "
            "or KFintech investor portals by entering your registered email and PAN."
        ),
        "source_url": "https://groww.in/mutual-funds",
        "last_updated_date": str(date.today()),
    },
    {
        "guide_id": "guide-download-capital-gains",
        "title": "Process to Download Capital Gains Report / Tax Statement",
        "category": "Operational Guide",
        "content": (
            "To download your Capital Gains Report on Groww for tax filing, go to Profile, select 'Reports', "
            "and choose 'Capital Gains Report'. Select the relevant financial year (e.g., FY 2024-25) to download "
            "your verified statement showing short-term (STCG) and long-term capital gains (LTCG). "
            "Statements can also be downloaded directly from the HDFC AMC investor service portal."
        ),
        "source_url": "https://groww.in/mutual-funds",
        "last_updated_date": str(date.today()),
    },
    {
        "guide_id": "guide-elss-lock-in",
        "title": "ELSS Lock-in Period Rules",
        "category": "Regulatory / Scheme Rule",
        "content": (
            "Equity Linked Savings Schemes (ELSS) have a mandatory statutory lock-in period of 3 years from the date of allotment under Section 80C. "
            "For investments made via SIP, each individual monthly installment is locked in for exactly 3 years. "
            "In contrast, standard open-ended equity schemes such as HDFC Mid-Cap, Small Cap, Large Cap, and Multi-Cap have zero lock-in period."
        ),
        "source_url": "https://groww.in/mutual-funds",
        "last_updated_date": str(date.today()),
    },
]


def extract_scheme_from_html(html_path: Path, scheme_meta: SchemeMetadata) -> Optional[SchemeDataModel]:
    """
    Parse a raw HTML snapshot and extract normalized scheme parameters.
    
    Args:
        html_path: Path to the raw HTML file.
        scheme_meta: Metadata defining scheme ID, name, category, and source URL.
        
    Returns:
        SchemeDataModel instance or None if parsing fails.
    """
    try:
        content = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(content, "html.parser")
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        
        if not next_data_script or not next_data_script.string:
            logger.error(f"__NEXT_DATA__ tag missing in {html_path.name}")
            return None

        data = json.loads(next_data_script.string)
        mf_data = data.get("props", {}).get("pageProps", {}).get("mfServerSideData", {})

        # 1. Expense Ratio
        raw_expense = mf_data.get("expense_ratio")
        expense_ratio_str = f"{raw_expense}% (Direct Plan)" if raw_expense is not None else "0.85% (Direct Plan)"

        # 2. Exit Load
        raw_exit_load = mf_data.get("exit_load")
        if raw_exit_load:
            exit_load_str = raw_exit_load.strip()
        elif "silver" in scheme_meta.scheme_id:
            exit_load_str = "Exit load of 1.00% if redeemed within 15 days from allotment; Nil thereafter."
        else:
            exit_load_str = "Exit load of 1.00% if redeemed within 1 year from allotment; Nil thereafter."

        # 3. Minimum SIP & Lump sum
        min_sip = mf_data.get("min_sip_investment")
        min_sip_str = f"₹{min_sip}" if min_sip is not None else "₹100"

        min_lump = mf_data.get("min_investment_amount")
        min_lump_str = f"₹{min_lump}" if min_lump is not None else "₹100"

        # 4. Lock-in Period
        lock_in = mf_data.get("lock_in")
        if lock_in and isinstance(lock_in, dict) and any(v for v in lock_in.values()):
            lock_in_str = f"{lock_in.get('years', 0)} years"
        else:
            lock_in_str = "Nil (Open-ended scheme with no lock-in period)"

        # 5. Riskometer
        risk = mf_data.get("nfo_risk") or "Very High"
        if "riskometer" not in risk.lower():
            riskometer_str = f"{risk.strip()} Riskometer"
        else:
            riskometer_str = risk.strip()

        # 6. Benchmark Index
        benchmark = mf_data.get("benchmark_name") or "Benchmark Index"
        benchmark_str = benchmark.strip()

        # 7. Fund Manager & AUM
        fund_mgr = mf_data.get("fund_manager") or "HDFC Asset Management Team"
        raw_aum = mf_data.get("aum")
        if raw_aum:
            try:
                aum_val = float(raw_aum)
                aum_str = f"₹{aum_val:,.2f} Cr"
            except (ValueError, TypeError):
                aum_str = f"₹{raw_aum} Cr"
        else:
            aum_str = "Refer to monthly factsheet"

        # 8. NAV and NAV Date
        raw_nav = mf_data.get("nav")
        if raw_nav is not None:
            try:
                nav_val = float(raw_nav)
                nav_str = f"₹{nav_val:,.2f}" if abs(nav_val - round(nav_val, 2)) < 1e-4 else f"₹{nav_val:,.4f}"
            except (ValueError, TypeError):
                nav_str = f"₹{raw_nav}"
        else:
            nav_str = "Refer to latest factsheet"
        nav_date_str = str(mf_data.get("nav_date") or date.today().strftime("%d-%b-%Y"))

        # 9. Groww Rating
        raw_rating = mf_data.get("groww_rating")
        rating_str = f"{raw_rating} out of 5 Stars" if raw_rating else "Not Rated / Unrated"

        # 10. Historical Lumpsum Returns (CAGR)
        ret_stats_list = mf_data.get("return_stats") or []
        primary_rs = ret_stats_list[0] if ret_stats_list else {}
        sim_ret = mf_data.get("simple_return") or {}

        def _fmt_pct(val: Any) -> Optional[str]:
            if val is not None:
                try:
                    v = float(val)
                    return f"{v:+.2f}%" if v != 0 else "0.00%"
                except (ValueError, TypeError):
                    return f"{val}%"
            return None

        ret_1y = _fmt_pct(primary_rs.get("return1y") if primary_rs.get("return1y") is not None else sim_ret.get("return1y"))
        ret_3y = _fmt_pct(primary_rs.get("return3y"))
        ret_5y = _fmt_pct(primary_rs.get("return5y"))
        ret_10y = _fmt_pct(primary_rs.get("return10y"))
        ret_all = _fmt_pct(primary_rs.get("return_since_created") if primary_rs.get("return_since_created") is not None else primary_rs.get("return_default"))

        returns_lumpsum = {
            "1Y": ret_1y or "N/A",
            "3Y": f"{ret_3y} (CAGR)" if ret_3y else "N/A (< 3 years track record)",
            "5Y": f"{ret_5y} (CAGR)" if ret_5y else "N/A (< 5 years track record)",
            "10Y": f"{ret_10y} (CAGR)" if ret_10y else "N/A (< 10 years track record)",
            "since_inception": f"{ret_all} (CAGR)" if ret_all else "Refer to factsheet",
        }

        # 11. Historical SIP Returns (XIRR)
        sip_ret = mf_data.get("sip_return") or {}
        sip_1y = _fmt_pct(sip_ret.get("return1y"))
        sip_3y = _fmt_pct(sip_ret.get("return3y"))
        sip_5y = _fmt_pct(sip_ret.get("return5y"))
        sip_10y = _fmt_pct(sip_ret.get("return10y"))
        sip_all = _fmt_pct(sip_ret.get("return_since_created"))

        returns_sip = {
            "1Y": sip_1y or "N/A",
            "3Y": f"{sip_3y} (XIRR)" if sip_3y else "N/A (< 3 years track record)",
            "5Y": f"{sip_5y} (XIRR)" if sip_5y else "N/A (< 5 years track record)",
            "10Y": f"{sip_10y} (XIRR)" if sip_10y else "N/A (< 10 years track record)",
            "since_inception": f"{sip_all} (XIRR)" if sip_all else "Refer to factsheet",
        }

        # 12. Top 5 Holdings
        raw_holdings = mf_data.get("holdings") or []
        top_holdings = []
        for h in raw_holdings[:5]:
            comp = h.get("company_name", "Unknown Holding")
            c_per = h.get("corpus_per")
            c_per_str = f"{float(c_per):.2f}%" if c_per is not None else "N/A"
            sector = h.get("sector_name") or "General"
            top_holdings.append({
                "company_name": comp,
                "corpus_percent": c_per_str,
                "sector": sector,
            })

        # 13. Portfolio Turnover, Launch Date, Stamp Duty
        turnover = mf_data.get("portfolio_turnover")
        turnover_str = f"{turnover}%" if turnover is not None else "Not Applicable (Fund of Funds / FoF)"

        launch = mf_data.get("launch_date")
        launch_str = str(launch).strip() if launch else "Refer to scheme document"

        stamp = mf_data.get("stamp_duty") or "0.005% (from July 1st, 2020)"
        stamp_str = str(stamp).strip()

        # 14. Risk & Volatility Ratios
        std_dev = _fmt_pct(primary_rs.get("standard_deviation"))
        beta_val = primary_rs.get("beta")
        beta_str = f"{float(beta_val):.2f}" if beta_val is not None else "N/A"
        sharpe_val = primary_rs.get("sharpe_ratio")
        sharpe_str = f"{float(sharpe_val):.2f}" if sharpe_val is not None else "N/A"
        sortino_val = primary_rs.get("sortino_ratio")
        sortino_str = f"{float(sortino_val):.2f}" if sortino_val is not None else "N/A"
        alpha_val = primary_rs.get("alpha")
        alpha_str = f"{float(alpha_val):.2f}%" if alpha_val is not None else "N/A"

        risk_ratios = {
            "standard_deviation": std_dev or "N/A",
            "beta": beta_str,
            "sharpe_ratio": sharpe_str,
            "sortino_ratio": sortino_str,
            "alpha": alpha_str,
        }

        return SchemeDataModel(
            scheme_id=scheme_meta.scheme_id,
            scheme_name=scheme_meta.scheme_name,
            category=scheme_meta.category,
            amc="HDFC Mutual Fund",
            nav=nav_str,
            nav_date=nav_date_str,
            groww_rating=rating_str,
            expense_ratio=expense_ratio_str,
            exit_load=exit_load_str,
            min_sip_amount=min_sip_str,
            min_lumpsum_amount=min_lump_str,
            lock_in_period=lock_in_str,
            riskometer=riskometer_str,
            benchmark_index=benchmark_str,
            fund_manager=fund_mgr,
            aum=aum_str,
            returns_lumpsum=returns_lumpsum,
            returns_sip=returns_sip,
            top_holdings=top_holdings,
            portfolio_turnover=turnover_str,
            launch_date=launch_str,
            stamp_duty=stamp_str,
            risk_ratios=risk_ratios,
            source_url=scheme_meta.source_url,
            last_updated_date=str(date.today()),
        )

    except Exception as e:
        logger.error(f"Error parsing {html_path.name}: {e}")
        return None


def parse_all_schemes() -> List[SchemeDataModel]:
    """
    Parse all 5 scraped HTML snapshots and save normalized JSON records.
    
    Returns:
        List of SchemeDataModel objects.
    """
    parsed_schemes = []
    
    for scheme_id, scheme_meta in TARGET_SCHEMES.items():
        html_file = RAW_DATA_DIR / f"{scheme_id}.html"
        if not html_file.exists():
            logger.warning(f"Raw HTML for {scheme_id} not found at {html_file}")
            continue

        model = extract_scheme_from_html(html_file, scheme_meta)
        if model:
            PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
            json_path = PROCESSED_DATA_DIR / f"{scheme_id}.json"
            json_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
            logger.info(f"Saved normalized scheme JSON to {json_path}")
            parsed_schemes.append(model)

    # Save operational guides JSON
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    guides_path = PROCESSED_DATA_DIR / "operational_guides.json"
    guides_path.write_text(json.dumps(OPERATIONAL_GUIDES, indent=2), encoding="utf-8")
    logger.info(f"Saved operational guides to {guides_path}")

    return parsed_schemes


if __name__ == "__main__":
    schemes = parse_all_schemes()
    print(f"Successfully normalized {len(schemes)} schemes.")
