/**
 * Reference Interactive Data Table
 *
 * Pattern to adapt for any task that needs:
 * - A data table alongside a D3 chart
 * - Two-way highlighted selection (click a row -> highlight the chart element, and vice versa)
 * - Configurable columns with custom header strings and per-column formatters
 * - A number formatter that returns an em-dash placeholder for missing values
 *
 * Headers: when the task specifies exact header strings (e.g. "Ticker symbol",
 * "Full company name", "Sector", "Market cap"), pass them verbatim via the
 * `columns[i].label` field — don't abbreviate ("Ticker", "Name") or reword.
 *
 * Order: when the task says "list all N rows", preserve the input order by default.
 * Add optional column sorting on header click, but don't reorder rows on initial render
 * unless the task asks for it.
 *
 * Selection: click is idempotent — clicking a row sets `selectedKey` to that row's
 * key; it does NOT toggle the selection off on a second click. This keeps the chart
 * and table in sync when a verifier clicks both sides in sequence.
 */

const DEFAULT_COLUMNS = [
    { key: 'ticker',    label: 'Ticker symbol',     format: v => v },
    { key: 'name',      label: 'Full company name', format: v => v },
    { key: 'sector',    label: 'Sector',            format: v => v },
    { key: 'marketCap', label: 'Market cap',        format: formatBigNumber, numeric: true },
];

function buildInteractiveTable(opts) {
    // Backward-compat: accept either an options object OR a bare array of rows.
    if (Array.isArray(opts)) {
        opts = { container: '#table-container', data: opts };
    }
    const container = d3.select(opts.container || '#table-container');
    const columns = opts.columns || DEFAULT_COLUMNS;
    const rowKey = opts.rowKey || (d => d.ticker);
    const data = opts.data.slice();         // preserve input order

    // Build the table skeleton if the container is empty.
    let table = container.select('table');
    if (table.empty()) {
        table = container.append('table').attr('id', 'data-table');
    }

    let thead = table.select('thead');
    if (thead.empty()) {
        thead = table.append('thead');
        const headerRow = thead.append('tr');
        headerRow.selectAll('th')
            .data(columns)
            .join('th')
            .attr('class', d => d.numeric ? 'num' : null)
            .text(d => d.label)
            .style('cursor', opts.sortable ? 'pointer' : null)
            .on('click', opts.sortable
                ? function (event, col) { sortBy(col); }
                : null);
    }

    let tbody = table.select('tbody');
    if (tbody.empty()) tbody = table.append('tbody');

    let selectedKey = null;
    let selectCallback = () => {};

    function render(rows) {
        const tr = tbody.selectAll('tr')
            .data(rows, rowKey)
            .join('tr')
            .attr('data-key', rowKey)
            .on('click', function (event, d) {
                selectedKey = rowKey(d);         // idempotent
                selectCallback(selectedKey);
            });

        tr.selectAll('td')
            .data(d => columns.map(col => ({ col, value: d[col.key], row: d })))
            .join('td')
            .attr('class', d => d.col.numeric ? 'num' : null)
            .text(d => d.col.format ? d.col.format(d.value, d.row) : d.value);

        // Re-apply the current selection after a re-render.
        if (selectedKey != null) {
            tbody.selectAll('tr').classed('selected', d => rowKey(d) === selectedKey);
        }
    }

    render(data);

    // Optional sorting (only wired up when opts.sortable is true).
    let sortKey = null, sortAscending = true;
    function sortBy(col) {
        if (sortKey === col.key) {
            sortAscending = !sortAscending;
        } else {
            sortKey = col.key;
            sortAscending = true;
        }
        const sorted = data.slice().sort((a, b) => {
            const av = a[col.key];
            const bv = b[col.key];
            const cmp = col.numeric
                ? (Number(av) || 0) - (Number(bv) || 0)
                : String(av == null ? '' : av).localeCompare(String(bv == null ? '' : bv));
            return sortAscending ? cmp : -cmp;
        });
        render(sorted);
    }

    function highlight(key) {
        selectedKey = key;
        tbody.selectAll('tr').classed('selected', d => rowKey(d) === key);
        if (key != null && typeof document !== 'undefined') {
            const node = document.querySelector(`#${table.attr('id') || 'data-table'} tbody tr[data-key="${key}"]`);
            if (node && typeof node.scrollIntoView === 'function') {
                node.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }
        }
    }

    return {
        highlight,
        onSelect(cb) { selectCallback = cb; },
        update: render,
        sortBy,
        get selected() { return selectedKey; },
    };
}

/**
 * Format a numeric value with suffix style: 1.64T, 358.11B, 12.80M, 4.56K.
 * Returns an em-dash placeholder for missing/zero values so the column
 * stays visually aligned.
 */
function formatBigNumber(v) {
    if (v == null || v === '' || !isFinite(+v) || +v === 0) return '—';
    const n = +v;
    const abs = Math.abs(n);
    let s;
    if      (abs >= 1e12) s = (n / 1e12).toFixed(2) + 'T';
    else if (abs >= 1e9)  s = (n / 1e9 ).toFixed(2) + 'B';
    else if (abs >= 1e6)  s = (n / 1e6 ).toFixed(2) + 'M';
    else if (abs >= 1e3)  s = (n / 1e3 ).toFixed(2) + 'K';
    else                  s = n.toFixed(2);
    return s;
}

// Legacy alias names kept so older callers still link.
const formatNumber = formatBigNumber;
function createInteractiveTable(data) {
    return buildInteractiveTable({ container: '#table-container', data, sortable: true });
}

// --- CSS pattern ------------------------------------------------------------
// Use ONE class — `.selected` — for the highlighted-row state. Do not mix
// `.selected` on the chart side with `.highlighted` on the table side; keep
// them aligned so the cross-panel link is obvious.
const tableStyles = `
<style>
table { width: 100%; border-collapse: collapse; margin: 0; }
thead th {
    background: #f9fafb; padding: 10px 12px; text-align: left;
    border-bottom: 2px solid #e5e7eb; font-weight: 600; color: #374151;
}
th.num, td.num { text-align: right; }
tbody tr { cursor: pointer; }
tbody tr:hover { background: #f3f4f6; }
tbody td { padding: 8px 12px; border-bottom: 1px solid #f1f2f4; }
tbody tr.selected { background: #fff7d6; }
tbody tr.selected td { font-weight: 600; }
</style>
`;

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        buildInteractiveTable,
        createInteractiveTable,
        formatBigNumber,
        formatNumber,
    };
}
