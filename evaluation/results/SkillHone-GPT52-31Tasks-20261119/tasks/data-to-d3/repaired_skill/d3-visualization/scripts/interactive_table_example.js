/**
 * Interactive Table (deterministic, linkable)
 *
 * Use this as a starting point for tasks that ask for:
 * - A table listing items and their attributes
 * - Formatted numbers (e.g., market cap as 1.64T)
 * - Clicking a row selects/highlights it
 * - Two-way linking with a chart (bubble, bar, etc.)
 *
 * This template intentionally keeps sorting deterministic and exposes a small API:
 * - highlightTableRow(id)
 * - onSelect(id)
 */

/* global d3 */

'use strict';

function formatAbbrevNumber(n, placeholder = '—') {
  // Treat null/undefined/NaN as missing, but keep 0 as a valid value.
  if (n == null || !Number.isFinite(n)) return placeholder;

  // Use SI-prefix formatting for stable, human-friendly output.
  // Example: 1641026945024 -> "1.64T".
  // Note: d3 uses "G" for billions; many finance tasks expect "B".
  const s = d3.format('.3~s')(n);
  return s.replace('G', 'B').replace('k', 'K');
}

/**
 * Create an interactive table.
 *
 * @param {object} options
 * @returns {{ render: function(object[]): void, highlightTableRow: function(string|null): void }}
 */
function createInteractiveTable(options) {
  const opts = options || {};

  const containerSelector = opts.containerSelector ?? '#tableWrap';
  const tableSelector = opts.tableSelector ?? '#dataTable';

  const idAccessor = opts.idAccessor ?? ((d) => d.ticker ?? d.id);

  const columns =
    opts.columns ??
    [
      { key: 'ticker', label: 'Ticker symbol', align: 'left', format: (v) => String(v ?? '') },
      { key: 'name', label: 'Full company name', align: 'left', format: (v) => String(v ?? '') },
      { key: 'sector', label: 'Sector', align: 'left', format: (v) => String(v ?? '') },
      { key: 'marketCap', label: 'Market cap', align: 'right', format: (v) => formatAbbrevNumber(v) },
    ];

  const onSelect =
    opts.onSelect ??
    ((id) => {
      highlightTableRow(id);
      if (typeof globalThis !== 'undefined' && typeof globalThis.highlightBubble === 'function') {
        globalThis.highlightBubble(id);
      }
    });

  const container = d3.select(containerSelector);
  if (container.empty()) {
    throw new Error(`createInteractiveTable: container not found: ${containerSelector}`);
  }

  // Create table skeleton (or reuse).
  const table = container.select(tableSelector).empty()
    ? container.append('table').attr('id', tableSelector.replace('#', '')).attr('class', 'dataTable')
    : container.select(tableSelector);

  const thead = table.select('thead').empty() ? table.append('thead') : table.select('thead');
  const tbody = table.select('tbody').empty() ? table.append('tbody') : table.select('tbody');

  // Header row.
  thead.selectAll('*').remove();
  const headerRow = thead.append('tr');

  headerRow
    .selectAll('th')
    .data(columns)
    .join('th')
    .attr('class', (d) => (d.align === 'right' ? 'num' : null))
    .text((d) => d.label);

  // State for deterministic sort.
  let sortKey = opts.defaultSortKey ?? columns[0].key;
  let sortAscending = opts.defaultSortAscending ?? true;

  function setSort(key) {
    if (key === sortKey) {
      sortAscending = !sortAscending;
    } else {
      sortKey = key;
      sortAscending = true;
    }
  }

  // Optional click-to-sort.
  if (opts.enableSort) {
    headerRow
      .selectAll('th')
      .style('cursor', 'pointer')
      .on('click', function (event, col) {
        setSort(col.key);
        // Re-render using the last data passed to render().
        if (Array.isArray(lastRows)) render(lastRows);
      });
  }

  let lastRows = null;

  function sortedCopy(rows) {
    const copy = rows.slice();

    // Always stable tie-breaker by id.
    copy.sort((a, b) => {
      const aId = String(idAccessor(a) ?? '');
      const bId = String(idAccessor(b) ?? '');

      const aVal = a?.[sortKey];
      const bVal = b?.[sortKey];

      const bothNumeric = Number.isFinite(+aVal) && Number.isFinite(+bVal);

      let cmp;
      if (bothNumeric) {
        cmp = d3.ascending(+aVal, +bVal);
      } else {
        cmp = d3.ascending(String(aVal ?? ''), String(bVal ?? ''));
      }

      if (!sortAscending) cmp *= -1;
      return cmp || d3.ascending(aId, bId);
    });

    return copy;
  }

  function render(rows) {
    lastRows = rows;

    const data = sortedCopy(Array.isArray(rows) ? rows : []);

    const tr = tbody
      .selectAll('tr')
      .data(data, (d) => String(idAccessor(d) ?? ''))
      .join('tr')
      .attr('data-id', (d) => String(idAccessor(d) ?? ''))
      .on('click', function (event, d) {
        onSelect(String(idAccessor(d) ?? ''));
      });

    tr
      .selectAll('td')
      .data((row) =>
        columns.map((col) => ({
          key: col.key,
          align: col.align,
          text: col.format(row?.[col.key]),
        }))
      )
      .join('td')
      .attr('class', (d) => (d.align === 'right' ? 'num' : null))
      .text((d) => d.text);
  }

  function highlightTableRow(id) {
    const target = id == null ? null : String(id);
    tbody
      .selectAll('tr')
      .classed('selected', (d) => target != null && String(idAccessor(d) ?? '') === target);
  }

  return { render, highlightTableRow };
}
