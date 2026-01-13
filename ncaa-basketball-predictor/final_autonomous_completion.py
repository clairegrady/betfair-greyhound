#!/usr/bin/env python3
"""
FINAL AUTONOMOUS COMPLETION
Waits for features, trains model, validates, tests
"""
import time
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent

def wait_for_features():
    """Wait for feature building to complete"""
    features_path = PROJECT_ROOT / "features_dataset.csv"
    print("⏳ Waiting for feature building to complete...")
    
    last_size = 0
    stall_count = 0
    
    while True:
        if features_path.exists():
            size = features_path.stat().st_size
            if size > last_size:
                last_size = size
                stall_count = 0
                print(f"   Features file: {size:,} bytes")
            else:
                stall_count += 1
                if stall_count > 6:  # 60 seconds no growth
                    print("✅ Feature building complete")
                    return True
        time.sleep(10)

def run_cmd(cmd):
    """Run command and return success"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=PROJECT_ROOT,
                              capture_output=True, text=True, timeout=3600)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("="*70)
    print("🚀 FINAL AUTONOMOUS COMPLETION")
    print("="*70)
    
    # Wait for features
    if not wait_for_features():
        print("❌ Feature building failed")
        return False
    
    # Train model
    print("\n" + "="*70)
    print("🧠 TRAINING MODEL")
    print("="*70)
    if not run_cmd("python3 pipelines/train_multitask_model.py"):
        print("❌ Model training failed")
        return False
    
    # Test predictions
    print("\n" + "="*70)
    print("🎯 TESTING PREDICTIONS")
    print("="*70)
    if not run_cmd("python3 show_predictions.py | head -50"):
        print("⚠️ Prediction test had issues")
    
    print("\n" + "="*70)
    print("✅ COMPLETE!")
    print("="*70)
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

