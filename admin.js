import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm';

// 1. Config & State
const APP_CONFIG = window.__APP_CONFIG__ || {};
const SUPABASE_URL = APP_CONFIG.supabaseUrl || '';
const SUPABASE_ANON_KEY = APP_CONFIG.supabaseAnonKey || '';
const CAFES_TABLE = APP_CONFIG.cafesTable || 'cafes';
const ADMIN_USERS_TABLE = APP_CONFIG.adminUsersTable || 'admin_users';
const STORAGE_BUCKET = APP_CONFIG.storageBucket || 'cafe-images';
const ADMIN_API_BASE = APP_CONFIG.adminApiBase || window.location.origin;

const state = {
  supabase: null,
  session: null,
  isAdmin: false,
  cafes: [],
  comments: [],
  dirty: new Map(),
  uploaded: new Set(),
  saving: new Set(),
  filters: { search: '', status: 'all' },
};

const dom = {};

// 2. Helpers
function $(id) { return document.getElementById(id); }

function escapeHTML(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function toast(message, type = 'success') {
  if (!dom.toast) return;
  dom.toast.textContent = message;
  dom.toast.className = `toast ${type} show`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => dom.toast.classList.remove('show'), 2600);
}

function setAuthStatus(text) {
  if (dom.authStatus) dom.authStatus.textContent = text;
}

// 3. Initialization
function initDom() {
  dom.loginPanel = $('loginPanel');
  dom.emailInput = $('emailInput');
  dom.passwordInput = $('passwordInput');
  dom.loginBtn = $('loginBtn');
  dom.logoutBtn = $('logoutBtn');
  dom.scraperBtn = $('scraperBtn');
  dom.saveAllBtn = $('saveAllBtn');
  dom.refreshBtn = $('refreshBtn');
  dom.scraperQuery = $('scraperQuery');
  dom.scraperMode = $('scraperMode');
  dom.scraperMaxNew = $('scraperMaxNew');
  dom.statsBar = $('statsBar');
  dom.filtersBar = $('filtersBar');
  dom.dashboard = $('dashboard');
  dom.accessDenied = $('accessDenied');
  dom.cafeGrid = $('cafeGrid');
  dom.emptyState = $('emptyState');
  dom.totalCount = $('totalCount');
  dom.activeCount = $('activeCount');
  dom.inactiveCount = $('inactiveCount');
  dom.dirtyCount = $('dirtyCount');
  dom.uploadedCount = $('uploadedCount');
  dom.searchInput = $('searchInput');
  dom.statusFilter = $('statusFilter');
  dom.clearFiltersBtn = $('clearFiltersBtn');
  dom.toast = $('toast');
  dom.authStatus = $('authStatus');
  dom.consoleOverlay = $('consoleOverlay');
  dom.consoleBody = $('consoleBody');
  dom.closeConsoleBtn = $('closeConsoleBtn');
  dom.commentSection = $('commentSection');
  dom.commentTableBody = $('commentTableBody');
}

function initSupabase() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null;
  try {
    return createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  } catch (e) {
    console.error('Supabase init failed', e);
    return null;
  }
}

// 4. Data Helpers
function normalizeCafe(row) {
  return {
    ...row,
    active: row.active !== false,
    image_url: row.image_url || row.image || '',
    image_path: row.image_path || '',
    one_liner: row.one_liner || row.oneLiner || '',
    description: row.description || row.desc || '',
  };
}
function cafeId(cafe) { return cafe.id || cafe.slug || cafe.name; }
function getFieldValue(card, field) {
  const el = card.querySelector(`[data-field="${field}"]`);
  if (!el) return '';
  return el.type === 'checkbox' ? el.checked : el.value;
}
function setFieldValue(card, field, value) {
  const el = card.querySelector(`[data-field="${field}"]`);
  if (!el) return;
  if (el.type === 'checkbox') el.checked = Boolean(value);
  else el.value = value ?? '';
}

