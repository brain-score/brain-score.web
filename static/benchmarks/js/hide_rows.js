document.addEventListener('DOMContentLoaded', () => {
  const btn      = document.getElementById('toggle-rows');
  if (!btn) return;

  const allRows   = Array.from(document.querySelectorAll('tbody tr'));
  const extraRows = allRows.slice(5);
  const total     = allRows.length;
  let expanded    = false;

  // no need to reset initial text if it's already in your HTML,
  // but here’s how you’d do it dynamically:
  btn.textContent = `Show all uploads (${total} total) ▼`;

  btn.addEventListener('click', () => {
    expanded = !expanded;
    extraRows.forEach(r => r.style.display = expanded ? 'table-row' : 'none');

    if (expanded) {
      btn.textContent = 'Show fewer uploads ▲';
    } else {
      btn.textContent = `Show all uploads (${total} total) ▼`;
    }
  });
});