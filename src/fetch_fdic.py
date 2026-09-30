"""
Extract quarterly bank financials from the FDIC BankFind Suite API (free, no API key).
Docs and field definitions: https://api.fdic.gov/banks/docs/

Saves two raw files:
    data/raw/fdic_financials.csv    one row per bank per quarter
    data/raw/fdic_institutions.csv  bank names and locations (incl. closed banks)
"""
from pathlib import Path
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api.fdic.gov/banks"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PAGE_SIZE = 10_000

START_DATE = "20200101"        # first report date to pull
MIN_ASSETS_THOUSANDS = 1_000_000   # $1B+ banks (FDIC reports dollars in thousands)

# Call Report fields (see "Financial API Definitions" in the FDIC docs)
FIN_FIELDS = {
    "CERT": "FDIC certificate number (bank ID)",
    "REPDTE": "Report date (quarter end)",
    "ASSET": "Total assets ($000)",
    "DEP": "Total deposits ($000)",
    "NETINC": "Net income, year to date ($000)",
    "ROA": "Return on assets (%)",
    "ROE": "Return on equity (%)",
    "NIMY": "Net interest margin (%)",
    "NCLNLSR": "Noncurrent loans to total loans (%)",
    "EEFFR": "Efficiency ratio (%) - lower is better",
    "RBC1AAJ": "Tier 1 leverage ratio (%)",
}
INST_FIELDS = ["CERT", "NAME", "CITY", "STALP", "ACTIVE"]


def _session():
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch(endpoint, params):
    """Page through an FDIC endpoint and return every record as a DataFrame."""
    session, rows, offset = _session(), [], 0
    while True:
        query = {**params, "limit": PAGE_SIZE, "offset": offset, "format": "json"}
        resp = session.get(f"{BASE_URL}/{endpoint}", params=query, timeout=120)
        resp.raise_for_status()
        batch = [item["data"] for item in resp.json().get("data", [])]
        rows.extend(batch)
        print(f"  {endpoint}: {len(rows):,} rows")
        if len(batch) < PAGE_SIZE:
            return pd.DataFrame(rows)
        offset += PAGE_SIZE
        time.sleep(1)   # be polite to a free public API


def fetch_all():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching FDIC quarterly financials ...")
    fin = fetch("financials", {
        "filters": f"REPDTE:[{START_DATE} TO *] AND ASSET:[{MIN_ASSETS_THOUSANDS} TO *]",
        "fields": ",".join(FIN_FIELDS), "sort_by": "REPDTE", "sort_order": "ASC"})
    missing = [f for f in FIN_FIELDS if f not in fin.columns]
    if missing:
        print(f"  WARNING: API did not return {missing}. Check the codes in the Financial API "
              "Definitions file; those metrics will be blank.")
        for f in missing:
            fin[f] = pd.NA

    print("Fetching institution names (including closed banks) ...")
    inst = fetch("institutions", {"fields": ",".join(INST_FIELDS)})

    fin.to_csv(RAW_DIR / "fdic_financials.csv", index=False)
    inst.to_csv(RAW_DIR / "fdic_institutions.csv", index=False)
    print(f"Saved {len(fin):,} bank-quarters and {len(inst):,} institutions to {RAW_DIR}")
    return fin, inst


if __name__ == "__main__":
    fetch_all()
