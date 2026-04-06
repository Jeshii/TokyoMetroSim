#!/usr/bin/env python3
"""
Download all jreast-*.json timetables from nagix/mini-tokyo-3d into
datasets/timetables/mini-tokyo-3d and copy them into datasets/timetables.
"""
import json
import os
import shutil
import sys
import time
from urllib.request import Request, urlopen

API_URL = "https://api.github.com/repos/nagix/mini-tokyo-3d/contents/data/train-timetables?ref=master"
HEADERS = {"User-Agent": "TokyoMetroSim-Agent", "Accept": "application/vnd.github.v3+json"}
OUT_DIR = os.path.join("datasets", "timetables", "mini-tokyo-3d")
TARGET_DIR = os.path.join("datasets", "timetables")

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(TARGET_DIR, exist_ok=True)

def fetch_json(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req) as r:
        return json.load(r)

def download_file(url, dest_path):
    req = Request(url, headers=HEADERS)
    with urlopen(req) as r:
        data = r.read()
    with open(dest_path, "wb") as f:
        f.write(data)


def main():
    try:
        listing = fetch_json(API_URL)
    except Exception as e:
        print("Failed to fetch listing:", e, file=sys.stderr)
        sys.exit(2)

    jreast_files = [it for it in listing if it.get("name", "").startswith("jreast-") and it.get("type") == "file"]
    if not jreast_files:
        print("No jreast files found in remote listing.")
        return

    downloaded = []
    for item in jreast_files:
        name = item["name"]
        dl = item.get("download_url")
        dest = os.path.join(OUT_DIR, name)
        try:
            if os.path.exists(dest):
                print(f"exists: {dest}")
            else:
                print(f"download: {name}")
                download_file(dl, dest)
                # brief pause to be polite
                time.sleep(0.1)
                downloaded.append(name)
        except Exception as e:
            print(f"error downloading {name}: {e}", file=sys.stderr)
            continue

        target = os.path.join(TARGET_DIR, name)
        if not os.path.exists(target):
            shutil.copy2(dest, target)
            print(f"copied to {target}")
        else:
            print(f"target exists, skipping copy: {target}")

    print("Done. Downloaded count:", len(downloaded))

if __name__ == "__main__":
    main()
