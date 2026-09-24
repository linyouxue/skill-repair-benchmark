---
name: obspy-datacenter-client
description: Use ObsPy FDSN/other clients to retrieve waveforms and metadata from
  data centers when the task requires downloading external data (not needed for local
  NPZ batch picking unless explicitly asked).
---

## Steps
1. If external waveforms are needed, use `obspy.clients.fdsn.Client(...)` and request waveforms/station/event metadata via FDSN web services.
2. Prefer FDSN interfaces unless a legacy service is specifically required (e.g., special IRIS endpoints).
3. Save downloaded waveforms to standard formats (e.g., MiniSEED) and load with `obspy.read()` for consistent processing.
## Expected Result
Waveforms and metadata are retrieved in standard ObsPy objects suitable for filtering, modeling, and pick export.
