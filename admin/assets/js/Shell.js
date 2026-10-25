/**
 * North Voice Newsroom Shell Renderer
 * Provides unified English navigation, dynamic authenticated user profiles,
 * route protection, and action button loading spinners.
 */

export const NAV = [
  {
    label: 'NEWSROOM',
    items: [
      { key: 'dashboard', text: 'Dashboard', href: 'index.html',
        icon: '<path d="M3 12 12 3l9 9"/><path d="M5 10v10h14V10"/>' },
      { key: 'news-hunter', text: 'Live News Hunter', href: 'live-hunt.html', badge: { kind: 'new', text: 'LIVE' },
        icon: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>' },
      { key: 'posts', text: 'Published Posts', href: 'posts.html',
        icon: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 16h18M9 4v16"/>' },
      { key: 'custom-post', text: 'Custom Post Studio', href: 'custom-post.html',
        icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4z"/>' },
    ],
  },
  {
    label: 'EDITORIAL STAFF',
    items: [
      { key: 'staff', text: 'Staff Directory & Roles', href: 'staff.html', badge: { kind: 'pro', text: 'ROLES' },
        icon: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>' },
      { key: 'profile', text: 'My Profile', href: 'profile.html',
        icon: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
    ],
  },
  {
    label: 'SYSTEM & SETTINGS',
    items: [
      { key: 'spam-monitor', text: 'Meta Spam Monitor', href: 'spam-monitor.html',
        icon: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>' },
      { key: 'settings', text: 'Database & API Keys', href: 'settings.html',
        icon: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' },
      { key: 'signout', text: 'Sign Out', href: 'javascript:void(0)',
        icon: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>' },
    ],
  },
];

const BRAND_LOGO = `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg">
  <rect width="36" height="36" rx="8" fill="#EF4444"/>
  <path fill="#ffffff" d="M10 26V10h3.5l8.5 11.5V10h4v16h-3.5L14 14.5V26h-4z"/>
</svg>`;

const CHEV = '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m9 18 6-6-6-6"/></svg>';

export function getAuthUser() {
  try {
    const raw = localStorage.getItem('north_auth_user');
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return {
    id: "stf_001",
    name: "Mohiuddin Kader",
    role: "editor_in_chief",
    role_en: "Editor-in-Chief",
    email: "editor@northvoice.com",
    avatar_initials: "MK",
    phone: "+880 1700-000001",
    bureau: "Central News Desk"
  };
}

export function checkAuth() {
  const path = window.location.pathname;
  if (path.endsWith('signin.html') || path.endsWith('signup.html')) {
    return;
  }
  const user = localStorage.getItem('north_auth_user');
  if (!user) {
    window.location.href = 'signin.html';
  }
}

window.logout = function() {
  localStorage.removeItem('north_auth_user');
  localStorage.removeItem('north_auth_token');
  window.location.href = 'signin.html';
};

window.setBtnLoading = function(btn, loading, text) {
  if (!btn) return;
  if (loading) {
    btn.dataset.origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.classList.add('is-loading');
    btn.innerHTML = `<span class="btn-spinner"></span> <span>${text || 'Processing...'}</span>`;
  } else {
    btn.disabled = false;
    btn.classList.remove('is-loading');
    if (btn.dataset.origHtml) {
      btn.innerHTML = btn.dataset.origHtml;
    }
  }
};

function renderNavLink(item, activeKey) {
  const active = item.key === activeKey ? ' is-active' : '';
  const badge = item.badge
    ? `<span class="nav-badge ${item.badge.kind}">${item.badge.text}</span>`
    : '';
  
  if (item.key === 'signout') {
    return `
      <a class="nav-link danger" href="javascript:void(0)" onclick="window.logout()">
        <svg viewBox="0 0 24 24">${item.icon}</svg>
        <span>${item.text}</span>
      </a>`;
  }

  const external = /^https?:\/\//.test(item.href) ? ' target="_blank" rel="noopener noreferrer"' : '';
  return `
    <a class="nav-link${active}" href="${item.href}"${external}>
      <svg viewBox="0 0 24 24">${item.icon}</svg>
      <span>${item.text}</span>
      ${badge}
    </a>`;
}

function renderNavGroup(item, activeKey) {
  const open = item.children.some((c) => c.key === activeKey) ? ' is-open' : '';
  const submenu = item.children
    .map((c) => `<a href="${c.href}">${c.text}</a>`)
    .join('');
  return `
    <div class="nav-item-group${open}" data-nav-group>
      <a class="nav-link" href="javascript:void(0)" data-nav-toggle>
        <svg viewBox="0 0 24 24">${item.icon}</svg>
        <span>${item.text}</span>
        ${CHEV}
      </a>
      <div class="nav-submenu">${submenu}</div>
    </div>`;
}

function renderSection(section, activeKey) {
  const items = section.items.map((item) => (
    item.children ? renderNavGroup(item, activeKey) : renderNavLink(item, activeKey)
  )).join('');
  return `
    <nav class="nav-section">
      <div class="nav-label">${section.label}</div>
      ${items}
    </nav>`;
}

function renderSidebar(activeKey) {
  const user = getAuthUser();
  const sections = NAV.map((s) => renderSection(s, activeKey)).join('');
  return `
    <aside class="d-sidebar">
      <div class="brand">
        <div class="brand-logo">${BRAND_LOGO}</div>
        <div class="brand-text">
          <div class="brand-name">North Voice</div>
          <div class="brand-tag">Newsroom Engine · v2.0</div>
        </div>
      </div>
      ${sections}
      <div class="sidebar-footer">
        <a href="profile.html" class="workspace" style="text-decoration:none;">
          <div class="workspace-avatar" style="background:#EF4444; color:#fff; font-weight:700;">${user.avatar_initials || 'NV'}</div>
          <div class="workspace-text">
            <div class="workspace-name">${user.name}</div>
            <div class="workspace-role">${user.role_en || user.role || 'Editorial Staff'}</div>
          </div>
          <svg class="workspace-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="m7 9 5-5 5 5"/><path d="m7 15 5 5 5-5"/>
          </svg>
        </a>
      </div>
    </aside>`;
}

function renderCrumbs(crumbsAttr) {
  if (!crumbsAttr) return '';
  const parts = crumbsAttr.split('|').map((p) => p.trim()).filter(Boolean);
  const sep = '<svg class="sep" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>';
  return parts.map((p, i) => {
    const cls = i === parts.length - 1 ? ' class="current"' : '';
    return `${i > 0 ? sep : ''}<span${cls}>${p}</span>`;
  }).join('');
}

function renderTopbar(crumbsAttr) {
  const user = getAuthUser();
  return `
    <header class="d-topbar">
      <div class="crumbs">
        <button class="hamburger" data-drawer-open aria-label="Open navigation">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
        ${renderCrumbs(crumbsAttr)}
      </div>
      <div class="topbar-actions">
        <a href="live-hunt.html" class="btn btn--sm btn--primary" style="display:inline-flex; align-items:center; gap:6px;">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
          <span>Scan Live News</span>
        </a>

        <div class="dd-wrap">
          <div class="avatar" data-dropdown tabindex="0" role="button" aria-label="Account menu" style="background:#EF4444; color:#fff; font-weight:700;">${user.avatar_initials || 'NV'}</div>
          <div class="dd-menu dd-profile" role="menu">
            <div class="dd-profile-head">
              <div class="dd-profile-name">${user.name}</div>
              <div class="dd-profile-email">${user.email}</div>
            </div>
            <a class="dd-menu-item" href="profile.html">
              <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              My Profile
            </a>
            <a class="dd-menu-item" href="settings.html">
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              Database & API Settings
            </a>
            <div class="dd-divider"></div>
            <a class="dd-menu-item danger" href="javascript:void(0)" onclick="window.logout()">
              <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>
              Sign Out
            </a>
          </div>
        </div>
      </div>
    </header>`;
}

function renderFooter() {
  return `
    <footer class="d-footer">
      <div>© 2026 North Voice Media Network · Autonomous Newsroom Engine</div>
      <div class="d-footer-meta">
        <span>v2.2.0</span>
        <span style="color:#10B981; font-weight:600;">● System Operational</span>
      </div>
    </footer>`;
}

export function mountShell() {
  // Ensure route protection
  checkAuth();

  const body = document.body;
  const activeKey = body.getAttribute('data-active') || '';
  const crumbs = body.getAttribute('data-crumbs') || '';

  const sidebarHost = document.querySelector('[data-shell-sidebar]');
  const topbarHost  = document.querySelector('[data-shell-topbar]');
  const footerHost  = document.querySelector('[data-shell-footer]');

  if (sidebarHost) sidebarHost.outerHTML = renderSidebar(activeKey);
  if (topbarHost)  topbarHost.outerHTML  = renderTopbar(crumbs);
  if (footerHost)  footerHost.outerHTML  = renderFooter();
}
