import pandas as pd
import numpy as np
import s3fs
from pathlib import Path
import matplotlib.pyplot as plt
import argparse

# S3 config
s3_bucket = "betfair-clairegrady"
s3_output_prefix = "shap-feature-importance-2025/"
s3 = s3fs.S3FileSystem(anon=False)

shap_plot_dir = Path("./models")
shap_plot_dir.mkdir(parents=True, exist_ok=True)

parser = argparse.ArgumentParser()
parser.add_argument('--years', nargs='+', type=str, required=True, help='List of years to aggregate, e.g. 2016 2017 2018')
parser.add_argument('--output', type=str, default='all_years', help='Output label for aggregated files')
args = parser.parse_args()

all_importances = []
all_features = None

# Download and aggregate per-year CSVs from S3
years = args.years
for year in years:
    s3_csv_path = f"{s3_bucket}/{s3_output_prefix}{year}/shap_feature_importance_{year}.csv"
    local_csv_path = shap_plot_dir / f"shap_feature_importance_{year}.csv"
    s3.get(s3_csv_path, local_csv_path.as_posix())
    df = pd.read_csv(local_csv_path)
    if all_features is None:
        all_features = df['feature']
    all_importances.append(df['mean_abs_shap'].values)

# Aggregate (mean) across years
all_importances = np.vstack(all_importances)
mean_importance = np.mean(all_importances, axis=0)
agg_df = pd.DataFrame({
    'feature': all_features,
    'mean_abs_shap': mean_importance
}).sort_values('mean_abs_shap', ascending=False)

# Save aggregated CSV
agg_csv_path = shap_plot_dir / f"shap_feature_importance_{args.output}.csv"
agg_df.to_csv(agg_csv_path, index=False)
print(f"Saved aggregated feature importance CSV: {agg_csv_path}")

# Plot aggregated SHAP feature importance
plt.figure(figsize=(10, 6))
plt.barh(agg_df['feature'], agg_df['mean_abs_shap'])
plt.xlabel('Mean |SHAP value|')
plt.title('Aggregated SHAP Feature Importance')
plt.gca().invert_yaxis()
agg_plot_path = shap_plot_dir / f"shap_summary_plot_{args.output}.png"
plt.tight_layout()
plt.savefig(agg_plot_path)
plt.close()
print(f"Saved aggregated SHAP plot: {agg_plot_path}")

# Upload to S3
s3_plot_path = f"{s3_bucket}/{s3_output_prefix}{args.output}/shap_summary_plot_{args.output}.png"
s3_csv_path = f"{s3_bucket}/{s3_output_prefix}{args.output}/shap_feature_importance_{args.output}.csv"
s3.put(agg_plot_path.as_posix(), s3_plot_path)
s3.put(agg_csv_path.as_posix(), s3_csv_path)
print(f"Uploaded aggregated plot and CSV to S3 subfolder '{args.output}'.")
