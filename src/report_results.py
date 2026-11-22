"""Summarize saved runs; score only an explicitly reviewed focal-chain reference register.

Reference format: {sample_id:{review_status:adjudicated, label:ALIGNED|POTENTIAL_MISMATCH|
UNRESOLVED, focal_source_ids:[...], cluster_id:..., reference_condition:independent_strict|
assisted_development, evidence_tier:S, evidence_review:{candidate_id:true|false}}}
Focal-source matching is a diagnostic approximation, so review chain identity before claims.
Missing legacy condition/tier metadata stays visible; it never establishes independent review.
Scoring additionally requires matching canonical observer_hash values in run and reference.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

LABELS = {"ALIGNED", "POTENTIAL_MISMATCH", "UNRESOLVED"}
REFERENCE_CONDITIONS = {"independent_strict", "assisted_development", "unspecified_legacy"}

def input_binding_status(run, reference):
    """Bind evidence identity only; equality does not certify semantic support."""
    for record, name in [(reference, "reference"), (run, "run")]:
        value = record.get("observer_hash")
        if value is None:
            return "missing_" + name + "_hash"
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            return "invalid_" + name + "_hash"
    return "matched" if run["observer_hash"] == reference["observer_hash"] else "mismatch"

def reference_condition(ref):
    condition = ref.get("reference_condition", "unspecified_legacy")
    if not isinstance(condition, str) or condition not in REFERENCE_CONDITIONS:
        raise ValueError("Unknown reference_condition: " + str(condition))
    return condition

def validate_reference(sid, ref):
    if not isinstance(ref, dict):
        raise ValueError("Reference must be an object: " + sid)
    reference_condition(ref)
    focal = ref.get("focal_source_ids", [])
    if not isinstance(focal, list) or any(not isinstance(x, str) or not x for x in focal):
        raise ValueError("focal_source_ids must be a list of source IDs: " + sid)
    if ref.get("review_status") == "adjudicated":
        if not isinstance(ref.get("label"), str) or ref["label"] not in LABELS:
            raise ValueError("Adjudicated reference requires a controlled label: " + sid)
        if not focal or not isinstance(ref.get("cluster_id"), str) or not ref["cluster_id"].strip():
            raise ValueError("Adjudicated reference requires focal IDs and a source cluster: " + sid)
    if not isinstance(ref.get("evidence_review", {}), dict):
        raise ValueError("evidence_review must map actual candidate IDs to judgments: " + sid)

def count_rows(rows):
    valid=[r for r in rows if r["score_eligible"]]
    pos=[r for r in valid if r["reference"]=="POTENTIAL_MISMATCH"]
    neg=[r for r in valid if r["reference"]=="ALIGNED"]
    unresolved=[r for r in valid if r["reference"]=="UNRESOLVED"]
    return {"runs":len(rows),"eligible_reviewed_pilot_cases":len(valid),
            "source_clusters":len({r["cluster_id"] for r in valid}),
            "correct_labels":sum(r["label_correct"] for r in valid),
            "correct_with_reviewed_evidence":sum(r["correct_with_reviewed_evidence"] for r in valid),
            "positive_reference_cases":len(pos),"aligned_reference_cases":len(neg),
            "unresolved_reference_cases":len(unresolved),
            "correct_warnings":sum(r["focal_prediction"]=="POTENTIAL_MISMATCH" and r["correct_with_reviewed_evidence"] for r in pos),
            "false_warnings_on_aligned":sum(r["focal_prediction"]=="POTENTIAL_MISMATCH" for r in neg),
            "warnings_on_unresolved_report_separately":sum(r["focal_prediction"]=="POTENTIAL_MISMATCH" for r in unresolved)}

def summarize(run_root, refs):
    if not isinstance(refs, dict):
        raise ValueError("References must be a case-ID-keyed object.")
    for sid, ref in refs.items():
        validate_reference(sid, ref)
    rows=[]
    seen=set()
    for path in sorted(Path(run_root).glob("*/prediction.json")):
        d=json.loads(path.read_text())
        sid=d["case_id"]
        if sid in seen:
            raise ValueError("Duplicate case runs: select one prespecified run per case in this report directory.")
        seen.add(sid)
        ref=refs.get(sid,{})
        binding=input_binding_status(d,ref)
        focal=set(ref.get("focal_source_ids",[]))
        matches=[c for c in d.get("candidates",[])
                 if focal & {q["source_id"] for q in c["focus_spans"]}]
        if d["prefix_status"]=="PROCESSING_FAILURE":
            pred="PROCESSING_FAILURE"
        elif not matches:
            pred="DISCOVERY_MISS"
        elif len(matches)>1:
            pred="CHAIN_MATCH_REVIEW_REQUIRED"
        else:
            pred=matches[0]["status"]
        eligible=(d.get("is_measured_model_run") is True
                  and d.get("response_origin")=="external_model"
                  and d.get("case_role")=="pilot"
                  and ref.get("review_status")=="adjudicated"
                  and ref.get("label") in LABELS
                  and d.get("evidence_tier", "S")=="S"
                  and ref.get("evidence_tier", "S")=="S"
                  and binding=="matched"
                  and bool(focal) and bool(ref.get("cluster_id")))
        evidence_ok=(len(matches)==1 and ref.get("evidence_review",{}).get(matches[0]["candidate_id"]) is True)
        rows.append({"sample_id":sid,"cluster_id":ref.get("cluster_id",""),"model":d["model_id"],
                     "origin":d["response_origin"],"role":d.get("case_role",""),
                     "reference_condition":reference_condition(ref),
                     "run_evidence_tier":d.get("evidence_tier","unspecified_legacy"),
                     "reference_evidence_tier":ref.get("evidence_tier","unspecified_legacy"),
                     "input_binding_status":binding,
                     "run_observer_hash":d.get("observer_hash"),
                     "reference_observer_hash":ref.get("observer_hash"),
                     "reference_observer_input_sha256":ref.get("observer_input_sha256"),
                     "prefix_status":d["prefix_status"],"focal_prediction":pred,
                     "reference":ref.get("label",""),"score_eligible":eligible,
                     "label_correct":eligible and pred==ref.get("label"),
                     "correct_with_reviewed_evidence":eligible and pred==ref.get("label") and evidence_ok})
    return {"counts":count_rows(rows),
            "input_binding_status_counts":dict(Counter(r["input_binding_status"] for r in rows)),
            "counts_by_reference_condition":{
                condition:count_rows([r for r in rows if r["reference_condition"]==condition])
                for condition in sorted(REFERENCE_CONDITIONS)},
            "limitations":["descriptive pilot counts only","no superiority claim",
                           "use condition-specific counts; aggregate totals are not independent blind-review results",
                           "source-cluster IDs do not establish independent participants or sessions",
                           "missing, invalid or mismatched canonical observer hashes are ineligible for scoring",
                           "matching input hashes establish evidence identity, not semantic correctness",
                           "focal chain matching and evidence need human review",
                           "no lead time without independently established event timing",
                           "unresolved references are not negative cases"],"rows":rows}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("run_root");ap.add_argument("--references");ap.add_argument("--out",required=True)
    args=ap.parse_args()
    refs=json.loads(Path(args.references).read_text()) if args.references else {}
    result=summarize(args.run_root,refs)
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise SystemExit("Choose a new output path; reports are not overwritten.")
    p.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["counts"],indent=2))
