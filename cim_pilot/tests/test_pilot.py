import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pilot import check_view, compare, evaluate_hypothesis, retain, task, advance, digest

def fixture():
    v = {"overall_task": "Reproduce a route on differing maps.",
         "participants": [{"participant_id": "G"}, {"participant_id": "F"}],
         "dialogue_prefix": [
             {"utterance_id": "t1", "speaker": "G", "text": "Use the upper van. Pass below it."},
             {"utterance_id": "t2", "speaker": "F", "text": "I will pass below the lower van."}],
         "context_sources": []}
    for p in ["G", "F"]:
        v["context_sources"].append({
            "source_id": "map" + p, "text": "upper van; lower van",
            "accessible_to_participants": [p],
            "adapter": {"kind": "map_inventory", "review_status": "verified",
                        "entities": [{"id": p+"_U", "class_id": "U"},
                                     {"id": p+"_L", "class_id": "L"}]}})
    c = {"participant_pair": ["G", "F"]}
    h = {"id": "h1", "subtask": "route", "event_id": "next"}
    r = {"readings": [
        {"id": "upper", "paraphrase": "Use upper van",
         "arguments": {"anchor_ids": {"G": "G_U", "F": "F_U"}, "anchor_class": "U",
                       "event_id": "next", "relation": "below"}},
        {"id": "lower", "paraphrase": "Use lower van",
         "arguments": {"anchor_ids": {"G": "G_L", "F": "F_L"}, "anchor_class": "L",
                       "event_id": "next", "relation": "below"}}], "incomplete": False}
    records, checks = {}, {}
    for p, chosen, tid in [("G","upper","t1"), ("F","lower","t2")]:
        records[p] = {"records": [], "updates": [], "unresolved_scope": False}
        checks[p] = {"reading_reviews": [], "path_checks": [],
                     "update_checks": [], "unresolved_scope": False}
        for rid in ["upper", "lower"]:
            judgment = "supported" if rid == chosen else "contradicted"
            paths = []
            if rid == chosen:
                paths = [{"id": p+"_path", "root_type": "INSTRUCTS" if p == "G" else "SAYS",
                          "root": {"source_id": tid, "quote": "upper van" if p == "G" else "lower van"},
                          "scope_id": "next", "links": []}]
                checks[p]["path_checks"].append({"path_id": p+"_path", "verdict": "supported"})
            records[p]["records"].append({"reading_id": rid, "judgment": judgment, "paths": paths})
            checks[p]["reading_reviews"].append({"reading_id": rid, "judgment": judgment})
    return v, c, h, r, records, checks

