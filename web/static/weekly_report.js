async function loadHistory() {
  try {
    const res = await fetch('/api/reports/weekly/my');
    if (res.status === 401) { location.href = '/login'; return; }
    const reports = await res.json();
    const el = document.getElementById('historyList');
    if (!reports.length) {
      el.innerHTML = '<p class="text-muted small">提出履歴がありません</p>';
      return;
    }
    el.innerHTML = reports.map(r => `
      <div class="card mb-2">
        <div class="card-body py-2 px-3">
          <div class="d-flex justify-content-between">
            <strong class="small">${escHtml(r.report_date)}</strong>
            <span class="badge bg-success">提出済み</span>
          </div>
          <p class="mb-1 small text-muted">${escHtml((r.work_content || '').slice(0, 80))}${r.work_content?.length > 80 ? '…' : ''}</p>
        </div>
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('historyList').innerHTML = '<p class="text-danger small">読み込みエラー</p>';
  }
}

async function submitReport() {
  const workContent = document.getElementById('workContent').value.trim();
  const nextWeekPlan = document.getElementById('nextWeekPlan').value.trim();
  const requestsOpinions = document.getElementById('requestsOpinions').value.trim();

  if (!workContent || !nextWeekPlan) {
    showAlert('今週の作業内容と来週の作業予定は必須です', 'danger');
    return;
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = '提出中...';

  try {
    const res = await fetch('/api/reports/weekly', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        work_content: workContent,
        next_week_plan: nextWeekPlan,
        requests_opinions: requestsOpinions,
      }),
    });

    if (res.status === 409) {
      showAlert('今週の週報はすでに提出済みです', 'warning');
      return;
    }
    if (!res.ok) {
      const err = await res.json();
      showAlert(err.detail || '提出に失敗しました', 'danger');
      return;
    }

    showAlert('週報を提出しました！', 'success');
    document.getElementById('workContent').value = '';
    document.getElementById('nextWeekPlan').value = '';
    document.getElementById('requestsOpinions').value = '';
    loadHistory();
  } catch (e) {
    showAlert('通信エラーが発生しました', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = '提出する';
  }
}

function showAlert(msg, type) {
  document.getElementById('formAlert').innerHTML =
    `<div class="alert alert-${type} alert-dismissible py-2 small">
       ${escHtml(msg)}
       <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert"></button>
     </div>`;
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

loadHistory();
