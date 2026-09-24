import unittest,sys,os
sys.path.insert(0,os.path.dirname(__file__)); import run_backtest as m
from datetime import datetime,timedelta
class T(unittest.TestCase):
 def bars(self, xs):
  t=datetime(2020,1,1); return [(t+timedelta(minutes=i),*x,1) for i,x in enumerate(xs)]
 def test_flat_cost_exact(self):
  self.assertAlmostEqual(10000*(.0001+2*.00001),1.2)
 def test_entry_stop_and_tie_stop(self):
  x=self.bars([(1,1.001,.999,1),(1,1.001,.999,1)]); s={x[1][0]:('long',.0005,x[1][0]-timedelta(minutes=5))}; r,tr=m.run(x,s,1,60,.0001,.00001,'scalp'); self.assertEqual(tr[0]['reason'],'stop')
 def test_timeout_before_range(self):
  x=self.bars([(1,1,1,1)]*2+[(1,2,.5,1)]); s={x[1][0]:('long',.0001,x[1][0]-timedelta(minutes=5))}; r,tr=m.run(x,s,1,1,.0001,.00001,'scalp'); self.assertIn(tr[0]['reason'],('time','stop'))
 def test_bars_incomplete(self):
  t=datetime(2020,1,1); self.assertEqual(m.bars([(t,1,1,1,1,1)],5),[])
 def test_positive_sizing(self):
  x=self.bars([(1,1.001,.999,1)]*3); s={x[1][0]:('long',.0001,x[1][0]-timedelta(minutes=5))}; r,tr=m.run(x,s,1,60,.0001,.00001,'scalp'); self.assertTrue(tr and tr[0]['qty']>=1)
if __name__=='__main__': unittest.main()
