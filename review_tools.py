"""Tier S review migration, validation, comparison and explicit adjudication export.

Checks declared support and source traceability, not semantic truth or human
independence. Never derives task consequences from prose or selects cases.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from pilot import digest as observer_digest
from review_key_codec import (to_human_reviews, to_reference_reviews, to_technical_reviews,
                              to_technical_record)

SCHEMA_VERSION = "1.0"
LABELS = {"ALIGNED", "POTENTIAL_MISMATCH", "UNRESOLVED"}
SUPPORT = {"supported", "possible", "unsupported", None}
REVIEW_STATUSES = {"unreviewed", "in_progress", "reviewed", "completed"}
FIELDS = ["review_status", "reviewer_id", "review_metadata", "focal_pair",
          "local_question", "focus_source_ids", "focus_quotes",
          "participant_meanings_with_source_quotes", "task_outputs",
          "blocking_uncertainty", "provisional_label", "prefix_only_rationale",
          "evidence_verified", "include_in_pilot", "inclusion_or_exclusion_reason"]
EXPOSURES = ["assistant_draft", "system_outputs", "released_labels", "later_evidence"]
WORDING_FIELDS = ["focal_pair", "local_question", "focus_source_ids", "focus_quotes",
                  "participant_meanings_with_source_quotes", "task_outputs",
                  "blocking_uncertainty", "prefix_only_rationale",
                  "inclusion_or_exclusion_reason"]
JUDGMENT_FIELDS = ["reviewer_id", "focal_pair", "local_question", "focus_source_ids",
                   "focus_quotes", "participant_meanings_with_source_quotes", "task_outputs",
                   "blocking_uncertainty", "provisional_label", "prefix_only_rationale",
                   "evidence_verified"]


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    def reject_constant(value):
        raise ValueError("Non-finite JSON number: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_object,
                      parse_constant=reject_constant)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def review_judgment_snapshot(record):
    """Freeze substantive first-pass fields; later selection/status changes are separate."""
    record = to_technical_record(record)
    snapshot = {key: deepcopy(record.get(key)) for key in JUDGMENT_FIELDS}
    reason = record.get("review_metadata", {}).get("focus_selection_reason")
    if isinstance(reason, str) and reason.strip():
        snapshot["focus_selection_reason"] = reason
    return snapshot


def strict_reference_ready(record):
    """Check declarations for a preserved unassisted judgment, not human identity."""
    record = to_technical_record(record)
    meta = record["review_metadata"]
    if not (meta["prefix_first_review_completed"] is True and
            all(meta["prior_exposure"][key] is False for key in EXPOSURES)):
        return False
    if meta.get("assistant_wording_fields"):
        return False
    events = meta.get("wording_exposure_events", [])
    if events:
        if not isinstance(events, list) or any(not isinstance(event, dict) or
                event.get("before_prefix_first_review") is not False for event in events):
            return False
    snapshot = meta.get("first_pass_judgment_snapshot")
    reason = meta.get("focus_selection_reason")
    has_reason = isinstance(reason, str) and bool(reason.strip())
    saved_reason = isinstance(snapshot, dict) and "focus_selection_reason" in snapshot
    if events or meta.get("later_evidence_review_completed") is True or has_reason or saved_reason:
        if not isinstance(snapshot, dict):
            return False
        if (digest(snapshot) != meta.get("first_pass_judgment_sha256") or
                snapshot != review_judgment_snapshot(record)):
            return False
    return True


def write_new(path, value):
    """Exclusive creation: never overwrite reviews, comparisons or references."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _observer(observer_dir, case_id):
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_]+", case_id):
        raise ValueError("Invalid case identifier")
    path = Path(observer_dir) / (case_id + ".json")
    view = load_json(path)
    if set(view) != {"overall_task", "participants", "context_sources", "dialogue_prefix"}:
        raise ValueError("Unexpected observer fields: " + case_id)
    rows = {r["utterance_id"]: r for r in view["dialogue_prefix"]}
    if len(rows) != len(view["dialogue_prefix"]):
        raise ValueError("Duplicate observer source IDs: " + case_id)
    people = {p["participant_id"] for p in view["participants"]
              if p.get("known_role") != "recorded_audio_not_player"}
    return view, rows, people, hashlib.sha256(path.read_bytes()).hexdigest()


