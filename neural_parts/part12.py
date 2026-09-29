"""Part 12 owned model: evidence consensus reliability head, not probability."""
from .common import TIMEFRAMES, mtf_signal_matrix, std, clip
FEATURE_NAMES=tuple([f"part{i}_strength" for i in range(1,11)]+["signed_consensus_vote","signal_dispersion","directional_agreement","active_quorum","neutral_fraction","anchor_alignment","high_tf_support","part7_veto_fraction"])
MODEL_SPEC={"task":"consensus_correctness","dims":(18,16,6,1),"acts":("relu","tanh","linear"),"labels":("incorrect","correct"),"kind":"sigmoid"}
def prepare_features(evidence):
 matrix=mtf_signal_matrix(evidence); weights=(1.,1.05,1.10,1.20,1.25,1.35,1.40,1.45); den=sum(weights)
 by_part=[sum(matrix[t][p]*weights[t] for t in range(8))/den for p in range(10)]; by_tf=[sum(row)/10 for row in matrix]; overall=sum(by_part)/10; direction=1 if overall>0 else -1 if overall<0 else 0
 agreement=sum(v*direction>0 for v in by_part)/10 if direction else 0; neutral=sum(abs(v)<=.05 for v in by_part)/10; active=sum(abs(v)>=.10 for row in matrix for v in row)/80
 anchors=(by_part[5],by_part[7],by_part[8]); alignment=sum((1 if v>0 else -1 if v<0 else 0)*bool(direction) for v in anchors)/3; high_tf=sum(by_tf[i]*weights[i] for i in range(4,8))/sum(weights[4:8])
 frames=evidence.get("frames",evidence); veto=sum(bool(frames[tf].get("part7_volatility",{}).get("entry_blocked")) for tf in TIMEFRAMES)/8
 return tuple(clip(v) for v in [*[abs(x) for x in by_part],overall,std(by_part),agreement,active,neutral,alignment,high_tf,veto])
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; vote=x[10]
 if abs(ret)<neutral_bps/10000 or abs(vote)<.02:return None
 return int(ret*vote>0)
