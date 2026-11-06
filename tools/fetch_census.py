#!/usr/bin/env python3
"""Download census files for one county from xml.arkivverket.no.

    python tools/fetch_census.py                     # Østfold: 1801 CSV + 1865/1900/1910 booklets
    python tools/fetch_census.py --counties 17Nord-Trondelag 04Hedmark --years 1865 1900 1910

Files go to data/raw/ (git-ignored: the licence is not stated, so the data is
not committed). Existing files are skipped. At most one request per second,
with a clear User-Agent. xml.arkivverket.no has no robots.txt; do not point
this at www.digitalarkivet.no or api.digitalarkivet.no, whose robots.txt
disallows AI agents.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ancestor_finder.sources.base import USER_AGENT, RateLimiter  # noqa: E402

BASE = "https://xml.arkivverket.no/folketellinger"
def ft1801_name(county_dir: str) -> str:
    """'17Nord-Trondelag' -> 'Ft1801_forsk_17NordTrondelag_v1.txt' (the 1801 files drop - and _)."""
    special = {"14Sogn_og_fjordane": "14SognFjordane", "15More_og_Romsdal": "15MoreRomsdal",
               "03Oslo": "03Kristiania", "09Aust-Agder": "09AustAgder", "10Vest-Agder": "10VestAgder",
               "16Sor-Trondelag": "16SorTrondelag", "17Nord-Trondelag": "17NordTrondelag"}
    return f"Ft1801_forsk_{special.get(county_dir, county_dir)}_v1.txt"
limiter = RateLimiter(1.0)


def _ssl_context():
    """Use certifi's certificates when installed: Python from python.org on a
    Mac has none of its own until 'Install Certificates.command' is run."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def get(url: str) -> bytes:
    if not url.startswith("https://xml.arkivverket.no/"):
        raise ValueError(f"refusing to fetch outside xml.arkivverket.no: {url}")
    limiter.wait()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as r:
        return r.read()


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(get(url))
    tmp.rename(dest)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--counties", nargs="+", default=["01Ostfold"],
                    help="folder names on xml.arkivverket.no, e.g. 01Ostfold 17Nord-Trondelag 04Hedmark")
    ap.add_argument("--years", nargs="+", type=int, default=[1801, 1865, 1900, 1910])
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    args = ap.parse_args(argv)

    for county in args.counties:
        for year in args.years:
            if year == 1801:
                name = ft1801_name(county)
                new = download(f"{BASE}/ft1801/{name}", args.out / "1801" / name)
                print(f"1801 {name} {'downloaded' if new else 'already present'}")
                continue
            listing = get(f"{BASE}/hefter/{year}/{county}/").decode("utf-8", "replace")
            files = sorted(set(re.findall(r'href="([^"/]+_hefte\.pdf)"', listing)))
            print(f"{county} {year}: {len(files)} booklets")
            for i, f in enumerate(files, 1):
                new = download(f"{BASE}/hefter/{year}/{county}/{f}", args.out / str(year) / county / f)
                print(f"  [{i}/{len(files)}] {f} {'downloaded' if new else 'present'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as e:
        msg = f"Download failed: {e.reason}"
        if "CERTIFICATE_VERIFY_FAILED" in str(e.reason):
            msg += ("\nPython can't check the site's certificate. Run  python3 -m pip install certifi  and try again\n"
                    "(or 'Install Certificates.command' in the Python folder under Applications).")
        sys.exit(msg)
