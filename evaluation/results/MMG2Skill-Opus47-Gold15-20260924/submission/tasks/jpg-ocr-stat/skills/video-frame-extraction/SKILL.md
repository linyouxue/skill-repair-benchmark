---
name: video-frame-extraction
description: Extract frames from video files and save them as images using OpenCV
---

## Steps
1. Open the video with `cv2.VideoCapture` and verify `cap.isOpened()`.
2. Read metadata (`CAP_PROP_FRAME_COUNT`, `CAP_PROP_FPS`, resolution).
3. Iterate frames with `cap.read()`, saving every N-th frame (interval) or by seconds via `int(fps*seconds)`.
4. Save with `cv2.imwrite` using zero-padded filenames like `frame_000001.jpg`.
5. Release the capture and return a JSON summary of counts and metadata.
## Expected Result
An output directory populated with extracted frame images plus a JSON summary.
