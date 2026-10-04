# Tooltip requirements → data binding (D3)

Use this procedure when the prompt specifies **exact tooltip fields/labels** (or forbids tooltips for a subset of marks), and you must avoid silent drift between the spec and the final `tooltip.html(...)` template.

## Procedure

### 1) Build a binding table from the prompt
Create a small table mapping **prompt label → data source → code expression**.

Example (replace with your task’s fields):

| Prompt label | Data column/property | JS expression |
|---|---|---|
| Ticker | `ticker` | `d.ticker` |
| Name | `full name` | `d.fullName` |
| Sector | `sector` | `d.sector` |

### 2) Implement tooltip HTML using prompt labels
Keep the prompt’s labels literal in the template, even if the dataset uses different column names.

```js
function tooltipHtml(d) {
  const rows = [
    { label: 'Ticker', value: d.ticker },
    { label: 'Name', value: d.name ?? d.fullName },
    { label: 'Sector', value: d.sector },
  ];

  return rows
    .map(r => `<div><span class="k">${r.label}:</span> <span class="v">${r.value ?? ''}</span></div>`)
    .join('');
}
```

### 3) Gate tooltips for excluded marks (runtime branch)
If the prompt says “no tooltip for X”, implement an explicit guard in the hover handler.

```js
function shouldShowTooltip(d) {
  // Branch A: excluded → no tooltip
  if (d.isExcluded) return false;

  // Branch B: allowed → show tooltip
  return true;
}

marks
  .on('mousemove', (event, d) => {
    if (!shouldShowTooltip(d)) return;
    d3.select('#tooltip').classed('visible', true).html(tooltipHtml(d));
  })
  .on('mouseleave', () => {
    d3.select('#tooltip').classed('visible', false);
  });
```

### 4) Verification (static + runtime)

**Static check (must pass):** open/grep the final JS and confirm:
- every required **prompt label** appears in the *final* tooltip template (not in comments or dead code), and
- the tooltip handler calls that template.

**Runtime check (must pass):** load the chart and hover at least one allowed mark and one excluded mark.

#### If verification fails, do this next
- Missing label/value in HTML: update the binding table, then update `tooltipHtml` to render the missing label exactly as in the prompt.
- Wrong label (e.g., rendered “Full name” but prompt says “Name”): change the label string to match the prompt; keep the same underlying value.
- Exclusion guard not working: move the guard to the first line of the hover handler and ensure the predicate uses the prompt’s definition (not a heuristic).
