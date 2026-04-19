let reports = [];

async function loadReports() {
  try {
    const res = await fetch('/api/reports');
    if (res.status === 401) { location.href = '/login'; return; }
    reports = await res.json();
    renderList();
  } catch (e) {
    document.getElementById('reportList').innerHTML = '<p class="text-danger small">読み込みエラー</p>';
  }
}

function renderList() {
  if (!reports.length) {
    document.getElementById('reportList').innerHTML = '<p class="text-muted small">レポートがありません</p>';
    return;
  }
  document.getElementById('reportList').innerHTML = reports.map(r => {
    const label = r.report_type === 'executive'
      ? '<span class="badge report-badge-executive text-white ms-1">Exec</span>'
      : '<span class="badge bg-primary ms-1">全体</span>';
    const dt = r.generated_at ? r.generated_at.slice(0, 10) : '';
    return `<div class="report-item p-2 border-bottom" onclick="showReport(${r.id})" id="item-${r.id}">
      <div class="d-flex justify-content-between align-items-center">
        <small class="fw-semibold">${escHtml(r.period_start)} ～ ${escHtml(r.period_end)}</small>
        ${label}
      </div>
      <small class="text-muted">${dt} / ${r.total_reports || 0}件</small>
    </div>`;
  }).join('');
}

async function showReport(id) {
  document.querySelectorAll('.report-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`item-${id}`)?.classList.add('active');

  const r = reports.find(x => x.id === id);
  if (!r) return;

  document.getElementById('reportTitle').textContent =
    `${r.period_start} ～ ${r.period_end}`;

  const linksEl = document.getElementById('reportLinks');
  linksEl.innerHTML = '';
  if (r.google_doc_url) {
    linksEl.innerHTML += `<a href="${escAttr(r.google_doc_url)}" target="_blank" class="btn btn-sm btn-outline-primary me-1">Docs</a>`;
  }
  if (r.google_pdf_url) {
    linksEl.innerHTML += `<a href="${escAttr(r.google_pdf_url)}" target="_blank" class="btn btn-sm btn-outline-secondary me-1">PDF</a>`;
  }
  if (!r.google_pdf_url) {
    linksEl.innerHTML += `<button class="btn btn-sm btn-outline-secondary" onclick="window.print()">印刷</button>`;
  }

  const preview = document.getElementById('reportPreview');
  if (r.markdown_content) {
    preview.innerHTML = marked.parse(r.markdown_content);
  } else {
    preview.innerHTML = '<p class="text-muted">マークダウン内容がありません。</p>';
  }
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function escAttr(str) {
  return String(str).replace(/"/g,'&quot;');
}

loadReports();
