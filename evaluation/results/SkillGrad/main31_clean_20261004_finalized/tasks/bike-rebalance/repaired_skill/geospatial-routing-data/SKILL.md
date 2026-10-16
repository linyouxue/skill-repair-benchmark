---
name: geospatial-routing-data
description: Handle depot/station coordinates, ID↔index mappings, distance matrices, and route-distance reconstruction for routing outputs that use latitude/longitude.
---

# Geospatial Routing Data

Use this skill before building a routing model or validating a routing report that contains coordinates, depots, station IDs, and route sequences.

The main risk is mixing user-facing IDs with internal array indices or using a different distance metric from the task.

## Parse Data Safely

Load structured data with a parser and build explicit mappings between external IDs and internal indices.

```python
station_ids = [int(rec["id"]) for rec in station_records]
if len(station_ids) != len(set(station_ids)):
    raise ValueError("duplicate station ids")

id_to_idx = {sid: idx for idx, sid in enumerate(station_ids)}
idx_to_id = {idx: sid for sid, idx in id_to_idx.items()}
```

Decision rule: use internal indices in optimization variables; convert back to original IDs only when producing the final report.

## Coordinate Validation

Validate coordinate ranges before building distances.

```python
def parse_location(record):
    lat = float(record["latitude"])
    lon = float(record["longitude"])
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("latitude out of range")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("longitude out of range")
    return {"latitude": lat, "longitude": lon}
```

## Great-Circle Distance

Match the task’s declared distance metric and constants; if the statement provides an Earth radius, use that exact value.

```python
import math

def great_circle(a, b, radius):
    deg_to_rad = math.pi / 180.0
    lat1, lon1 = float(a["latitude"]), float(a["longitude"])
    lat2, lon2 = float(b["latitude"]), float(b["longitude"])

    phi1 = (90.0 - lat1) * deg_to_rad
    phi2 = (90.0 - lat2) * deg_to_rad
    theta1 = lon1 * deg_to_rad
    theta2 = lon2 * deg_to_rad

    cos_arc = (
        math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2)
        + math.cos(phi1) * math.cos(phi2)
    )
    cos_arc = max(-1.0, min(1.0, cos_arc))
    return math.acos(cos_arc) * float(radius)
```

Decision rule: never mix Euclidean distance on degrees, a different radius/unit system, or rounded distances inside the objective.

## Route Distance Reconstruction

Recompute reported travel distance from route sequences using the same arc set and distance function.

```python
def pairwise(items):
    return zip(items, items[1:])

def route_distance(route_nodes, dist):
    return sum(dist[i, j] for i, j in pairwise(route_nodes))
```

Read references/sandbox-path-and-tooling-awareness.md when you can locate the input path but cannot read it due to tool sandbox restrictions or malformed shell commands. Skip when input reading is already working and reproducible.

## Common Pitfalls

- Treating external IDs as contiguous indices, causing mis-addressed distances, constraints, or reports.
- Using the wrong distance metric/units/constant (e.g., wrong Earth radius) or copying distances instead of reconstructing from coordinates.
- Computing route distance from a different arc set than the solver used (missing depot arcs or allowing forbidden arcs).
