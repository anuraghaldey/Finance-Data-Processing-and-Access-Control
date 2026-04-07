const API = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://localhost:5000/api/v1'
  : 'https://finance-backend-api-tg7i.onrender.com/api/v1';
let accessToken = null;
let refreshToken = null;
let currentUser = null;
let recordsCursor = null;

// ─── API HELPER ───
async function api(endpoint, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

  try {
    const res = await fetch(`${API}${endpoint}`, { ...options, headers });

    if (res.status === 401 && refreshToken) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${accessToken}`;
        const retry = await fetch(`${API}${endpoint}`, { ...options, headers });
        return { ok: retry.ok, status: retry.status, data: await retry.json() };
      }
      handleLogout();
      return { ok: false, status: 401, data: { error: 'Session expired' } };
    }

    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: 'Network error — is the backend running?' } };
  }
}

async function tryRefreshToken() {
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${refreshToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      accessToken = data.access_token;
      refreshToken = data.refresh_token;
      localStorage.setItem('accessToken', accessToken);
      localStorage.setItem('refreshToken', refreshToken);
      return true;
    }
  } catch (e) {}
  return false;
}

// ─── NOTIFICATIONS ───
function notify(msg, type = 'info') {
  const el = document.getElementById('notification');
  el.textContent = msg;
  el.className = `notification ${type}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── AUTH ───
function showTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  event.target.classList.add('active');
  document.getElementById('auth-message').textContent = '';
}

function showAuthMessage(msg, isError = true) {
  const el = document.getElementById('auth-message');
  el.textContent = msg;
  el.className = `message ${isError ? 'error' : 'success'}`;
}

async function handleRegister(e) {
  e.preventDefault();
  const res = await api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      username: document.getElementById('reg-username').value,
      email: document.getElementById('reg-email').value,
      password: document.getElementById('reg-password').value,
    }),
  });
  if (res.ok) {
    showAuthMessage('Registered! You can now login.', false);
    document.getElementById('register-form').reset();
  } else {
    const msg = res.data.error || res.data.details ? JSON.stringify(res.data.details || res.data.error) : 'Registration failed';
    showAuthMessage(msg);
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;
  await doLogin(email, password);
}

async function quickLogin(email, password) {
  document.getElementById('login-email').value = email;
  document.getElementById('login-password').value = password;
  await doLogin(email, password);
}

async function doLogin(email, password) {
  const res = await api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  if (res.ok) {
    accessToken = res.data.access_token;
    refreshToken = res.data.refresh_token;
    currentUser = res.data.user;
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
    localStorage.setItem('currentUser', JSON.stringify(currentUser));
    enterApp();
  } else {
    showAuthMessage(res.data.error || 'Login failed');
  }
}

async function handleLogout() {
  await api('/auth/logout', { method: 'POST' });
  accessToken = null;
  refreshToken = null;
  currentUser = null;
  localStorage.clear();
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
  notify('Logged out', 'info');
}

function enterApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
  document.getElementById('user-info').textContent = currentUser.username;
  const roleBadge = document.getElementById('user-role');
  roleBadge.textContent = currentUser.role.replace('_', ' ');
  roleBadge.className = `badge ${currentUser.role}`;
  navigate('dashboard');
}

// ─── NAVIGATION ───
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.remove('hidden');

  // Highlight the correct nav button
  const navBtns = document.querySelectorAll('.nav-btn');
  const pages = ['dashboard', 'records', 'users', 'audit', 'health'];
  const idx = pages.indexOf(page);
  if (idx >= 0 && navBtns[idx]) navBtns[idx].classList.add('active');

  switch (page) {
    case 'dashboard': loadDashboard(); break;
    case 'records': recordsCursor = null; loadRecords(); break;
    case 'users': loadUsers(); break;
    case 'audit': loadAuditLogs(); break;
    case 'health': loadHealth(); break;
  }
}

// ─── DASHBOARD ───
async function loadDashboard() {
  const from = document.getElementById('dash-from').value;
  const to = document.getElementById('dash-to').value;
  const params = from && to ? `?date_from=${from}&date_to=${to}` : '';

  // Summary
  const summary = await api(`/dashboard/summary${params}`);
  if (summary.ok) renderSummaryCards(summary.data);
  else document.getElementById('summary-cards').innerHTML = `<div class="card">${summary.data.error}</div>`;

  // Categories
  const cats = await api(`/dashboard/categories${params}`);
  if (cats.ok) renderCategories(cats.data);

  // Trends
  loadTrends();

  // Recent
  const recent = await api('/dashboard/recent?limit=10');
  if (recent.ok) renderRecentActivity(recent.data.recent_activity);
}

