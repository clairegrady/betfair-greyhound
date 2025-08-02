import subprocess
import time
import sys

MAIN_SCRIPT = "/Users/clairegrady/RiderProjects/betfair/afl-model/scripts/data-extraction-and-preparation/clean-and-prepare-monthly-data.py" 
MAX_RETRIES = 50
RETRY_DELAY = 20

def run_main_script():
    attempt = 0
    while attempt < MAX_RETRIES:
        attempt += 1
        print(f"▶️ Starting main script, attempt {attempt}...")
        proc = subprocess.run([sys.executable, MAIN_SCRIPT])
        
        # Check exit code
        if proc.returncode == 0:
            print("✅ Main script completed successfully.")
            return True
        else:
            print(f"⚠️ Main script exited with code {proc.returncode}. Retrying after {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)

    print(f"❌ Main script failed after {MAX_RETRIES} attempts.")
    return False

if __name__ == "__main__":
    run_main_script()