// 5. Auth Handlers
async function handleLogin() {
  const email = dom.emailInput.value.trim();
  const password = dom.passwordInput.value;
  if (!email || !password) return toast('이메일/비밀번호를 입력하세요.', 'error');
  setAuthStatus('상태: 로그인 시도 중...');
  const { data, error } = await state.supabase.auth.signInWithPassword({ email, password });
  if (error) {
    setAuthStatus('상태: 로그인 실패');
    return toast(error.message, 'error');
  }
  state.session = data.session;
  await afterAuth();
}

async function handleLogout() {
  await state.supabase.auth.signOut();
  state.session = null; state.isAdmin = false; state.cafes = [];
  localStorage.removeItem('is_admin_cache');
  setAuthStatus('상태: 로그아웃됨');
  render();
}

async function checkAdmin() {
  const userId = state.session?.user?.id;
  if (!userId) return false;
  setAuthStatus('상태: 관리자 확인 중...');
  const query = state.supabase.from(ADMIN_USERS_TABLE).select('user_id').eq('user_id', userId).maybeSingle();
  const timeout = new Promise(r => setTimeout(() => r({ timeout: true }), 30000));
  const res = await Promise.race([query, timeout]);
  if (res?.timeout) {
    setAuthStatus(state.isAdmin ? '상태: 확인 지연 (기존 권한 유지)' : '상태: 확인 지연');
    return state.isAdmin;
  }
  if (res.error) return state.isAdmin;
  const isNowAdmin = Boolean(res.data);
  state.isAdmin = isNowAdmin;
  if (isNowAdmin) localStorage.setItem('is_admin_cache', 'true');
  setAuthStatus(isNowAdmin ? '상태: 관리자 확인 완료' : '상태: 권한 없음');
  return isNowAdmin;
}

async function afterAuth() {
  const isNowAdmin = await checkAdmin();
  if (!isNowAdmin) {
    render();
    return toast('관리자 권한이 없습니다.', 'error');
  }
  dom.loginPanel.classList.add('hidden');
  dom.accessDenied.classList.add('hidden');
  dom.statsBar.classList.remove('hidden');
  dom.filtersBar.classList.remove('hidden');
  dom.dashboard.classList.remove('hidden');
  dom.logoutBtn.disabled = false;
  dom.scraperBtn.disabled = false;
  dom.saveAllBtn.disabled = false;
  await Promise.all([loadCafes(), loadComments()]);
}

async function loadSessionAndMaybeOpen() {
  const { data } = await state.supabase.auth.getSession();
  state.session = data.session || null;
  if (state.session) {
    state.isAdmin = localStorage.getItem('is_admin_cache') === 'true';
    await afterAuth();
  } else {
    setAuthStatus('상태: 로그인 대기 중');
    render();
  }
}

// 6. Data Fetch/Save
async function loadCafes() {
  const { data, error } = await state.supabase.from(CAFES_TABLE).select('*').order('active', { ascending: false }).order('updated_at', { ascending: false });
  if (error) return toast('불러오기 실패', 'error');
  state.cafes = (data || []).map(normalizeCafe);
  if (state.cafes.length > 0) { state.isAdmin = true; localStorage.setItem('is_admin_cache', 'true'); }
  render();
}

async function saveCafe(card) {
  const id = card.dataset.id;
  const cafe = state.cafes.find(c => String(cafeId(c)) === String(id));
  if (!cafe || state.saving.has(id)) return;
  
  const payload = {
    ...cafe,
    active: getFieldValue(card, 'active'),
    name: getFieldValue(card, 'name'),
    image_url: getFieldValue(card, 'image_url'),
    one_liner: getFieldValue(card, 'one_liner')
  };

  state.saving.add(id);
  const { error } = await state.supabase.from(CAFES_TABLE).update(payload).eq('id', cafe.id);
  state.saving.delete(id);
  
  if (error) toast('저장 실패', 'error');
  else { 
    state.dirty.delete(id); 
    // If the image_url was updated to a local path, ensure it remains after render
    const updatedCafe = state.cafes.find(c => String(cafeId(c)) === String(id));
    if (updatedCafe) {
      updatedCafe.name = payload.name;
      updatedCafe.active = payload.active;
      updatedCafe.image_url = payload.image_url;
      updatedCafe.one_liner = payload.one_liner;
    }
    renderStats(); 
    toast('저장 완료'); 
  }
}

