import json
from pathlib import Path
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import traceback

MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def sort_months(p: Path) -> float:
    return float(MONTH_ORDER.index(p.name)) if p.name in MONTH_ORDER else float('inf')

def sort_days(p: Path) -> float:
    try:
        return float(p.name)
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
    try:
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
    except Exception as e:
        print(f"❌ Exception in extract_data_from_file for {file_path}:")
        traceback.print_exc()
        raise

def process_day(day_dir: Path, output_dir: Path, year_str: str, month_str: str, day_str: str):
    day_output_dir = output_dir / f"{year_str}-{month_str}-{day_str}"
    day_output_dir.mkdir(parents=True, exist_ok=True)
    markets_out = day_output_dir / f"markets_{year_str}_{month_str}_{day_str}.parquet"
    runners_out = day_output_dir / f"runners_{year_str}_{month_str}_{day_str}.parquet"

    # Skip processing if both output files already exist
    if markets_out.exists() and runners_out.exists():
        print(f"⏭️ Skipping {year_str}-{month_str}-{day_str} — already processed.")
        return []

    all_markets, all_runners = [], []
    error_log = []
    for json_file in sorted(day_dir.iterdir()):
        if json_file.is_file():
            try:
                m, r = extract_data_from_file(json_file)
                all_markets.extend(m)
                all_runners.extend(r)
            except Exception as e:
                err_msg = f"❌ Error in file {json_file}: {e}\n{traceback.format_exc()}"
                print(err_msg)
                error_log.append(err_msg)

    if all_markets and all_runners:
        markets_df = pd.DataFrame(all_markets)
        runners_df = pd.DataFrame(all_runners)

        if "bsp" in runners_df.columns:
            runners_df["bsp"] = pd.to_numeric(runners_df["bsp"], errors="coerce")

        # Filter ltp_pt before datetime conversion
        dropped_ltp_pt = None
        if "ltp_pt" in runners_df.columns:
            ltp_pt_mask = (
                runners_df["ltp_pt"].notnull() &
                (runners_df["ltp_pt"] > 0) &
                np.isfinite(runners_df["ltp_pt"])
            )
            dropped_ltp_pt = runners_df.loc[~ltp_pt_mask, ["marketId", "id", "ltp_pt"]]
            if not dropped_ltp_pt.empty:
                dropped_ltp_pt.to_csv(day_output_dir / f"dropped_ltp_pt_{year_str}_{month_str}_{day_str}.csv", index=False)
            runners_df = runners_df[ltp_pt_mask].copy()
            runners_df["ltp_dt"] = pd.to_datetime(runners_df["ltp_pt"], unit="ms", errors="coerce")

        markets_df.to_parquet(markets_out, index=False)
        runners_df.to_parquet(runners_out, index=False)

        print(f"✅ Saved {year_str}-{month_str}-{day_str}: {len(markets_df)} markets, {len(runners_df)} runners")

    # Write error log to file if any errors occurred
    if error_log:
        error_log_path = day_output_dir / f"error_log_{year_str}_{month_str}_{day_str}.txt"
        with open(error_log_path, "w") as elog:
            elog.write("\n".join(error_log))
    return error_log

def process_month(month_dir: Path, output_dir: Path, year_str: str):
    month_str = month_dir.name
    print(f"🗃️  Processing {year_str}-{month_str}...")

    all_day_dirs = [d for d in sorted(month_dir.iterdir(), key=sort_days) if d.is_dir()]

    error_logs = []
    for day_dir in all_day_dirs:
        day_str = day_dir.name
        try:
            result = process_day(day_dir, output_dir, year_str, month_str, day_str)
            if result:
                error_logs.extend(result)
        except Exception as e:
            err_msg = f"❌ Error in process_day for {day_dir}: {e}\n{traceback.format_exc()}"
            print(err_msg)
            error_logs.append(err_msg)

    # After all days processed, print summary of errors if any
    if error_logs:
        print(f"\nSummary of errors for {year_str}-{month_str}:")
        for err in error_logs:
            print(err)

def process_selected_months(json_root: Path, output_dir: Path, year: str, months: list):
    output_dir.mkdir(parents=True, exist_ok=True)
    year_dir = json_root / year
    if not year_dir.is_dir():
        print(f"⚠️ Year directory not found: {year_dir}")
        return
    print(f"📆 Starting year: {year}")
    for month in months:
        month_dir = year_dir / month
        if month_dir.is_dir():
            process_month(month_dir, output_dir, year)
        else:
            print(f"⚠️ Month directory not found: {month_dir}")
    print("🏁 Selected months processing complete.")

if __name__ == "__main__":
    json_root_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/extracted-horseracing/BASIC/decompressed_files")
    output_path = Path("/Users/clairegrady/RiderProjects/betfair/data-model/historical-data/horseracing_parquet_by_day")
    months_to_run = ['Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
    process_selected_months(json_root_path, output_path, '2025', months_to_run)
