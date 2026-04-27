let allSchedules = [];

const DOW_LABELS = ['月', '火', '水', '木', '金', '土', '日'];

async function loadSchedules() {
  try {
    const res = await fetch('/api/admin/schedules');
    if (res.status === 401 || res.status === 403) { location.href = '/login'; return; }
    allSchedules = await res.json();
    renderSchedules(allSchedules);
  } catch (e) {
    document.getElementById('schedulesBody').innerHTML =
      '<tr><td colspan="9" class="text-danger text-center">読み込みエラー</td></tr>';
  }
}

function fmtDateTime(iso) {
  if (!iso) return '<span class="text-muted">-</span>';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z');
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('ja-JP', { hour12: false, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function fmtDays(arr) {
  if (!arr || !arr.length) return '<span class="text-muted">なし</span>';
  return arr.map(d => DOW_LABELS[d]).join('・');
}

function fmtTime(h, m) {
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function renderSchedules(rows) {
  if (!rows.length) {
    document.getElementById('schedulesBody').innerHTML =
      '<tr><td colspan="9" class="text-center text-muted py-3">スケジュールが登録されていません</td></tr>';
    return;
  }
  document.getElementById('schedulesBody').innerHTML = rows.map(s => `
    <tr>
      <td><strong>${escHtml(s.name)}</strong></td>
      <td><small>${escHtml(s.report_type)}</small></td>
      <td><small>${fmtDays(s.days_of_week)}</small></td>
      <td><small>${fmtTime(s.hour, s.minute)} <span class="text-muted">${escHtml(s.timezone)}</span></small></td>
      <td>${s.enabled
        ? '<span class="badge bg-success">有効</span>'
        : '<span class="badge bg-secondary">無効</span>'}</td>
      <td><small>${fmtDateTime(s.next_run_at)}</small></td>
      <td><small>${fmtDateTime(s.last_run_at)}</small></td>
      <td><small>${s.last_run_status ? escHtml(s.last_run_status).slice(0, 60) : '<span class="text-muted">-</span>'}</small></td>
      <td>
        <button class="btn btn-xs btn-outline-secondary btn-sm py-0 px-1" onclick="openEditScheduleModal(${s.id})">編集</button>
        <button class="btn btn-xs btn-outline-success btn-sm py-0 px-1" onclick="runScheduleNow(${s.id})">Run Now</button>
        <button class="btn btn-xs btn-outline-danger btn-sm py-0 px-1" onclick="deleteSchedule(${s.id})">削除</button>
      </td>
    </tr>
  `).join('');
}

function _resetScheduleForm() {
  document.getElementById('editScheduleId').value = '';
  document.getElementById('schName').value = '';
  document.getElementById('schReportType').value = 'both';
  document.querySelectorAll('.sch-dow').forEach(cb => cb.checked = false);
  document.getElementById('schHour').value = 9;
  document.getElementById('schMinute').value = 0;
  document.getElementById('schTimezone').value = 'Asia/Tokyo';
  document.getElementById('schEnabled').checked = true;
  document.getElementById('scheduleModalError').textContent = '';
}

function openCreateScheduleModal() {
  document.getElementById('scheduleModalTitle').textContent = '新規スケジュール';
  _resetScheduleForm();
  new bootstrap.Modal(document.getElementById('scheduleModal')).show();
}

function openEditScheduleModal(id) {
  const s = allSchedules.find(x => x.id === id);
  if (!s) return;
  document.getElementById('scheduleModalTitle').textContent = 'スケジュール編集';
  _resetScheduleForm();
  document.getElementById('editScheduleId').value = s.id;
  document.getElementById('schName').value = s.name;
  document.getElementById('schReportType').value = s.report_type;
  (s.days_of_week || []).forEach(d => {
    const cb = document.getElementById('schDow' + d);
    if (cb) cb.checked = true;
  });
  document.getElementById('schHour').value = s.hour;
  document.getElementById('schMinute').value = s.minute;
  document.getElementById('schTimezone').value = s.timezone;
  document.getElementById('schEnabled').checked = s.enabled;
  new bootstrap.Modal(document.getElementById('scheduleModal')).show();
}

async function saveSchedule() {
  const id = document.getElementById('editScheduleId').value;
  const days = Array.from(document.querySelectorAll('.sch-dow:checked')).map(cb => parseInt(cb.value, 10));
  const payload = {
    name: document.getElementById('schName').value.trim(),
    report_type: document.getElementById('schReportType').value,
    days_of_week: days,
    hour: parseInt(document.getElementById('schHour').value, 10),
    minute: parseInt(document.getElementById('schMinute').value, 10),
    timezone: document.getElementById('schTimezone').value.trim() || 'Asia/Tokyo',
    enabled: document.getElementById('schEnabled').checked,
  };
  const errEl = document.getElementById('scheduleModalError');
  if (!payload.name) {
    errEl.textContent = '名前は必須です';
    return;
  }
  if (!payload.days_of_week.length) {
    errEl.textContent = '曜日を1つ以上選択してください';
    return;
  }
  if (Number.isNaN(payload.hour) || Number.isNaN(payload.minute)) {
    errEl.textContent = '時刻が正しくありません';
    return;
  }

  const url = id ? `/api/admin/schedules/${id}` : '/api/admin/schedules';
  const method = id ? 'PATCH' : 'POST';
  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      errEl.textContent = err.detail || `保存に失敗しました (HTTP ${res.status})`;
      return;
    }
    bootstrap.Modal.getInstance(document.getElementById('scheduleModal')).hide();
    loadSchedules();
  } catch (e) {
    errEl.textContent = '通信エラー';
  }
}

async function deleteSchedule(id) {
  const s = allSchedules.find(x => x.id === id);
  if (!s) return;
  if (!confirm(`スケジュール「${s.name}」を削除しますか？`)) return;
  try {
    const res = await fetch(`/api/admin/schedules/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      alert(`削除に失敗しました (HTTP ${res.status})`);
      return;
    }
    loadSchedules();
  } catch (e) {
    alert('通信エラー');
  }
}

async function runScheduleNow(id) {
  const s = allSchedules.find(x => x.id === id);
  if (!s) return;
  if (!confirm(`「${s.name}」を今すぐ実行しますか？レポート生成には数十秒〜数分かかります。`)) return;
  try {
    const res = await fetch(`/api/admin/schedules/${id}/run-now`, { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      alert(`実行失敗: ${data.detail || res.status}`);
    } else {
      alert(`実行結果: ${data.status || 'unknown'}` + (data.error ? `\n${data.error}` : ''));
    }
    loadSchedules();
  } catch (e) {
    alert('通信エラー');
  }
}

function escHtml(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

loadSchedules();
