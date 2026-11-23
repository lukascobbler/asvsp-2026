import gzip
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
OUTPUT_DIR = Path("batch-dataset")
MAX_WORKERS = 12
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

CATEGORY_PATTERNS = {
    "details": re.compile(r"StormEvents_details.*_(d\d+).*\.csv\.gz$", re.IGNORECASE),
    "fatalities": re.compile(r"StormEvents_fatalities.*_(d\d+).*\.csv\.gz$", re.IGNORECASE),
    "locations": re.compile(r"StormEvents_locations.*_(d\d+).*\.csv\.gz$", re.IGNORECASE),
}


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (compatible; StormEventsDownloader/1.0)"}
    )
    return session


def parse_target(filename: str) -> tuple[str, str] | None:
    for category, pattern in CATEGORY_PATTERNS.items():
        match = pattern.search(filename)
        if match:
            year_token = match.group(1)
            return category, year_token
    return None


def fetch_remote_files(session: requests.Session, url: str) -> list[tuple[str, str, str]]:
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    targets: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        filename = href.split("/")[-1]
        parsed = parse_target(filename)
        if not parsed:
            continue

        category, year_token = parsed
        full_url = urljoin(url, href)
        if full_url not in seen_urls:
            seen_urls.add(full_url)
            targets.append((category, year_token, full_url))

    return targets


def download_and_decompress(
    category: str,
    year_token: str,
    file_url: str,
    keep_gz: bool = False,
) -> tuple[str, str, str]:
    filename = file_url.split("/")[-1]
    cat_dir = OUTPUT_DIR / category
    cat_dir.mkdir(parents=True, exist_ok=True)

    gz_path = cat_dir / filename
    csv_path = cat_dir / f"{category}_{year_token}.csv"

    if csv_path.exists() and csv_path.stat().st_size > 0:
        return ("skipped", category, str(csv_path))

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with create_session() as session:
                with session.get(file_url, stream=True, timeout=REQUEST_TIMEOUT) as r:
                    r.raise_for_status()
                    with open(gz_path, "wb") as f_out:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f_out.write(chunk)

            with gzip.open(gz_path, "rb") as f_in, open(csv_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            if not keep_gz and gz_path.exists():
                gz_path.unlink()

            return ("ok", category, str(csv_path))

        except Exception as exc:
            last_err = exc
            if gz_path.exists():
                gz_path.unlink(missing_ok=True)
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)

    raise RuntimeError(f"Failed to process {file_url}: {last_err}")


def main(keep_gz: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for category in CATEGORY_PATTERNS:
        (OUTPUT_DIR / category).mkdir(parents=True, exist_ok=True)

    with create_session() as session:
        targets = fetch_remote_files(session, BASE_URL)

    print(f"Found {len(targets)} matching compressed CSV files.")

    completed = 0
    skipped = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(download_and_decompress, category, year_token, url, keep_gz)
            for category, year_token, url in targets
        ]

        for future in as_completed(futures):
            try:
                status, category, out_path = future.result()
                if status == "ok":
                    completed += 1
                    print(f"[DONE] [{category}] {out_path}")
                elif status == "skipped":
                    skipped += 1
            except Exception as exc:
                failed += 1
                print(f"[ERROR] {exc}")

    print(
        f"\nSummary -> Downloaded & decompressed: {completed}, "
        f"Skipped (already exists): {skipped}, Failed: {failed}"
    )


if __name__ == "__main__":
    main(keep_gz=False)