def _has_unknown(value):
    if value is None or (isinstance(value, str) and value.upper() == "UNKNOWN"):
        return True
    if isinstance(value, dict):
        return any(_has_unknown(x) for x in value.values())
    if isinstance(value, list):
        return any(_has_unknown(x) for x in value)
    return False


def decision_rule(a, b, blocked=False):
    """F7 on already canonical, supported consequences for the same task/event.

    Null/UNKNOWN indicates an unknown required argument. Evidence admission and
    semantic equivalence of the declared canonical values remain human duties.
    """
    if not isinstance(a, list) or not isinstance(b, list) or type(blocked) is not bool:
        raise ValueError("Consequence sets must be arrays; blocked must be boolean.")
    if blocked or not a or not b or any(_has_unknown(x) for x in a + b):
        return "UNRESOLVED"
    aa = {json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False) for x in a}
    bb = {json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False) for x in b}
    if aa == bb and len(aa) == 1:
        return "ALIGNED"
    if aa.isdisjoint(bb):
        return "POTENTIAL_MISMATCH"
    return "UNRESOLVED"


def migrate_reviews(legacy, observer_dir, *, wording=None, reviewer_id=None, blank=False):
    """Return technical-key reviews, preserving history without promoting completion.

    Explicit wording overlays affect prose fields only. Blank creates a reader
    slot, not a completed review. Either input key convention is accepted.
    Existing canonical metadata is preserved. The Python return convention stays
    technical for compatibility; the CLI emits original form keys by default.
    """
    if not isinstance(legacy, dict) or not legacy:
        raise ValueError("Source reviews must be a nonempty case-keyed object.")
    if wording is not None and not isinstance(wording, dict):
        raise ValueError("Wording must be a case-keyed object.")
    legacy = to_technical_reviews(legacy)
    wording = to_technical_reviews(wording) if wording is not None else None
    result = {}
    for cid, source in legacy.items():
        if not isinstance(source, dict):
            raise ValueError(str(cid) + ": source review must be an object")
        _, rows, _, input_hash = _observer(observer_dir, cid)
        if "review_metadata" in source and wording is None and not blank:
            result[cid] = deepcopy(source)
            if reviewer_id is not None:
                result[cid]["reviewer_id"] = reviewer_id
            continue
        item = deepcopy(source)
        if wording is not None:
            for field in WORDING_FIELDS:
                if field in wording.get(cid, {}):
                    item[field] = deepcopy(wording[cid][field])
        task = item.get("task_outputs")
        authored = (wording is not None or
                    (isinstance(task, dict) and "assistant" in str(task.get("authorship", "")).lower()))
        meta = deepcopy(source.get("review_metadata", {}))
        meta.setdefault("schema_version", SCHEMA_VERSION)
        meta.setdefault("evidence_tier", "S")
        meta.setdefault("observer_input_sha256", input_hash)
        prior = meta.setdefault("prior_exposure", {})
        prior.setdefault("assistant_draft", source.get("assistant_draft_seen_before_judgment"))
        for key in EXPOSURES[1:]:
            prior.setdefault(key, None)
        prior.setdefault("notes", "")
        meta.setdefault("prefix_first_review_completed", source.get("prefix_first_review_completed", False))
        meta.setdefault("later_evidence_review_completed", source.get("later_evidence_review_completed", False))
        meta.setdefault("assistant_wording_fields", WORDING_FIELDS[:] if authored else [])
        meta.setdefault("human_content_confirmed", False)
        if authored:
            meta["human_content_confirmed"] = False
            meta["assistant_wording_fields"] = sorted(set(meta["assistant_wording_fields"]) | set(WORDING_FIELDS))
        focus_ids = item.get("focus_source_ids", [])
        focus_quotes = deepcopy(item.get("focus_quotes", []))
        if not focus_quotes:
            focus_quotes = [{"source_id": sid, "speaker": rows[sid]["speaker"], "quote": rows[sid]["text"]}
                            for sid in focus_ids if sid in rows]
        meanings = deepcopy(item.get("participant_meanings_with_source_quotes", []))
        for meaning in meanings:
            if wording is not None:
                meaning["support"] = None
            else:
                meaning.setdefault("support", None)
        rationale = item.get("prefix_only_rationale")
        if rationale is None and isinstance(task, dict):
            rationale = task.get("comparison")
        record = {
            "review_status": source.get("review_status", "unreviewed"),
            "reviewer_id": reviewer_id if reviewer_id is not None else source.get("reviewer_id"),
            "review_metadata": meta, "focal_pair": deepcopy(item.get("focal_pair")),
            "local_question": item.get("local_question"), "focus_source_ids": deepcopy(focus_ids),
            "focus_quotes": focus_quotes, "participant_meanings_with_source_quotes": meanings,
            "task_outputs": deepcopy(task), "blocking_uncertainty": item.get("blocking_uncertainty"),
            "provisional_label": source.get("provisional_label"), "prefix_only_rationale": rationale,
            "evidence_verified": source.get("evidence_verified"),
            "include_in_pilot": source.get("include_in_pilot"),
            "inclusion_or_exclusion_reason": item.get("inclusion_or_exclusion_reason"),
        }
        if blank:
            record.update(review_status="unreviewed", focal_pair=None, local_question=None,
                          focus_source_ids=[], focus_quotes=[], participant_meanings_with_source_quotes=[],
                          task_outputs=None, blocking_uncertainty=None, provisional_label=None,
                          prefix_only_rationale=None, evidence_verified=None, include_in_pilot=None,
                          inclusion_or_exclusion_reason=None)
            record["review_metadata"] = {
                "schema_version": SCHEMA_VERSION, "evidence_tier": "S", "observer_input_sha256": input_hash,
                "prior_exposure": {**{key: None for key in EXPOSURES}, "notes": ""},
                "prefix_first_review_completed": False, "later_evidence_review_completed": False,
                "assistant_wording_fields": [], "human_content_confirmed": False,
            }
        result[cid] = record
    return result


