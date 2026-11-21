"""Check whether the source documents behind the page have changed.

The page shows only figures that were read in a source document. This script does not
update any figure. It tells a person which documents need to be read again.

  python3 check_sources.py                 compare against data/sources.lock.json
  python3 check_sources.py --update        record the current state as the baseline

What it compares:
  file (PDF or other download): SHA-256 of the bytes. A different hash means the document changed.
  page (HTML): reachability only, because pages change on every load.

Many government sites block automated requests. When a document cannot be fetched directly,
the script asks the Internet Archive (an open, public API) for its most recent capture of that
URL and compares the capture's content digest with the one in the baseline. That is a lagging
signal: it only moves when the Archive crawls the document again.

Outcomes per URL: ok, ok through the Archive, changed, gone (404 or 410), unreachable
(blocked and no Archive capture), new (used by the page but not comparable with the baseline).
Only "changed" and "gone" ask for attention.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent
LOCK = ROOT / "data" / "sources.lock.json"
SCAN = [ROOT / "data" / "facts.md", ROOT / "index.html"]
SKIP_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com", "mugilu.live", "github.com"}
UA = "india-loss-damage-source-check/1.0 (+https://github.com/Ashwask/india-loss-damage)"
MAX_BYTES = 120 * 1024 * 1024
TIMEOUT = 60


def collect_urls():
    """Every source URL used by the fact sheet or the page, with where it is used."""
    used = {}
    for path in SCAN:
        for line in path.read_text(encoding="utf-8").splitlines():
            for url in re.findall(r"https?://[^\s\"'<>`)\]]+", line):
                url = url.rstrip(".,;")
                if "${" in url or urllib.parse.urlsplit(url).hostname in SKIP_HOSTS:
                    continue
                where = used.setdefault(url, [])
                if path.name == "facts.md" and line.startswith("|"):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    label = cells[2] if len(cells) >= 8 else cells[0]
                    label = re.sub(r"\s+", " ", label)[:80]
                else:
                    label = path.name
                if label not in where:
                    where.append(label)
    return used


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = (r.headers.get("Content-Type") or "").lower()
            digest, size = hashlib.sha256(), 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    return dict(status=0, error="too large")
                digest.update(chunk)
            path = urllib.parse.urlsplit(url).path.lower()
            is_file = "pdf" in ctype or "octet-stream" in ctype or path.endswith(".pdf")
            return dict(status=r.status, kind="file" if is_file else "page", sha256=digest.hexdigest(), size=size)
    except urllib.error.HTTPError as e:
        return dict(status=e.code, error=f"HTTP {e.code}")
    except Exception as e:  # timeouts, TLS and connection errors
        return dict(status=0, error=type(e).__name__)


def archive_capture(url):
    """Latest successful Internet Archive capture of a URL: timestamp and content digest, or None."""
    q = urllib.parse.urlencode(dict(url=url, output="json", limit=-1, fl="timestamp,digest", filter="statuscode:200"))
    req = urllib.request.Request("https://web.archive.org/cdx/search/cdx?" + q, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rows = json.loads(r.read().decode("utf-8") or "[]")
            return dict(timestamp=rows[-1][0], digest=rows[-1][1]) if len(rows) > 1 else None
        except Exception:
            time.sleep(5 * (attempt + 1))  # the Archive throttles bursts
    return None


def fetch_with_retry(url):
    res = fetch(url)
    if res["status"] not in (200, 404, 410):
        res = fetch(url)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="write the current state as the baseline")
    ap.add_argument("--report", default="", help="write a Markdown report to this path")
    args = ap.parse_args()

    used = collect_urls()
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(zip(used, pool.map(fetch_with_retry, used)))
    # Archive lookups run one at a time: for every source when recording, else only for blocked ones.
    for url, res in results.items():
        if args.update or res["status"] not in (200, 404, 410):
            res["archive"] = archive_capture(url)
            time.sleep(1)
    today = datetime.date.today().isoformat()

    if args.update:
        new_lock = {}
        for url in sorted(used):
            res = results[url]
            entry = dict(recorded=today)
            if res["status"] == 200:
                entry.update(kind=res["kind"], sha256=res["sha256"], size=res["size"])
            elif url in lock and "sha256" in lock[url]:
                entry = dict(lock[url])  # keep the last good direct record if it cannot be reached today
            if res.get("archive"):
                entry["archive"] = res["archive"]
            if len(entry) > 1:
                new_lock[url] = entry
        LOCK.write_text(json.dumps(new_lock, indent=1) + "\n", encoding="utf-8")
        missing = [u for u in used if u not in new_lock]
        print(f"baseline written: {len(new_lock)} of {len(used)} sources recorded")
        for u in missing:
            print(f"  not recorded ({results[u].get('error')}): {u}")
        return

    groups = dict(changed=[], gone=[], unreachable=[], new=[], ok=[], ok_archive=[])
    via_archive = set()
    for url in sorted(used):
        res, base = results[url], lock.get(url)
        if res["status"] in (404, 410):
            groups["gone"].append(url)
        elif res["status"] != 200:
            seen, was = res.get("archive"), (base or {}).get("archive")
            if not seen or not was:
                groups["unreachable"].append(url)
            elif seen["digest"] != was["digest"]:
                groups["changed"].append(url)
                via_archive.add(url)
            else:
                groups["ok_archive"].append(url)
        elif base is None or "sha256" not in base:
            groups["new"].append(url)
        elif base["kind"] == "file" and res["kind"] == "file" and base["sha256"] != res["sha256"]:
            groups["changed"].append(url)
        else:
            groups["ok"].append(url)

    def how_changed(u):
        if u in via_archive:
            return f"\n  - Seen through the Internet Archive: capture of {results[u]['archive']['timestamp'][:8]} differs from the capture of {lock[u]['archive']['timestamp'][:8]} in the baseline"
        return f"\n  - Size {lock[u]['size']} bytes when recorded on {lock[u]['recorded']}, {results[u]['size']} bytes now"

    def rows(urls, extra=lambda u: ""):
        return "\n".join(f"- {u}\n  - Used by: {'; '.join(used[u])}{extra(u)}" for u in urls) or "- None"

    attention = bool(groups["changed"] or groups["gone"])
    report = f"""## Source document check, {today}

{len(used)} sources checked: {len(groups['ok'])} unchanged, {len(groups['ok_archive'])} unchanged as far as the Internet Archive shows, {len(groups['changed'])} changed, {len(groups['gone'])} gone, {len(groups['unreachable'])} unreachable, {len(groups['new'])} not comparable with the baseline.

### Changed: read again before trusting the figures
{rows(groups['changed'], how_changed)}

### Gone (404 or 410): find the new location or an archive copy
{rows(groups['gone'])}

### Blocked, checked through the Internet Archive (lagging: only as fresh as the Archive's last capture)
{rows(groups['ok_archive'], lambda u: f"\n  - {results[u].get('error')}; latest capture {results[u]['archive']['timestamp'][:8]}, same as baseline")}

### Unreachable and not in the Internet Archive: not monitored
{rows(groups['unreachable'], lambda u: f"\n  - {results[u].get('error')}")}

### Used by the page but not comparable with the baseline
{rows(groups['new'])}

### What to do
1. Open each changed or gone document and re-read the figures listed under "Used by".
2. Correct `data/facts.md` if a figure changed, then run `python3 build.py`.
3. Run `python3 check_sources.py --update` and include `data/sources.lock.json` in the same pull request.
"""
    print(report)
    if args.report:
        pathlib.Path(args.report).write_text(report, encoding="utf-8")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"attention={'true' if attention else 'false'}\n")


if __name__ == "__main__":
    main()