function renderSummaryCards(data) {
  document.getElementById('summary-cards').innerHTML = `
    <div class="stat-card"><div class="label">Total Income</div><div class="value income">&#8377;${formatNum(data.total_income)}</div></div>
    <div class="stat-card"><div class="label">Total Expenses</div><div class="value expense">&#8377;${formatNum(data.total_expenses)}</div></div>
    <div class="stat-card"><div class="label">Net Balance</div><div class="value net">&#8377;${formatNum(data.net_balance)}</div></div>
    <div class="stat-card"><div class="label">Records</div><div class="value">${data.record_count}</div></div>
    <div class="stat-card"><div class="label">Avg Transaction</div><div class="value">&#8377;${formatNum(data.avg_transaction)}</div></div>
    <div class="stat-card"><div class="label">Max Transaction</div><div class="value">&#8377;${formatNum(data.max_transaction)}</div></div>
  `;
}

function renderCategories(data) {
  if (!data.categories.length) {
    document.getElementById('categories-list').innerHTML = '<p style="color:var(--text2)">No data</p>';
    document.getElementById('top-expenses').innerHTML = '';
    document.getElementById('top-income').innerHTML = '';
    return;
  }
  document.getElementById('categories-list').innerHTML = `
    <table>
      <tr><th>Category</th><th>Type</th><th>Total</th><th>%</th><th>Count</th></tr>
      ${data.categories.map(c => `
        <tr>
          <td>${c.name}</td>
          <td><span class="type-${c.type}">${c.type}</span></td>
          <td>&#8377;${formatNum(c.total)}</td>
          <td>${c.percentage}%</td>
          <td>${c.count}</td>
        </tr>
      `).join('')}
    </table>
  `;
  renderTopK('top-expenses', data.top_expense_categories, 'expense');
  renderTopK('top-income', data.top_income_categories, 'income');
}

function renderTopK(elementId, items, type) {
  const el = document.getElementById(elementId);
  if (!items || !items.length) { el.innerHTML = '<p style="color:var(--text2);font-size:12px">No data</p>'; return; }
  const maxVal = Math.max(...items.map(i => parseFloat(i.value || 0)));
  el.innerHTML = items.map(i => {
    const pct = maxVal > 0 ? (parseFloat(i.value) / maxVal * 100) : 0;
    return `
      <div class="topk-item">
        <span>${i.key}</span>
        <span class="type-${type}">&#8377;${formatNum(i.value)}</span>
      </div>
      <div class="topk-bar" style="width:${pct}%;background:var(--${type})"></div>
    `;
  }).join('');
}

async function loadTrends() {
  const period = document.getElementById('trend-period').value;
  const months = document.getElementById('trend-months').value;
  const res = await api(`/dashboard/trends?period=${period}&months=${months}`);

  if (!res.ok) {
    document.getElementById('trends-table').innerHTML = `<p style="color:var(--text2)">${res.data.error || 'Cannot access trends'}</p>`;
    return;
  }

  const trends = res.data.trends;
  document.getElementById('trends-table').innerHTML = `
    <table>
      <tr><th>Period</th><th>Income</th><th>Expense</th><th>Net</th><th>Records</th><th>Visual</th></tr>
      ${trends.map(t => {
        const income = parseFloat(t.income) || 0;
        const expense = parseFloat(t.expense) || 0;
        const maxVal = Math.max(income, expense, 1);
        return `
          <tr>
            <td>${t.period}</td>
            <td class="type-income">&#8377;${formatNum(t.income)}</td>
            <td class="type-expense">&#8377;${formatNum(t.expense)}</td>
            <td style="color:${parseFloat(t.net) >= 0 ? 'var(--income)' : 'var(--expense)'}">&#8377;${formatNum(t.net)}</td>
            <td>${t.count}</td>
            <td style="width:200px">
              <div style="display:flex;gap:2px;align-items:center">
                <div style="height:8px;background:var(--income);border-radius:2px;width:${income/maxVal*100}px"></div>
                <div style="height:8px;background:var(--expense);border-radius:2px;width:${expense/maxVal*100}px"></div>
              </div>
            </td>
          </tr>
        `;
      }).join('')}
    </table>
  `;
}

