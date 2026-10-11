---
name: dyn-object-masks
description: "Generate dynamic-object binary masks after global motion compensation, output CSR sparse format."
---

# When to use
- Detect moving objects in scenes with camera motion; produce sparse masks aligned to sampled frames.

# Frame-to-mask assignment contract
- For sampled frames `frames[0:N]`, compute forward motion evidence from `frames[i]` to `frames[i+1]` and store the resulting source-frame mask as `f_i`.
- Produce exactly one mask for every sampled frame. For `f_{N-1}`, propagate or copy the last valid mask estimate, or compute an aligned backward estimate when appropriate.
- Do not make `f_0` empty merely because there is no preceding frame. It has valid forward evidence from `frames[0]` to `frames[1]`.
- Keep this assignment consistent through temporal filtering and CSR serialization; do not shift pairwise evidence by one index.

# Workflow
1) **Dense observed motion**: compute dense optical flow from each sampled frame to the next (for example, Farneback). Pairwise intensity difference may be used as supporting evidence, but not as the primary detector when the camera moves.
2) **Dedicated projective global-motion model**: for mask compensation, estimate a homography from `frames[i]` to `frames[i+1]` using spatially distributed correspondences and robust outlier rejection, then convert it into expected background flow at every valid pixel. Do not reuse a partial affine transform selected for motion-label classification as the default mask model: affine or spatial-median flow is only a documented fallback after the homography fails finite, non-degeneracy, inlier-support, or valid-warp checks. The motion classifier and mask compensator may deliberately use different transforms.
3) **Residual-flow evidence**: subtract the expected global flow from the observed dense flow and threshold the residual magnitude. Use a distribution-aware threshold with a small flow floor so interpolation, compression, and low-amplitude noise are not promoted to foreground.
4) **Valid region and edge suppression**: exclude pixels whose transformed coordinates fall outside the image and suppress a resolution-scaled outer margin where warping artifacts dominate.
5) **Morphology + area filter**: open then close; keep connected components above a minimum area scaled to image size. If filtering removes every component even though coherent residual evidence remains, retain the unfiltered coherent mask rather than returning an unconditional empty mask.
6) **Temporal propagation**: maintain a confidence map, move it from its source-frame coordinates into the current-frame coordinates, decay it, and fuse it numerically with current residual evidence before thresholding. Do not replace this with a sequence-level IoU gate followed by a one-off boolean OR: that discards useful history precisely when a mask is sparse or displaced.
7) **CSR encoding**: for each final bool mask
   - `rows, cols = nonzero(mask)`
   - `indices = cols.astype(int32)`; `data = ones(nnz, uint8)`
   - `counts = bincount(rows, minlength=H)`; `indptr = cumsum(counts, prepend=0)`
   - store as `f_{i}_data/indices/indptr`

# Robust residual-flow sketch
```python
flow = cv2.calcOpticalFlowFarneback(
    prev_gray, curr_gray, None,
    pyr_scale=0.5, levels=3, winsize=15,
    iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
)

# Estimate a dedicated projective transform for the mask branch, for example:
# H_mat, inliers = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, reproj_px)
# Validate that H_mat is finite/non-degenerate and has adequate distributed
# inlier support. Fall back only when those checks fail.
if H_mat is not None:
    yy, xx = np.mgrid[0:H_img, 0:W_img].astype(np.float32)
    points = np.stack([xx, yy, np.ones_like(xx)], axis=-1)
    warped = points.reshape(-1, 3) @ H_mat.T
    warped = warped.reshape(H_img, W_img, 3)
    expected_x = warped[..., 0] / (warped[..., 2] + 1e-8) - xx
    expected_y = warped[..., 1] / (warped[..., 2] + 1e-8) - yy
else:
    expected_x = np.full((H_img, W_img), np.median(flow[..., 0]))
    expected_y = np.full((H_img, W_img), np.median(flow[..., 1]))

residual = np.hypot(flow[..., 0] - expected_x, flow[..., 1] - expected_y)
threshold = max(flow_floor, residual[valid].std() * residual_sigma)
raw = (residual > threshold) & valid & interior_mask

m = cv2.morphologyEx(raw.astype(np.uint8), cv2.MORPH_OPEN, kernel)
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
mask = filter_connected_components(m, min_area_fraction)

class TemporalTracker:
    def __init__(self, decay=0.7, decision_level=0.3):
        self.confidence = None
        self.decay = decay
        self.decision_level = decision_level

    def update(self, current_mask, flow_prev_to_current=None):
        current = current_mask.astype(np.float32)
        if self.confidence is None:
            self.confidence = current
        else:
            propagated = warp_forward_confidence(
                self.confidence, flow_prev_to_current,
                border_value=0,
            )
            propagated *= self.decay
            self.confidence = np.maximum(current, propagated)
        refined = self.confidence >= self.decision_level
        return cv2.morphologyEx(
            refined.astype(np.uint8), cv2.MORPH_CLOSE,
            np.ones((3, 3), np.uint8),
        ).astype(bool)

# pair_flow[i] and raw_mask[i] are evidence for source sampled frame i.
# When updating f_i for i>0, propagate prior state with pair_flow[i-1], which
# maps sampled frame i-1 into sampled frame i. For the final sampled frame,
# propagate once with the last available pair flow and no new forward evidence.
```

# Observable quality gate without ground truth
- Record, for every sampled frame, raw/postprocessed/tracked foreground ratios, connected-component count, residual-flow quantiles, and whether the projective model passed its support checks.
- Flag repeated empty or near-empty postprocessed masks when coherent raw residual components persist; also flag an isolated occupancy spike that is an extreme outlier relative to the positive-occupancy sequence, or repeated zero/nonzero toggling while motion statistics remain smooth.
- If a flag fires, re-check homography support, flow direction, expected-flow construction, threshold scale, edge validity, morphology, and component filtering, then re-estimate or use the documented fallback before serialization. Do not fabricate foreground merely to satisfy this check.

# Self-check
- [ ] `f_i` uses evidence assigned to sampled frame `i`; pairwise results are not shifted by one frame.
- [ ] There is one mask per sampled frame, including evidence-based handling of the first frame and propagation/aligned handling of the final frame.
- [ ] Dynamic evidence is residual motion after removing global camera motion, not raw photometric difference alone.
- [ ] The mask branch uses a dedicated projective homography when perspective/scale motion is present; any fallback is deliberate and documented.
- [ ] Masks only cover valid/interior pixels; edge warping artifacts are suppressed.
- [ ] Temporal propagation uses correctly aligned, decaying confidence rather than an IoU-gated boolean OR.
- [ ] Foreground ratios and frame-to-frame changes are inspected for systematic over-segmentation, repeated empty/tiny-mask collapse, isolated spikes, and excessive flicker; detected collapse triggers re-estimation before submission.
- [ ] `shape` is `[H, W]` int32; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices remain in `[0, W)`.
