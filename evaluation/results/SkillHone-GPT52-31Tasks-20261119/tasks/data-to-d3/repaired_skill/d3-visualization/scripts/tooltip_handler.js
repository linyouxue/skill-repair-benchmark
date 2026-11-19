/**
 * TooltipHandler (small reusable helper)
 *
 * This is a minimal helper for showing/hiding a single tooltip div.
 * Prefer this pattern over inline tooltip code when multiple charts need tooltips.
 *
 * Design goals:
 * - No framework / no build step
 * - Works with D3 v6 event signatures (event, d)
 * - Conditional display (e.g., "do not show tooltip for ETFs")
 * - CSS class-based visibility (.visible)
 */

/* global d3 */

'use strict';

class TooltipHandler {
  constructor(options = {}) {
    this.selector = options.selector || '#tooltip';
    this.offsetX = options.offsetX ?? 10;
    this.offsetY = options.offsetY ?? -10;
    this.shouldShow = options.shouldShow || (() => true);
    this.formatContent = options.formatContent || ((d) => `<strong>${escapeHtml(d?.name ?? d?.id ?? '')}</strong>`);

    this.tooltip = d3.select(this.selector);

    // Create tooltip if it doesn't exist.
    if (this.tooltip.empty()) {
      const id = this.selector.startsWith('#') ? this.selector.slice(1) : 'tooltip';
      this.tooltip = d3.select('body').append('div').attr('id', id).attr('class', 'tooltip').classed('visible', false);
    }
  }

  show(event, data) {
    if (!this.shouldShow(data)) return;

    this.tooltip
      .classed('visible', true)
      .attr('aria-hidden', 'false')
      .html(this.formatContent(data))
      .style('left', `${event.pageX + this.offsetX}px`)
      .style('top', `${event.pageY + this.offsetY}px`);
  }

  move(event) {
    if (!this.tooltip.classed('visible')) return;
    this.tooltip.style('left', `${event.pageX + this.offsetX}px`).style('top', `${event.pageY + this.offsetY}px`);
  }

  hide() {
    this.tooltip.classed('visible', false).attr('aria-hidden', 'true');
  }

  /**
   * Attach tooltip events to a D3 selection.
   *
   * Example:
   *   const tip = new TooltipHandler({ shouldShow: d => !d.isETF });
   *   tip.attach(svg.selectAll('circle'));
   */
  attach(selection) {
    selection
      .on('mouseover', (event, d) => this.show(event, d))
      .on('mousemove', (event) => this.move(event))
      .on('mouseout', () => this.hide());

    return selection;
  }
}

function escapeHtml(s) {
  // Avoid String.prototype.replaceAll for broader runtime compatibility.
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// CommonJS export for tooling; safe in browser too.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TooltipHandler;
}
