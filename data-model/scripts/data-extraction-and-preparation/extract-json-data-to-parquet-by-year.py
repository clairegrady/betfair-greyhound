## change json_root path and output_path when working with new data (this script is suitable for greyhounds and horses and possible all betfair historical data)

import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple

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
    latest_ltp: Dict[Tuple[str, int], Tuple[int, float]] = {}  # (marketId, runnerId) → (pt, ltp)

    with file_path.open('r', encoding='utf-8') as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("op") != "mcm":
                continue
            pt = obj.get("pt")

            # Update latest LTP for any runner changes in this message (whether or not marketDefinition exists)
            if "mc" in obj:
                for market_change in obj["mc"]:
                    market_id = market_change.get("id")
                    for runner_change in market_change.get("rc", []):
                        runner_id = runner_change.get("id")
                        ltp = runner_change.get("ltp")
                        if ltp is not None and market_id is not None and runner_id is not None:
                            key = (market_id, runner_id)
                            # Keep the latest by pt
                            if key not in latest_ltp or pt > latest_ltp[key][0]:
                                latest_ltp[key] = (pt, ltp)

            # Process marketDefinition if present
            for mc in obj.get("mc", []):
                market_id = mc.get("id")
                market_def = mc.get("marketDefinition", {})

                if market_def:
                    mkt = parse_market_definition(market_def)
                    mkt["pt"] = pt
                    mkt["marketId"] = market_id
                    markets.append(mkt)

                    # Runner static defs
                    for runner in market_def.get("runners", []):
                        rd = parse_runner_definition(runner)
                        rd["marketId"] = market_id
                        rd["pt"] = pt
                        runners_def.append(rd)

    # Merge latest LTP and PT into runners_def
    for runner in runners_def:
        key = (runner["marketId"], runner["id"])
        if key in latest_ltp:
            runner["ltp"] = latest_ltp[key][1]
            runner["ltp_pt"] = latest_ltp[key][0]
        else:
            runner["ltp"] = np.nan
            runner["ltp_pt"] = np.nan

    return markets, runners_def

def process_all_files(json_root: Path, output_dir: Path, years_to_process: List[str] = None):
    output_dir.mkdir(parents=True, exist_ok=True)

    for year_dir in sorted(json_root.iterdir()):
        if not year_dir.is_dir():
            continue

        year_str = year_dir.name

        # 👉 Skip if we're not targeting this year
        if years_to_process is not None and year_str not in years_to_process:
            continue

        markets_file = output_dir / f"markets_{year_str}.parquet"
        runners_file = output_dir / f"runners_{year_str}.parquet"

        if markets_file.exists() and runners_file.exists():
            print(f"⏭️ Skipping year {year_str} as output files already exist.")
            continue

        markets_year, runners_year = [], []

        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                for json_file in sorted(day_dir.iterdir()):
                    if not json_file.is_file():
                        continue
                    m, r = extract_data_from_file(json_file)
                    markets_year.extend(m)
                    runners_year.extend(r)

        if markets_year and runners_year:
            markets_df = pd.DataFrame(markets_year)
            runners_df = pd.DataFrame(runners_year)

            if "bsp" in runners_df.columns:
                runners_df["bsp"] = pd.to_numeric(runners_df["bsp"], errors="coerce")
            if "ltp_pt" in runners_df.columns:
                runners_df["ltp_dt"] = pd.to_datetime(runners_df["ltp_pt"], unit="ms", errors="coerce")

            try:
                markets_df.to_parquet(markets_file, index=False)
                runners_df.to_parquet(runners_file, index=False)
                print(f"✅ Saved data for year {year_str}: {len(markets_df)} markets, {len(runners_df)} runners")
            except Exception as e:
                print(f"❌ Error saving parquet for year {year_str}: {e}")

    print("🏁 Extraction complete.")


if __name__ == "__main__":
    json_root_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/extracted-horseracing/BASIC/decompressed_files")
    output_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_year")

    years = ["2021", "2024"]
    process_all_files(json_root_path, output_path, years_to_process=years)