import os
import glob
import json

extracted_dir = 'historical-data/extracted/'
json_output_dir = 'historical-data/json_files/'

os.makedirs(json_output_dir, exist_ok=True)

# Find all files, exclude .bz2, .gz, and already-JSON files
all_files = glob.glob(os.path.join(extracted_dir, '**', '*'), recursive=True)

for file_path in all_files:
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()

    # Skip compressed files and JSON files
    if ext in ['.bz2', '.gz', '.json']:
        continue

    try:
        # Read the raw document
        with open(file_path, 'r') as f:
            content = f.read()

        # Attempt to parse as JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # If not JSON, you might want to handle differently
            print(f"File {file_path} is not valid JSON, skipping.")
            continue

        # Save as JSON
        output_path = os.path.join(json_output_dir, filename + '.json')
        with open(output_path, 'w') as f_out:
            json.dump(data, f_out)
        print(f"Converted {file_path} to {output_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
