"""Visual beats of each dance clip (Davis & Agrawala 'visual rhythm'): dense optical flow → directogram
(flow magnitude per direction, 16 bins) → visual impact = sum of decreases (sudden stops / direction changes).
Run with /usr/bin/python3 (has cv2). Output motion.json {clip: {fps, impact[], vy[], mag[]}}"""
import cv2, numpy as np, json, glob
out = {}
for f in sorted(glob.glob("0*_prime_*.mp4")):
    cap = cv2.VideoCapture(f); fps = cap.get(cv2.CAP_PROP_FPS); prev = None
    D, VY, MG = [], [], []
    while True:
        ok, fr = cap.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(fr, (180, 320)), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            fl -= np.median(fl.reshape(-1, 2), 0)  # remove camera pan
            mag, ang = cv2.cartToPolar(fl[..., 0], fl[..., 1])
            m = mag > np.percentile(mag, 70)       # moving body
            h = np.bincount((ang[m] / (2 * np.pi) * 16).astype(int) % 16, weights=mag[m], minlength=16)
            D.append(h / m.sum()); VY.append(float(fl[..., 1][m].mean())); MG.append(float(mag[m].mean()))
        prev = g
    D = np.array(D)
    imp = np.r_[0, np.clip(D[:-1] - D[1:], 0, None).sum(1)]
    out[f[:-4]] = {"fps": fps, "impact": imp.tolist(), "vy": VY, "mag": MG, "dir": D.round(4).tolist()}
    print(f, len(D), "frames")
json.dump(out, open("motion.json", "w"))
