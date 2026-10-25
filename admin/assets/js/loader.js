/**
 * Tiny asset loader — the build-free replacement for webpack's dynamic import().
 *
 * The three heavy widgets (Chart.js, FullCalendar, jsvectormap) ship as plain
 * <script>-tag bundles in assets/vendor/, so they can't be pulled in with
 * `import()`. loadScript()/loadStyle() append the tag on demand and cache the
 * promise, which preserves the "a page only downloads what it actually uses"
 * property the bundler used to give us.
 *
 * URLs are resolved against import.meta.url, so the pages stay free to move.
 */

const scripts = new Map();
const styles = new Set();

/** Absolute URL for a path under assets/, resolved from this module's location. */
export function asset(path) {
  return new URL(`../${path}`, import.meta.url).href;
}

/** Append a classic <script> once; resolves when it has executed. */
export function loadScript(url) {
  if (scripts.has(url)) return scripts.get(url);

  const pending = new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = url;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error(`Failed to load ${url}`));
    document.head.appendChild(el);
  });

  scripts.set(url, pending);
  return pending;
}

/**
 * Append a <link rel=stylesheet> once. Deliberately not awaited: vendor CSS
 * must land after style.css so our token overrides keep winning, and blocking
 * on it would only delay the widget.
 */
export function loadStyle(url) {
  if (styles.has(url)) return;
  styles.add(url);

  const el = document.createElement('link');
  el.rel = 'stylesheet';
  el.href = url;
  document.head.appendChild(el);
}
