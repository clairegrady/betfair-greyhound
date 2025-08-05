import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def sort_months(p: Path) -> int:
    return MONTH_ORDER.index(p.name) if p.name in MONTH_ORDER else float('inf')

def sort_days(p: Path) -> int:
    try:
        return int(p.name)
    except ValueError:
        return float('inf')

def parse_market_definition(md: dict) -> dict:
    keys = [
        "id", "bspMarket", "turnInPlayEnabled", "persistenceEnabled", "marketBaseRate",
        "eventId", "eventTypeId", "numberOfWinners", "bettingType", "marketType",
        "marketTime", "suspendTime", "bspReconciled", "complete", "inPlay",
        "crossMatching", "runnersVoidable", "numberOfActiveRunners", "betDelay",
        "status", "venue", "countryCode", "discountAllowed", "timezone", "openDate",
        "version", "name", "eventName"
    ]
    return {k: md.get(k) for k in keys}

def parse_runner_definition(runner: dict) -> dict:
    keys = [
        "status", "sortPriority", "bsp", "removalDate", "id", "name", "hc", "adjustmentFactor"
    ]
    rd = {k: runner.get(k) for k in keys}

    bsp_val = rd.get("bsp")
    if isinstance(bsp_val, str) and bsp_val.lower() in {"infinity", "inf"}:
        rd["bsp"] = float('nan')

    return rd

def extract_data_from_file(file_path: Path) -> Tuple[List[Dict], List[Dict]]:
    markets, runners_def = [], []
    latest_ltp: Dict[Tuple[str, int], Tuple[int, float]] = {}

    with file_path.open('r', encoding='utf-8') as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("op") != "mcm":
                continue
            pt = obj.get("pt")

            for market_change in obj.get("mc", []):
                market_id = market_change.get("id")
                for runner_change in market_change.get("rc", []):
                    runner_id = runner_change.get("id")
                    ltp = runner_change.get("ltp")
                    if ltp is not None and market_id and runner_id:
                        key = (market_id, runner_id)
                        if key not in latest_ltp or pt > latest_ltp[key][0]:
                            latest_ltp[key] = (pt, ltp)

            for mc in obj.get("mc", []):
                market_id = mc.get("id")
                market_def = mc.get("marketDefinition", {})
                if market_def:
                    mkt = parse_market_definition(market_def)
                    mkt["pt"] = pt
                    mkt["marketId"] = market_id
                    markets.append(mkt)
                    for runner in market_def.get("runners", []):
                        rd = parse_runner_definition(runner)
                        rd["marketId"] = market_id
                        rd["pt"] = pt
                        runners_def.append(rd)

    for runner in runners_def:
        key = (runner["marketId"], runner["id"])
        if key in latest_ltp:
            runner["ltp"] = latest_ltp[key][1]
            runner["ltp_pt"] = latest_ltp[key][0]
        else:
            runner["ltp"] = np.nan
            runner["ltp_pt"] = np.nan

    return markets, runners_def

def process_day_dir(day_dir: Path) -> Tuple[List[Dict], List[Dict]]:
    all_markets, all_runners = [], []
    for json_file in sorted(day_dir.iterdir()):
        if json_file.is_file():
            try:
                m, r = extract_data_from_file(json_file)
                all_markets.extend(m)
                all_runners.extend(r)
            except Exception as e:
                print(f"❌ Error in file {json_file}: {e}")
    return all_markets, all_runners

def process_month(month_dir: Path, output_dir: Path, year_str: str):
    month_str = month_dir.name
    print(f"🗃️  Processing {year_str}-{month_str}...")

    markets_month, runners_month = [], []
    all_day_dirs = [d for d in sorted(month_dir.iterdir(), key=sort_days) if d.is_dir()]

    with ProcessPoolExecutor(max_workers=min(3, multiprocessing.cpu_count())) as executor:
        futures = [executor.submit(process_day_dir, d) for d in all_day_dirs]

        for future in as_completed(futures):
            try:
                m, r = future.result()
                markets_month.extend(m)
                runners_month.extend(r)
            except Exception as e:
                print(f"❌ Error in parallel processing: {e}")

    if markets_month and runners_month:
        markets_df = pd.DataFrame(markets_month)
        runners_df = pd.DataFrame(runners_month)

        if "bsp" in runners_df.columns:
            runners_df["bsp"] = pd.to_numeric(runners_df["bsp"], errors="coerce")
        if "ltp_pt" in runners_df.columns:
            runners_df["ltp_dt"] = pd.to_datetime(runners_df["ltp_pt"], unit="ms", errors="coerce")

        month_output_dir = output_dir / f"{year_str}-{month_str}"
        month_output_dir.mkdir(parents=True, exist_ok=True)

        markets_out = month_output_dir / f"markets_{year_str}_{month_str}.parquet"
        runners_out = month_output_dir / f"runners_{year_str}_{month_str}.parquet"

        markets_df.to_parquet(markets_out, index=False)
        runners_df.to_parquet(runners_out, index=False)

        print(f"✅ Saved {year_str}-{month_str}: {len(markets_df)} markets, {len(runners_df)} runners")

def process_all_files(json_root: Path, output_dir: Path, years_to_process: List[str]):
    output_dir.mkdir(parents=True, exist_ok=True)

    for year_int in range(2016, 2026):
        year_str = str(year_int)
        if years_to_process and year_str not in years_to_process:
            continue

        year_dir = json_root / year_str
        if not year_dir.is_dir():
            print(f"⚠️ Year directory not found: {year_dir}")
            continue

        print(f"📆 Starting year: {year_str}")
        for month_dir in sorted(year_dir.iterdir(), key=sort_months):
            if month_dir.is_dir():
                process_month(month_dir, output_dir, year_str)

    print("🏁 All processing complete.")

if __name__ == "__main__":
    json_root_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/extracted-horseracing/BASIC/decompressed_files")
    output_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_month")

    years_to_run = [str(y) for y in range(2016, 2026)]  # Process all years 2016-2025
    process_all_files(json_root_path, output_path, years_to_process=years_to_run)
