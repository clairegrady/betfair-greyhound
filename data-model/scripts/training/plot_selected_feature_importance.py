import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# === User configuration ===
# Path to your SHAP feature importance CSV (e.g., aggregated or for a specific year)
feature_importance_csv = Path("/Users/clairegrady/RiderProjects/betfair/data-model/models/shap_feature_importance_aggregated_all_days.csv")

# List the features you want to plot (in order, or leave empty to plot all)
features_to_plot = []  # e.g., ["feature1", "feature2", ...]

# Number of top features to plot if features_to_plot is empty (set to None to plot all)
top_n = 20

# Output plot file
output_plot = feature_importance_csv.parent / "selected_feature_importance_plot.png"

# === Script logic ===
importance_df = pd.read_csv(feature_importance_csv)

if features_to_plot:
    plot_df = importance_df[importance_df['feature'].isin(features_to_plot)]
    # Preserve user order if possible
    plot_df['feature'] = pd.Categorical(plot_df['feature'], categories=features_to_plot, ordered=True)
    plot_df = plot_df.sort_values('feature')
else:
    plot_df = importance_df.head(top_n) if top_n else importance_df

plt.figure(figsize=(10, max(4, 0.4 * len(plot_df))))
plt.barh(plot_df['feature'], plot_df['mean_abs_shap'], color='skyblue')
plt.xlabel('Mean(|SHAP value|)')
plt.title('Selected Feature Importance (SHAP)')
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig(output_plot)
plt.show()
print(f"Feature importance plot saved to {output_plot}")
