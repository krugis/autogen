#!/usr/bin/env python3
"""Convert Parquet metadata files to JSONL format for GAIA init_tasks.py"""

import json
import os
import pandas as pd

GAIA_DIR = os.path.join(os.path.dirname(__file__), "Downloads", "GAIA", "2023")

def convert_metadata_to_jsonl():
    """Convert Parquet metadata files to JSONL."""
    
    for split in ["validation", "test"]:
        split_dir = os.path.join(GAIA_DIR, split)
        parquet_file = os.path.join(split_dir, "metadata.parquet")
        jsonl_file = os.path.join(split_dir, "metadata.jsonl")
        
        if not os.path.exists(parquet_file):
            print(f"Skipping {parquet_file} - not found")
            continue
        
        print(f"Converting {parquet_file} to {jsonl_file}...")
        
        # Read Parquet file
        df = pd.read_parquet(parquet_file)
        
        # Convert to JSONL
        with open(jsonl_file, "w") as f:
            for _, row in df.iterrows():
                json_obj = row.to_dict()
                # Handle NaN and other non-JSON-serializable values
                json_obj = {k: (None if pd.isna(v) else v) for k, v in json_obj.items()}
                # Convert Level to integer
                if "Level" in json_obj and json_obj["Level"] is not None:
                    json_obj["Level"] = int(json_obj["Level"])
                f.write(json.dumps(json_obj) + "\n")
        
        print(f"  ✓ Created {jsonl_file} with {len(df)} records")

if __name__ == "__main__":
    convert_metadata_to_jsonl()
    print("\nConversion complete!")