def _bool_or_null(value):
    return value is None or type(value) is bool


def validate_reviews(reviews, observer_dir, require_complete=False):
    errors, warnings, cases = [], [], {}
    if not isinstance(reviews, dict) or not reviews:
        return {"valid": False, "case_count": 0, "completed_reviews": 0,
                "errors": ["Review file must be a nonempty case-keyed object."],
                "warnings": [], "cases": {}}
    for cid, r in reviews.items():
        case_errors, missing = [], []
        def error(message):
            case_errors.append(str(cid) + ": " + message)
        try:
            r = to_technical_record(r)
            _, rows, people, input_hash = _observer(observer_dir, cid)
            if not isinstance(r, dict):
                raise ValueError("review must be an object")
            if set(r) != set(FIELDS):
                raise ValueError("canonical fields differ; migrate the legacy file first")
            meta = r["review_metadata"]
            if not isinstance(meta, dict):
                raise ValueError("review_metadata must be an object")
            if meta.get("schema_version") != SCHEMA_VERSION: error("unknown review schema version")
            if meta.get("evidence_tier") != "S": error("evidence tier must be S")
            if meta.get("observer_input_sha256") != input_hash: error("frozen observer hash does not match")
            if ("focus_selection_reason" in meta and meta["focus_selection_reason"] is not None
                    and not isinstance(meta["focus_selection_reason"], str)):
                error("focus.why_selected must be text/null")
            if r["review_status"] not in REVIEW_STATUSES:
                error("review_status must be unreviewed/in_progress/reviewed/completed")
            if r["reviewer_id"] is not None and not isinstance(r["reviewer_id"], str):
                error("reviewer_id must be text/null")
            for field in ["blocking_uncertainty", "evidence_verified", "include_in_pilot"]:
                if not _bool_or_null(r[field]): error(field + " must be boolean/null")
            for field in ["prefix_first_review_completed", "later_evidence_review_completed", "human_content_confirmed"]:
                if type(meta.get(field)) is not bool:
                    error("review_metadata." + field + " must be boolean")
            if not isinstance(meta.get("assistant_wording_fields"), list) or any(
                    not isinstance(field, str) for field in meta.get("assistant_wording_fields", [])):
                error("assistant_wording_fields must be a list of field names")
            exposure = meta.get("prior_exposure", {})
            if not isinstance(exposure, dict): raise ValueError("prior_exposure must be an object")
            for field in EXPOSURES:
                if field not in exposure or not _bool_or_null(exposure[field]):
                    error("prior_exposure." + field + " must be boolean/null")
            if not isinstance(exposure.get("notes"), str): error("prior_exposure.notes must be text")
            pair = r["focal_pair"]
            if pair is not None and (not isinstance(pair, list) or len(pair) != 2 or
                                     len(set(pair)) != 2 or not set(pair) <= people):
                error("focal_pair must contain two actual participants; the narrator is not a player")
            pair = pair or []
            for field in ["local_question", "prefix_only_rationale", "inclusion_or_exclusion_reason"]:
                if r[field] is not None and not isinstance(r[field], str):
                    error(field + " must be text/null")
            if not isinstance(r["focus_source_ids"], list): raise ValueError("focus_source_ids must be a list")
            if len(set(r["focus_source_ids"])) != len(r["focus_source_ids"]):
                error("focus_source_ids contains duplicates")
            for sid in r["focus_source_ids"]:
                if sid not in rows: error("focus source outside frozen prefix: " + str(sid))
            def check_quote(q):
                if not isinstance(q, dict) or not isinstance(q.get("quote"), str) or not q["quote"]:
                    error("source quotation needs nonempty quote text")
                    return None
                row = rows.get(q.get("source_id"))
                if row is None or q["quote"] not in row["text"]:
                    error("quotation is not an exact prefix span: " + str(q.get("source_id")))
                    return None
                if "speaker" in q and q["speaker"] != row["speaker"]:
                    error("quotation speaker does not match source")
                return row
            if not isinstance(r["focus_quotes"], list): raise ValueError("focus_quotes must be a list")
            for q in r["focus_quotes"]:
                check_quote(q)
                if not isinstance(q, dict):
                    continue
                if q.get("source_id") not in r["focus_source_ids"]:
                    error("focus quote ID is not in focus_source_ids")
            if not isinstance(r["participant_meanings_with_source_quotes"], list):
                raise ValueError("participant meanings must be a list")
            supported_people, represented = set(), set()
            for m in r["participant_meanings_with_source_quotes"]:
                if not isinstance(m, dict):
                    raise ValueError("each participant reading must be an object")
                if not {"participant_id", "meaning", "source_quotes", "support"} <= set(m):
                    error("each reading needs participant_id, meaning, source_quotes and support")
                person = m.get("participant_id")
                represented.add(person)
                if person not in pair: error("meaning belongs to someone outside focal_pair")
                if not isinstance(m.get("meaning"), str) or not m["meaning"].strip():
                    error("meaning must contain text")
                if m.get("support") not in SUPPORT:
                    error("support must be supported/possible/unsupported/null")
                if not isinstance(m.get("source_quotes"), list):
                    raise ValueError("reading source_quotes must be a list")
                own = False
                for q in m["source_quotes"]:
                    row = check_quote(q)
                    own |= bool(row and row["speaker"] == person)
                if m.get("support") == "supported":
                    supported_people.add(person)
                    if not own:
                        error("a supported Tier S reading needs participant-owned expressed evidence")
            label = r["provisional_label"]
            if label is not None and label not in LABELS: error("invalid provisional label code")
            outputs = r["task_outputs"]
            if outputs is not None and not isinstance(outputs, dict):
                raise ValueError("task_outputs must be an object/null")
            if outputs and outputs.get("evidence_tier", "S") != "S":
                error("task_outputs evidence tier must be S")
            sets = outputs.get("supported_consequences") if outputs else None
            computed = None
            if sets is not None:
                if not isinstance(sets, dict) or set(sets) != set(pair) or len(pair) != 2:
                    error("supported_consequences must name exactly the two focal participants")
                else:
                    if any(sets[person] and person not in supported_people for person in pair):
                        error("nonempty supported consequences require a supported reading for that participant")
                    computed = decision_rule(sets[pair[0]], sets[pair[1]],
                                             r["blocking_uncertainty"] is not False)
                    if label is not None and computed != label:
                        error("label contradicts declared consequence sets/blocker; expected " + computed)
            if label in {"ALIGNED", "POTENTIAL_MISMATCH"}:
                if r["blocking_uncertainty"] is not False:
                    error("a determinate label requires blocking_uncertainty=false")
                if not set(pair) <= supported_people or len(pair) != 2:
                    error("a determinate label needs a supported reading for each participant")
                if sets is None:
                    warnings.append(cid + ": no canonical supported_consequences; F7 cannot be checked from prose")
            requirements = [
                (bool(r["reviewer_id"]), "reviewer_id"),
                (r["review_status"] in {"reviewed", "completed"}, "completed individual review status"),
                (meta.get("human_content_confirmed") is True, "human confirmation of current content"),
                (len(pair) == 2, "focal pair"), (bool(r["local_question"]), "local question"),
                (bool(r["focus_source_ids"]) and bool(r["focus_quotes"]), "focus sources and quotations"),
                (set(pair) <= represented and len(pair) == 2, "both readings or explained uncertainty"),
                (isinstance(outputs, dict) and bool(outputs), "task outputs or explained unknowns"),
                (type(r["blocking_uncertainty"]) is bool, "blocking uncertainty assessment"),
                (label in LABELS, "provisional label"), (bool(r["prefix_only_rationale"]), "prefix-only rationale"),
                (r["evidence_verified"] is True, "evidence verification"),
                (label not in {"ALIGNED", "POTENTIAL_MISMATCH"} or sets is not None,
                 "canonical supported consequence sets"),
            ]
            missing = [name for condition, name in requirements if not condition]
            if r["review_status"] in {"reviewed", "completed"} and missing:
                warnings.append(cid + ": recorded complete status still needs " + "; ".join(missing))
            if require_complete and missing: error("incomplete review: " + "; ".join(missing))
            cases[cid] = {"structurally_valid": not case_errors,
                          "complete": not missing and not case_errors,
                          "missing_for_completion": missing, "computed_label": computed}
        except (KeyError, TypeError, ValueError, OSError) as exc:
            error(str(exc))
            cases[cid] = {"structurally_valid": False, "complete": False,
                          "missing_for_completion": missing}
        errors.extend(case_errors)
    return {"valid": not errors, "case_count": len(reviews),
            "completed_reviews": sum(c["complete"] for c in cases.values()),
            "errors": errors, "warnings": warnings, "cases": cases,
            "limits": "Source/structure checks cannot certify semantics or human independence."}