class MethodTests(unittest.TestCase):
    def test_slide_mismatch(self):
        self.assertEqual(evaluate_hypothesis(*fixture())["status"], "POTENTIAL_MISMATCH")

    def test_shared_correspondence(self):
        v,c,h,r,a,b=fixture()
        for s in v["context_sources"]:
            for e in s["adapter"]["entities"]: e["class_id"]="same"
        for x in r["readings"]: x["arguments"]["anchor_class"]="same"
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "ALIGNED")

    def test_access_only_not_selection(self):
        v,c,h,r,a,b=fixture()
        path=a["F"]["records"][1]["paths"][0]
        path["root"]={"source_id":"mapF","quote":"lower van"}
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_bare_ack_fails_semantic_check(self):
        v,c,h,r,a,b=fixture()
        v["dialogue_prefix"][1]["text"]="Okay."
        a["F"]["records"][1]["paths"][0]["root"]["quote"]="Okay."
        b["F"]["path_checks"][0]["verdict"]="undetermined"
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_other_participant_assertion_not_own(self):
        v,c,h,r,a,b=fixture()
        a["F"]["records"][1]["paths"][0]["root"]={"source_id":"t1","quote":"upper van"}
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_private_map_link_invalid(self):
        v,c,h,r,a,b=fixture()
        a["F"]["records"][1]["paths"][0]["links"]=[{"relation":"MAP_FACT","source_id":"mapG","quote":"lower van"}]
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_later_turn_missing_from_view(self):
        v,c,h,r,a,b=fixture()
        a["F"]["records"][1]["paths"][0]["root"]={"source_id":"t99","quote":"lower van"}
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_unresolved_event_blocks(self):
        v,c,h,r,a,b=fixture()
        b["F"]["unresolved_scope"]=True
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_unknown_relation_blocks(self):
        v,c,h,r,a,b=fixture()
        r["readings"][0]["arguments"]["relation"]="turn_right_egocentric"
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"], "UNRESOLVED")

    def test_correction_removes_only_target_path(self):
        v,c,h,r,a,b=fixture()
        v["dialogue_prefix"].append({"utterance_id":"t3","speaker":"F",
                                    "text":"Correction: use the upper van."})
        a["F"]["updates"]=[{"id":"u1","action":"CORRECTS","source":{"source_id":"t3","quote":"Correction"},
                           "target_path_id":"F_path","scope_id":"next"}]
        b["F"]["update_checks"]=[{"update_id":"u1","verdict":"supported"}]
        kept=retain(v,"F",h,r["readings"],a["F"],b["F"])
        self.assertEqual(kept["X"],[])
        self.assertIn("lower",kept["excluded"])

    def test_uncertain_correction_blocks(self):
        v,c,h,r,a,b=fixture()
        a["F"]["updates"]=[{"id":"u1","action":"CORRECTS","source":{"source_id":"t2","quote":"lower van"},
                           "target_path_id":"missing","scope_id":"another_event"}]
        b["F"]["update_checks"]=[{"update_id":"u1","verdict":"undetermined"}]
        self.assertTrue(retain(v,"F",h,r["readings"],a["F"],b["F"])["blocking_scope"])

    def test_shared_nonsingleton_unresolved(self):
        self.assertEqual(compare({("a",),("b",)},{("a",),("b",)}),"UNRESOLVED")

    def test_different_holder_premises_not_compared(self):
        v,c,h,r,a,b=fixture()
        v["context_sources"]=[{"source_id":"rules","text":"swap","accessible_to_participants":["G","F"],
            "adapter":{"kind":"game_rules","review_status":"verified","roles":["Werewolf"]}}]
        h["subtask"]="holder"
        for x,p,branch in zip(r["readings"],["G","F"],["claim1","claim2"]):
            x["arguments"]={"event_id":"next","mode":"reported","holder":p,"role":"Werewolf",
                            "phase":"after","premise_branch":branch}
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"],"UNRESOLVED")

    def test_vote_and_accusation_are_distinct_questions(self):
        v,c,h,r,a,b=fixture();h["subtask"]="target"
        for x,p,act in zip(r["readings"],["G","F"],["vote","accuse"]):
            x["arguments"]={"event_id":"next","target":p,"act":act}
        self.assertEqual(evaluate_hypothesis(v,c,h,r,a,b)["status"],"UNRESOLVED")

    def test_unknown_is_not_negative(self):
        self.assertEqual(compare({None},{("a",)}),"UNRESOLVED")

    def test_malformed_reply_is_processing_failure(self):
        v,*_=fixture()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td); (p/"case.json").write_text(json.dumps({"sample_id":"demo","observer_input":v}))
            x=advance(p/"case.json",p/"run","fixture","manual_replay")
            self.assertEqual(x["status"],"AWAITING_MODEL_RESPONSE")
            (p/"run/01_discovery.response.txt").write_text("NOT JSON")
            y=advance(p/"case.json",p/"run","fixture","manual_replay")
            self.assertEqual(y["prefix_status"],"PROCESSING_FAILURE")

    def test_complete_saved_response_protocol(self):
        v,c,h,r,a,b=fixture()
        c.update({"id":"c1","focus_spans":[{"source_id":"t1","quote":"upper van"}]})
        h["scope_evidence"]=[{"source_id":"t1","quote":"Pass below it."}]
        c["hypotheses"]=[h]
        replies={"01_discovery":{"candidates":[c],"overflow":False},"c01_h01_F3":r,
                 "c01_h01_p1_F4":a["G"],"c01_h01_p1_check":b["G"],
                 "c01_h01_p2_F4":a["F"],"c01_h01_p2_check":b["F"]}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);run=p/"run"
            (p/"case.json").write_text(json.dumps({"sample_id":"demo","study_role":"teaching",
                                                 "observer_input":v}))
            for step,reply in replies.items():
                pending=advance(p/"case.json",run,"fixture","manual_replay")
                self.assertEqual(pending["status"],"AWAITING_MODEL_RESPONSE")
                self.assertTrue((run/(step+".request.json")).exists())
                (run/(step+".response.txt")).write_text(json.dumps(reply))
            final=advance(p/"case.json",run,"fixture","manual_replay")
            self.assertEqual(final["prefix_status"],"POTENTIAL_MISMATCH")
            self.assertFalse(final["is_measured_model_run"])

    def test_label_metadata_cannot_enter_view(self):
        v,*_=fixture(); v["manual_annotation"]={"label":"ALIGNED"}
        with self.assertRaises(ValueError): check_view(v)

    def test_unreviewed_maps_block_execution(self):
        v,*_=fixture(); v["context_sources"][0]["adapter"]["review_status"]="draft"
        with self.assertRaises(ValueError): check_view(v)

    def test_cross_year_schedule(self):
        v,*_=fixture()
        v["context_sources"]=[{"source_id":"schedule","text":"rules","accessible_to_participants":["G","F"],
            "adapter":{"kind":"schedule","review_status":"verified","rule":"earliest_available_in_interval",
                       "intervals":{"finance":["2026-11-01","2027-01-31"]},
                       "available_dates":["2026-09-15","2026-11-15","2027-01-15"]}}]
        self.assertEqual(task(v,"G",{"subtask":"review_date","event_id":"review"},
            {"arguments":{"event_id":"review","interval_id":"finance"}}),
            ("ReviewDate","review","2026-11-15"))

    def test_swap_is_conditional_not_hidden_truth(self):
        v,*_=fixture()
        v["context_sources"]=[{"source_id":"rules","text":"swap","accessible_to_participants":["G","F"],
            "adapter":{"kind":"game_rules","review_status":"verified","roles":["Robber","Werewolf"]}}]
        h={"subtask":"holder","event_id":"swap1"}
        a={"event_id":"swap1","mode":"swap","initial_state":{"G":"Robber","F":"Werewolf"},
           "moves":[{"operation":"swap","a":"G","b":"F"}],"order_resolved":True,
           "no_later_movement":True,"role":"Werewolf","phase":"after","premise_branch":"reported1"}
        self.assertEqual(task(v,"G",h,{"arguments":a})[3],"G")
        a["order_resolved"]=False
        self.assertIsNone(task(v,"G",h,{"arguments":a}))

if __name__=="__main__": unittest.main()
