"""Replay assistant-supplied readings on real prefixes. Never an independent model experiment."""
import argparse,copy,json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT.parent))
from pilot import VERSION,evaluate_hypothesis,write_new

def make(short,subtask,args,roots,conditional=False):
 case=json.loads(next((ROOT/'curator_cases').glob(short+'_*.json')).read_text())
 view=case['observer_input']; d=case['assistant_annotation_draft']; pair=d['focal_pair']
 h={'id':'h1','subtask':subtask,'event_id':short+'_local_event'}
 arguments=copy.deepcopy(args); arguments['event_id']=h['event_id']
 if subtask=='target': meaning=f"The current {args['act']} target is {args['target']}."
 elif subtask=='route': meaning=f"The current route step is {args['relation']} the landmark class {args['anchor_class']}."
 else: meaning='Justin reports a swap between two players whose identities are not bound in this text; the resulting Werewolf holder is unknown.'
 readings={'readings':[{'id':'r1','paraphrase':meaning,'arguments':arguments}],'incomplete':False}
 if subtask=='outside':
  readings={'readings':[{'id':role,'paraphrase':f'Katie is claiming the initial role {role}.',
    'arguments':{'event_id':h['event_id'],'claimed_role':role,'claimant':'Katie'}} for role in ['Mason','Troublemaker']], 'incomplete':False}
 turns={t['utterance_id']:t for t in view['dialogue_prefix']}
 records={}; checks={}
 for p in pair:
  root=roots.get(p)
  paths=[]; pc=[]
  if root:
   n,quote,link_rows=root
   uid=f"{case['source']['dialogue_id']}.row.{n:03}"
   assert quote in turns[uid]['text'] and turns[uid]['speaker']==p
   links=[]
   for link_n in link_rows:
    lid=f"{case['source']['dialogue_id']}.row.{link_n:03}"
    links.append({'relation':'COREF','source_id':lid,'quote':turns[lid]['text']})
   paths=[{'id':p+'_path','root_type':'SAYS','root':{'source_id':uid,'quote':quote},'scope_id':h['event_id'],'links':links}]
   pc=[{'path_id':p+'_path','verdict':'supported'}]
  judgment='supported' if root else 'undetermined'
  chosen=('Mason' if p=='Katie' else 'Troublemaker') if subtask=='outside' else 'r1'
  records[p]={'records':[{'reading_id':r['id'],'judgment':judgment if r['id']==chosen else 'undetermined','paths':paths if r['id']==chosen else []}
                        for r in readings['readings']], 'updates':[], 'unresolved_scope':False}
  checks[p]={'reading_reviews':[{'reading_id':r['id'],'judgment':judgment if r['id']==chosen else 'undetermined'} for r in readings['readings']],
             'path_checks':pc,'update_checks':[],'unresolved_scope':False}
 candidate={'participant_pair':pair}
 result=evaluate_hypothesis(view,candidate,h,readings,records,checks)
 return {'case_id':case['sample_id'],'record_type':'real_prefix_supplied_record_replay',
  'is_model_prediction':False,'primary_evaluation_eligible':False,
  'scope':'Focal exchange only. Discovery, meanings, attribution and semantic checks were supplied by the same assistant; F5–F7 were executed by code.',
  'map_review_condition_pending':conditional,
  'context_review_status':[s['adapter'].get('review_status') for s in view['context_sources']],
  'interpretation_coverage_tested':False,
  'source_prefix_sha256':hashlib.sha256(json.dumps(view,sort_keys=True).encode()).hexdigest(),
  'supplied_candidate':candidate,'supplied_hypothesis':h,'supplied_readings':readings,
  'supplied_attribution':records,'supplied_semantic_checks':checks,'computed_result':result}

def anchor(short,mid,cls,roots):
 case=json.loads(next((ROOT/'observer_cases').glob(short+'_*.json')).read_text())
 ids={}
 for src in case['observer_input']['context_sources']:
  p=src['accessible_to_participants'][0]
  ids[p]=next(e['id'] for e in src['adapter']['entities'] if e['class_id']==f'{mid}_{cls}')
 return make(short,'route',{'anchor_ids':ids,'anchor_class':f'{mid}_{cls}','relation':'above' if short=='MT03' else 'below'},roots,True)

def replay():
 traces=[
  make('WW02','target',{'act':'accuse','target':'Caitlynn'},
       {'Justin':(39,"Caitlynn's a Werewolf.",[]),'Dan':(40,'I think that she is a Werewolf.',[39])}),
  anchor('MT03','m3','old_pine',{'giver':(18,'up above it',[15]),'follower':(19,'up above it',[15,18])}),
  anchor('MT05','m3','bakery',{'follower':(52,"i'm going east underneath the bakery",[]),'giver':(53,'underneath the bakery',[49,52])}),
  anchor('MT10','m3','start',{'follower':(43,'straight down under the start',[]),'giver':(41,"until you're beneath the the start",[])}),
  make('WW01','holder',{'mode':'swap','role':'Werewolf','phase':'after_reported_swap','premise_branch':'Justin_report','order_resolved':False,'no_later_movement':False,'initial_state':{},'moves':[]},
       {'Justin':(27,"I switched your guys' cards.",[])}),
  make('WW09','outside',{},
       {'Katie':(58,'I was all by myself.',[56,57]),'Brett':(59,"you're claiming the Troublemaker",[57,58])})
 ]
 output={'record_type':'assistant_supplied_record_replays','software':VERSION,'replays':traces,
  'counts_are_not_accuracy':'Six code replays, zero independent model runs. The four computed local alignments include three conditional on unverified map inventories. Two unresolved outputs illustrate missing evidence or adapter coverage; none is a calibrated prediction.',
  'source_condition':'This replay does not assess or change human selection, reference adjudication or context verification. No model service is called.'}
 return output

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--out',type=Path,help='New output path; existing different records are not overwritten.')
 args=parser.parse_args()
 output=replay()
 if args.out:write_new(args.out,output)
 print(json.dumps(output,indent=2))

if __name__=='__main__':main()
