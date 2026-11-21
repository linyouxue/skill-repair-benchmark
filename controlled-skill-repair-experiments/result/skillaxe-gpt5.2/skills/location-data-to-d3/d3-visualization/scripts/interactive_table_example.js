/**
 * Interactive Data Table Example
 *
 * Creates a sortable, filterable data table that links with charts.
 * Features:
 * - Two-way highlighting (click table row -> highlight chart element)
 * - Formatted numbers
 * - Click to sort columns
 *
 * NOTE (SkillAxe repair):
 * This example now uses a single shared selection contract:
 *   - global function setSelection(key)
 * If setSelection is not provided by the host app, it falls back to
 * calling highlightBubble/highlightTableRow if present.
 */

function createInteractiveTable(data, options = {}) {
    const container = d3.select(options.containerSelector || '#table-container');
    const keyFn = options.keyFn || (d => d.ticker);

    // Create table structure
    const table = container.append('table')
        .attr('id', options.tableId || 'data-table');

    // Define columns
    const columns = options.columns || [
        {key: 'ticker', label: 'Ticker', format: d => d},
        {key: 'name', label: 'Company Name', format: d => d},
        {key: 'sector', label: 'Sector', format: d => d},
        {key: 'marketCap', label: 'Market Cap', format: formatNumber}
    ];

    // Create header
    const thead = table.append('thead');
    const headerRow = thead.append('tr');

    headerRow.selectAll('th')
        .data(columns)
        .join('th')
        .text(d => d.label)
        .on('click', function(event, col) {
            sortTable(data, col.key);
        })
        .style('cursor', 'pointer');

    // Create body
    const tbody = table.append('tbody');

    function renderTable(rowsData) {
        const rows = tbody.selectAll('tr')
            .data(rowsData, d => keyFn(d))
            .join('tr')
            .attr('data-key', d => keyFn(d))
            .on('click', function(event, d) {
                const key = keyFn(d);
                // Preferred: single shared selection function
                if (typeof window !== 'undefined' && typeof window.setSelection === 'function') {
                    window.setSelection(key);
                    return;
                }
                // Fallbacks for older patterns
                selectRow(key);
            });

        rows.selectAll('td')
            .data(d => columns.map(col => ({
                value: d[col.key],
                format: col.format
            })))
            .join('td')
            .text(d => d.format(d.value));
    }

    renderTable(data);

    // Sorting function
    let sortAscending = true;
    let sortKey = null;

    function sortTable(rowsData, key) {
        if (sortKey === key) {
            sortAscending = !sortAscending;
        } else {
            sortKey = key;
            sortAscending = true;
        }

        rowsData.sort((a, b) => {
            const aVal = a[key];
            const bVal = b[key];

            if (typeof aVal === 'string') {
                return sortAscending ?
                    (aVal || '').localeCompare(bVal || '') :
                    (bVal || '').localeCompare(aVal || '');
            } else {
                return sortAscending ?
                    (aVal || 0) - (bVal || 0) :
                    (bVal || 0) - (aVal || 0);
            }
        });

        renderTable(rowsData);
    }

    // Return table API
    return {
        update: renderTable,
        sort: sortTable
    };
}

/**
 * Legacy selection helpers (fallbacks)
 * Prefer using a single shared window.setSelection(key) in real apps.
 */
function selectRow(key) {
    // Highlight row
    d3.selectAll('#data-table tbody tr')
        .classed('selected', function(d) {
            return d && d.ticker === key;
        });

    // Trigger chart highlight if exists
    if (typeof window !== 'undefined' && typeof window.highlightBubble === 'function') {
        window.highlightBubble(key);
    }
}

function highlightTableRow(key) {
    d3.selectAll('#data-table tbody tr')
        .classed('selected', function(d) {
            return d && d.ticker === key;
        });
}

// Number formatting utility
function formatNumber(num) {
    if (num === null || num === undefined || num === '') return '-';

    const n = +num;
    if (!isFinite(n)) return '-';

    const absNum = Math.abs(n);
    let formatted;

    if (absNum >= 1e12) {
        formatted = (n / 1e12).toFixed(2) + 'T';
    } else if (absNum >= 1e9) {
        formatted = (n / 1e9).toFixed(2) + 'B';
    } else if (absNum >= 1e6) {
        formatted = (n / 1e6).toFixed(2) + 'M';
    } else if (absNum >= 1e3) {
        formatted = (n / 1e3).toFixed(2) + 'K';
    } else {
        formatted = n.toFixed(2);
    }

    return n < 0 ? '-' + formatted : formatted;
}

// CSS for table styling
const tableStyles = `
<style>
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}

th {
    background: #f5f5f5;
    padding: 10px;
    text-align: left;
    border-bottom: 2px solid #ddd;
    font-weight: bold;
}

th:hover {
    background: #e0e0e0;
}

td {
    padding: 8px 10px;
    border-bottom: 1px solid #eee;
}

tr:hover {
    background: #f9f9f9;
}

tr.selected {
    background: #e3f2fd !important;
    border-left: 3px solid #2196f3;
}
</style>
`;

// Inject styles
if (typeof document !== 'undefined') {
    const styleEl = document.createElement('div');
    styleEl.innerHTML = tableStyles;
    document.head.appendChild(styleEl.firstChild);
}
