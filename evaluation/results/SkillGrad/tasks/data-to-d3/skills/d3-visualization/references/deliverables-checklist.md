# Deliverables checklist (required-path tasks)

Use this when the task specifies an explicit output inventory (often under `/root/output/`). Your goal is to **materialize every required file** and then **prove it exists** before you stop.

## Procedure

### 1) Enumerate required paths
Create a list of exact required file paths (HTML/CSS/JS/data/vendor). Treat these as authoritative.

### 2) Create parent directories
Create every parent directory needed for the required files.

```python
from pathlib import Path

required_files = [
    Path("/root/output/index.html"),
    Path("/root/output/js/visualization.js"),
    Path("/root/output/css/style.css"),
]

for p in required_files:
    p.parent.mkdir(parents=True, exist_ok=True)
```

### 3) Copy data assets (branch on whether data is required)
If the visualization loads local data, copy the input data files into the required output data folder (preserving any subfolders).

```python
import shutil
from pathlib import Path

src = Path("/path/to/input_data")
dst = Path("/root/output/data")

if src.exists():
    dst.mkdir(parents=True, exist_ok=True)
    # Branch A: directory copy (preserve tree)
    if src.is_dir():
        shutil.copytree(src, dst / src.name, dirs_exist_ok=True)
    # Branch B: single file copy
    else:
        shutil.copy2(src, dst / src.name)
```

### 4) Write minimal scaffolding early
Write a minimal `index.html` that links your CSS/JS and contains the mount node for the SVG.

```python
from pathlib import Path

index_path = Path("/root/output/index.html")
html = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <link rel=\"stylesheet\" href=\"css/style.css\" />
</head>
<body>
  <div id=\"chart\"></div>
  <script src=\"js/d3.min.js\"></script>
  <script src=\"js/visualization.js\"></script>
</body>
</html>"""
index_path.write_text(html, encoding="utf-8", newline="\n")
```

### 5) Verification (must prescribe next action)
Verify every required file exists and is non-empty.

```python
from pathlib import Path

required_files = [
    Path("/root/output/index.html"),
    Path("/root/output/js/visualization.js"),
    Path("/root/output/css/style.css"),
]

missing = [str(p) for p in required_files if not p.exists()]
empty = [str(p) for p in required_files if p.exists() and p.stat().st_size == 0]

if missing or empty:
    raise RuntimeError(
        "Deliverables check failed. "
        f"missing={missing} empty={empty}. "
        "Next action: create/copy/write these files, then re-run this check."
    )
```

If the check fails: **do not proceed to chart refinement**. First create the missing directories/files or copy the missing data assets, then re-run the verification.
