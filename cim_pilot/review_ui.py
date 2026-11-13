"""Build a self-contained, offline human review editor from observer-only files.

No curator records, completed reviews, suggested focus, or wording alternatives
are read by this builder. They can only be imported deliberately by a reader.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ALLOWED = {"overall_task", "participants", "context_sources", "dialogue_prefix"}


def _script_json(value) -> str:
    """Escape data for a non-executable JSON script element."""
    payload = json.dumps(value, ensure_ascii=False)
    return payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build_review_html(root: str | Path, output: str | Path | None = None) -> Path:
    root = Path(root).resolve()
    source = root / "prospective" / "observer_inputs"
    cases = []
    for path in sorted(source.glob("*.json")):
        raw = path.read_bytes()
        observer = json.loads(raw)
        if set(observer) != ALLOWED:
            raise ValueError(f"Observer fields must be exactly the four permitted fields: {path.name}")
        if not isinstance(observer["dialogue_prefix"], list):
            raise ValueError(f"Missing prefix list: {path.name}")
        cases.append({"case_id": path.stem, "observer_input_sha256": hashlib.sha256(raw).hexdigest(),
                      "observer_input": observer})
    if not cases:
        raise ValueError("No observer-only inputs found under prospective/observer_inputs.")
    payload = _script_json({"schema_version": "1.0", "evidence_tier": "S", "cases": cases})
    key_spec = json.loads((root / "schemas" / "review_key_map.json").read_text(encoding="utf-8"))
    maps = key_spec.get("maps")
    if not isinstance(maps, dict) or not isinstance(maps.get("review"), dict):
        raise ValueError("Review key mapping needs a review context.")
    for context, entries in maps.items():
        if not isinstance(entries, dict) or not all(isinstance(value, str) and value for value in entries.values()):
            raise ValueError("Invalid review key context: " + context)
        if len(set(entries.values())) != len(entries):
            raise ValueError("Ambiguous human review key in context: " + context)
        if any(value in entries and value != key for key, value in entries.items()):
            raise ValueError("Ambiguous technical/human review key in context: " + context)
    # Embed only translation rules; never read case reviews or wording files.
    map_payload = _script_json({key: key_spec[key] for key in
                                ("format_id", "maps", "children", "field_reference_lists") if key in key_spec})
    css = (root / "web" / "review_app.css").read_text(encoding="utf-8")
    script = (root / "web" / "review_app.js").read_text(encoding="utf-8")
    codec_script = (root / "web" / "review_keys.js").read_text(encoding="utf-8")
    if "</script" in script.lower() or "</script" in codec_script.lower():
        raise ValueError("Inline review script contains a closing script token.")
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Consequential Interpretation Mismatch (CIM) · Tier S human review</title><style>{css}</style></head>
<body><div id="app"></div><noscript>This offline editor requires JavaScript. The JSON review files can also be edited directly.</noscript>
<script id="observer-data" type="application/json">{payload}</script>
<script id="review-key-map-data" type="application/json">{map_payload}</script>
<script>{codec_script}</script><script>{script}</script></body></html>'''
    target = Path(output) if output else root / "REVIEW.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    path = build_review_html(args.root, args.output)
    print(path)


if __name__ == "__main__":
    main()
