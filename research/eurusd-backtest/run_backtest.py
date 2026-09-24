import csv,json,math,statistics,os
from datetime import datetime,timedelta
SRC='/tasklet/threads/a_2x9ndcmnz5ga63vn1b34/uploads/DAT_MT_EURUSD_M1_2020.csv'; OUT=os.path.dirname(__file__); PIP=1e-4; START=10000.; LEV=30.; RISK=.005

def parse():
 rows=[]; bad=dup=zero=0; seen=set()
 with open(SRC) as f:
  for r in csv.reader(f):
   if len(r)!=7: bad+=1; continue
   try:
    t=datetime.strptime(r[0]+' '+r[1],'%Y.%m.%d %H:%M'); x=list(map(float,r[2:])); o,h,l,c,v=x
    if not all(math.isfinite(z) for z in x) or h<max(o,c) or l>min(o,c) or l>h: bad+=1; continue
    if t in seen: dup+=1; continue
    seen.add(t); rows.append((t,o,h,l,c,v)); zero+=v==0
   except: bad+=1
 rows.sort(); gaps=[(b[0]-a[0]).total_seconds()/60 for a,b in zip(rows,rows[1:]) if (b[0]-a[0]).total_seconds()!=60]
 return rows,{'raw_rows':len(rows)+bad+dup,'parsed_rows':len(rows),'invalid_rows':bad,'duplicate_timestamps':dup,'zero_volume_rows':zero,'gap_count':len(gaps),'gap_minutes_total':sum(d-1 for d in gaps),'largest_gap_minutes':max(gaps,default=0),'timezone':'unknown; used as supplied','price_side':'unknown'}

