let allMembers = [];

async function loadMembers() {
  try {
    const res = await fetch('/api/members?active_only=false');
    if (res.status === 401) { location.href = '/login'; return; }
    allMembers = await res.json();
    renderMembers(allMembers);
  } catch (e) {
    document.getElementById('membersBody').innerHTML =
      '<tr><td colspan="6" class="text-danger text-center">読み込みエラー</td></tr>';
  }
}

function renderMembers(members) {
  const cols = IS_ADMIN ? 6 : 5;
  if (!members.length) {
    document.getElementById('membersBody').innerHTML =
      `<tr><td colspan="${cols}" class="text-center text-muted py-3">メンバーが登録されていません</td></tr>`;
    return;
  }
  document.getElementById('membersBody').innerHTML = members.map(m => `
    <tr>
      <td>${escHtml(m.name)}</td>
      <td><small class="text-muted">${escHtml(m.email || '')}</small></td>
      <td>${escHtml(m.department)}</td>
      <td><span class="badge bg-secondary">${escHtml(m.role)}</span></td>
      <td>${m.active
        ? '<span class="badge bg-success">有効</span>'
        : '<span class="badge bg-danger">無効</span>'}</td>
      ${IS_ADMIN ? `<td><button class="btn btn-xs btn-outline-secondary btn-sm py-0 px-1" onclick="openEditModal(${m.id})">編集</button></td>` : ''}
    </tr>
  `).join('');
}

function openCreateModal() {
  document.getElementById('modalTitle').textContent = '新規メンバー追加';
  document.getElementById('editMemberId').value = '';
  document.getElementById('editName').value = '';
  document.getElementById('editEmail').value = '';
  document.getElementById('editDepartment').value = 'Other';
  document.getElementById('editRole').value = 'employee';
  document.getElementById('editSlackId').value = '';
  document.getElementById('editActive').checked = true;
  document.getElementById('modalError').textContent = '';
  new bootstrap.Modal(document.getElementById('memberModal')).show();
}

function openEditModal(id) {
  const m = allMembers.find(x => x.id === id);
  if (!m) return;
  document.getElementById('modalTitle').textContent = 'メンバー編集';
  document.getElementById('editMemberId').value = m.id;
  document.getElementById('editName').value = m.name;
  document.getElementById('editEmail').value = m.email || '';
  document.getElementById('editDepartment').value = m.department;
  document.getElementById('editRole').value = m.role;
  document.getElementById('editSlackId').value = m.slack_id || '';
  document.getElementById('editActive').checked = m.active;
  document.getElementById('modalError').textContent = '';
  new bootstrap.Modal(document.getElementById('memberModal')).show();
}

async function saveMember() {
  const id = document.getElementById('editMemberId').value;
  const payload = {
    name: document.getElementById('editName').value.trim(),
    email: document.getElementById('editEmail').value.trim() || null,
    department: document.getElementById('editDepartment').value,
    role: document.getElementById('editRole').value,
    slack_id: document.getElementById('editSlackId').value.trim() || null,
    active: document.getElementById('editActive').checked,
  };
  if (!payload.name) {
    document.getElementById('modalError').textContent = '名前は必須です';
    return;
  }
  const url = id ? `/api/members/${id}` : '/api/members';
  const method = id ? 'PATCH' : 'POST';
  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      document.getElementById('modalError').textContent = err.detail || '保存に失敗しました';
      return;
    }
    bootstrap.Modal.getInstance(document.getElementById('memberModal')).hide();
    loadMembers();
  } catch (e) {
    document.getElementById('modalError').textContent = '通信エラー';
  }
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

loadMembers();