function renderRecentActivity(records) {
  if (!records.length) {
    document.getElementById('recent-activity').innerHTML = '<p style="color:var(--text2)">No recent activity</p>';
    return;
  }
  document.getElementById('recent-activity').innerHTML = `
    <table>
      <tr><th>Date</th><th>Type</th><th>Category</th><th>Amount</th><th>Description</th></tr>
      ${records.map(r => `
        <tr>
          <td>${r.date}</td>
          <td><span class="type-${r.type}">${r.type}</span></td>
          <td>${r.category}</td>
          <td>&#8377;${formatNum(r.amount)}</td>
          <td style="color:var(--text2)">${r.description || '-'}</td>
        </tr>
      `).join('')}
    </table>
  `;
}

// ─── RECORDS ───
let allRecords = [];

async function loadRecords(append = false) {
  if (!append) { recordsCursor = null; allRecords = []; }
  const type = document.getElementById('filter-type').value;
  const category = document.getElementById('filter-category').value;
  const from = document.getElementById('filter-from').value;
  const to = document.getElementById('filter-to').value;
  const sort = document.getElementById('filter-sort').value;

  let params = `?sort_by=${sort}&sort_order=desc&limit=20`;
  if (type) params += `&type=${type}`;
  if (category) params += `&category=${category}`;
  if (from) params += `&date_from=${from}`;
  if (to) params += `&date_to=${to}`;
  if (recordsCursor) params += `&cursor=${recordsCursor}`;

  const res = await api(`/records${params}`);
  if (!res.ok) {
    document.getElementById('records-table').innerHTML = `<p style="color:var(--text2)">${res.data.error || 'Cannot access records'}</p>`;
    document.getElementById('load-more-btn').style.display = 'none';
    return;
  }

  allRecords = append ? [...allRecords, ...res.data.records] : res.data.records;
  recordsCursor = res.data.pagination.next_cursor;
  document.getElementById('load-more-btn').style.display = res.data.pagination.has_more ? 'inline-block' : 'none';
  renderRecords();
}

function loadMoreRecords() { loadRecords(true); }

function renderRecords() {
  if (!allRecords.length) {
    document.getElementById('records-table').innerHTML = '<p style="color:var(--text2)">No records found</p>';
    return;
  }
  document.getElementById('records-table').innerHTML = `
    <table>
      <tr><th>Date</th><th>Type</th><th>Category</th><th>Amount</th><th>Description</th><th>Tags</th><th>Actions</th></tr>
      ${allRecords.map(r => `
        <tr>
          <td>${r.date}</td>
          <td><span class="type-${r.type}">${r.type}</span></td>
          <td>${r.category}</td>
          <td>&#8377;${formatNum(r.amount)}</td>
          <td style="color:var(--text2);max-width:200px;overflow:hidden;text-overflow:ellipsis">${r.description || '-'}</td>
          <td>${(r.tags || []).map(t => `<span class="badge viewer">${t}</span>`).join(' ')}</td>
          <td>
            <button class="btn tiny" onclick="editRecord('${r.id}')">Edit</button>
            <button class="btn tiny danger" onclick="deleteRecord('${r.id}')">Del</button>
            <button class="btn tiny danger" onclick="hardDeleteRecord('${r.id}')">Hard</button>
          </td>
        </tr>
      `).join('')}
    </table>
  `;
}

async function handleRecordSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('record-id').value;
  const tags = document.getElementById('record-tags').value.split(',').map(t => t.trim()).filter(Boolean);
  const body = {
    amount: document.getElementById('record-amount').value,
    type: document.getElementById('record-type').value,
    category: document.getElementById('record-category').value,
    date: document.getElementById('record-date').value,
    description: document.getElementById('record-description').value,
    tags,
  };

  let res;
  if (id) {
    res = await api(`/records/${id}`, { method: 'PUT', body: JSON.stringify(body) });
  } else {
    res = await api('/records', { method: 'POST', body: JSON.stringify(body) });
  }

  if (res.ok) {
    hideModal('record-modal');
    notify(id ? 'Record updated' : 'Record created', 'success');
    loadRecords();
  } else {
    notify(res.data.error || JSON.stringify(res.data.details || 'Failed'), 'error');
  }
}

