"""Step 1a: download one FAERS quarterly ASCII extract from the FDA."""
from pathlib import Path

import requests

from .config import DATA_DIR, FAERS_URL


def download_quarter(quarter: str) -> Path:
    """Download e.g. '2026q3'. Skips the download if the zip already exists."""
    quarter = quarter.lower()
    dest = DATA_DIR / f"faers_ascii_{quarter}.zip"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  Using existing file {dest.name}")
        return dest

    # The FDA site uses lowercase 'q' for most files and uppercase 'Q' for a few.
    candidates = [quarter, quarter.replace("q", "Q")]
    last_error = None
    for q in dict.fromkeys(candidates):
        url = FAERS_URL.format(quarter=q)
        print(f"  Downloading {url} (about 60 MB) ...")
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code != 200:
                    last_error = f"HTTP {r.status_code}"
                    continue
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
                print(f"  Saved {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
                return dest
        except requests.RequestException as e:
            last_error = str(e)
    raise RuntimeError(
        f"Could not download FAERS {quarter} ({last_error}). Check the quarter on "
        "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html, or download "
        "the ASCII zip manually and pass it with --zip-path."
    )
