#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

scripts=(
  "clean-and-prepare-data.py"
  "select-greyhound-features.py"
  "prepare-data-for-model.py"
  "split-data-by-year.py"
  "train-xgboost.py"
)

for script in "${scripts[@]}"; do
  echo "Running $script..."
  python3 "$script"
done

echo "✅ All scripts completed successfully."