function editRecord(id) {
  const record = allRecords.find(r => r.id === id);
  if (!record) return;
  document.getElementById('record-modal-title').textContent = 'Edit Record';
  document.getElementById('record-id').value = id;
  document.getElementById('record-amount').value = record.amount;
  document.getElementById('record-type').value = record.type;
  document.getElementById('record-category').value = record.category;
  document.getElementById('record-date').value = record.date;
  document.getElementById('record-description').value = record.description || '';
  document.getElementById('record-tags').value = (record.tags || []).join(', ');
  showModal('record-modal');
}

async function deleteRecord(id) {
  if (!confirm('Soft delete this record?')) return;
  const res = await api(`/records/${id}`, { method: 'DELETE' });
  if (res.ok) { notify('Record soft deleted', 'success'); loadRecords(); }
  else notify(res.data.error, 'error');
}

async function hardDeleteRecord(id) {
  if (!confirm('PERMANENTLY delete this record? This cannot be undone.')) return;
  const res = await api(`/records/${id}?hard=true`, { method: 'DELETE' });
  if (res.ok) { notify('Record permanently deleted', 'success'); loadRecords(); }
  else notify(res.data.error, 'error');
}

// ─── SEARCH ───
let searchTimeout = null;
async function handleSearch() {
  const q = document.getElementById('search-input').value.trim();
  const dropdown = document.getElementById('search-results');
  clearTimeout(searchTimeout);

  if (q.length < 2) { dropdown.classList.add('hidden'); return; }

  searchTimeout = setTimeout(async () => {
    const res = await api(`/records/search?q=${encodeURIComponent(q)}&limit=8`);
    if (res.ok && res.data.suggestions.length) {
      dropdown.innerHTML = res.data.suggestions.map(s => `
        <div class="search-item" onclick="applySearch('${s.word}')">
          <span>${s.word}</span>
          <span class="source">${s.source}</span>
        </div>
      `).join('');
      dropdown.classList.remove('hidden');
    } else {
      dropdown.classList.add('hidden');
    }
  }, 200);
}

function applySearch(word) {
  document.getElementById('filter-category').value = word;
  document.getElementById('search-input').value = '';
  document.getElementById('search-results').classList.add('hidden');
  loadRecords();
}

// ─── USERS ───
async function loadUsers() {
  const res = await api('/users');
  if (!res.ok) {
    document.getElementById('users-table').innerHTML = `<p style="color:var(--text2)">${res.data.error || 'Cannot access user management'}</p>`;
    return;
  }

  const users = res.data.users;
  document.getElementById('users-table').innerHTML = `
    <table>
      <tr><th>Username</th><th>Email</th><th>Role</th><th>Status</th><th>Last Login</th><th>Created</th><th>Actions</th></tr>
      ${users.map(u => `
        <tr>
          <td>${u.username}</td>
          <td>${u.email}</td>
          <td><span class="badge ${u.role?.name || ''}">${u.role?.name || 'N/A'}</span></td>
          <td>${u.is_active ? '<span style="color:var(--success)">Active</span>' : '<span style="color:var(--danger)">Inactive</span>'}</td>
          <td style="color:var(--text2)">${u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</td>
          <td style="color:var(--text2)">${new Date(u.created_at).toLocaleDateString()}</td>
          <td>
            <button class="btn tiny" onclick="openRoleModal('${u.id}')">Role</button>
            <button class="btn tiny ${u.is_active ? 'danger' : 'success'}" onclick="toggleUserStatus('${u.id}', ${!u.is_active})">${u.is_active ? 'Deactivate' : 'Activate'}</button>
            <button class="btn tiny danger" onclick="deleteUser('${u.id}')">Delete</button>
          </td>
        </tr>
      `).join('')}
    </table>
  `;
}

function openRoleModal(userId) {
  document.getElementById('role-user-id').value = userId;
  showModal('role-modal');
}

async function handleRoleChange(e) {
  e.preventDefault();
  const userId = document.getElementById('role-user-id').value;
  const roleName = document.getElementById('new-role').value;
  const res = await api(`/users/${userId}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role_name: roleName }),
  });
  if (res.ok) { hideModal('role-modal'); notify('Role updated', 'success'); loadUsers(); }
  else notify(res.data.error, 'error');
}

async function toggleUserStatus(userId, isActive) {
  const res = await api(`/users/${userId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ is_active: isActive }),
  });
  if (res.ok) { notify(`User ${isActive ? 'activated' : 'deactivated'}`, 'success'); loadUsers(); }
  else notify(res.data.error, 'error');
}

