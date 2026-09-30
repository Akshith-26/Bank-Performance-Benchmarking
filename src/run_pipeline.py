"""
U.S. Bank Performance Benchmarking - end-to-end pipeline.

Steps
  1. Extract quarterly financials for $1B+ U.S. banks from the FDIC API (fetch_fdic.py)
  2. Build peer groups, peer medians, bank-vs-peer comparisons and a watchlist in SQL (DuckDB)
  3. Export a formatted Excel peer report, a Tableau-ready CSV, charts and a results summary

Run from the project root:
    python src/run_pipeline.py              # fetch fresh data from the FDIC API, then analyze
    python src/run_pipeline.py --use-cache  # reuse data/raw/*.csv from the last fetch
"""
from pathlib import Path
import sys
import time

import duckdb
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from excel_utils import write_sheet
import fetch_fdic

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SQL_DIR = ROOT / "sql"
OUT = ROOT / "outputs"
IMG = ROOT / "images"

plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10})
PEER_COLORS = {"1: $1-10B Community/Regional": "#8FA9D6",
               "2: $10-100B Regional": "#2E5AAC",
               "3: $100B+ Large": "#C0392B"}


def sql(name):
    return (SQL_DIR / name).read_text()


def fmt(v):
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    if isinstance(v, (float, np.floating)):
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"
    return str(v)


def to_md(df):
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def get_data(use_cache):
    fin_path, inst_path = RAW / "fdic_financials.csv", RAW / "fdic_institutions.csv"
    if use_cache and fin_path.exists() and inst_path.exists():
        print("Using cached FDIC data from data/raw/")
        return pd.read_csv(fin_path), pd.read_csv(inst_path)
    return fetch_fdic.fetch_all()


def run_sql(fin, inst):
    print("Building peer benchmarks in SQL ...")
    con = duckdb.connect()
    for col in fetch_fdic.FIN_FIELDS:
        if col not in ("CERT", "REPDTE"):
            fin[col] = pd.to_numeric(fin[col], errors="coerce")
    con.register("fin", fin)
    con.register("inst", inst)
    con.execute(sql("01_bank_quarters.sql"))
    con.execute(sql("02_peer_medians.sql"))
    con.execute(sql("03_bank_vs_peer.sql"))
    peers = con.sql("SELECT * FROM peer_medians ORDER BY report_date, peer_group").df()
    banks = con.sql("SELECT * FROM bank_vs_peer ORDER BY report_date, peer_group, assets_bn DESC").df()
    watch = con.sql(sql("04_watchlist.sql")).df()
    con.close()
    return peers, banks, watch


def export_excel(peers, banks, watch):
    print("Writing Excel peer report ...")
    latest_date = banks["report_date"].max()
    latest = (banks[banks["report_date"] == latest_date]
              .sort_values("assets_bn", ascending=False)
              [["bank_name", "city", "state", "peer_group", "assets_bn", "deposits_bn", "roa", "roa_vs_peer",
                "roa_rank_in_peer", "roe", "nimy", "nim_vs_peer", "nclnlsr", "noncurrent_vs_peer",
                "eeffr", "rbc1aaj"]]
              .rename(columns={"nimy": "nim", "nclnlsr": "noncurrent_loans", "eeffr": "efficiency_ratio",
                               "rbc1aaj": "leverage_ratio"}))
    latest_peers = peers[peers["report_date"] == latest_date].drop(columns="report_date")
    trend = peers.copy()
    trend["report_date"] = trend["report_date"].dt.strftime("%Y-%m-%d")
    defs = pd.DataFrame({"field": list(fetch_fdic.FIN_FIELDS), "definition": list(fetch_fdic.FIN_FIELDS.values())})
    defs.loc[len(defs)] = ["Source", "FDIC BankFind Suite API (api.fdic.gov/banks), quarterly Call Report data"]
    defs.loc[len(defs)] = ["As of", latest_date.strftime("%Y-%m-%d")]

    num2 = "0.00"
    path = OUT / "bank_peer_report.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        write_sheet(xw, latest_peers, "Peer Medians (Latest)",
                    {c: num2 for c in ["roa", "roe", "nim", "noncurrent_loans", "efficiency_ratio",
                                       "leverage_ratio"]} | {"total_assets_bn": "#,##0.0"})
        write_sheet(xw, latest, "All Banks (Latest)",
                    {c: num2 for c in latest.columns if latest[c].dtype.kind == "f"},
                    color_scale_cols=["roa_vs_peer"], reverse_scale=True)
        write_sheet(xw, watch, "Watchlist", {c: num2 for c in watch.columns if watch[c].dtype.kind == "f"})
        write_sheet(xw, trend, "Peer Trends", {c: num2 for c in trend.columns if trend[c].dtype.kind == "f"})
        write_sheet(xw, defs, "Definitions")
    return path


