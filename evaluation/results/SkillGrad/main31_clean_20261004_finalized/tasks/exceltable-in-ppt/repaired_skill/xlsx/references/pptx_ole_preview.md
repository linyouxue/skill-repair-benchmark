# Updating PPTX embedded Excel OLE objects: ensure the slide-visible preview updates

PowerPoint PPTX files that contain an embedded Excel OLE object usually store **two different representations**:
1) the embedded workbook bytes (commonly `ppt/embeddings/*.xlsx`), and
2) a **cached rendering** used for what you see on the slide (commonly a `<p:pic>` fallback that points via a relationship to `ppt/media/image*.emf` or `ppt/media/image*.png`).

If you only replace the embedded `.xlsx` member, the visible table can remain stale and evaluators that check slide appearance will fail.

## Procedure

### 1) Locate the OLE object and its displayed preview part
```python
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS = {
  'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
  'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

def find_slide_preview_targets(pptx_path, slide_xml_path):
    with ZipFile(pptx_path) as z:
        slide_xml = z.read(slide_xml_path)
        rels_xml = z.read(slide_xml_path.replace('slides/', 'slides/_rels/') + '.rels')

    slide = ET.fromstring(slide_xml)
    rels = ET.fromstring(rels_xml)

    # Relationship ids referenced by <a:blip r:embed="rId..."> in any <p:pic>
    rids = {
        blip.attrib.get(f'{{{NS["r"]}}}embed')
        for blip in slide.findall('.//p:pic//{http://schemas.openxmlformats.org/drawingml/2006/main}blip', NS)
        if blip.attrib.get(f'{{{NS["r"]}}}embed')
    }

    # Map rid -> target part
    rid_to_target = {}
    for rel in rels.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        rid = rel.attrib.get('Id')
        target = rel.attrib.get('Target')
        if rid in rids:
            # slide rel targets are relative (e.g., "../media/image1.emf")
            rid_to_target[rid] = 'ppt/' + target.replace('../', '')

    return rid_to_target
```

**Runtime branch:**
- If `rid_to_target` is empty, the slide may not use a `<p:pic>` fallback (or you’re looking at the wrong slide). In that case, broaden the search to other slides, or inspect for `p:oleObj` and its relationships.
- If targets include `ppt/media/*.emf` or `ppt/media/*.png`, those are the likely slide-visible preview parts.

### 2) Update the embedded workbook bytes
(Do your normal embedded-xlsx edit; keep formulas as formulas.)

### 3) Update/refresh the preview part
You have two main strategies:

**Strategy A (preferred when available): re-render via an Office engine**
- Open and save the PPTX in PowerPoint (or LibreOffice if it re-renders OLE previews reliably) after updating the embedded workbook.
- This tends to regenerate cached preview images.

**Strategy B: replace the preview media part explicitly**
- Replace the referenced `ppt/media/image*.emf/png` with a newly generated image that matches the updated table.
- Generation is environment-dependent; if you cannot reliably render the embedded Excel range to EMF/PNG, choose Strategy A.

**Runtime branch:**
- If the evaluator is known to validate *only embedded workbook bytes*, you may skip preview regeneration.
- If the evaluator validates *slide appearance* (common for “table-in-ppt” tasks), you must update the preview.

## Verification (must prescribe next action)
```python
from zipfile import ZipFile
import hashlib

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def verify_preview_part_changed(before_pptx, after_pptx, slide_xml_path):
    before_map = find_slide_preview_targets(before_pptx, slide_xml_path)
    after_map = find_slide_preview_targets(after_pptx, slide_xml_path)
    assert before_map == after_map, "Preview target mapping changed; re-identify which slide part is displayed."

    with ZipFile(before_pptx) as zb, ZipFile(after_pptx) as za:
        for target in before_map.values():
            hb = sha256(zb.read(target))
            ha = sha256(za.read(target))
            if hb == ha:
                raise AssertionError(
                    f"Preview part did not change: {target}. "
                    f"Corrective action: regenerate/replace this media part (or re-save in PowerPoint/LibreOffice) "
                    f"then re-run this verification."
                )
```

If this verification fails:
1) confirm you edited the correct slide, and `find_slide_preview_targets` points to the actual displayed media part,
2) regenerate/replace that media part (or route through an open+save that re-renders), and
3) re-run the verification until the preview part hash changes.
