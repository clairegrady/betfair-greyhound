import bz2
from pathlib import Path

# Paths
BASIC_DIR = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/extracted-horseracing/BASIC")
OUTPUT_DIR = Path("/Users/clairegrady/RiderProjects/betfair/afl-model/historical-data/extracted-horseracing/BASIC/decompressed_files")

# Find all .bz2 files recursively
bz2_files = list(BASIC_DIR.rglob("*.bz2"))

if not bz2_files:
    print("No .bz2 files found.")
    exit()

print(f"Found {len(bz2_files)} .bz2 files")

for bz2_file in bz2_files:
    # Extract year/month/day from path parts relative to BASIC_DIR
    try:
        relative_parts = bz2_file.relative_to(BASIC_DIR).parts
        year, month, day = relative_parts[:3]
    except Exception:
        print(f"Skipping {bz2_file}: cannot extract year/month/day from path")
        continue

    # Make output dir for decompressed file
    output_dir = OUTPUT_DIR / year / month / day
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output filename same as compressed but without .bz2 extension
    output_file = output_dir / bz2_file.with_suffix('').name

    # Skip decompression if output file already exists
    if output_file.exists():
        print(f"Skipping {bz2_file}, already decompressed.")
        continue

    print(f"Decompressing {bz2_file} → {output_file}")

    try:
        with bz2.open(bz2_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            f_out.write(f_in.read())
    except Exception as e:
        print(f"Failed to decompress {bz2_file}: {e}")
