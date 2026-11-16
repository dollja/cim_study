"""Build 20 traceable, unadjudicated prospective records; no model call or automatic gold label."""
import argparse, copy, csv, hashlib, html, json, re, shutil
from pathlib import Path
try:
 from . import draft_map_inventories
except ImportError:
 import draft_map_inventories

ROOT=Path(__file__).parent
TASK_MAP='One participant describes a route, and another attempts to reproduce it on their own map. Their maps may differ, and neither participant can see the other\'s map.'
TASK_GAME='Participants discuss a One Night Ultimate Werewolf game after its night actions and decide whom to accuse or vote for. Statements about roles and actions are reports that may be disputed or strategic. Preserve the distinction between a reported initial role, a role after a reported exchange, and a current role. Use the publicly spoken instructions in this prefix for the variant; do not infer hidden cards or final votes.'

def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def parse(source,werewolf,root=None):
 path=Path(root or ROOT)/'source_transcripts'/f'{source}.txt'
 text=path.read_text(encoding='utf-8-sig')
 rows=[]; crosswalk=[]; skipped=[]
 for n,line in enumerate(text.splitlines(),1):
  if not line.strip():
   skipped.append({'source_line':n,'reason':'blank_line'}); continue
  stamp=None
  if werewolf:
   m=re.fullmatch(r'(.+?) \((\d{1,2}:\d{2})\): ?(.*)',line)
   if not m: raise ValueError(f'Unparsed source line {source}:{n}: {line}')
   person,stamp,utterance=m.groups()
  else:
   fields=line.split('\t')
   if fields[0] not in ['g','f']:
    if n>3: raise ValueError(f'Unexpected transcript header {source}:{n}')
    skipped.append({'source_line':n,'reason':'source_header','text':line}); continue
   person={'g':'giver','f':'follower'}[fields[0]]; utterance=fields[1].strip()
  uid=f'{source}.row.{len(rows)+1:03}'
  rows.append({'utterance_id':uid,'speaker':person,'text':utterance})
  crosswalk.append({'utterance_id':uid,'source_line':n,'timestamp_as_supplied':stamp,'raw_line':line})
 if werewolf:
  seconds=[int(x['timestamp_as_supplied'].split(':')[0])*60+int(x['timestamp_as_supplied'].split(':')[1]) for x in crosswalk]
  reversals=[crosswalk[i]['utterance_id'] for i in range(1,len(seconds)) if seconds[i]<seconds[i-1]]
 else: reversals=[]
 return rows,{'source':source,'generated_ids':True,'ordering':'original file order; never timestamp-sorted',
   'normalization':'MapTask speaker-code expansion and outer field whitespace removal only. Werewolf speaker/timestamp delimiters parsed; utterance wording retained.',
   'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':crosswalk,'non_utterance_lines':skipped,
   'timestamp_reversals':reversals}