async function saveAll() {
  for (const id of state.dirty.keys()) {
    const card = dom.cafeGrid.querySelector(`[data-id="${id}"]`);
    if (card) await saveCafe(card);
  }
}

async function uploadImage(card, file) {
  if (!state.session) return toast('로그인이 필요합니다.', 'error');
  
  toast('사진 업로드 중...', 'info');
  try {
    const res = await fetch(`${ADMIN_API_BASE}/api/admin/upload-image`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${state.session.access_token}`,
        'X-File-Name': file.name,
        'Content-Type': file.type || 'image/jpeg'
      },
      body: await file.arrayBuffer()
    });
    
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Upload failed');
    }
    
    const data = await res.json();
    setFieldValue(card, 'image_url', data.url);
    state.dirty.set(card.dataset.id, true);
    renderStats();
    toast('사진 업로드 성공');
  } catch (e) {
    toast(`업로드 실패: ${e.message}`, 'error');
  }
}

async function loadComments() {
  const { data, error } = await state.supabase
    .from('cafe_comments')
    .select(`
      *,
      cafes ( name )
    `)
    .order('created_at', { ascending: false });
    
  if (error) {
    console.error('Comments load failed:', error);
    return;
  }
  
  state.comments = data || [];
  renderComments();
}

async function deleteComment(id) {
  if (!confirm('정말 이 댓글을 삭제하시겠습니까?')) return;
  
  const { error } = await state.supabase.from('cafe_comments').delete().eq('id', id);
  if (error) toast('댓글 삭제 실패', 'error');
  else {
    toast('댓글 삭제 완료');
    state.comments = state.comments.filter(c => c.id !== id);
    renderComments();
  }
}

// 7. Rendering
function renderStats() {
  if (!dom.totalCount) return;
  const total = state.cafes.length, active = state.cafes.filter(c => c.active).length;
  dom.totalCount.textContent = total; dom.activeCount.textContent = active; dom.inactiveCount.textContent = total - active;
  dom.dirtyCount.textContent = state.dirty.size; dom.uploadedCount.textContent = state.uploaded.size;
}

function renderCard(cafe) {
  const id = cafeId(cafe), dirty = state.dirty.has(String(id)), imageSrc = cafe.image_url || '';
  return `
    <article class="card cafe-card" data-id="${escapeHTML(id)}">
      <div class="cafe-inner">
        <div class="top-row">
          <label class="thumb"><img src="${escapeHTML(imageSrc)}" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 400 300\"%3E%3Crect width=\"400\" height=\"300\" fill=\"%23111827\"/%3E%3C/svg%3E'"><input type="file" style="display:none" /></label>
          <div style="flex:1">
            <div class="title-line"><h3>${escapeHTML(cafe.name)}</h3><div class="badge ${cafe.active?'active':'inactive'}">${cafe.active?'활성':'비활성'}</div></div>
          </div>
        </div>
        <div class="actions">
          <label><input type="checkbox" data-field="active" ${cafe.active?'checked':''} /> 활성</label>
          <div class="spacer"></div>
          <button class="primary" data-action="upload-trigger">사진 업로드</button>
          <button class="danger" data-action="save-cafe">저장</button>
        </div>
        <div class="field-grid">
          <div class="field full"><label>이름</label><input data-field="name" value="${escapeHTML(cafe.name)}" /></div>
          <div class="field full"><label>이미지 URL</label><input data-field="image_url" value="${escapeHTML(cafe.image_url)}" /></div>
          <div class="field full"><label>한줄평</label><textarea data-field="one_liner">${escapeHTML(cafe.one_liner)}</textarea></div>
        </div>
        
        <!-- Individual Cafe Comments Section -->
        <div class="card-comments" style="margin-top: 12px; border-top: 1px solid rgba(255,255,255,.06); padding-top: 12px;">
          <h4 style="margin: 0 0 8px; font-size: 0.85rem; color: var(--muted);">실시간 댓글</h4>
          <div class="comment-list">
            ${(state.comments.filter(c => c.cafe_id === cafe.id)).map(c => `
              <div style="display: flex; gap: 8px; margin-bottom: 6px; font-size: 0.85rem; background: rgba(255,255,255,0.03); padding: 6px; border-radius: 8px;">
                <div style="flex: 1;">${escapeHTML(c.comment_text)}</div>
                <button class="danger ghost" style="padding: 2px 6px; font-size: 0.7rem;" onclick="window.MCG_ADMIN.deleteComment('${c.id}')">삭제</button>
              </div>
            `).join('') || '<div style="font-size: 0.8rem; color: var(--muted); opacity: 0.6;">아직 댓글이 없습니다.</div>'}
          </div>
        </div>
      </div>
    </article>
  `;
}

function render() {
  renderStats();
  if (!state.session) { dom.loginPanel.classList.remove('hidden'); dom.dashboard.classList.add('hidden'); return; }
  if (!state.isAdmin) { dom.accessDenied.classList.remove('hidden'); dom.loginPanel.classList.add('hidden'); return; }
  const filtered = state.cafes.filter(c => {
    const hay = (c.name + ' ' + (c.suburb||'')).toLowerCase();
    if (state.filters.search && !hay.includes(state.filters.search)) return false;
    if (state.filters.status === 'active' && !c.active) return false;
    if (state.filters.status === 'inactive' && c.active) return false;
    return true;
  });
  dom.cafeGrid.innerHTML = filtered.map(renderCard).join('');
  bindCardEvents();
}

function renderComments() {
  // Break the loop: Instead of calling another function, just trigger render
  render(); 
}

function bindCardEvents() {
  dom.cafeGrid.querySelectorAll('.cafe-card').forEach(card => {
    card.querySelectorAll('input, textarea').forEach(el => el.addEventListener('input', () => { state.dirty.set(card.dataset.id, true); renderStats(); }));
    card.querySelector('[data-action="save-cafe"]').addEventListener('click', () => saveCafe(card));
    
    // Upload trigger
    const fileInput = card.querySelector('input[type="file"]');
    card.querySelector('[data-action="upload-trigger"]').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      if (e.target.files?.[0]) uploadImage(card, e.target.files[0]);
    });
  });
}

// 8. Scraper Console
function appendLog(text) {
  if (!dom.consoleBody) return;
  const div = document.createElement('div'); div.className = 'log-line';
  if (text.includes('[ERROR]')) div.style.color = '#ff7b72';
  if (text.includes('[SUCCESS]')) div.style.color = '#3fb950';
  div.textContent = text;
  dom.consoleBody.appendChild(div);
  dom.consoleBody.scrollTop = dom.consoleBody.scrollHeight;
}

async function runScraper() {
  if (!state.session) return;
  dom.scraperBtn.disabled = true; dom.consoleBody.textContent = ''; dom.consoleOverlay.classList.add('show');
  appendLog('[INFO] 스크래퍼 구동 시작...');
  try {
    const res = await fetch(`${ADMIN_API_BASE}/api/admin/run-scraper`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${state.session.access_token}` },
      body: JSON.stringify({ query: dom.scraperQuery.value, mode: dom.scraperMode.value, maxNew: dom.scraperMaxNew.value })
    });
    const reader = res.body.getReader(), decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      appendLog(decoder.decode(value, { stream: true }));
    }
  } catch (e) { appendLog(`[ERROR] ${e.message}`); } finally { dom.scraperBtn.disabled = false; }
}

// 9. Events
function bindEvents() {
  dom.loginBtn.addEventListener('click', handleLogin);
  dom.logoutBtn.addEventListener('click', handleLogout);
  dom.scraperBtn.addEventListener('click', runScraper);
  dom.saveAllBtn.addEventListener('click', saveAll);
  dom.closeConsoleBtn.addEventListener('click', () => dom.consoleOverlay.classList.remove('show'));
  dom.refreshBtn.addEventListener('click', () => { loadCafes(); loadComments(); });
  dom.searchInput?.addEventListener('input', e => { state.filters.search = e.target.value.toLowerCase(); render(); });
  dom.statusFilter?.addEventListener('change', e => { state.filters.status = e.target.value; render(); });
}

// 10. Start
window.addEventListener('load', async () => {
  initDom();
  // Expose for inline handlers
  window.MCG_ADMIN = { deleteComment };
  state.supabase = initSupabase();
  bindEvents();
  await loadSessionAndMaybeOpen();
});
