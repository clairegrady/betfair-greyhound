import os
import tarfile
import bz2
import gzip
import glob
import json

# Base directories
raw_tar_dir = '/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/raw'
extract_base_dir = '/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/extracted'
jsonl_output_base = '/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/jsonl_files'

os.makedirs(extract_base_dir, exist_ok=True)
os.makedirs(jsonl_output_base, exist_ok=True)

# Find all .tar files in the raw data directory
tar_files = glob.glob(os.path.join(raw_tar_dir, '*.tar'))

print(f"🔍 Found {len(tar_files)} .tar files to process.\n")

for tar_path in tar_files:
    tar_name = os.path.splitext(os.path.basename(tar_path))[0]
    extract_dir = os.path.join(extract_base_dir, tar_name)
    jsonl_output_dir = os.path.join(jsonl_output_base, tar_name)

    os.makedirs(extract_dir, exist_ok=True)
    os.makedirs(jsonl_output_dir, exist_ok=True)

    print(f"📦 Extracting {tar_path} to {extract_dir}...")
    with tarfile.open(tar_path, 'r') as tar:
        tar.extractall(path=extract_dir)
    print(f"✅ Extraction complete: {extract_dir}\n")

    # Find compressed files in the extracted folder
    bz2_files = glob.glob(os.path.join(extract_dir, '**', '*.bz2'), recursive=True)
    gz_files = glob.glob(os.path.join(extract_dir, '**', '*.gz'), recursive=True)
    all_compressed_files = bz2_files + gz_files

    print(f"📄 Found {len(all_compressed_files)} compressed files in {tar_name} to convert.\n")

    for compressed_file in all_compressed_files:
        rel_path = os.path.relpath(compressed_file, extract_dir)
        output_file_rel = rel_path
        if output_file_rel.endswith('.bz2'):
            output_file_rel = output_file_rel[:-4] + '.jsonl'
        elif output_file_rel.endswith('.gz'):
            output_file_rel = output_file_rel[:-3] + '.jsonl'
        else:
            continue  # Skip unknown

        output_path = os.path.join(jsonl_output_dir, output_file_rel)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if os.path.exists(output_path):
            print(f"⏩ Skipping (already exists): {output_path}")
            continue

        try:
            open_func = bz2.open if compressed_file.endswith('.bz2') else gzip.open

            with open_func(compressed_file, 'rt') as f_in, open(output_path, 'w') as f_out:
                for line in f_in:
                    try:
                        json_obj = json.loads(line)
                        f_out.write(json.dumps(json_obj) + '\n')
                    except json.JSONDecodeError:
                        print(f"⚠️ Skipping bad JSON in {compressed_file}")
            print(f"✅ Converted: {compressed_file} → {output_path}")
        except Exception as e:
            print(f"❌ Error with {compressed_file}: {e}")

print("\n🎉 All tar files processed and converted to JSONL.")
