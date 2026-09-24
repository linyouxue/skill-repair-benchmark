---
name: egomotion-estimation
description: "Estimate camera motion with optical flow + affine/homography, allow multi-label per frame."
---

# When to use
- You need to classify camera motion (Stay/Dolly/Pan/Tilt/Roll) from video, allowing multiple labels on the same frame.
# Workflow
1) **Feature tracking**: `goodFeaturesToTrack` on `prev_gray` + `calcOpticalFlowPyrLK(prev→curr)`; drop tracks with status=0 or too few remaining.
2) **Robust transform**: `estimateAffinePartial2D(prev_pts, curr_pts, method=RANSAC)` — this returns M mapping *prev→curr*, so `(dx,dy)=M[:,2]` is how features shifted in the image from prev to curr.
3) **Sign convention (map to CAMERA motion, not image motion)**:
   - Features moving RIGHT in image (`dx>0`) ⇒ camera panned LEFT ⇒ label `"Pan Left"`.
   - Features moving LEFT (`dx<0`) ⇒ `"Pan Right"`.
   - Features moving DOWN (`dy>0`) ⇒ camera tilted UP ⇒ `"Tilt Up"`.
   - Features moving UP (`dy<0`) ⇒ `"Tilt Down"`.
   - `scale>1` (features spread outward) ⇒ `"Dolly In"`; `scale<1` ⇒ `"Dolly Out"`.
   - `rotation>0` (CCW in image) ⇒ `"Roll Right"` for a hand-held camera rolling clockwise about its optical axis (verify on the specific transform direction you used; flip if needed).
   Confirm the mapping by sanity-checking one frame with an obvious motion cue in the video (e.g. horizon shift) before finalizing.
4) **Thresholding**: `th_trans` in px/frame (scale with resolution and fps step), `th_rot` in radians, `th_scale` as relative deviation from 1.
5) **Multi-label**: independently test each axis; do NOT gate one axis on another (esp. do not require `|dx|>=|dy|` for Pan — that suppresses legitimate Tilt+Pan combos). Emit both if both exceed threshold.
6) **Outlier / transition preservation**: after per-frame labels, run mild temporal smoothing (window mode); do NOT collapse away isolated frames whose translation clearly exceeds threshold (e.g. `|dy|>th_trans`) — they should surface as a distinct interval.
7) **Interval compression**: merge consecutive frames with identical label *sets* (order-insensitive) into `"start->end"` half-open ranges.
8) **Fallback**: if the transform estimate fails, use identity → `"Stay"`; never emit an empty label list.
# Decision sketch
```python
labels=[]
for i in range(1, len(sample_ids)):
    M, _ = cv2.estimateAffinePartial2D(prev_pts, curr_pts, method=cv2.RANSAC)
    if M is None: labels.append(["Stay"]); continue
    dx, dy = M[0,2], M[1,2]
    a, b = M[0,0], M[1,0]
    scale = math.hypot(a,b); rot = math.atan2(b,a)
    lbl=[]
    if abs(scale-1)>th_scale: lbl.append("Dolly In" if scale>1 else "Dolly Out")
    if abs(rot)>th_rot:       lbl.append("Roll Right" if rot>0 else "Roll Left")
    if abs(dx)>th_trans:      lbl.append("Pan Left"  if dx>0 else "Pan Right")
    if abs(dy)>th_trans:      lbl.append("Tilt Up"   if dy>0 else "Tilt Down")
    if not lbl: lbl.append("Stay")
    labels.append(lbl)
```
# Self-check
- [ ] Fallback to identity transform on failure; never emit empty labels.
- [ ] Sign convention explicitly matches CAMERA motion (image-right feature shift ⇒ Pan Left, etc.), and was sanity-checked against one obvious cue in the clip.
- [ ] Pan and Tilt tested independently — no `|dx|>=|dy|` gating.
- [ ] Frames whose translation crosses threshold are not silently merged away.
- [ ] Compressed intervals cover all sampled frames as a half-open partition of `[0, n_samples)`.
