---
name: openai-vision
description: Analyze images and multi-frame sequences using OpenAI GPT vision models
---

(unchanged — see original skill content)
## Steps
1. Encode local images to base64 with correct media type, or pass URLs directly.
2. Call `client.chat.completions.create` with `model="gpt-4o"` and a `content` array mixing `text` and `image_url` parts.
3. Choose `detail`: `high` for OCR / small objects, `low` for scene classification, `auto` otherwise.
4. For structured output, instruct the model to return only JSON and parse it, stripping code fences.
5. Handle rate limits with exponential backoff; resize images over ~15MB before sending.
## Expected Result
A parsed analysis (string or JSON) plus token-usage metadata for each processed image.