def make_charts(peers, banks):
    print("Saving charts ...")
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for ax, (col, title) in zip(axes, [("roa", "Median ROA %"), ("nim", "Median net interest margin %"),
                                       ("noncurrent_loans", "Median noncurrent loans %")]):
        for peer, grp in peers.groupby("peer_group"):
            ax.plot(grp["report_date"], grp[col], label=peer.split(": ")[1], color=PEER_COLORS.get(peer))
        ax.set_title(title, loc="left", fontweight="bold")
        ax.tick_params(axis="x", rotation=45)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(IMG / "peer_trends.png"); plt.close(fig)

    latest = banks[banks["report_date"] == banks["report_date"].max()]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for peer, grp in latest.groupby("peer_group"):
        ax.scatter(grp["nclnlsr"], grp["roa"], s=np.clip(grp["assets_bn"], 5, 400) / 2,
                   alpha=0.6, color=PEER_COLORS.get(peer), label=peer.split(": ")[1])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Noncurrent loans % (asset quality, lower is better)")
    ax.set_ylabel("Return on assets %")
    ax.set_xlim(0, latest["nclnlsr"].quantile(0.99) * 1.1)
    ax.set_ylim(latest["roa"].quantile(0.01) - 0.2, latest["roa"].quantile(0.99) + 0.2)
    ax.set_title(f"Profitability vs asset quality, {latest['report_date'].max():%b %Y} (bubble = assets)",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(IMG / "roa_vs_asset_quality.png"); plt.close(fig)


def write_summary(banks, peers, watch):
    latest_date = banks["report_date"].max()
    latest = banks[banks["report_date"] == latest_date]
    quarters = banks["report_date"].nunique()
    lp = peers[peers["report_date"] == latest_date][["peer_group", "banks", "roa", "nim",
                                                     "noncurrent_loans", "efficiency_ratio"]]
    text = f"""# Results summary (auto-generated by src/run_pipeline.py)

| Metric | Value |
|---|---|
| Banks covered (latest quarter) | {latest['cert'].nunique():,} |
| Unique banks across all quarters | {banks['cert'].nunique():,} |
| Quarters covered | {quarters} ({banks['report_date'].min():%b %Y} to {latest_date:%b %Y}) |
| Bank-quarter records | {len(banks):,} |
| Banks on watchlist (latest quarter) | {len(watch):,} |

### Peer medians, {latest_date:%b %Y}
{to_md(lp)}

## Resume bullets (numbers filled in from this run)
- Automated quarterly extraction of Call Report data for {latest['cert'].nunique():,} U.S. banks via the FDIC API using Python, replacing manual data collection with a scheduled pipeline.
- Calculated and benchmarked 6 key performance ratios (ROA, ROE, NIM, noncurrent loans, efficiency, Tier 1 leverage) across 3 peer groups over {quarters} quarters using SQL window functions.
- Built an early-warning watchlist flagging {len(watch):,} banks on asset quality, profitability, and capital, delivered as an Excel peer report and dashboard-ready dataset.
"""
    (OUT / "results_summary.md").write_text(text)
    return text


def update_readme(summary_text):
    readme = ROOT / "README.md"
    start, end = "<!-- RESULTS_START -->", "<!-- RESULTS_END -->"
    text = readme.read_text()
    if start in text and end in text:
        body = summary_text.split("\n", 2)[2].split("## Resume bullets")[0].strip()
        readme.write_text(text.split(start)[0] + start + "\n" + body + "\n" + end + text.split(end)[1])


def main():
    t0 = time.time()
    OUT.mkdir(exist_ok=True); IMG.mkdir(exist_ok=True)
    fin, inst = get_data(use_cache="--use-cache" in sys.argv)
    peers, banks, watch = run_sql(fin, inst)

    banks.to_csv(OUT / "bank_benchmarks_for_tableau.csv", index=False)
    peers.to_csv(OUT / "peer_medians.csv", index=False)
    watch.to_csv(OUT / "watchlist.csv", index=False)

    export_excel(peers, banks, watch)
    make_charts(peers, banks)
    summary = write_summary(banks, peers, watch)
    update_readme(summary)
    print("\n" + summary)
    print(f"Done in {time.time() - t0:.0f}s. See outputs/ and images/.")


if __name__ == "__main__":
    main()
