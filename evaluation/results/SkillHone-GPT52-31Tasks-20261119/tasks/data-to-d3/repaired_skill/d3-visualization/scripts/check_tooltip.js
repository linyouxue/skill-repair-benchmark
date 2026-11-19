/**
 * Tooltip Implementation Checker (dev helper)
 *
 * This helper is optional; it can be pasted into the browser console.
 * It verifies that:
 * - a tooltip element exists
 * - the tooltip uses a CSS class ("visible") to toggle visibility
 * - pointer-events are disabled (prevents mouse interference)
 */

'use strict';

function checkTooltipSetup(tooltipId = 'tooltip') {
  const tooltip = document.getElementById(tooltipId);
  if (!tooltip) {
    console.error(`Tooltip element not found: #${tooltipId}`);
    return false;
  }

  const style = window.getComputedStyle(tooltip);
  const okPointer = style.pointerEvents === 'none';

  console.log('Tooltip exists:', tooltip);
  console.log('pointer-events:', style.pointerEvents, okPointer ? '✓' : '⚠ (recommended: none)');

  return true;
}

function checkTooltipVisibilityClass(tooltipId = 'tooltip') {
  const tooltip = document.getElementById(tooltipId);
  if (!tooltip) return false;

  console.log('Has .visible:', tooltip.classList.contains('visible'));
  console.log('Computed opacity:', window.getComputedStyle(tooltip).opacity);
  return true;
}

// Auto-run when executed in a browser environment.
if (typeof document !== 'undefined') {
  console.log('=== Tooltip Implementation Check ===');
  checkTooltipSetup();
  checkTooltipVisibilityClass();
}
