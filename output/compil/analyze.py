import json, numpy as np, librosa, sys
F = json.load(open("flow.json"))
def flow_tempi(vy, fps):
    x = np.asarray(vy, float); x = x - np.convolve(x, np.ones(int(fps))/int(fps), "same")  # remove drift
    x = (x - x.mean())/(x.std()+1e-9); n=len(x)
    ac = np.correlate(x, x, "full")[n-1:]/np.arange(n,0,-1)
    out=[]
    for bpm in np.arange(55,180,0.5):
        lag = 60/bpm*fps; i=int(lag); f=lag-i
        if i+1>=n//2: continue
        out.append((ac[i]*(1-f)+ac[i+1]*f, bpm))
    out.sort(reverse=True); return out
def audio_tempi(wav):
    y, sr = librosa.load(wav, sr=22050)
    oe = librosa.onset.onset_strength(y=y, sr=sr)
    tg = librosa.feature.tempogram(onset_envelope=oe, sr=sr).mean(1)
    bpms = librosa.tempo_frequencies(len(tg), sr=sr)
    idx = [i for i in range(1,len(tg)) if 55<=bpms[i]<=180]
    return sorted([(tg[i], bpms[i]) for i in idx], reverse=True)
def peaks(lst, k=3):
    res=[]
    for s,b in lst:
        if all(abs(b-r)>4 for _,r in res): res.append((round(float(s),2), round(float(b),1)))
        if len(res)==k: break
    return res
for name in sorted(F):
    d=F[name]; base=name[:-4]
    print(base, "dur %.1f"%(len(d["vy"])/d["fps"]), "flow", peaks(flow_tempi(d["vy"], d["fps"])), "audio", peaks(audio_tempi(base+".wav")))
