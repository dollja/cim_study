"""Lossless contextual conversion between technical and original-form review keys.

Only review keys declared in schemas/review_key_map.json are renamed. Dialogue,
quotes, controlled values, participant IDs, consequence payloads and unknown
history are data, not candidates for a recursive string replacement. Public
functions accept either naming style and return a fresh object. Alias collisions
are errors even when the two supplied values are equal.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


class ReviewKeyCollisionError(ValueError):
    """Two different spellings refer to the same review field or field reference."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in review key map: " + key)
        result[key] = value
    return result


KEY_MAP_PATH = Path(__file__).resolve().parent / "schemas" / "review_key_map.json"
REVIEW_KEY_MAP = json.loads(KEY_MAP_PATH.read_text(encoding="utf-8"),
                            object_pairs_hook=_unique_object)
FORMAT_ID = REVIEW_KEY_MAP["format_id"]
MAPS = REVIEW_KEY_MAP["maps"]
CHILDREN = REVIEW_KEY_MAP.get("children", {})
FIELD_REFERENCE_LISTS = REVIEW_KEY_MAP.get("field_reference_lists", {})
_ALIASES = {}

for _context, _mapping in MAPS.items():
    _aliases = {}
    for _technical, _human in _mapping.items():
        if not isinstance(_technical, str) or not isinstance(_human, str):
            raise ValueError("Review key names must be strings")
        for _alias in {_technical, _human}:
            if _alias in _aliases and _aliases[_alias] != _technical:
                raise ValueError("Ambiguous review key map in " + _context + ": " + _alias)
            _aliases[_alias] = _technical
    _ALIASES[_context] = _aliases

for _context, _children in CHILDREN.items():
    if _context not in MAPS:
        raise ValueError("Unknown parent review-key context: " + _context)
    for _key, _child in _children.items():
        if _key not in MAPS[_context] or _child.get("context") not in MAPS:
            raise ValueError("Unknown child review-key context: " + _context + "." + _key)
for _context, _fields in FIELD_REFERENCE_LISTS.items():
    if _context not in MAPS or any(_key not in MAPS[_context] for _key in _fields):
        raise ValueError("Unknown review field-reference list context: " + _context)


def _field_references(value, *, human, path):
    if not isinstance(value, list):
        return deepcopy(value)
    converted, seen = [], {}
    for index, item in enumerate(value):
        if not isinstance(item, str):
            converted.append(deepcopy(item))
            continue
        technical = _ALIASES["review"].get(item, item)
        if technical in seen and seen[technical] != item:
            raise ReviewKeyCollisionError(
                f"Conflicting review-field aliases at {path}[{index}]: "
                f"{seen[technical]!r} and {item!r}")
        seen[technical] = item
        converted.append(MAPS["review"].get(technical, technical) if human else technical)
    return converted


def _convert(value, context, *, human, path):
    # Preserve malformed shapes for the actual validator; key conversion is not
    # permission to coerce types or repair a pending review.
    if not isinstance(value, dict):
        return deepcopy(value)
    result, seen = {}, {}
    aliases = _ALIASES[context]
    for supplied_key, original in value.items():
        technical = aliases.get(supplied_key, supplied_key)
        if technical in seen:
            raise ReviewKeyCollisionError(
                f"Conflicting review-key aliases at {path}: "
                f"{seen[technical]!r} and {supplied_key!r}")
        seen[technical] = supplied_key
        output_key = MAPS[context].get(technical, technical) if human else technical
        item_path = path + "." + str(supplied_key)
        child = CHILDREN.get(context, {}).get(technical)
        if technical in FIELD_REFERENCE_LISTS.get(context, []):
            converted = _field_references(original, human=human, path=item_path)
        elif child and child.get("array") is True:
            converted = ([_convert(item, child["context"], human=human,
                                   path=f"{item_path}[{index}]")
                          for index, item in enumerate(original)]
                         if isinstance(original, list) else deepcopy(original))
        elif child:
            converted = _convert(original, child["context"], human=human, path=item_path)
        else:
            # In particular, participant_outputs and supported_consequences
            # remain opaque participant-keyed payloads. Unknown history does too.
            converted = deepcopy(original)
        result[output_key] = converted
    return result


def to_human_record(record):
    """Return one review or partial first-pass snapshot with original form keys."""
    return _convert(record, "review", human=True, path="review")


def to_technical_record(record):
    """Return one review/snapshot in the stable internal key convention."""
    return _convert(record, "review", human=False, path="review")


def _reviews(reviews, *, human):
    if not isinstance(reviews, dict):
        return deepcopy(reviews)
    return {case_id: _convert(record, "review", human=human,
                              path="reviews[" + repr(case_id) + "]")
            for case_id, record in reviews.items()}


def to_human_reviews(reviews):
    """Convert case-keyed reviews; case IDs and values retain their identities."""
    return _reviews(reviews, human=True)


def to_technical_reviews(reviews):
    """Canonicalize case-keyed reviews before validation, comparison or hashing."""
    return _reviews(reviews, human=False)


__all__ = ["FORMAT_ID", "REVIEW_KEY_MAP", "MAPS", "CHILDREN",
           "FIELD_REFERENCE_LISTS", "ReviewKeyCollisionError",
           "to_human_record", "to_technical_record",
           "to_human_reviews", "to_technical_reviews"]
