import unittest
from pilot import task, validate_discovery

class PublicNarratorTests(unittest.TestCase):
 def setUp(self):
  self.v={'participants':[{'participant_id':'Audio','known_role':'recorded_audio_not_player'},{'participant_id':'A'},{'participant_id':'B'}],
   'context_sources':[],'dialogue_prefix':[{'utterance_id':'t1','speaker':'Audio','text':'Everyone, wake up.'},{'utterance_id':'t2','speaker':'A','text':'I suspect B.'}]}
 def test_public_narrator_is_not_accusation_target(self):
  h={'subtask':'target','event_id':'e1'}
  x={'arguments':{'event_id':'e1','act':'accuse','target':'Audio'}}
  self.assertIsNone(task(self.v,'A',h,x))
  x['arguments']['target']='B'
  self.assertEqual(task(self.v,'A',h,x),('Target','e1','accuse','B'))
 def test_public_narrator_is_not_focal_player(self):
  d={'candidates':[{'id':'c1','participant_pair':['A','Audio'],'focus_spans':[{'source_id':'t2','quote':'I suspect B.'}],
     'hypotheses':[{'id':'h1','subtask':'target','event_id':'e1','scope_evidence':[{'source_id':'t2','quote':'I suspect B.'}]}]}],'overflow':False}
  with self.assertRaisesRegex(ValueError,'Invalid focal pair'):validate_discovery(d,self.v)
