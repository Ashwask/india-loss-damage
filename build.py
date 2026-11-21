"""Build data.js from data/facts.md (the verified fact sheet).

Usage: python3 build.py
The page (index.html) reads window.LD from data.js, so it works from file:// and GitHub Pages alike.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "data" / "facts.md"


def table_rows(block):
    rows = [l for l in block.splitlines() if l.startswith("|")]
    out = []
    for line in rows[2:]:  # skip header and separator
        out.append([c.strip() for c in line.strip().strip("|").split("|")])
    return out


def main():
    text = SRC.read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.M)
    by_num = {s[0]: s for s in sections[1:]}

    facts = []
    for r in table_rows(by_num["1"]):
        stage, lens, name, status, desc, key, source, url = r
        facts.append(dict(stage=stage, lens=lens, name=name, status=status,
                          desc=desc, key=key, source=source, url=url))

    gaps = []
    for r in table_rows(by_num["2"]):
        stage, lens, name, says, source, url = r
        gaps.append(dict(stage=stage, lens=lens, name=name, status="gap",
                         desc=says, key="", source=source, url=url))

    places = []
    for r in table_rows(by_num["3"]):
        place, latlong, lost, paid, open_, sources = r
        lat, lon = map(float, re.match(r"([\d.]+) N, ([\d.]+) E", latlong).groups())
        links = [dict(name=n, url=u) for n, u in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", sources)]
        places.append(dict(place=place, lat=lat, lon=lon, lost=lost, paid=paid, open=open_, sources=links))

    left_out = [l[2:].strip() for l in by_num["4"].splitlines() if l.startswith("- ")]

    data = dict(facts=facts, gaps=gaps, places=places, leftOut=left_out)
    blob = json.dumps(data, ensure_ascii=False, indent=1)
    for bad in ("—", "–"):
        assert bad not in blob, "dash found in data"
    (ROOT / "data.js").write_text("window.LD = " + blob + ";\n", encoding="utf-8")
    # state outlines for the places map, rounded to keep the file small
    geo = json.loads((ROOT / "data" / "india_states.geojson").read_text(encoding="utf-8"))
    shapes = []
    for f in geo["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = [[[round(x, 2), round(y, 2)] for x, y in ring] for poly in polys for ring in poly]
        shapes.append(dict(name=f["properties"]["st_nm"], rings=rings))
    (ROOT / "india.js").write_text("window.INDIA = " + json.dumps(shapes, separators=(",", ":")) + ";\n", encoding="utf-8")

    print(f"facts {len(facts)}, gaps {len(gaps)}, places {len(places)}, left out {len(left_out)}")


if __name__ == "__main__":
    main()