async function deleteUser(userId) {
  if (!confirm('Delete this user?')) return;
  const res = await api(`/users/${userId}`, { method: 'DELETE' });
  if (res.ok) { notify('User deleted', 'success'); loadUsers(); }
  else notify(res.data.error, 'error');
}

// ─── AUDIT LOGS ───
async function loadAuditLogs() {
  const action = document.getElementById('audit-action').value;
  const resource = document.getElementById('audit-resource').value;
  let params = '?limit=100';
  if (action) params += `&action=${action}`;
  if (resource) params += `&resource=${resource}`;

  const res = await api(`/audit-logs${params}`);
  if (!res.ok) {
    document.getElementById('audit-table').innerHTML = `<p style="color:var(--text2)">${res.data.error || 'Cannot access audit logs'}</p>`;
    return;
  }

  const logs = res.data.audit_logs;
  document.getElementById('audit-table').innerHTML = `
    <table>
      <tr><th>Time</th><th>Action</th><th>Resource</th><th>Resource ID</th><th>IP</th><th>Changes</th></tr>
      ${logs.map(l => `
        <tr>
          <td style="white-space:nowrap">${l.timestamp ? new Date(l.timestamp).toLocaleString() : '-'}</td>
          <td><span class="badge ${l.action === 'create' ? 'manager' : l.action === 'delete' || l.action === 'soft_delete' ? 'admin' : 'analyst'}">${l.action}</span></td>
          <td>${l.resource}</td>
          <td style="font-size:11px;color:var(--text2)">${l.resource_id ? l.resource_id.substring(0, 8) + '...' : '-'}</td>
          <td style="color:var(--text2)">${l.ip_address || '-'}</td>
          <td style="font-size:11px;max-width:250px;overflow:hidden;text-overflow:ellipsis">${l.new_value ? JSON.stringify(l.new_value) : '-'}</td>
        </tr>
      `).join('')}
    </table>
    <p style="color:var(--text2);font-size:12px;margin-top:8px">Showing ${logs.length} entries</p>
  `;
}

// ─── HEALTH ───
async function loadHealth() {
  const res = await api('/health');
  if (!res.ok) {
    document.getElementById('health-status').innerHTML = '<p style="color:var(--danger)">Cannot reach backend</p>';
    return;
  }

  const s = res.data.services;
  document.getElementById('health-status').innerHTML = `
    <div class="health-card">
      <div class="health-dot ${res.data.status === 'healthy' ? 'healthy' : 'unhealthy'}"></div>
      <div><strong>Overall Status:</strong> ${res.data.status.toUpperCase()}</div>
    </div>
    ${Object.entries(s).map(([name, status]) => `
      <div class="health-card">
        <div class="health-dot ${status === 'healthy' ? 'healthy' : status.includes('unavailable') ? 'unavailable' : 'unhealthy'}"></div>
        <div><strong>${name.charAt(0).toUpperCase() + name.slice(1)}:</strong> ${status}</div>
      </div>
    `).join('')}
  `;
}

// ─── MODALS ───
function showModal(id) {
  document.getElementById(id).classList.remove('hidden');
  if (id === 'record-modal' && !document.getElementById('record-id').value) {
    document.getElementById('record-modal-title').textContent = 'New Record';
    document.getElementById('record-form').reset();
    document.getElementById('record-date').value = new Date().toISOString().split('T')[0];
  }
}

function hideModal(id) {
  document.getElementById(id).classList.add('hidden');
  if (id === 'record-modal') document.getElementById('record-id').value = '';
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    e.target.classList.add('hidden');
  }
});

// ─── UTILS ───
function formatNum(n) {
  const num = parseFloat(n) || 0;
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ─── INIT ───
(function init() {
  accessToken = localStorage.getItem('accessToken');
  refreshToken = localStorage.getItem('refreshToken');
  const saved = localStorage.getItem('currentUser');
  if (saved) currentUser = JSON.parse(saved);

  if (accessToken && currentUser) {
    enterApp();
  }
})();
