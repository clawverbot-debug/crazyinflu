"""Body keypoints per frame (YOLO11 pose) for each dance clip → pose.json {clip: {fps, kp: [[17x(x,y,conf)] of the biggest person]}}.
Run with the posevenv python."""
import json, glob, sys, os, cv2, numpy as np
from ultralytics import YOLO
m = YOLO("yolo11m-pose.pt")
out = {}
FILES = sys.argv[1:] or sorted(glob.glob("0*_prime_*.mp4"))
if os.path.exists("pose.json") and sys.argv[1:]: out = json.load(open("pose.json"))
for f in FILES:
    cap = cv2.VideoCapture(f); fps = cap.get(cv2.CAP_PROP_FPS); K = []
    while True:
        ok, fr = cap.read()
        if not ok: break
        r = m.predict(fr, imgsz=640, verbose=False)[0]
        if r.keypoints is None or len(r.boxes) == 0: K.append(None); continue
        b = r.boxes.xyxy.cpu().numpy(); area = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
        conf = r.keypoints.conf.cpu().numpy(); full = conf[:, [11, 12, 15, 16]].mean(1)   # hips + ankles visible = the dancer, not a crowd head
        i = int((area * (0.2 + full)).argmax())
        kp = np.concatenate([r.keypoints.xy[i].cpu().numpy(), r.keypoints.conf[i].cpu().numpy()[:, None]], 1)
        K.append(kp.round(2).tolist())
    out[f[:-4]] = {"fps": fps, "kp": K}
    print(f, len(K), "frames,", sum(k is None for k in K), "without person", flush=True)
json.dump(out, open("pose.json", "w"))
