"""Check whether the source documents behind the page have changed.

The page shows only figures that were read in a source document. This script does not
update any figure. It tells a person which documents need to be read again.

  python3 check_sources.py                 compare against data/sources.lock.json
  python3 check_sources.py --update        record the current state as the baseline

What it compares:
  file (PDF or other download): SHA-256 of the bytes. A different hash means the document changed.
  page (HTML): reachability only, because pages change on every load.

Outcomes per URL: ok, changed, gone (404 or 410), unreachable (timeout, block or other error),
new (used by the page but not in the baseline).
Only "changed" and "gone" ask for attention. Many government sites block automated requests,
so "unreachable" is listed but does not raise an issue by itself.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import re
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
    today = datetime.date.today().isoformat()

    if args.update:
        new_lock = {}
        for url in sorted(used):
            res = results[url]
            if res["status"] == 200:
                new_lock[url] = dict(kind=res["kind"], sha256=res["sha256"], size=res["size"], recorded=today)
            elif url in lock:
                new_lock[url] = lock[url]  # keep the last good record if it cannot be reached today
        LOCK.write_text(json.dumps(new_lock, indent=1) + "\n", encoding="utf-8")
        missing = [u for u in used if u not in new_lock]
        print(f"baseline written: {len(new_lock)} of {len(used)} sources recorded")
        for u in missing:
            print(f"  not recorded ({results[u].get('error')}): {u}")
        return

    groups = dict(changed=[], gone=[], unreachable=[], new=[], ok=[])
    for url in sorted(used):
        res, base = results[url], lock.get(url)
        if res["status"] in (404, 410):
            groups["gone"].append(url)
        elif res["status"] != 200:
            groups["unreachable"].append(url)
        elif base is None:
            groups["new"].append(url)
        elif base["kind"] == "file" and res["kind"] == "file" and base["sha256"] != res["sha256"]:
            groups["changed"].append(url)
        else:
            groups["ok"].append(url)

    def rows(urls, extra=lambda u: ""):
        return "\n".join(f"- {u}\n  - Used by: {'; '.join(used[u])}{extra(u)}" for u in urls) or "- None"

    attention = bool(groups["changed"] or groups["gone"])
    report = f"""## Source document check, {today}

{len(used)} sources checked: {len(groups['ok'])} unchanged, {len(groups['changed'])} changed, {len(groups['gone'])} gone, {len(groups['unreachable'])} unreachable, {len(groups['new'])} not yet in the baseline.

### Changed: read again before trusting the figures
{rows(groups['changed'], lambda u: f"\n  - Size {lock[u]['size']} bytes when recorded on {lock[u]['recorded']}, {results[u]['size']} bytes now")}

### Gone (404 or 410): find the new location or an archive copy
{rows(groups['gone'])}

### Unreachable this run (often a block on automated requests, not a change)
{rows(groups['unreachable'], lambda u: f"\n  - {results[u].get('error')}")}

### Used by the page but not in the baseline
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
