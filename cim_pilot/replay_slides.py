"""Execute constructed/supplied records. No model inference and no research accuracy."""
import argparse
import json
from pathlib import Path
from tests.test_pilot import fixture
from pilot import VERSION, evaluate_hypothesis, write_new

def replay():
    v,c,h,r,a,b=fixture()
    return {"record_type":"constructed_supplied_record_replay",
        "software":VERSION,
        "source":"Adapted MapTask teaching fixture; current integrated deck slide 11 illustrates the same explicit anchor comparison. Both anchors are present on both fixture maps; stimuli are not identical.",
        "is_model_prediction":False,
        "primary_evaluation_eligible":False,
        "purpose":"Explain and test F5-F7 with stipulated F1-F4 records",
        "input_records":{"observer_input":v,"candidate":c,"hypothesis":h,
                         "readings":r,"attributions":a,"support_checks":b},
        "result":evaluate_hypothesis(v,c,h,r,a,b)}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='New output path; existing different records are not overwritten.')
    args=parser.parse_args()
    out=replay()
    if args.out: write_new(args.out,out)
    print(json.dumps(out,indent=2))
