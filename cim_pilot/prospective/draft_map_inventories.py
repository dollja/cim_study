"""Assistant map transcriptions for review. These are deliberately not verified facts."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
# label, proposed correspondence class, qualitative location. Duplicates stay distinct.
MAPS = {
 'm3': {
  'giver': [('START','start','upper left'),('cliffs','cliffs','below start'),('forge','forge','below cliffs'),('old pine','old_pine','right of forge'),('pine forest','pine_forest','upper right'),('wheatfields','wheatfields_upper','left middle'),('canal','canal','left of bakery'),('bakery','bakery','right middle'),('wheatfields','wheatfields_lower','lower left above rocket warehouse'),('crane bay','crane_bay','lower right'),('rocket warehouse','rocket_warehouse','lower left'),('old lighthouse','old_lighthouse','bottom left')],
  'follower': [('START','start','upper left'),('green bay','green_bay','top'),('sandstone cliffs','cliffs','below start'),('old pine','old_pine','upper left-middle'),('pine forest','pine_forest','upper right'),('forest stream','forest_stream','extends down from pine forest'),('wheatfields','wheatfields_upper','left middle'),('bakery','bakery','right middle'),('crane bay','crane_bay','lower right'),('rocket warehouse','rocket_warehouse','lower left'),('cave','cave','below rocket warehouse'),('old lighthouse','old_lighthouse','bottom left')]
 },
 'm6': {
  'giver': [('START','start','top left above diamond mine'),('diamond mine','diamond_mine','upper left'),('graveyard','graveyard','right of diamond mine'),('fast flowing river','watercourse','upper right'),('desert','desert','left below diamond mine'),('carved wooden pole','pole_upper','middle above walled city'),('apache camp','apache_camp','right above flat rocks'),('walled city','walled_city','left middle'),('flat rocks','flat_rocks','right middle'),('stone creek','stone_creek','below flat rocks'),('carved wooden pole','pole_lower','lower left above fort'),('buffalo','buffalo','lower right'),('cattle ranch','cattle_ranch','bottom middle'),('fort','fort','bottom left'),('FINISH','finish','left above fort')],
  'follower': [('START','start','top left above diamond mine'),('diamond mine','diamond_mine','upper left'),('fast running creek','watercourse','upper right'),('canoes','canoes','below fast running creek'),('desert','desert','left below diamond mine'),('apache camp','apache_camp','right above flat rocks'),('walled city','walled_city','left middle'),('flat rocks','flat_rocks','right middle'),('ghost town','ghost_town','left below walled city'),('saloon bar','saloon_bar','right below flat rocks'),('stone creek','stone_creek','lower middle'),('carved wooden pole','pole_lower','lower left above fort'),('buffalo','buffalo','lower right'),('fort','fort','bottom left')]
 },
 'm12': {
  'giver': [('farmed land','farmed_land','top middle'),('west lake','west_lake','upper left'),('east lake','east_lake','upper right'),('FINISH','finish','left of east lake'),('trig point','trig_point','right of west lake'),('nuclear test site','nuclear_test_site','right below east lake'),('monument','monument','right middle'),('abandoned cottage','abandoned_cottage','middle'),('fenced meadow','meadow_left','left below west lake'),('START','start','lower left above caravan park'),('caravan park','caravan_park','lower left'),('old mill','mill','below/right of caravan park'),('fenced meadow','meadow_lower_right','lower right')],
  'follower': [('farmed land','farmed_land','top middle'),('west lake','west_lake','upper left'),('east lake','east_lake','upper right'),('golf course','golf_course','right below east lake'),('monument','monument','right middle'),('abandoned cottage','abandoned_cottage','middle'),('forest','forest','lower middle above caravan park level'),('START','start','lower left above caravan park'),('caravan park','caravan_park','lower left'),('mill wheel','mill','below/right of caravan park'),('picket fence','picket_fence','bottom left'),('fenced meadow','meadow_lower_right','lower right')]
 }
}

def build(root=None):
 root = Path(root or ROOT)
 out = root/'context_drafts'
 planned = {}
 for mid,sides in MAPS.items():
  contexts=[]
  for person,rows in sides.items():
   entities=[{'id':f'{mid}_{person}_{i:02}', 'label':name, 'class_id':f'{mid}_{cls}', 'description':where}
             for i,(name,cls,where) in enumerate(rows,1)]
   contexts.append({'source_id':f'{mid}_{person}_inventory',
     'text':'\n'.join(f"{e['id']}: {e['label']}; {e['description']}; correspondence {e['class_id']}" for e in entities),
     'accessible_to_participants':[person],
     'adapter':{'kind':'map_inventory','review_status':'draft','entities':entities}})
  record={'map_pair':mid,'review_status':'assistant_draft_not_independently_reviewed',
   'provenance':f'../source_maps/map{mid[1:]}g.gif and map{mid[1:]}f.gif; see source_maps/provenance.json',
   'scope':'Printed names, start/finish markers where labelled, qualitative location and proposed static correspondences. No traced giver path or completed follower drawing.',
   'review_note':'The assistant transcribed these after source-dialogue screening. This does not satisfy two independent readers working without selected dialogue or labels. Check the original maps afresh and preserve uncertainty.',
   'context_sources':contexts}
  planned[out/f'{mid}_DRAFT.json'] = json.dumps(record,indent=2)+'\n'
 # Preserve the previously supplied m9 draft, also unverified.
 old=json.loads((root.parent/'context/m9_inventory_DRAFT.json').read_text())
 planned[out/'m9_DRAFT.json'] = json.dumps(old,indent=2)+'\n'
 # Check the entire batch before writing: a changed inventory may hold a reader's work.
 for path,text in planned.items():
  if path.exists() and path.read_text(encoding='utf-8') != text:
   raise ValueError(f'Refusing to overwrite changed or reviewed inventory: {path}. Use a new output directory.')
 out.mkdir(parents=True,exist_ok=True)
 for path,text in planned.items():
  if not path.exists():
   path.write_text(text,encoding='utf-8')
 return len(planned)

if __name__=='__main__': build()
