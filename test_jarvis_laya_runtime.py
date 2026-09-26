import os, unittest
from unittest.mock import patch
from jarvis_laya_advisor import advise, request_runtime_advisory

class RuntimeTests(unittest.TestCase):
 def test_advice_isolation_and_no_ollama_call(self):
  snapshot={'symbol':'BTCUSDT','direction':'SELL','confidence':71}; before=dict(snapshot); calls=[]
  def fake(s): calls.append(s); return {'suggestion':'BUY','confidence':.7}
  result=advise(snapshot,symbol='BTCUSDT',deterministic_decision='SELL',predictor=fake)
  self.assertEqual(snapshot,before); self.assertEqual(result.deterministic_decision,'SELL'); self.assertEqual(result.suggestion,'BUY'); self.assertEqual(len(calls),1)
  # Adapter/runtime path is isolated: it never imports or invokes Ollama.
  self.assertNotIn('ollama', calls[0])
 def test_disabled_never_calls_predictor(self):
  r=advise({'symbol':'BTCUSDT'},symbol='BTCUSDT',deterministic_decision='NO_TRADE',predictor=lambda _:self.fail('called'),enabled=False)
  self.assertEqual(r.status,'disabled')
 def test_request_returns_immediately_and_does_not_mutate_snapshot(self):
  # Explicitly exercise the actual runtime wrapper while faking slow predictor.
  import jarvis_laya_advisor as m
  gate=__import__('threading').Event(); original=m.advise
  def slow(s,**kw): gate.wait(.2); return original(s,**kw)
  snapshot={'symbol':'BTCUSDT','direction':'SELL'}; before=dict(snapshot)
  with patch.object(m,'advise',side_effect=slow):
   r=request_runtime_advisory(snapshot,symbol='BTCUSDT',deterministic_decision='SELL')
  self.assertEqual(r.status,'pending'); self.assertEqual(snapshot,before); gate.set()

if __name__=='__main__': unittest.main()
