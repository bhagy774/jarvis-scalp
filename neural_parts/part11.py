"""Part 11 owned model: complete eight-frame, ten-Part directional fusion."""
import math
from .common import TIMEFRAMES, mtf_signal_matrix, std, clip
FEATURE_NAMES=tuple([f"part{i}_weighted_signal" for i in range(1,11)]+[f"{tf}_mean_signal" for tf in TIMEFRAMES]+["overall_vote","vote_dispersion","quorum_ratio","anchor_agreement","dissent_ratio","signal_entropy"])
MODEL_SPEC={"task":"eight_frame_evidence_fusion","dims":(24,24,12,3),"acts":("relu","tanh","linear"),"labels":("sell","neutral","buy"),"kind":"softmax"}
def prepare_features(evidence):
 matrix=mtf_signal_matrix(evidence); weights=(1.,1.05,1.10,1.20,1.25,1.35,1.40,1.45); den=sum(weights)
 by_part=[sum(matrix[t][p]*weights[t] for t in range(8))/den for p in range(10)]; by_tf=[sum(row)/10 for row in matrix]; flat=[v for row in matrix for v in row]; overall=sum(by_part)/10; dispersion=std(flat)
 quorum=sum(abs(v)>=.10 for v in flat)/80; direction=1 if overall>0 else -1 if overall<0 else 0; anchors=(by_part[5],by_part[7],by_part[8]); alignment=sum((1 if v>0 else -1 if v<0 else 0)*bool(direction) for v in anchors)/3
 dissent=sum(direction and v*direction<-.05 for v in flat)/80; counts=(sum(v<-.05 for v in flat),sum(abs(v)<=.05 for v in flat),sum(v>.05 for v in flat)); probs=[v/80 for v in counts]; entropy=-sum(p*math.log(max(p,1e-12)) for p in probs)/math.log(3)
 return tuple(clip(v) for v in by_part+by_tf+[overall,dispersion,quorum,alignment,dissent,entropy])
def interpret_scores(scores,prediction): return {"fusion_direction":{"sell":"SELL","neutral":"NEUTRAL","buy":"BUY"}.get(prediction,"NEUTRAL"),"evidence_matrix_bucket":prediction}
def label_target(rows,i,horizon,neutral_bps,x):
 ret=rows[i+horizon]["close"]/rows[i]["close"]-1; threshold=neutral_bps/10000
 return 2 if ret>threshold else 0 if ret< -threshold else 1
