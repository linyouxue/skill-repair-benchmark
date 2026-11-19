/* global d3 */

'use strict';

/*
  Single-page app TEMPLATE.

  This file is intentionally data-agnostic:
  - You must load/parse your dataset (CSV/JSON) and map fields.
  - Prefer deterministic ordering: sort by (sector, ticker) before rendering.

  Offline note:
  - If you use fetch('data/...'), the page likely needs to be served (not file://).
  - For "double-click to open" requirements, embed data directly and use d3.csvParse.

  The helpers below mirror the reusable snippets in this skill bundle:
  - scripts/bubble_chart_example.js
  - scripts/interactive_table_example.js

  You can either copy those functions into this file (common for single-file builds)
  or keep them separate and load them before this script.
*/

// --- Minimal selection state (chart ↔ table) ---
let _selectedId = null;
let _chartApi = null;
let _tableApi = null;

function setSelected(id) {
  _selectedId = id;
  if (_chartApi) _chartApi.highlightBubble(id);
  if (_tableApi) _tableApi.highlightTableRow(id);
}

// Expose global hooks so the chart/table helpers can link by default.
// (If you prefer module patterns, remove this and pass explicit onSelect callbacks.)
globalThis.highlightBubble = function (id) {
  if (_chartApi) _chartApi.highlightBubble(id);
};

globalThis.highlightTableRow = function (id) {
  if (_tableApi) _tableApi.highlightTableRow(id);
};

// --- Render entrypoint ---

function initApp(rows) {
  // EXPECTED SHAPE (example):
  // rows: [{ ticker, sector, fullName, marketCap, ... }]

  const data = (Array.isArray(rows) ? rows : []).slice();

  // Deterministic ordering helps ensure stable color mapping and force layout.
  data.sort((a, b) => d3.ascending(a.sector ?? '', b.sector ?? '') || d3.ascending(a.ticker ?? '', b.ticker ?? ''));

  // Build chart.
  _chartApi = createClusteredBubbleChart({
    svgSelector: '#bubbleSvg',
    legendSelector: '#legend',
    tooltipSelector: '#tooltip',
    width: document.getElementById('bubbleSvg')?.clientWidth || 620,
    height: 500,
    data,
    idAccessor: (d) => d.ticker,
    labelAccessor: (d) => d.ticker,
    groupAccessor: (d) => d.sector,
    valueAccessor: (d) => (d.marketCap == null || d.marketCap === '' ? null : +d.marketCap),
    nameAccessor: (d) => d.fullName,
    // Example conditional tooltip: return false for rows with missing marketCap.
    shouldShowTooltip: (d) => d.marketCap != null && d.marketCap !== '' && Number.isFinite(+d.marketCap),
    onSelect: (id) => setSelected(id),
  });

  // Build table.
  _tableApi = createInteractiveTable({
    containerSelector: '#tableWrap',
    tableSelector: '#dataTable',
    idAccessor: (d) => d.ticker,
    enableSort: false,
    columns: [
      { key: 'ticker', label: 'Ticker symbol', align: 'left', format: (v) => String(v ?? '') },
      { key: 'fullName', label: 'Full company name', align: 'left', format: (v) => String(v ?? '') },
      { key: 'sector', label: 'Sector', align: 'left', format: (v) => String(v ?? '') },
      { key: 'marketCap', label: 'Market cap', align: 'right', format: (v) => formatAbbrevNumber(v) },
    ],
    onSelect: (id) => setSelected(id),
  });

  _tableApi.render(data);

  // Optional: restore selection.
  if (_selectedId != null) setSelected(_selectedId);
}

// --- Data loading stub ---

async function loadData() {
  // Replace this with your data source.
  // Example for served environments:
  // const rows = await d3.csv('data/stock-descriptions.csv');
  // rows.forEach(d => { d.marketCap = d.marketCap === '' ? null : +d.marketCap; });
  // return rows;

  return [];
}

// Boot.
loadData()
  .then((rows) => {
    initApp(rows);
  })
  .catch((err) => {
    console.error('Failed to load data:', err);
  });

/*
  ------------------------------------------------------------
  Helper implementations (copied from skill scripts)
  ------------------------------------------------------------

  This template expects these functions to exist:
  - createClusteredBubbleChart
  - createInteractiveTable
  - formatAbbrevNumber

  For convenience, you can paste the implementations below.
  Keeping them in one file makes "single-page app" packaging simpler.
*/

// ---- BEGIN: Paste bubble + table helpers here when needed ----

// Placeholder no-op implementations so this template does not crash
// if opened before helpers are pasted in.
function createClusteredBubbleChart() {
  console.warn('createClusteredBubbleChart not implemented: paste from skills/d3-visualization/scripts/bubble_chart_example.js');
  return { highlightBubble() {}, destroy() {}, nodes: [] };
}

function createInteractiveTable() {
  console.warn('createInteractiveTable not implemented: paste from skills/d3-visualization/scripts/interactive_table_example.js');
  return { render() {}, highlightTableRow() {} };
}

function formatAbbrevNumber() {
  console.warn('formatAbbrevNumber not implemented: paste from skills/d3-visualization/scripts/interactive_table_example.js');
  return '—';
}

// ---- END: Paste bubble + table helpers here when needed ----
