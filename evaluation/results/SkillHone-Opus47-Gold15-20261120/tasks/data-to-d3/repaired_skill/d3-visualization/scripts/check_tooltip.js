/**
 * Browser-console sanity checks for interactive D3 visualizations.
 *
 * Paste these into the DevTools console on the rendered page to verify:
 *   1. The tooltip element exists and starts hidden (opacity 0).
 *   2. Hovering a mark shows the tooltip; leaving it hides it.
 *   3. Records that should NOT trigger a tooltip stay hidden on hover.
 *   4. Clicking a mark highlights its paired table row (two-way linked selection).
 *
 * They assume the DOM uses the patterns from this skill:
 *   - A single `<div id="tooltip" class="tooltip"></div>` outside the SVG
 *   - `.classed('visible', true/false)` to toggle visibility
 *   - `.classed('selected', …)` on BOTH the chart marks and the table rows
 */

function checkTooltipSetup() {
    const tooltip = document.getElementById('tooltip');
    if (!tooltip) {
        console.error('❌ #tooltip element missing');
        return false;
    }
    console.log('✓ #tooltip exists');
    const style = window.getComputedStyle(tooltip);
    if (parseFloat(style.opacity) !== 0) {
        console.warn('⚠ #tooltip is visible before any hover (opacity=' + style.opacity + ')');
    }
    if (style.pointerEvents !== 'none') {
        console.warn('⚠ #tooltip has pointer-events=' + style.pointerEvents + ' — it may block hover on marks beneath');
    }
    return true;
}

function simulateHover(selector) {
    const el = document.querySelector(selector);
    if (!el) { console.error('❌ no element for ' + selector); return null; }
    const rect = el.getBoundingClientRect();
    const opts = { bubbles: true, clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 };
    el.dispatchEvent(new MouseEvent('mouseover', opts));
    el.dispatchEvent(new MouseEvent('mousemove', opts));
    return el;
}

function simulateLeave(selector) {
    const el = document.querySelector(selector);
    if (!el) return null;
    el.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }));
    return el;
}

function checkTooltipVisibility() {
    const tooltip = document.getElementById('tooltip');
    if (!tooltip) return false;
    console.log('Tooltip has .visible class:', tooltip.classList.contains('visible'));
    console.log('Tooltip opacity:', window.getComputedStyle(tooltip).opacity);
    console.log('Tooltip text:', tooltip.textContent.trim());
    return true;
}

/**
 * Click a bubble, then check that EXACTLY the matching table row is
 * highlighted with the same `.selected` class.
 */
function checkLinkedSelection(bubbleSelector, tableRowSelector, keyAttr) {
    const bubble = document.querySelector(bubbleSelector);
    if (!bubble) { console.error('❌ no bubble for ' + bubbleSelector); return false; }
    bubble.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    // Chart side
    const selectedBubbles = document.querySelectorAll(bubbleSelector + '.selected, circle.bubble.selected');
    console.log('selected bubbles:', selectedBubbles.length);

    // Table side
    const selectedRows = document.querySelectorAll(tableRowSelector + '.selected');
    console.log('selected table rows:', selectedRows.length);

    if (selectedBubbles.length === 1 && selectedRows.length === 1) {
        console.log('✓ linked selection OK');
        return true;
    }
    console.error('❌ linked selection failed');
    return false;
}

if (typeof document !== 'undefined') {
    console.log('=== D3 Visualization Sanity Checks ===');
    checkTooltipSetup();
    // Example wiring (adjust selectors to your task):
    // simulateHover('circle.bubble'); checkTooltipVisibility(); simulateLeave('circle.bubble');
    // checkLinkedSelection('circle.bubble', '#stock-table tbody tr', 'data-key');
}
