# SKILL.md

## When to use
Use this skill when you must build a **standalone single-page D3.js (v6) web app** that:
- Loads **local CSV datasets** (copied into the app’s output tree) and visualizes them in **two coordinated views** arranged side-by-side (e.g., a force-directed bubble chart plus a table).
- Implements **semantic encodings** (size, color, grouping/clustering) and **interactive linking** (clicking in one view highlights the corresponding item in the other).
- Requires a specific **output file/folder layout** (HTML + separate JS/CSS + vendored D3 + copied data) that must work when opened in a browser.

Before acting, gather evidence from the target context and data files:
- Inspect the CSV headers and confirm the identifier field(s) used to join/label rows (e.g., ticker-like key, sector/category, display name, numeric measure).
- Identify which records have missing fields and which UI behaviors must differ for them (e.g., special handling for “ETF”-like rows).
- Confirm whether the app must run via `file://` open (no server) and plan around browser restrictions accordingly (see failure modes).

## Possible Failure Modes
- **Local file loading breaks**: Using `d3.csv("...")` from `file://` may fail due to CORS in many browsers, causing empty charts/tables.
- **Wrong data paths / not copying inputs**: The app references source locations instead of the required `/output/data/` copy, or uses incorrect relative paths.
- **Force simulation scatter**: Sector/category clusters drift far apart or off-canvas because centering forces are missing/weak or forces are unbalanced.
- **Overlapping bubbles**: `forceCollide` radius not aligned with rendered circle radius, or padding too small.
- **Incorrect size scale**: Market-cap sizing is not normalized, uses raw values without scale, or fails on missing/NaN values; special-case sizing not applied uniformly where required.
- **Color legend mismatch**: Legend labels/colors don’t match the actual color scale domain, or domain changes after data load without updating legend.
- **Tooltip rule violations**: Tooltip shows for rows that should not have it, or displays missing fields as `undefined`/`NaN`.
- **Linking not symmetric**: Clicking a bubble highlights table but clicking a table row does not highlight bubble (or vice versa), or highlight state can’t be cleared/updated.
- **Ambiguous mapping key**: Using company name instead of a unique key causes collisions and incorrect highlighting.
- **Table formatting issues**: Market cap not human-formatted, inconsistent units, or sort/row order not stable.
- **SVG/text readability**: Ticker labels overflow bubbles or become unreadable; no truncation, scaling, or contrast handling.

## Possible procedures
1. **Set up the required output structure**
   - Create the HTML that references **one CSS** and **one JS** file, plus a local copy of **D3 v6**.
   - Copy input datasets into the app’s required data folder and ensure the app references them via **relative paths** from `index.html`.

2. **Load and normalize data**
   - Load the main “stock description”-type CSV and any per-item history files only if needed for the required visuals.
   - Parse numeric fields with `+value` or `parseFloat`, guarding against empty strings.
   - Define a single unique key per entity (e.g., ticker-like id) and use it consistently for:
     - Bubble datum binding
     - Table row binding
     - Cross-highlighting selection state

3. **Design scales and derived fields**
   - **Radius scale**: Use a continuous scale (`scaleSqrt` is common) for numeric magnitude; compute domain from valid numeric values only.
   - **Uniform radius override**: For special categories without magnitude, assign a fixed radius and ensure collide force uses the same computed radius.
   - **Color scale**: Use an ordinal scale keyed by sector/category; extract domain from data, then build a legend from that domain.

4. **Build the bubble chart with a stable force layout**
   - Create an SVG with margins and a clear chart area.
   - Add forces:
     - `forceX` / `forceY` to cluster items by category (e.g., map each sector to a target centroid).
     - A centering force (`forceCenter` or appropriately weighted X/Y forces) to keep the overall system centered and “reasonably close together.”
     - `forceCollide` based on radius + padding to prevent overlap.
   - Run the simulation and on each tick update circle and label positions.
   - Add text labels centered on bubbles; implement readability tactics (font sizing by radius, truncation, or conditional display) as needed.

5. **Add tooltips with conditional logic**
   - Implement a tooltip div positioned on mouse events.
   - On hover:
     - If required fields are missing for an item class, **skip tooltip entirely** for those items.
     - Otherwise, show exactly the allowed fields (avoid showing missing/unsupported fields).
   - Ensure mouseout reliably hides the tooltip.

6. **Create the table view**
   - Render a table listing all entities with the required columns.
   - Format large numbers into compact human-readable strings (K/M/B/T style) with consistent rounding.
   - Bind rows to the same unique key used in the bubble chart.

7. **Implement coordinated selection (bubble ↔ table)**
   - Choose a selection model (single selection is simplest):
     - On bubble click: store selected key; apply a CSS class to the matching row and bubble; remove it from others.
     - On row click: same, but triggered from table.
   - Add a clear “active” style in CSS for both bubble and row (stroke/outline for bubbles; background for rows).
   - Include a recovery interaction if helpful (e.g., clicking empty space clears selection), if not prohibited by the task contract.

8. **Resilience and recovery checks**
   - If data loading fails, display a small on-page error message (in DOM) rather than silently failing.
   - Validate that:
     - The number of rendered rows equals the number of entities expected from the dataset.
     - The legend count matches the number of unique categories.

## Verification Checklist
- [ ] Output files exist at the required paths: `index.html`, `js/visualization.js`, `css/style.css`, local `js/d3.v6.min.js`, and a `data/` folder containing copies of the input data.
- [ ] `index.html` loads **only local relative resources** (no missing references); opening in a browser displays both views side-by-side.
- [ ] Bubble chart requirements met:
  - [ ] Bubble size encodes magnitude where available; special-category items use a uniform size.
  - [ ] Colors map to sector/category; legend labels match color assignments.
  - [ ] Force layout produces visible clusters by category and stays centered (no extreme scatter/off-screen).
  - [ ] No bubble overlap (collide radius matches rendered radius).
  - [ ] Each bubble has an internal label (ticker-like id) readable enough to verify.
  - [ ] Tooltip shows correct fields on hover and **does not show** for items that must not display it.
- [ ] Table requirements met:
  - [ ] Contains all entities and required columns.
  - [ ] Magnitude column is human-formatted (e.g., compact suffixes) and not raw/unreadable.
- [ ] Linking works both directions:
  - [ ] Clicking a bubble highlights the corresponding table row.
  - [ ] Clicking a table row highlights the corresponding bubble.
  - [ ] Only the intended item is highlighted; highlight updates correctly on subsequent clicks.
- [ ] No unintended leakage from retrieved examples:
  - [ ] No copied identifiers, filenames, column names, or numeric constants taken from other tasks unless derived from the current task’s data/context.
- [ ] Unrelated state preserved:
  - [ ] No modification of input files in place; only copies are used under the output directory.
- [ ] Recovery check:
  - [ ] If data cannot be loaded (path/CORS), the page surfaces a visible error message or fallback indicator rather than a blank UI.
