import { chromium } from 'playwright';

interface CLSResult {
  url: string;
  cls: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  metrics: Record<string, number>;
  shifts: { value: number; startTime: number }[];
}

async function measureCLS(url: string, scroll: boolean = false): Promise<CLSResult> {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const client = await page.context().newCDPSession(page);

  // Enable Performance domain
  await client.send('Performance.enable');

  // Install before navigation so early shifts are included.
  await page.addInitScript(() => {
    const state = { supported: PerformanceObserver.supportedEntryTypes.includes('layout-shift'),
      cls: 0, score: 0, start: null as number | null, last: 0,
      shifts: [] as { value: number; startTime: number }[] };
    (window as any).__clsResult = state;
    if (!state.supported) return;
    new PerformanceObserver(list => {
      for (const raw of list.getEntries()) {
        const entry = raw as PerformanceEntry & { value: number; hadRecentInput: boolean };
        if (entry.hadRecentInput) continue;
        if (state.start === null || entry.startTime - state.last >= 1000 ||
            entry.startTime - state.start >= 5000) {
          state.score = 0;
          state.start = entry.startTime;
        }
        state.score += entry.value;
        state.last = entry.startTime;
        state.cls = Math.max(state.cls, state.score);
        state.shifts.push({ value: entry.value, startTime: entry.startTime });
      }
    }).observe({ type: 'layout-shift', buffered: true });
  });

  // Navigate and wait for load
  await page.goto(url, { waitUntil: 'networkidle' });

  // Optional: scroll to trigger lazy-loaded content shifts
  if (scroll) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);
  }

  // Wait for any remaining shifts
  await page.waitForTimeout(2000);

  // Get diagnostic CDP counters
  const perfMetrics = await client.send('Performance.getMetrics');

  // Convert metrics array to object
  const metrics: Record<string, number> = {};
  for (const m of perfMetrics.metrics) {
    metrics[m.name] = m.value;
  }

  // CDP metrics are diagnostic counters, not the CLS source.
  const observed = await page.evaluate(() => (window as any).__clsResult);
  if (!observed?.supported || !Number.isFinite(observed.cls)) {
    throw new Error('Layout-shift telemetry unavailable; CLS cannot be rated');
  }
  const cls = observed.cls;
  await browser.close();

  // Determine rating (Google's thresholds)
  let rating: 'good' | 'needs-improvement' | 'poor';
  if (cls < 0.1) {
    rating = 'good';
  } else if (cls < 0.25) {
    rating = 'needs-improvement';
  } else {
    rating = 'poor';
  }

  return {
    url,
    cls: Math.round(cls * 1000) / 1000,
    rating,
    shifts: observed.shifts,
    metrics
  };
}

// Main
const url = process.argv[2] || 'http://localhost:3000';
const scroll = process.argv.includes('--scroll');

measureCLS(url, scroll)
  .then(result => console.log(JSON.stringify(result, null, 2)))
  .catch(err => {
    console.error('CLS measurement failed:', err.message);
    process.exit(1);
  });
