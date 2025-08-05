import subprocess
import time
import sys
from pathlib import Path

MAIN_SCRIPT = "/Users/clairegrady/RiderProjects/betfair/data-model/scripts/data-extraction-and-preparation/clean-and-prepare-monthly-data.py"
MAX_RETRIES = 3
RETRY_DELAY = 15

current_processing_file = Path("currently_processing.txt")
failed_log = Path("failed_months.txt")

def log_failed_month(month_str):
    with failed_log.open("a") as f:
        f.write(month_str + "\n")

def get_current_month():
    if current_processing_file.exists():
        return current_processing_file.read_text().strip()
    return None

def clear_current_month():
    if current_processing_file.exists():
        current_processing_file.unlink()

def run_main_script():
    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        print(f"▶️ Starting main script, attempt {attempt}...")
        proc = subprocess.run([sys.executable, MAIN_SCRIPT])

        # Exit 0 means success
        if proc.returncode == 0:
            print("✅ Main script completed successfully.")
            return True

        print(f"⚠️ Main script exited with code {proc.returncode}. Retrying after {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)

    # Final failure after retries — log current month if still set
    month = get_current_month()
    if month:
        print(f"❌ Logging failed month: {month}")
        log_failed_month(month)
        clear_current_month()
    else:
        print("❌ No month was being processed during failure.")

    print(f"❌ Main script failed after {MAX_RETRIES} attempts.")
    return False

if __name__ == "__main__":
    run_main_script()