def bars(rows,step):
 d={}
 for z in rows:
  t,o,h,l,c,v=z; b=t.replace(minute=t.minute//step*step,second=0)
  q=d.setdefault(b,[]); q.append(z)
 out=[]
 for b,q in sorted(d.items()):
  # complete only, exact contiguous minutes; no filling
  if len(q)!=step or any((q[i][0]-q[i-1][0]).total_seconds()!=60 for i in range(1,len(q))): continue
  out.append((b,q[0][1],max(x[2] for x in q),min(x[3] for x in q),q[-1][4],sum(x[5] for x in q),step))
 return out

def signals(bb,step):
 sig={}; seg=[]
 for i,b in enumerate(bb):
  if i and (b[0]-bb[i-1][0]).total_seconds()!=step*60: seg=[]
  seg.append(b)
  if len(seg)>=21:
   p=seg[-21:-1]; cur=seg[-1]; trs=[]
   for j in range(1,len(seg)):
    if j>=len(seg)-14: trs.append(max(seg[j][2]-seg[j][3],abs(seg[j][2]-seg[j-1][4]),abs(seg[j][3]-seg[j-1][4])))
   a=sum(trs)/14; hi=max(x[2] for x in p); lo=min(x[3] for x in p)
   if cur[4]>hi: sig[cur[0]+timedelta(minutes=step)]=('long',a,cur[0])
   elif cur[4]<lo: sig[cur[0]+timedelta(minutes=step)]=('short',a,cur[0])
 return sig

def run(rows,sig,atr_mult,tmin,spread,slip,name):
 eq=START; peak=START; dd=0.; pos=None; trades=[]; noentry=None
 for i,(t,o,h,l,c,v) in enumerate(rows):
  exited=False
  if pos:
   side,ep,stop,target,qty,et=pos; xp=reason=None
   if (side=='long' and o<=stop) or (side=='short' and o>=stop): xp=o; reason='stop_gap'
   elif (side=='long' and l<=stop) or (side=='short' and h>=stop): xp=stop; reason='stop'
   # timeout at open, before using this minute's range
   elif t>=et+timedelta(minutes=tmin): xp=o; reason='time'
   elif (side=='long' and h>=target) or (side=='short' and l<=target): xp=target; reason='target'
   if xp is not None:
    gross=(xp-ep)*qty*(1 if side=='long' else -1); cost=qty*(spread+2*slip); pnl=gross-cost; eq+=pnl
    trades.append({'entry_time':et.isoformat(),'exit_time':t.isoformat(),'side':side,'entry':ep,'exit':xp,'qty':qty,'pnl':pnl,'reason':reason,'duration_min':(t-et).total_seconds()/60,'R':pnl/(abs(ep-stop)*qty) if qty else 0}); pos=None; exited=True; noentry=t
  if not pos and not exited and t in sig:
   side,a,st=sig[t]
   if t!=st+timedelta(minutes=5 if name=='scalp' else 60) or i==0 or (t-rows[i-1][0]).total_seconds()!=60: continue
   ep=o; dist=atr_mult*a; stop=ep-dist if side=='long' else ep+dist; target=ep+2*dist if side=='long' else ep-2*dist
   # risk includes exact roundtrip unit cost; conservative quantity cap
   unit_risk=dist+spread+2*slip; qty=min(eq*RISK/unit_risk,eq*LEV/max(ep,1e-9)) if eq>0 else 0
   qty=math.floor(qty) # meaningful minimum 1 FX unit; skip zero
   if qty>=1:
    pos=(side,ep,stop,target,qty,t)
    # entry minute is fully tradable: conservative stop before target
    hit=(side=='long' and l<=stop) or (side=='short' and h>=stop)
    if hit:
     pnl=((stop-ep)*qty if side=='long' else (ep-stop)*qty)-qty*(spread+2*slip); eq+=pnl
     trades.append({'entry_time':t.isoformat(),'exit_time':t.isoformat(),'side':side,'entry':ep,'exit':stop,'qty':qty,'pnl':pnl,'reason':'stop','duration_min':0,'R':pnl/(dist*qty)}); pos=None
  mark=c
  mtm=eq if not pos else eq-((pos[4]*(spread+2*slip))+((pos[1]-mark)*pos[4]*(1 if pos[0]=='long' else -1)))
  peak=max(peak,mtm); dd=max(dd,peak-mtm)
 if pos:
  side,ep,stop,target,qty,et=pos; xp=rows[-1][4]; pnl=(xp-ep)*qty*(1 if side=='long' else -1)-qty*(spread+2*slip); eq+=pnl; trades.append({'entry_time':et.isoformat(),'exit_time':rows[-1][0].isoformat(),'side':side,'entry':ep,'exit':xp,'qty':qty,'pnl':pnl,'reason':'eod','duration_min':(rows[-1][0]-et).total_seconds()/60,'R':pnl/(abs(ep-stop)*qty)})
 wins=sum(x['pnl']>0 for x in trades); loss=sum(x['pnl']<0 for x in trades); gp=sum(x['pnl'] for x in trades if x['pnl']>0); gl=-sum(x['pnl'] for x in trades if x['pnl']<0)
 return {'strategy':name,'trades':len(trades),'wins':wins,'losses':loss,'breakeven':len(trades)-wins-loss,'win_rate_closed':wins/len(trades) if trades else None,'net_pnl':eq-START,'net_pct':(eq/START-1)*100,'profit_factor':gp/gl if gl else None,'max_mtm_drawdown':dd,'final_equity':eq},trades

def main():
 rows,audit=parse(); results=[]; alltr={}
 for step,mult,t,name in [(5,1.5,60,'scalp'),(60,2,2880,'swing')]:
  bb=bars(rows,step); sg=signals(bb,step)
  for n in [1,2]:
   sp=PIP*n; sl=.1*PIP*n; r,tr=run(rows,sg,mult,t,sp,sl,name); r.update({'cost_case':'baseline' if n==1 else 'doubled','bar_count':len(bb),'signals':len(sg),'spread_pips':n,'slippage_pips_per_side':.1*n}); results.append(r); alltr[name+('_baseline' if n==1 else '_doubled')]=tr
 json.dump(audit,open(OUT+'/audit.json','w'),indent=2); json.dump({'audit':audit,'results':results,'method':'fixed breakout proxy; corrected accounting; zero swap assumption'},open(OUT+'/summary.json','w'),indent=2)
 for k,tr in alltr.items():
  with open(OUT+'/trades_'+k+'.csv','w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=['entry_time','exit_time','side','entry','exit','qty','pnl','reason','duration_min','R']); w.writeheader(); w.writerows(tr)
 with open(OUT+'/methodology.md','w') as f:f.write('# Corrected EURUSD backtest\n\nFixed 5m/1h breakout proxy, using only complete contiguous OHLC bars and prior closed bars. Raw open entry reference; raw ATR stop/2R target. Gross raw price difference; exact one-time exit cost qty*(spread+2×slippage). MTM reserves that total cost once while open. Risk 0.5% includes stop plus unit roundtrip cost, 30x cap, integer FX units; zero skipped. Existing gap stop, then open time expiry, then intraminute stop/target (stop wins ties). Entry minute is processed for stop/target. No re-entry on exit minute. Timeout is wall-clock (60/2880 minutes). Zero swap assumed. Indicators reset across missing bars. EOD closes once and updates DD.\n')
 with open(OUT+'/report_gu.md','w') as f:
  f.write('# EURUSD 2020 — સુધારેલ પરિણામો\n\nપહેલાંના આંતરિક પરિણામો અમાન્ય હતા; નીચેના આંકડા સુધારેલી accounting પછીના છે. આ fixed breakout proxy છે, Jarvis/full-system test નથી. Zero-swap assumption.\n\n')
  for r in results:f.write(f"- {r['strategy']} / {r['cost_case']}: trades {r['trades']}, win-rate {r['win_rate_closed']}, net ${r['net_pnl']:.2f} ({r['net_pct']:.2f}%), PF {r['profit_factor']}, MTM DD ${r['max_mtm_drawdown']:.2f}\n")
 print(json.dumps({'audit':audit,'results':results}))
if __name__=='__main__': main()