def compare_reviews(a, b):
    """Show literal differences, never silently declare semantic agreement."""
    a, b = to_technical_reviews(a), to_technical_reviews(b)
    records = []
    compared = ["focal_pair", "local_question", "focus_source_ids", "focus_quotes",
                "participant_meanings_with_source_quotes", "task_outputs", "blocking_uncertainty",
                "provisional_label", "prefix_only_rationale", "include_in_pilot",
                "inclusion_or_exclusion_reason"]
    for cid in sorted(set(a) | set(b)):
        if cid not in a or cid not in b:
            records.append({"case_id": cid, "state": "missing_reader", "label_match": None})
            continue
        ar, br = a[cid], b[cid]
        rated = ar.get("provisional_label") in LABELS and br.get("provisional_label") in LABELS
        differences = {key: {"reader_1": ar.get(key), "reader_2": br.get(key)}
                       for key in compared if ar.get(key) != br.get(key)}
        a_reason = ar.get("review_metadata", {}).get("focus_selection_reason")
        b_reason = br.get("review_metadata", {}).get("focus_selection_reason")
        if a_reason != b_reason:
            differences["focus.why_selected"] = {"reader_1": a_reason, "reader_2": b_reason}
        records.append({"case_id": cid, "state": "needs_adjudication" if rated else "pending_judgments",
                        "label_match": ar["provisional_label"] == br["provisional_label"] if rated else None,
                        "differences": differences,
                        "note": "Literal agreement does not prove the same question/event or evidence was judged."})
    return {"case_count": len(records), "both_rated": sum(r["label_match"] is not None for r in records),
            "matching_labels": sum(r["label_match"] is True for r in records),
            "human_adjudications_created": 0, "records": records}


