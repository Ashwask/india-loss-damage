# India's Loss and Damage System

**Live page: https://ashwask.github.io/india-loss-damage/**

"Relief arrives. Recovery does not." A public page on how India pays for climate loss and damage: what the system warns about, counts, pays for and leaves open. Every figure is verified against official documents as of 21 November 2026.

## What is on the page

The page reads top to bottom in four movements, each with numbered sections that open with a one-line takeaway.

| Movement | Sections |
|---|---|
| I. The system | The journey of a loss (warn, count, pay, recover), a live warnings strip, and the system map: 68 tiles marked as exists, partial or missing, with lenses for laws, institutions, money, data and warning, and global |
| II. The record | One year's death counts from three official publications; slow and widely spread losses (coastal erosion, displacement, heat, uninsured loss) |
| III. The bill | Relief rates before and after the 2026 revision; what states asked for against what was released; money set aside against money released; eleven place cases on a map |
| IV. The choice | Sixteen documented absences; six open questions already raised in official documents; dated items to watch |

Detail is collapsed until opened: tile figures, place cases, gaps, the document list and the list of figures left out.

## How it works

- `data/facts.md` is the verified fact sheet. Every row in its first section rests on a primary or official document that was opened and read.
- `python3 build.py` turns the fact sheet into `data.js` and the state outlines (`data/india_states.geojson`) into `india.js`. It fails if an em-dash or en-dash appears in the data.
- `index.html` reads both files and renders the page. There is no other build step and no script library.

To change a figure: edit `data/facts.md`, run `python3 build.py`, open `index.html` to check, then run `python3 check_sources.py --update` if a source address changed.

## Live elements

Two parts of the page update on each visit. Both are labelled as live and not verified, and both hide themselves if the feed cannot be reached.

- **Stage 1, right now** (section 2): official alerts from NDMA's SACHET feed, read through [mugilu](https://mugilu.live) (`/warnings.json`), newest first.
- **Now** line on each place card (section 9): modelled weather and any returned official warning at the marker's coordinates (`/c/{lat},{lon}.json`). A card with no warning shown does not mean no warning is in force.

Everything else is fixed to the verification date.

## Weekly source check

The page never updates a figure by itself. Instead, two scheduled jobs check whether the source documents have changed, and open or comment on an issue labelled `source-check` when one has changed or returns 404. A person then re-reads the document, corrects `data/facts.md` if needed, and refreshes the baseline (`data/sources.lock.json`) with `python3 check_sources.py --update`.

| Job | When | Reach |
|---|---|---|
| GitHub workflow `.github/workflows/source-check.yml` | Mondays 09:00 IST, or on manual trigger | 47 of 53 sources |
| `scripts/local_check.sh` on a computer in India | Mondays 09:30 with the macOS schedule in `scripts/` | 53 of 53 sources |

How `check_sources.py` compares:

- PDFs and other downloads are compared by SHA-256. Web pages are checked for reachability only.
- When a site refuses automated requests, the script asks the Internet Archive's public API for its latest capture and compares that capture's digest. This lags: it only moves when the Archive crawls the document again.
- Some sites (for example ndmindia.mha.gov.in) refuse connections from GitHub's servers altogether but answer from an Indian connection, which is why the local job exists.

To set up the local job on macOS: copy `scripts/local_check.sh` to `~/Library/Application Support/india-loss-damage/`, copy the plist to `~/Library/LaunchAgents/`, and load it with `launchctl bootstrap gui/$(id -u) <path to the plist>`. It needs `git`, `python3` and a logged-in `gh`. It logs to `~/Library/Logs/india-loss-damage-source-check.log`.

## Rules for content

- Sourced, verified data only. If a figure cannot be confirmed in a primary document it is left out, or shown as "not found".
- Figures reported by a news outlet or a named speaker appear only in the place cases and are labelled as reported.
- The "Figures left out, and why" list on the page records widely circulated numbers that failed verification.
- The page records open questions from official documents. It does not make recommendations.
- No em-dashes or en-dashes anywhere.

## Known limits

- Several Home Ministry documents are scans read by OCR. The death and housing relief figures were checked by eye; other amounts from those letters were not.
- The Home Ministry damage table for 2025-26 does not sum to its printed totals. The page shows this as printed, with the caveat.
- COP31 had not concluded on 21 November 2026, so no outcome from it is included.
- The places map uses approximate markers; state-wide events are marked at one city. State outlines are simplified and for orientation only.
- Weather on the place cards is modelled, not measured, and describes the marker point only.

## Workflow

Changes go through a branch and a pull request. Nothing is pushed directly to `main`.

## Licence

Code: MIT, see `LICENSE`. The source documents cited keep their own terms. State boundaries (`data/india_states.geojson`): Local Government Directory (https://lgdirectory.gov.in/), published by yashveeeeeeer/india-geodata and downloaded from bharatlas (layer `lgd_states`, States 2024), licence CC0-1.0 / CC-BY-4.0; simplified with mapshaper, small islands dropped. Live data comes from mugilu and its upstream sources (NDMA SACHET, IMD, Open-Meteo), each under its own licence.