def _build_records(root):
 ROOT=Path(root)
 draft_map_inventories.build(ROOT)
 specs=json.loads((ROOT/'selection_specs.json').read_text())
 provenance={r['source_id']:r for name in ['maptask_sources','werewolf_sources']
             for r in json.loads((ROOT/'provenance'/f'{name}.json').read_text())}
 records=[]; register=[]; screens=[]
 for s in specs:
  ww=s['id'].startswith('WW'); rows,crosswalk=parse(s['source'],ww,ROOT)
  assert 1<=s['focus']<s['cutoff']<=len(rows)
  assert s['cutoff']==s['focus']+1, 'This batch uses an immediate next-source-row response.'
  focus,response=rows[s['focus']-1],rows[s['cutoff']-1]
  assert focus['speaker']!=response['speaker']
  assert [focus['speaker'],response['speaker']]==s['pair']
  prefix=rows[:s['cutoff']]
  participants=[{'participant_id':p,'known_role':('recorded_audio_not_player' if p=='Audio' else None) if ww else p}
                for p in dict.fromkeys(r['speaker'] for r in prefix)]
  if ww:
   # Only already-public instructions are copied as general context. No hidden role roster.
   instructions=[r for r in prefix if r['speaker']=='Audio']
   rule_text='\n'.join(r['text'] for r in instructions)
   vocabulary=['Werewolf','Villager','Seer','Robber','Troublemaker','Mason','Drunk','Insomniac','Minion','Tanner']
   contexts=[{'source_id':f"{s['source']}_public_instructions",'text':rule_text,
    'accessible_to_participants':[p['participant_id'] for p in participants if p['participant_id']!='Audio'],
    'adapter':{'kind':'game_rules','review_status':'draft','roles':vocabulary}}]
  else:
   contexts=copy.deepcopy(json.loads((ROOT/'context_drafts'/f"{s['map_pair']}_DRAFT.json").read_text())['context_sources'])
  view={'overall_task':TASK_GAME if ww else TASK_MAP,'participants':participants,'context_sources':contexts,'dialogue_prefix':prefix}
  sid=f"{s['id']}_{s['source']}_r{s['cutoff']:03}"
  src=copy.deepcopy(provenance[s['source']]); src['dialogue_id']=s['source']; src['ids_are_generated']=True
  src['crosswalk_file']=f"crosswalks/{s['source']}.json"
  cluster=s.get('map_pair') or src['original_path'].split('/')[-1].split('_Game')[0]
  metadata={'focal_episode_start_id':focus['utterance_id'],'focus_utterance_id':focus['utterance_id'],
   'first_relevant_response_id':response['utterance_id'],'observation_cutoff_id':response['utterance_id'],
   'cutoff_reason':f"The next source utterance by {response['speaker']} responds to the focal contribution; no intervening response is skipped.",
   'prefix_utterance_count':len(prefix),'prefix_word_count':sum(len(r['text'].split()) for r in prefix),
   'prefix_token_count':None,'focus_position_normalized':s['focus']/len(prefix),'focus_to_cutoff_utterances':s['cutoff']-s['focus'],
   'paired_delayed_prefix_id':None,'selection_status':'assistant_proposed_awaiting_human_selection',
   'confirmed_as_original_selection':False}
  draft={k:s[k] for k in ['title','subtask','draft_status','supported_A','supported_B','consequence','reason','uncertainty','timing','adapter','media_priority']}
  draft.update({'author':'assistant','is_human_reference':False,'is_model_prediction':False,'scope':'focal exchange only; not a full-prefix label',
   'focal_pair':s['pair'],'focus_quote':focus['text'],'response_quote':response['text'],
   'evidence_scope':'Justification must be checked using prefix only. The assistant screened longer transcript passages, so this draft is not a blinded independent annotation.'})
  record={'sample_id':sid,'dataset':'Werewolf Among Us' if ww else 'MapTask/GMMT','study_role':'prospective_candidate_unselected',
   'source':src,'selection_metadata':metadata,'observer_input':view,'manual_annotation':None,'assistant_annotation_draft':draft,
   'later_evidence':{'dialogue':rows[s['cutoff']:],'observed_action_or_outcome':None,'event_type':None,
                    'what_it_supports':'Retained for a separate later-evidence review; no suffix inference is used as prefix support in this draft.'},
   'annotation_review':{'review_status':'unreviewed','independent_coder_1':None,'independent_coder_2':None,'adjudicated_label':None},
   'sampling_and_reference_protocol':{'map_pair_id':s.get('map_pair'),'provisional_source_group':cluster,
    'merged_cluster_id':None,'partition':'development_candidate_only','full_dev_test_split_drawn':False,
    'evidence_tier':'S','exposure':'Assistant curation and preliminary interpretation; not a blind test set.'}}
  write(ROOT/'curator_cases'/f'{sid}.json',record)
  write(ROOT/'observer_cases'/f'{sid}.json',{'sample_id':sid,'study_role':record['study_role'],'observer_input':view})
  write(ROOT/'observer_inputs'/f'{sid}.json',view)
  write(ROOT/'crosswalks'/f"{s['source']}.json",crosswalk)
  records.append(record)
  register.append({'slot_id':s['id'],'dataset':record['dataset'],'sample_id':sid,'source_conversation':s['source'],
   'map_pair_or_game_group':cluster,'cutoff_id':response['utterance_id'],'selected':'false','reference_status':'assistant_draft_unreviewed'})
  screens.append({'source':s['source'],'prospective_records_created':1,'reviewed_candidate_chains_recorded':1,
   'comprehensive_chain_enumeration':False,'selection_reason':s['reason'],'draft_status':s['draft_status'],
   'eligible_for_measured_run_now':False,'timestamp_reversals':crosswalk['timestamp_reversals']})
 with (ROOT.parent/'pilot_selection.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(register[0])); w.writeheader(); w.writerows(register)
 write(ROOT/'screening_log.json',{'protocol':'Convenience feasibility batch, one prospective record per source. Sources chosen before this draft analysis from four MapTask pairs and ten distinct Werewolf file-title groups. Not a prespecified comprehensive screening study.',
  'candidate_retrieval':'Source transcript text, no released interpretation/persuasion/outcome labels.',
  'limits':'The assistant saw longer passages during curation. Independent prefix-first annotation, complete candidate enumeration, event timing and session/person overlap review remain undone.',
  'records':screens})
 write(ROOT/'readiness.json',{'prospective_episode_records':20,'MapTask_records':10,'Werewolf_records':10,
  'MapTask_dialogues':10,'MapTask_pairs':4,'Werewolf_games':10,'Werewolf_title_groups':10,
  'independent_session_clusters':None,'confirmed_original_selection_records':0,'human_adjudicated_records':0,
  'inference_execution':'not performed by candidate generation',
  'source_validation':'Run validate_candidates.py against this new output before use.',
  'all_prefixes_complete_to_cutoff':True,
  'blocked_by':['independent source/context/reference review','case inclusion decisions','configured and recorded inference run'],
  'source_acquisition_change':'Ten actual Werewolf transcripts acquired; the earlier source-access blocker is resolved for these ten games.'})
 build_html(records,ROOT)
 return {'prospective_cases':len(records),'prefix_utterances':sum(len(r['observer_input']['dialogue_prefix']) for r in records),'confirmed_selection':0,'inference_execution':'not performed'}

def build_html(records,root=ROOT):
 ROOT=Path(root)
 e=html.escape
 articles=[]; links=[]
 for r in records:
  d=r['assistant_annotation_draft']; s=r['selection_metadata']; sid=r['sample_id']; short=sid.split('_')[0]
  links.append(f'<a href="#{e(short)}">{e(short)} · {e(d["title"])}</a>')
  turns=''.join(f'<tr><td>{e(t["utterance_id"])}</td><td>{e(t["speaker"])}</td><td>{e(t["text"])}</td></tr>' for t in r['observer_input']['dialogue_prefix'])
  notes=''.join(f'<dt>{e(label)}</dt><dd>{e(d[key])}</dd>' for label,key in [('Local question','subtask'),('Participant A','supported_A'),('Participant B','supported_B'),('Computed-output proposal','consequence'),('Why this case','reason'),('Uncertainty','uncertainty'),('Timing','timing'),('Media review','media_priority')])
  ctx=''.join(f'<h4>{e(c["source_id"])}</h4><pre>{e(c["text"])}</pre>' for c in r['observer_input']['context_sources'])
  articles.append(f'''<article id="{e(short)}"><p class="eyebrow">{e(r['dataset'])} · {e(short)}</p><h2>{e(d['title'])}</h2>
<p>{s['prefix_utterance_count']} utterances · {s['prefix_word_count']} whitespace-delimited words · cutoff {e(s['observation_cutoff_id'])}</p>
<p><a href="{e(r['source']['url'],quote=True)}">Pinned original source</a> · Human reference: not yet reviewed</p>
<details><summary>Draft participant context — requires verification</summary>{ctx}</details>
<details open><summary>Complete observer prefix</summary><div class="scroll"><table><thead><tr><th>ID</th><th>Speaker</th><th>Original wording</th></tr></thead><tbody>{turns}</tbody></table></div></details>
<details><summary>Assistant's preliminary interpretation — open after your own reading</summary><p class="flag">{e(d['draft_status'])} · focal exchange only</p><dl>{notes}</dl><p>{e(d['evidence_scope'])}</p></details>
<p class="small">Later turns are retained separately in curator_cases/{e(sid)}.json. They are absent from this prefix and observer_inputs/{e(sid)}.json.</p></article>''')
 page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CIM — 20 prospective episodes</title>
<style>:root{font-family:system-ui,sans-serif;color:#152b40;background:#f0f3f7;line-height:1.55}body{margin:0}header{background:#153951;color:white;padding:40px max(24px,5vw)}h1{font-size:2.2rem;margin:4px 0 12px}header p{max-width:900px}.layout{display:grid;grid-template-columns:290px minmax(0,1fr);max-width:1450px;margin:auto}nav{padding:24px;position:sticky;top:0;height:95vh;overflow:auto}nav a{display:block;margin:0 0 11px;color:#214e74;text-decoration:none;font-size:.88rem}main{padding:24px;min-width:0}article,.intro{background:white;border:1px solid #d8e0e7;border-radius:10px;padding:26px;margin-bottom:24px;scroll-margin-top:16px}h2{line-height:1.25;margin:4px 0 14px}.eyebrow{font-size:.8rem;font-weight:700;letter-spacing:.06em;color:#365e79;margin:0}.flag{background:#fff2cd;padding:12px;border-radius:6px}details{margin-top:18px;border-top:1px solid #d9e1e8;padding-top:12px}summary{font-weight:650;cursor:pointer}.scroll{overflow-x:auto;max-height:650px;overflow-y:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #e5eaf0}th{position:sticky;top:0;background:#eef3f7}td:first-child{white-space:nowrap;color:#526778;font-size:.8rem}dt{font-weight:700;margin-top:14px}dd{margin:3px 0}pre{white-space:pre-wrap;font-size:.85rem;background:#f4f7fa;padding:14px}.small{font-size:.8rem;color:#526778}a{color:#205a87}@media(max-width:850px){.layout{display:block}nav{position:static;height:auto;max-height:260px}main{padding:12px}article{padding:18px}h1{font-size:1.7rem}}@media print{nav{display:none}.layout{display:block}header{background:white;color:#152b40}article{break-before:page}.scroll{max-height:none}details{display:block}summary{display:none}}</style>
<header><p>Chapters 3–4 · current-method development</p><h1>20 prospective episodes now exist</h1><p>10 MapTask prefixes and 10 Werewolf prefixes, each from a real source conversation. These are newly proposed records, not a recovered list of the originally requested selected cases. Human-adjudicated cases: 0. Measured model runs: 0.</p></header><div class="layout"><nav>'''+''.join(links)+'''</nav><main><section class="intro"><h2>Review the evidence before opening the draft interpretation</h2><p>This is a curator workbook. Read each complete prefix and the draft context first. Record your own focal pair, question, supported meanings and uncertainty separately before reading the assistant notes. All map inventories and variant settings still require review. The assistant saw longer passages during source screening; these notes are not independent blinded annotations.</p><p>A different map, an accusation, a question or an “okay” is not by itself proof of a consequential interpretation mismatch. Compare supported meanings about the same local question, then compute the task consequence. Unresolved output is legitimate.</p><p>The three previously exposed q1ec2 teaching examples are kept separately. No future-work method is included. Start with CONTINUATION_STATUS.md for what changed and what remains.</p></section>'''+''.join(articles)+'''</main></div></html>'''
 (ROOT/'REVIEW_20_EPISODES.html').write_text(page,encoding='utf-8')

def build_records(output_dir,source_root=None):
 """Regenerate only into a new/empty package directory; never reset live reviews."""
 destination=Path(output_dir).resolve()
 source_root=Path(source_root or ROOT).resolve()
 context_root=source_root.parent/'context'
 if destination.is_relative_to(source_root) or destination.is_relative_to(context_root):
  raise ValueError('Choose a destination outside the source and context directories.')
 if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
  raise ValueError('Destination must be new or empty; no files have been replaced.')
 destination.mkdir(parents=True,exist_ok=True)
 generated=destination/'prospective';generated.mkdir()
 for name in ['source_transcripts','source_maps','provenance']:
  shutil.copytree(source_root/name,generated/name)
 shutil.copy2(source_root/'selection_specs.json',generated/'selection_specs.json')
 (destination/'context').mkdir()
 shutil.copy2(context_root/'m9_inventory_DRAFT.json',destination/'context/m9_inventory_DRAFT.json')
 result=_build_records(generated)
 return {**result,'generated_directory':str(destination),'existing_reviews_preserved':True,'selection_decisions_created':0}

def main():
 parser=argparse.ArgumentParser(description="Regenerate candidate data in a new directory. Existing reviews, contexts and selections are never overwritten.")
 parser.add_argument('--output-dir',type=Path,required=True,help='New or empty destination outside prospective/ and context/.')
 args=parser.parse_args()
 try:
  result=build_records(args.output_dir)
 except ValueError as ex:
  parser.error(str(ex))
 print(json.dumps(result,indent=2))

if __name__=='__main__': main()