def _source_group(observer_dir, cid):
    path = Path(observer_dir).parent / "curator_cases" / (cid + ".json")
    if path.exists():
        protocol = load_json(path).get("sampling_and_reference_protocol", {})
        return protocol.get("provisional_source_group") or protocol.get("map_pair_id")
    return None


def adjudication_template(a, b, observer_dir):
    a, b = to_technical_reviews(a), to_technical_reviews(b)
    result = {}
    for cid in sorted(set(a) & set(b)):
        result[cid] = {
            "review_status": "pending", "adjudicator_id": None, "adjudicated_at": None,
            "reader_ids": [a[cid].get("reviewer_id"), b[cid].get("reviewer_id")],
            "review_hashes": {"reader_1": digest(a[cid]), "reader_2": digest(b[cid])},
            "independent_reviews_confirmed": False, "same_scope_confirmed": False,
            "focal_pair": None, "local_question": None, "focus_source_ids": [],
            "participant_meanings_with_source_quotes": [],
            "label": None, "blocking_uncertainty": None, "supported_consequences": None,
            "source_group": _source_group(observer_dir, cid),
            "cluster_id": None, "cluster_verified": False,
            "rationale": None, "evidence_review": {},
        }
    return result


def export_adjudicated(a, b, ledger, observer_dir, *, allow_assisted=False):
    # Ledger/reference files retain their existing machine contract. Only the
    # two human review inputs are normalized before their canonical hashes.
    a, b = to_technical_reviews(a), to_technical_reviews(b)
    output = {}
    for cid, item in ledger.items():
        if item.get("review_status") != "adjudicated":
            continue
        if cid not in a or cid not in b:
            raise ValueError(cid + ": both reader records are required")
        for record in [a[cid], b[cid]]:
            check = validate_reviews({cid: record}, observer_dir, require_complete=True)
            if not check["valid"]: raise ValueError("; ".join(check["errors"]))
        ar, br = a[cid], b[cid]
        ids = [ar["reviewer_id"], br["reviewer_id"]]
        if len(set(ids)) != 2 or item.get("reader_ids") != ids:
            raise ValueError(cid + ": identify two distinct actual readers")
        if item.get("review_hashes") != {"reader_1": digest(ar), "reader_2": digest(br)}:
            raise ValueError(cid + ": adjudication refers to stale or different reader records")
        for key in ["adjudicator_id", "adjudicated_at", "local_question", "rationale", "cluster_id"]:
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(cid + ": adjudication requires " + key)
        if item.get("independent_reviews_confirmed") is not True or item.get("same_scope_confirmed") is not True:
            raise ValueError(cid + ": confirm independent submissions and the shared question/event")
        if item.get("cluster_verified") is not True:
            raise ValueError(cid + ": source grouping requires review")
        group = _source_group(observer_dir, cid)
        if group is None or item.get("source_group") != group:
            raise ValueError(cid + ": source-group provenance is missing or different")
        observer_view, rows, _, observer_input_sha256 = _observer(observer_dir, cid)
        focal = item.get("focus_source_ids", [])
        if not focal or any(sid not in rows for sid in focal):
            raise ValueError(cid + ": adjudicated focus must cite the frozen prefix")
        if any(not set(focal) & set(r["focus_source_ids"]) for r in [ar, br]):
            raise ValueError(cid + ": adjudicated focus must link to both reviewed chains")
        pair = item.get("focal_pair")
        if not isinstance(pair, list) or len(pair) != 2 or any(set(pair) != set(r["focal_pair"]) for r in [ar, br]):
            raise ValueError(cid + ": adjudicated participants must match both comparisons")
        label = item.get("label")
        if label not in LABELS or type(item.get("blocking_uncertainty")) is not bool:
            raise ValueError(cid + ": allowed label and blocking assessment are required")
        sets = item.get("supported_consequences")
        if sets is not None:
            if not isinstance(sets, dict) or set(sets) != set(pair):
                raise ValueError(cid + ": adjudicated consequences must name both participants")
            if decision_rule(sets[pair[0]], sets[pair[1]], item["blocking_uncertainty"]) != label:
                raise ValueError(cid + ": adjudicated label conflicts with F7")
        elif label != "UNRESOLVED":
            raise ValueError(cid + ": determinate adjudication requires canonical consequence sets")
        if label in {"ALIGNED", "POTENTIAL_MISMATCH"}:
            readings = item.get("participant_meanings_with_source_quotes")
            if not isinstance(readings, list) or not readings:
                raise ValueError(cid + ": determinate adjudication requires explicit supported participant readings and quotes")
            adjudicated = deepcopy(ar)
            adjudicated.update(focal_pair=pair, local_question=item["local_question"],
                               focus_source_ids=focal,
                               focus_quotes=[{"source_id": sid, "speaker": rows[sid]["speaker"],
                                              "quote": rows[sid]["text"]} for sid in focal],
                               participant_meanings_with_source_quotes=readings,
                               task_outputs={"supported_consequences": sets},
                               blocking_uncertainty=item["blocking_uncertainty"],
                               provisional_label=label, prefix_only_rationale=item["rationale"])
            check = validate_reviews({cid: adjudicated}, observer_dir)
            if not check["valid"]:
                raise ValueError("Adjudicated evidence: " + "; ".join(check["errors"]))
        evidence = item.get("evidence_review", {})
        if not isinstance(evidence, dict) or any(not isinstance(k, str) or not k or type(v) is not bool
                                                 for k, v in evidence.items()):
            raise ValueError(cid + ": evidence_review needs actual candidate IDs and human booleans")
        strict = all(strict_reference_ready(r) for r in [ar, br])
        if not strict and not allow_assisted:
            raise ValueError(cid + ": unexposed prefix-first review not established; use --allow-assisted only for an assisted-development reference")
        output[cid] = {
            "review_status": "adjudicated", "label": label, "focal_source_ids": focal,
            "observer_input_sha256": observer_input_sha256,
            "observer_hash": observer_digest(observer_view),
            "cluster_id": item["cluster_id"], "evidence_review": deepcopy(evidence),
            "reference_condition": "independent_strict" if strict else "assisted_development",
            "evidence_tier": "S", "local_question": item["local_question"], "focal_pair": pair,
            "adjudicator_id": item["adjudicator_id"], "adjudicated_at": item["adjudicated_at"],
            "adjudication_rationale": item["rationale"], "review_hashes": deepcopy(item["review_hashes"]),
            "adjudicated_participant_meanings": deepcopy(item.get("participant_meanings_with_source_quotes", [])),
            "prior_exposure": {ids[0]: deepcopy(ar["review_metadata"]["prior_exposure"]),
                               ids[1]: deepcopy(br["review_metadata"]["prior_exposure"])},
        }
    if not output:
        raise ValueError("No explicit completed adjudications; no reference file was written.")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("migrate", help="Create reviews in a supported key format without overwriting")
    p.add_argument("input"); p.add_argument("--wording"); p.add_argument("--observer-dir", required=True)
    p.add_argument("--out", required=True); p.add_argument("--reviewer-id"); p.add_argument("--blank", action="store_true")
    p.add_argument("--output-keys", choices=["reference", "human", "technical"], default="reference",
                   help="Output key names; Python API continues to return technical keys.")
    p = subs.add_parser("convert-keys", help="Convert review representation without changing judgments")
    p.add_argument("input"); p.add_argument("--out", required=True)
    p.add_argument("--to", choices=["reference", "human", "technical"], default="reference")
    p = subs.add_parser("validate", help="Check schema, quotes and declared decision consistency")
    p.add_argument("reviews"); p.add_argument("--observer-dir", required=True); p.add_argument("--complete", action="store_true")
    for name in ["compare", "adjudication-template", "export-adjudicated"]:
        p = subs.add_parser(name)
        p.add_argument("reader_1"); p.add_argument("reader_2"); p.add_argument("--observer-dir", required=True)
        p.add_argument("--out", required=True)
        if name == "export-adjudicated":
            p.add_argument("--ledger", required=True); p.add_argument("--allow-assisted", action="store_true")
    p = subs.add_parser("decision-rule", help="Compare explicit canonical consequence arrays")
    p.add_argument("--a", required=True); p.add_argument("--b", required=True); p.add_argument("--blocked", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "decision-rule":
            print(decision_rule(json.loads(args.a), json.loads(args.b), args.blocked))
            return 0
        if args.command == "convert-keys":
            source = load_json(args.input)
            canonical = to_technical_reviews(source)
            if (not isinstance(canonical, dict) or not canonical or
                    any(not isinstance(cid, str) or not re.fullmatch(r"[A-Za-z0-9_]+", cid)
                        or not isinstance(record, dict) or not set(record).intersection(FIELDS)
                        for cid, record in canonical.items())):
                raise ValueError("Key conversion requires a nonempty case-keyed review object, not observer/model input.")
            result = (to_reference_reviews(canonical) if args.to == "reference" else
                      to_human_reviews(canonical) if args.to == "human" else canonical)
            write_new(args.out, result)
            print(json.dumps({"output": args.out, "records": len(result),
                              "output_keys": args.to, "key_conversion_only": True,
                              "semantic_validation_performed": False,
                              "human_judgments_created": 0}))
            return 0
        if args.command == "migrate":
            result = migrate_reviews(load_json(args.input), args.observer_dir,
                                     wording=load_json(args.wording) if args.wording else None,
                                     reviewer_id=args.reviewer_id, blank=args.blank)
            check = validate_reviews(result, args.observer_dir)
            if not check["valid"]: raise ValueError("; ".join(check["errors"]))
            if args.output_keys == "reference":
                result = to_reference_reviews(result)
            elif args.output_keys == "human":
                result = to_human_reviews(result)
        elif args.command == "validate":
            result = validate_reviews(load_json(args.reviews), args.observer_dir, args.complete)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 2
        else:
            a, b = load_json(args.reader_1), load_json(args.reader_2)
            for data in [a, b]:
                check = validate_reviews(data, args.observer_dir)
                if not check["valid"]: raise ValueError("; ".join(check["errors"]))
            if args.command == "compare":
                result = compare_reviews(a, b)
            elif args.command == "adjudication-template":
                result = adjudication_template(a, b, args.observer_dir)
            else:
                result = export_adjudicated(a, b, load_json(args.ledger), args.observer_dir,
                                             allow_assisted=args.allow_assisted)
        write_new(args.out, result)
        print(json.dumps({"output": args.out, "records": len(result), "human_judgments_created": 0}))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
