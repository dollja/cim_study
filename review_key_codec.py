"""Lossless contextual conversion of technical, readable and reference reviews.

Only declared fields are renamed. Participant IDs, quotation text, consequences
and unknown history remain data. Ambiguous aliases and unrepresentable reference
shapes raise errors instead of silently discarding information.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path


class ReviewKeyCollisionError(ValueError):
    """Different spellings or containers declare the same review field."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in review key map: " + key)
        result[key] = value
    return result


KEY_MAP_PATH = Path(__file__).resolve().parent / "schemas" / "review_key_map.json"
REVIEW_KEY_MAP = json.loads(KEY_MAP_PATH.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
FORMAT_ID = REVIEW_KEY_MAP["format_id"]
MAPS = REVIEW_KEY_MAP["maps"]
CHILDREN = REVIEW_KEY_MAP.get("children", {})
FIELD_REFERENCE_LISTS = REVIEW_KEY_MAP.get("field_reference_lists", {})
REFERENCE_FORMAT_ID = "CIM_REFERENCE_KEYS_V1"
REFERENCE_FIELDS = {
    "local_question": "subtask_hypotheses", "focus_source_ids": "focus", "focus_quotes": "focus",
    "participant_meanings_with_source_quotes": "participant_interpretations",
    "task_outputs": "consequence_analysis", "prefix_only_rationale": "rationale",
    "inclusion_or_exclusion_reason": "selection_reason",
}
REFERENCE_FIELD_PATHS = {
    "local_question": "subtask_hypotheses[0].description",
    "focus_source_ids": "focus.selected_utterance_ids", "focus_quotes": "focus",
    "participant_meanings_with_source_quotes": "participant_interpretations",
    "task_outputs": "consequence_analysis", "prefix_only_rationale": "rationale",
    "inclusion_or_exclusion_reason": "selection_reason",
    "review_metadata.focus_selection_reason": "focus.why_selected",
}
_SIMPLE_REFERENCE_FIELDS = {k: v for k, v in REFERENCE_FIELDS.items()
                            if k not in {"local_question", "focus_source_ids", "focus_quotes"}}
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
_REFERENCE_PATH_ALIASES = {v: k for k, v in REFERENCE_FIELD_PATHS.items()}
_REFERENCE_PATH_ALIASES["subtask_hypotheses"] = "local_question"
_REFERENCE_PATH_ALIASES.update({v: k for k, v in _SIMPLE_REFERENCE_FIELDS.items()})
_FOCUS_KEYS = {"utterance_id", "quote", "speaker", "why_selected", "additional_quotes",
               "selected_utterance_ids", "quote_metadata"}
_QUOTE_CORE = {"source_id", "speaker", "quote"}
_QUOTE_ALIASES = set(_ALIASES["focus_quote"])


def _aliases_present(record, technical, context="review"):
    return [key for key in record if _ALIASES[context].get(key, key) == technical]


def _one_alias(record, technical, path, context="review"):
    keys = _aliases_present(record, technical, context)
    if len(keys) > 1:
        raise ReviewKeyCollisionError(f"Conflicting review-key aliases at {path}: {keys!r}")
    return keys[0] if keys else None


def _snapshot_context(record, explicit=False):
    return explicit or (not _aliases_present(record, "review_status") and
                        not _aliases_present(record, "review_metadata"))


def _require(condition, path, message):
    if not condition:
        raise ValueError(f"{path}: {message}")


def _decode_additional_quote(value, path):
    _require(isinstance(value, dict), path, "additional quote must be an object")
    _require("utterance_id" in value and "quote" in value, path,
             "additional quote requires utterance_id and quote")
    _require(isinstance(value["utterance_id"], str) and isinstance(value["quote"], str),
             path, "quote identifier and text must be strings")
    if "speaker" in value:
        _require(isinstance(value["speaker"], str), path, "speaker must be text")
    collisions = (set(value) & _QUOTE_ALIASES) - {"quote", "speaker"}
    if collisions:
        raise ReviewKeyCollisionError(f"Conflicting quote aliases at {path}: {sorted(collisions)!r}")
    return {("source_id" if key == "utterance_id" else key): deepcopy(item)
            for key, item in value.items()}


def _decode_focus(value, path):
    _require(isinstance(value, dict), path, "focus must be an object")
    _require(not set(value) - _FOCUS_KEYS, path,
             "unknown focus fields; primary quote extras belong in quote_metadata")
    _require({"utterance_id", "quote", "additional_quotes", "selected_utterance_ids"} <= set(value),
             path, "focus requires utterance_id, quote, additional_quotes and selected_utterance_ids")
    ids, additional = value["selected_utterance_ids"], value["additional_quotes"]
    _require(isinstance(ids, list) and all(isinstance(x, str) for x in ids), path,
             "selected_utterance_ids must be an array of strings")
    _require(isinstance(additional, list), path, "additional_quotes must be an array")
    if "why_selected" in value:
        _require(value["why_selected"] is None or isinstance(value["why_selected"], str),
                 path, "why_selected must be text or null")
    sid, quote = value["utterance_id"], value["quote"]
    if sid is None and quote is None:
        _require("speaker" not in value and "quote_metadata" not in value and not additional,
                 path, "an empty primary quote cannot have speaker, quote metadata or additional quotes")
        return deepcopy(ids), []
    _require(isinstance(sid, str) and isinstance(quote, str), path,
             "primary quote identifier and text must both be strings, or both null")
    primary = {"source_id": sid, "quote": quote}
    if "speaker" in value:
        _require(isinstance(value["speaker"], str), path, "speaker must be text")
        primary["speaker"] = value["speaker"]
    if "quote_metadata" in value:
        extra = value["quote_metadata"]
        _require(isinstance(extra, dict), path, "quote_metadata must be an object")
        if set(extra) & _QUOTE_ALIASES:
            raise ReviewKeyCollisionError(f"Reserved quote fields in {path}.quote_metadata")
        primary.update(deepcopy(extra))
    quotes = [primary] + [_decode_additional_quote(q, f"{path}.additional_quotes[{i}]")
                          for i, q in enumerate(additional)]
    return deepcopy(ids), quotes


def _normalize_reference_review(value, path, snapshot=False):
    result = deepcopy(value)
    snapshot = _snapshot_context(value, snapshot)
    for technical, reference in _SIMPLE_REFERENCE_FIELDS.items():
        if reference in result:
            if _aliases_present(result, technical):
                raise ReviewKeyCollisionError(f"Conflicting reference and review aliases at {path}: {reference!r}")
            result[technical] = result.pop(reference)
    if "subtask_hypotheses" in result:
        if _aliases_present(result, "local_question"):
            raise ReviewKeyCollisionError(f"Conflicting task-question aliases at {path}")
        hypotheses = result.pop("subtask_hypotheses")
        _require(isinstance(hypotheses, list) and len(hypotheses) == 1, path,
                 "human review supports exactly one subtask hypothesis")
        _require(isinstance(hypotheses[0], dict) and set(hypotheses[0]) == {"description"},
                 path, "the single subtask hypothesis must contain only description")
        question = hypotheses[0]["description"]
        _require(question is None or isinstance(question, str), path,
                 "subtask description must be text or null")
        result["local_question"] = question
    if "focus" in result:
        if _aliases_present(result, "focus_source_ids") or _aliases_present(result, "focus_quotes"):
            raise ReviewKeyCollisionError(f"Conflicting structured and flat focus fields at {path}")
        focus = result.pop("focus")
        ids, quotes = _decode_focus(focus, path + ".focus")
        result["focus_source_ids"], result["focus_quotes"] = ids, quotes
        meta_key = _one_alias(result, "review_metadata", path)
        meta = result.get(meta_key) if meta_key is not None else None
        reason_in_meta = isinstance(meta, dict) and "focus_selection_reason" in meta
        reason_at_top = "focus_selection_reason" in result
        if "why_selected" in focus and (reason_in_meta or reason_at_top):
            raise ReviewKeyCollisionError(f"Duplicate focus-selection reason at {path}")
        reason = focus.get("why_selected")
        if reason is not None:
            if snapshot:
                result["focus_selection_reason"] = reason
            else:
                if meta_key is None:
                    meta_key = "review_metadata"
                    result[meta_key] = {}
                _require(isinstance(result[meta_key], dict), path,
                         "focus selection reason requires object review metadata")
                result[meta_key]["focus_selection_reason"] = reason
    return result


def _field_references(value, *, target, path):
    if not isinstance(value, list):
        return deepcopy(value)
    converted, seen = [], {}
    for index, item in enumerate(value):
        if not isinstance(item, str):
            converted.append(deepcopy(item)); continue
        technical = _REFERENCE_PATH_ALIASES.get(item, _ALIASES["review"].get(item, item))
        if technical in seen and seen[technical] != item:
            raise ReviewKeyCollisionError(f"Conflicting review-field aliases at {path}[{index}]: {seen[technical]!r} and {item!r}")
        seen[technical] = item
        if target == "reference":
            converted.append(REFERENCE_FIELD_PATHS.get(technical, MAPS["review"].get(technical, technical)))
        elif target == "human":
            converted.append(MAPS["review"].get(technical, technical))
        else:
            converted.append(technical)
    return converted


def _encode_quote(quote, path):
    technical = _convert(quote, "focus_quote", target="technical", path=path)
    _require(isinstance(technical, dict), path, "focus quote must be an object")
    _require("source_id" in technical and "quote" in technical and
             isinstance(technical["source_id"], str) and isinstance(technical["quote"], str),
             path, "focus quote must contain string source_id and quote")
    if "speaker" in technical:
        _require(isinstance(technical["speaker"], str), path, "speaker must be text")
    return technical


def _encode_reference_review(value, path, snapshot=False):
    result = deepcopy(value)
    snapshot = _snapshot_context(value, snapshot)
    for technical, reference in _SIMPLE_REFERENCE_FIELDS.items():
        label = MAPS["review"][technical]
        if label in result:
            result[reference] = result.pop(label)
    question_key = MAPS["review"]["local_question"]
    if question_key in result:
        question = result.pop(question_key)
        _require(question is None or isinstance(question, str), path, "subtask description must be text or null")
        result["subtask_hypotheses"] = [{"description": question}]
    ids_key, quotes_key = (MAPS["review"][key] for key in ["focus_source_ids", "focus_quotes"])
    if (ids_key in result) != (quotes_key in result):
        raise ValueError(f"{path}: reference export requires both focus source IDs and focus quotes")
    reason_present, reason = False, None
    meta_key = MAPS["review"]["review_metadata"]
    meta = result.get(meta_key)
    if isinstance(meta, dict) and "focus_selection_reason" in meta:
        reason_present = True
        reason = meta.pop("focus_selection_reason")
    if "focus_selection_reason" in result:
        if reason_present:
            raise ReviewKeyCollisionError(f"Duplicate focus-selection reason at {path}")
        _require(snapshot, path, "a full review stores focus_selection_reason in review metadata")
        reason_present = True
        reason = result.pop("focus_selection_reason")
    if reason_present:
        _require(isinstance(reason, str), path, "stored focus_selection_reason must be text")
        _require(ids_key in result, path, "focus selection reason requires the complete focus fields")
    if ids_key in result:
        ids, quotes = result.pop(ids_key), result.pop(quotes_key)
        _require(isinstance(ids, list) and all(isinstance(x, str) for x in ids), path,
                 "focus source IDs must be an array of strings")
        _require(isinstance(quotes, list), path, "focus quotes must be an array")
        canonical_quotes = [_encode_quote(q, f"{path}.focus_quotes[{i}]") for i, q in enumerate(quotes)]
        focus = {"utterance_id": None, "quote": None, "why_selected": reason,
                 "additional_quotes": [], "selected_utterance_ids": deepcopy(ids)}
        if canonical_quotes:
            primary = canonical_quotes[0]
            focus["utterance_id"], focus["quote"] = primary["source_id"], primary["quote"]
            if "speaker" in primary: focus["speaker"] = primary["speaker"]
            extras = {key: deepcopy(item) for key, item in primary.items() if key not in _QUOTE_CORE}
            if extras: focus["quote_metadata"] = extras
            for index, q in enumerate(canonical_quotes[1:], 1):
                if "utterance_id" in q:
                    raise ReviewKeyCollisionError(f"Conflicting quote aliases at {path}.focus_quotes[{index}]")
                focus["additional_quotes"].append({("utterance_id" if key == "source_id" else key): deepcopy(item)
                                                    for key, item in q.items()})
        result["focus"] = focus
    return result


def _convert(value, context, *, target, path, snapshot=False):
    # Legacy malformed shapes remain available to the validator. Structured
    # reference shapes are explicitly rejected when no lossless encoding exists.
    if not isinstance(value, dict): return deepcopy(value)
    if context == "review":
        snapshot = _snapshot_context(value, snapshot)
        value = _normalize_reference_review(value, path, snapshot=snapshot)
    result, seen = {}, {}
    aliases = _ALIASES[context]
    for supplied_key, original in value.items():
        technical = aliases.get(supplied_key, supplied_key)
        if technical in seen:
            raise ReviewKeyCollisionError(f"Conflicting review-key aliases at {path}: {seen[technical]!r} and {supplied_key!r}")
        seen[technical] = supplied_key
        output_key = MAPS[context].get(technical, technical) if target != "technical" else technical
        item_path = path + "." + str(supplied_key)
        child = CHILDREN.get(context, {}).get(technical)
        if technical in FIELD_REFERENCE_LISTS.get(context, []):
            converted = _field_references(original, target=target, path=item_path)
        elif child and child.get("array") is True:
            converted = ([_convert(item, child["context"], target=target, path=f"{item_path}[{index}]")
                          for index, item in enumerate(original)] if isinstance(original, list) else deepcopy(original))
        elif child:
            converted = _convert(original, child["context"], target=target, path=item_path,
                                 snapshot=context == "metadata" and technical == "first_pass_judgment_snapshot")
        else:
            converted = deepcopy(original)
        result[output_key] = converted
    if context == "review" and target == "reference":
        return _encode_reference_review(result, path, snapshot=snapshot)
    return result


def to_human_record(record):
    """Return a review or partial snapshot with the original readable form keys."""
    return _convert(record, "review", target="human", path="review")


def to_technical_record(record):
    """Normalize any supported review format to stable internal keys."""
    return _convert(record, "review", target="technical", path="review")


def to_reference_record(record):
    """Return one review/snapshot in the requested reference-shaped convention."""
    return _convert(record, "review", target="reference", path="review")


def _reviews(reviews, *, target):
    if not isinstance(reviews, dict): return deepcopy(reviews)
    return {case_id: _convert(record, "review", target=target, path="reviews[" + repr(case_id) + "]")
            for case_id, record in reviews.items()}


def to_human_reviews(reviews):
    """Convert case-keyed reviews to the original readable form labels."""
    return _reviews(reviews, target="human")


def to_technical_reviews(reviews):
    """Canonicalize case-keyed reviews before validation, comparison or hashing."""
    return _reviews(reviews, target="technical")


def to_reference_reviews(reviews):
    """Convert case-keyed reviews to the reference structure without rating cases."""
    return _reviews(reviews, target="reference")


__all__ = ["FORMAT_ID", "REFERENCE_FORMAT_ID", "REVIEW_KEY_MAP", "MAPS", "CHILDREN",
           "FIELD_REFERENCE_LISTS", "REFERENCE_FIELDS", "REFERENCE_FIELD_PATHS", "ReviewKeyCollisionError",
           "to_human_record", "to_technical_record", "to_reference_record",
           "to_human_reviews", "to_technical_reviews", "to_reference_reviews"]
