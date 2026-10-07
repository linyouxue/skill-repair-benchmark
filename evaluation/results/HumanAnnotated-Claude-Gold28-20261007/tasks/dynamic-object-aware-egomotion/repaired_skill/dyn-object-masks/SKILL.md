---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Workflow
For a pair from sampled frame i to i+1, save its source-frame mask as f_i. Use forward evidence for f_0; advance the last confidence once with the last pair flow for the final sampled frame. Keep exactly N masks for N samples.

1) **Camera-motion compensation**: compute dense optical flow and fit a separate robust homography from spatially distributed matches for the mask branch. Check finite/non-degenerate geometry and inlier support; use affine or median-flow fallback only if that fit fails. The motion-label classifier may use a different transform. For an additional background plane, first identify rigid background support in the source pair, fit that support separately, and apply its compensation to that region. Treat residual outliers as unclassified candidates until this review; taking the minimum residual across arbitrary planes over the whole image can absorb independent motion.
2) **Valid region**: retain source pixels whose projected coordinates remain in the next frame and suppress a resolution-scaled outer margin.
3) **Residual-flow threshold**: subtract projected background displacement from dense flow. Threshold its magnitude using the valid-region distribution and a small flow floor; photometric difference is supporting evidence.
4) **Morphology + area filter**: open then close; keep connected components above a minimum area (tune as fraction of image area or a fixed pixel threshold).
5) **Temporal confidence**: use the numerical update below after per-frame component filtering. Keep the confidence and pair flow between samples; the incoming state for f_i uses flow from i-1 to i. A zero-current-evidence translation check should move and gradually decay the prior.
6) **CSR encoding**: for final bool mask  
   - `rows, cols = nonzero(mask)`  
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`  
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`  
   - store as `f_{i}_data/indices/indptr`

# Code sketch
```python
flow = cv2.calcOpticalFlowFarneback(prev_gray, curr_gray, None,
    0.5, 3, 15, 3, 5, 1.2, 0)
# H_mat is the validated source-to-next homography fitted for this mask pair.
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
src = np.stack([xx, yy], axis=-1)
dst = cv2.perspectiveTransform(src.reshape(-1, 1, 2), H_mat).reshape(H, W, 2)
expected = dst - src
valid = (dst[..., 0] >= 0) & (dst[..., 0] < W) & (dst[..., 1] >= 0) & (dst[..., 1] < H)
# interior excludes the resolution-scaled outer margin.
valid &= interior
residual = np.linalg.norm(flow - expected, axis=-1)
thr = max(flow_floor, residual[valid].std() * residual_sigma)
raw = (residual > thr) & valid

m = cv2.morphologyEx(raw.astype(np.uint8)*255, cv2.MORPH_OPEN, k3)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k7)
n, cc, stats, _ = cv2.connectedComponentsWithStats((m>0).astype(np.uint8), connectivity=8)
mask = np.zeros_like(raw, dtype=bool)
for cid in range(1,n):
    if stats[cid, cv2.CC_STAT_AREA] >= min_area:
        mask |= (cc==cid)

def forward_confidence(state, pair_flow):
    h, w = state.shape
    y, x = np.indices(state.shape)
    dest = np.rint(np.dstack((x, y)) + pair_flow)
    inside = np.isfinite(dest).all(axis=-1) & (dest[...,0] >= 0) & (dest[...,0] < w) & (dest[...,1] >= 0) & (dest[...,1] < h)
    q = dest[inside].astype(np.int32)
    out = np.zeros_like(state, dtype=np.float32)
    np.maximum.at(out, (q[:,1], q[:,0]), state[inside])
    return out

# Initialize previous_confidence=None before the loop; decay/decision_level
# are tunable confidence parameters (for example 0.7/0.3).
confidence = mask.astype(np.float32)
if previous_confidence is not None:
    confidence = np.maximum(confidence,
        decay * forward_confidence(previous_confidence, previous_pair_flow))
mask = (confidence >= decision_level) & valid
previous_confidence = confidence * valid
previous_pair_flow = flow
```

# Self-check
- [ ] Reopen saved masks and inspect source overlays for object interiors, static parallax, repeated empty masks and occupancy spikes. Under camera translation, a single background model can fail across depths: re-estimate it, then use local background support or source-guided contour refinement where needed. Judge displacement/deformation from source pairs rather than object category or stable attachment.
- [ ] Masks only for sampled frames; keys match sampled indices.
- [ ] `shape` stored as `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`.
- [ ] Border fill not treated as foreground; threshold stats computed on valid region only.
- [ ] Threshold + morphology + area filter applied. 
