/**
 * On phones, wide tables are shown as one card per row (see mobile.css).
 * Each cell needs its column name to make sense on its own, so this copies the
 * header text of every table into `data-label` on its cells. One observer for
 * the whole app; tables added later (tabs, drafts) are labelled as they appear.
 */
const TABLES = 'table.data-table, table.will-miss-table';

function labelTable(table: HTMLTableElement): void {
  const heads = Array.from(table.querySelectorAll('thead th')).map(th => (th.textContent ?? '').trim());
  if (!heads.length) return;
  table.querySelectorAll('tbody tr').forEach(tr => {
    let col = 0;
    Array.from(tr.children).forEach(cell => {
      const label = heads[col] ?? '';
      if (cell.getAttribute('data-label') !== label) cell.setAttribute('data-label', label);
      // Long text (explanations, next actions) reads better under its label than squeezed beside it.
      const long = (cell.textContent ?? '').trim().length > 30 || !!cell.querySelector('input, select, textarea');
      if (long) cell.setAttribute('data-long', '');
      else cell.removeAttribute('data-long');
      col += (cell as HTMLTableCellElement).colSpan || 1;
    });
  });
  table.classList.add('is-labelled');
}

export function startTableLabels(root: HTMLElement = document.body): () => void {
  let queued = false;
  const run = () => {
    queued = false;
    root.querySelectorAll<HTMLTableElement>(TABLES).forEach(labelTable);
  };
  const schedule = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(run);
  };
  const obs = new MutationObserver(schedule);
  obs.observe(root, { childList: true, subtree: true });
  run();
  return () => obs.disconnect();
}
