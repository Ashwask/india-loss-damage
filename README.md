# India's Loss and Damage System

A public, single-page map of what India has, what is partial and what is missing when climate change causes loss: laws, institutions, money, data and warning systems, places, and the global architecture. Verified against official documents as of 21 November 2026.

## How it works

- `data/facts.md` is the verified fact sheet. Every row in its first section rests on a primary or official document that was opened and read.
- `python3 build.py` turns the fact sheet into `data.js` and the state outlines into `india.js`.
- `index.html` reads `data.js` and renders the page. No build step beyond that, and no external scripts.

To change a figure, edit `data/facts.md`, run `python3 build.py`, and open `index.html`.

## Weekly source check

`.github/workflows/source-check.yml` runs `check_sources.py` every Monday. It compares each source document with the record in `data/sources.lock.json` and opens an issue (label `source-check`) when a document has changed or returns 404. It never changes a figure: a person re-reads the document, corrects `data/facts.md` if needed, and refreshes the baseline with `python3 check_sources.py --update`.

Some government sites refuse automated requests. For those, the script asks the Internet Archive's public API for its latest capture of the document and compares that capture's digest with the baseline. This is a lagging signal: it only moves when the Archive crawls the document again. Documents that are blocked and have no Archive capture are listed as not monitored in each run's summary.

## Rules for content

- Sourced, verified data only. If a figure cannot be confirmed in a primary document it is left out, or shown as "not found".
- Figures reported by a news outlet or a named speaker appear only in the place cases and are labelled as reported.
- The "Figures left out, and why" list on the page records widely circulated numbers that failed verification.
- No em-dashes or en-dashes anywhere; `build.py` fails if one appears in the data.

## Known limits

- The "Stage 1, right now" strip and the "Now" line on each place card are the only live elements. The "Now" line reads modelled weather and any returned official warning for the marker coordinates from `mugilu.live/c/{lat},{lon}.json`, when the reader reaches section 9. It reads NDMA SACHET alerts through `mugilu.live/warnings.json` in the visitor's browser, is labelled as not verified, and hides itself if the feed cannot be reached.
- Several Home Ministry documents are scans read by OCR. The death and housing relief figures were checked by eye; other amounts from those letters were not.
- The Home Ministry damage table for 2025-26 does not sum to its printed totals. The page shows this as printed, with the caveat.
- COP31 had not concluded on 21 November 2026, so no outcome from it is included.
- The places map uses approximate markers; state-wide events are marked at one city. State outlines (`data/india_states.geojson`) are simplified and for orientation only; the provenance and licence of that boundary file are not recorded.

## Workflow

Changes go through a branch and a pull request. Nothing is pushed directly to `main`.

## Licence

MIT. See `LICENSE`.
