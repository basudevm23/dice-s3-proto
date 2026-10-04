# %% [markdown]
# # Step 1.1 - Get the two public datasets
# 1. **Amazon India sales report** (Kaggle): real orders with status, SKU, size, pincode.
# 2. **All India Pincode Directory** (India Post / data.gov.in): district, lat/long per pincode.
#
# Run: `python step1_collect/01_get_data.py`  (or open in VS Code / Jupyter and run cell by cell)

# %%
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(ROOT))
from common import RAW  # noqa: E402

ORDERS_FILE = RAW / "amazon_sale_report.csv"
PINCODE_FILE = RAW / "pincode_directory.csv"

KAGGLE_SLUG = "thedevastator/unlock-profits-with-e-commerce-sales-data"
# Fallback: a public GitHub copy of the same file (used only if Kaggle isn't set up)
MIRROR_ZIP = "https://raw.githubusercontent.com/ThaoNguyen710/Indian-Amazon-Sales-Report/main/Dataset/amz_report_original.zip"
PINCODE_URL = "https://raw.githubusercontent.com/dropdevrahul/pincodes-india/main/pincode.csv"


def download(url, dest):
    print(f"downloading {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


# %% Orders dataset
def get_orders():
    if ORDERS_FILE.exists():
        print(f"already have {ORDERS_FILE.name}")
        return
    tmp = RAW / "_tmp"
    tmp.mkdir(exist_ok=True)
    # Option A: official Kaggle CLI (needs ~/.kaggle/kaggle.json, see README)
    if shutil.which("kaggle"):
        try:
            subprocess.run(["kaggle", "datasets", "download", "-d", KAGGLE_SLUG, "-p", str(tmp), "--unzip"], check=True)
            found = [p for p in tmp.rglob("*.csv") if "amazon sale report" in p.name.lower()]
            if found:
                shutil.move(str(found[0]), ORDERS_FILE)
                print(f"saved {ORDERS_FILE} (from Kaggle)")
                shutil.rmtree(tmp, ignore_errors=True)
                return
        except subprocess.CalledProcessError as e:
            print("Kaggle download failed, trying mirror:", e)
    # Option B: GitHub mirror
    z = tmp / "orders.zip"
    download(MIRROR_ZIP, z)
    with zipfile.ZipFile(z) as zf:
        name = [n for n in zf.namelist() if n.endswith(".csv")][0]
        zf.extract(name, tmp)
        shutil.move(str(tmp / name), ORDERS_FILE)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"saved {ORDERS_FILE} (from GitHub mirror)")


# %% Pincode directory
def get_pincodes():
    if PINCODE_FILE.exists():
        print(f"already have {PINCODE_FILE.name}")
        return
    download(PINCODE_URL, PINCODE_FILE)
    print(f"saved {PINCODE_FILE}")


# %%
if __name__ == "__main__" or "__file__" not in globals():
    get_orders()
    get_pincodes()
    print("\nNext: python step2_prepare/04_prepare_orders.py")
