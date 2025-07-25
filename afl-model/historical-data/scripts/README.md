# 🐕 Greyhound Data Pipeline – Script Overview

This repository processes Betfair greyhound market and runner data from raw `.tar.bz2` archives into a structured format for training machine learning models (e.g. XGBoost).

---

## 📂 Script Execution Order

### 1. `extract-data-from-tar-and-convert-to-jsonl.py`
Extract `.tar.bz2` archives and convert each compressed `.bz2` file inside to newline-delimited JSON (`.jsonl`) format.  
💡 This replaces older individual extract/convert scripts.

---

### 2. `load-data-into-df.py`
Load `.jsonl` market stream data into a pandas DataFrame for processing.

---

### 3. `extract-runner-level-data.py`
Extract and structure runner-level data (e.g. individual dogs, prices, positions) from the DataFrame.

---

### 4. `extract-greyhound-market-data.py`
Extract market-level metadata (e.g. venue, event IDs, market start times) relevant to greyhound races.

---

### 5. `merge-runner-and-market-data.py`
Merge runner-level and market-level DataFrames into a unified dataset.

---

### 6. `clean-and-prepare-data.py`
Clean the merged data:
- Handle missing values
- Filter invalid records
- Ensure correct datatypes

---

### 7. `create-and-select-greyhound-features.py`
Generate domain-specific features (e.g. price movement, trap numbers) and optionally select a subset of useful ones for modeling.

---

### 8. `prepare-data-for-model.py`
Final transformations:
- Encode categorical variables  
- Normalize/scale values  
- Drop unnecessary columns

---

### 9. `split-data-by-year.py`
Split the dataset into train/test sets based on year for time-aware validation.

---

### 10. `train-xgboost.py`
Train an XGBoost model on the prepared dataset using selected features.

---

### 11. `explore-data.py`
(Optional) Perform exploratory data analysis at any point in the pipeline.

