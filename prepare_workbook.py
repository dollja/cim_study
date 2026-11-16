"""Create clearly provisional working copies; never promote teaching cases to selected pilot."""
import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path
from pilot import write_new

ROOT=Path(__file__).parent
REF="75814e7c5898e3b1f35f823c90e5f4582b24e140"
NAMES={
 "giver":[("01","lake","lake","upper part"),("02","roman baths","roman_baths","below lake"),
          ("03","site of plane crash","plane_upper","upper right"),
          ("04","white mountain","white_mountain","left of antelope"),
          ("05","antelope","antelope","central upper part"),
          ("06","hot wells","springs","left of slate mountain"),
          ("07","slate mountain","slate_mountain","central part"),
          ("08","savannah","savannah","right lower part"),
          ("09","collapsed shelter","shelter","lower part"),
          ("10","site of plane crash","plane_lower","lower left"),
          ("11","stony desert","desert","lower right")],
 "follower":[("01","lake","lake","upper part"),("02","round rocks","round_rocks","upper left"),
             ("03","site of plane crash","plane_upper","upper right"),
             ("04","white mountain","white_mountain","left of antelope"),
             ("05","antelope","antelope","central upper part"),
             ("06","hot springs","springs","central left"),
             ("07","elephants","elephants","left lower part"),
             ("08","savannah","savannah","right lower part"),
             ("09","collapsed shelter","shelter","lower part"),
             ("10","waterhole","waterhole","lower middle"),
             ("11","stony desert","desert","lower right")]}

def main():
    contexts=[]
    for p,entries in NAMES.items():
        entities=[{"id":f"m9_{p}_{i}","label":name,"class_id":"m9_"+cls,"description":loc}
                  for i,name,cls,loc in entries]
        text="\n".join(f"{e['id']}: {e['label']}; {e['description']}; correspondence {e['class_id']}"
                       for e in entities)
        contexts.append({"source_id":"m9_"+p+"_inventory","text":text,
          "accessible_to_participants":[p],
          "adapter":{"kind":"map_inventory","review_status":"draft",
                     "entities":entities}})
    write_new(ROOT/"context"/"m9_inventory_DRAFT.json",{
      "status":"assistant_transcription_not_independently_reviewed",
      "source_commit":REF,
      "source_maps":["maps/map9g.gif","maps/map9f.gif"],
      "scope":"Printed landmarks and provisional correspondences; no traced giver route, geometry or drawn follower outcome.",
      "review_needed":"Two readers check names, duplicates, correspondences and required relations against the maps. Unknown facts remain unknown.",
      "context_sources":contexts})
    findings=[]
    for src in sorted((ROOT/"source_examples").glob("*.json")):
        old=json.loads(src.read_text())
        case={"sample_id":old["sample_id"],"study_role":"teaching_example_not_selected",
              "source":old["source"],"selection_metadata":old["selection_metadata"],
              "observer_input":copy.deepcopy(old["observer_input"])}
        case["observer_input"]["context_sources"]=copy.deepcopy(contexts)
        write_new(ROOT/"candidate_cases"/src.name,case)
        write_new(ROOT/"reference_drafts"/src.name,{
          "sample_id":old["sample_id"],"reference_status":"unreviewed",
          "original_annotation":old["manual_annotation"],
          "warning":"This inherited annotation is not an independent human reference and never enters model requests."})
        findings.append({"sample_id":old["sample_id"],"prefix_utterances":len(case["observer_input"]["dialogue_prefix"]),
                         "ready_for_measured_pilot":False,
                         "blockers":["not selected for pilot","map inventory requires independent review",
                                     "reference annotation requires review"]})
    sel=ROOT/"pilot_selection.csv"
    if not sel.exists():
        with sel.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["slot_id","dataset","sample_id","source_conversation",
                                         "map_pair_or_game_group","cutoff_id","selected","reference_status"])
            w.writeheader()
            for d in ["MapTask_GMMT","Werewolf"]:
                for n in range(1,11):
                    w.writerow({"slot_id":f"{d}_{n:02}","dataset":d,"selected":"false",
                                "reference_status":"unfilled"})
    write_new(ROOT/"results"/"readiness.json",{
      "prospective_slots":20,"actual_selected_episodes":0,
      "teaching_cases":findings,"measured_model_runs":0,
      "werewolf_transcripts_available_in_inspected_repository":False,
      "inference_endpoint_configured_in_this_workspace":False,
      "counting_rule":"Empty slots are not data. Shared conversation and map-pair dependence remains visible."})
    print(json.dumps({"working_examples":len(findings),"selected_pilot_episodes":0,"draft_map_inventory":True}))

if __name__=="__main__":main()
