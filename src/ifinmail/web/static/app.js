const API = window.location.origin;

let state = {
  token: localStorage.getItem("ifinmail_token") || null,
  refreshToken: localStorage.getItem("ifinmail_refresh") || null,
  email: localStorage.getItem("ifinmail_email") || null,
  isAdmin: localStorage.getItem("ifinmail_is_admin") === "true",
  accounts: JSON.parse(localStorage.getItem("ifinmail_accounts") || "[]"),
  folder: "INBOX",
  messages: [],
  currentMsg: null,
  page: 1,
  totalCount: 0,
  perPage: 50,
  loading: false,
  hasMore: true,
  searchQuery: "",
};

let _refreshing = null;

async function apiFetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (state.token) opts.headers["Authorization"] = `Bearer ${state.token}`;
  let res = await fetch(url, opts);
  if (res.status === 401 && state.refreshToken) {
    if (!_refreshing) {
      _refreshing = (async () => {
        try {
          const r = await fetch(`${API}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: state.refreshToken }),
          });
          if (r.ok) {
            const data = await r.json();
            state.token = data.access_token;
            localStorage.setItem("ifinmail_token", state.token);
            if (data.is_admin !== undefined) {
              state.isAdmin = data.is_admin;
              localStorage.setItem("ifinmail_is_admin", String(state.isAdmin));
              const adminNav = document.getElementById("adminNav");
              if (adminNav) adminNav.style.display = state.isAdmin ? "" : "none";
            }
            // update accounts too
            if (state.email) {
            state.accounts = state.accounts.map(a =>
              a.email === state.email ? { ...a, token: state.token, refreshToken: state.refreshToken } : a
            );
              saveAccounts();
            }
          } else {
            state.token = null;
            state.refreshToken = null;
            localStorage.removeItem("ifinmail_token");
            localStorage.removeItem("ifinmail_refresh");
            // remove invalid account from list
            if (state.email) {
              state.accounts = state.accounts.filter(a => a.email !== state.email);
              saveAccounts();
            }
            render();
            return null;
          }
        } catch {}
      })();
    }
    await _refreshing;
    _refreshing = null;
    if (state.token) {
      opts.headers["Authorization"] = `Bearer ${state.token}`;
      res = await fetch(url, opts);
    }
  }
  return res;
}

function saveAccounts() {
  localStorage.setItem("ifinmail_accounts", JSON.stringify(state.accounts));
}

function switchAccount(email, token, refreshToken) {
  state.token = token;
  state.refreshToken = refreshToken || null;
  state.email = email;
  state.messages = [];
  state.currentMsg = null;
  state.folder = "INBOX";
  state.page = 1;
  localStorage.setItem("ifinmail_token", token);
  if (state.refreshToken) {
    localStorage.setItem("ifinmail_refresh", state.refreshToken);
  } else {
    localStorage.removeItem("ifinmail_refresh");
  }
  localStorage.setItem("ifinmail_email", email);
  state.accounts = state.accounts.filter(a => a.email !== email);
  state.accounts.push({ email, token, refreshToken: state.refreshToken });
  saveAccounts();
  render();
}



let _sentinelObserver = null;

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

// ── Views ──

function showView(name) {
  ["loginView", "inboxView", "messageView", "composeView", "settingsView", "adminView"].forEach(id => {
    document.getElementById(id).style.display = id === name + "View" ? "block" : "none";
  });
}

function render() {
  if (!state.token) {
    showView("login");
    $("#sidebar").innerHTML = "";
    return;
  }
  renderSidebar();
  document.getElementById("inboxView").innerHTML = document.getElementById("inboxTmpl").innerHTML;
  showView("inbox");
  fetchMessages();
  setupBatchBar();
  setupTrashToolbar();
  renderCustomFolders();
  document.getElementById("markAllReadBtn")?.addEventListener("click", markAllRead);
}

// ── Sidebar ──

function renderSidebar() {
  const tmpl = document.getElementById("sidebarTmpl");
  $("#sidebar").innerHTML = tmpl.innerHTML;
  document.getElementById("userEmail").textContent = state.email;

  const accList = document.getElementById("accountsListSidebar");
  if (accList) {
    const colors = ["#4361ee","#e63946","#2ec4b6","#ff9f1c","#7209b7","#f72585","#06d6a0","#ef476f"];
    state.accounts.forEach((a, i) => {
      const wrapper = document.createElement("div");
      wrapper.className = "ifinmail-account-avatar-wrapper" + (a.email === state.email ? " active" : "");
      const initial = a.email.charAt(0).toUpperCase();
      // In future: check a.profilePic for <img>, fall back to initial
      wrapper.innerHTML = `<div class="ifinmail-account-avatar" style="background:${colors[i % colors.length]}" title="${a.email}">${initial}</div>`;
      wrapper.onclick = () => switchAccount(a.email, a.token, a.refreshToken);
      accList.appendChild(wrapper);
    });
  }
  document.getElementById("accountsAddBtn").onclick = showAddAccount;

  document.querySelectorAll(".ifinmail-nav-item").forEach(el => {
    el.addEventListener("click", () => {
      if (!el.dataset.folder) return;
      state.folder = el.dataset.folder;
      state.currentMsg = null;
      showView("inbox");
      fetchMessages();
      document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
      el.classList.add("active");
      updateHash();
    });
    if (el.dataset.folder === state.folder) el.classList.add("active");
  });

  document.getElementById("composeBtn").addEventListener("click", () => showCompose());
  document.getElementById("logoutBtn").addEventListener("click", logout);
  document.getElementById("darkModeToggle").addEventListener("click", toggleDark);
  document.getElementById("settingsNav").addEventListener("click", () => {
    state.currentMsg = null;
    showView("settings");
    renderSettings();
  });
  const adminNav = document.getElementById("adminNav");
  if (adminNav) {
    adminNav.style.display = state.isAdmin ? "" : "none";
    adminNav.addEventListener("click", () => {
      state.currentMsg = null;
      showView("admin");
      renderAdmin();
    });
  }

  fetchFolderCounts();
}

function toggleDark() {
  const html = document.documentElement;
  const isDark = html.getAttribute("data-theme") === "dark";
  if (isDark) {
    html.removeAttribute("data-theme");
    localStorage.setItem("ifinmail_dark", "0");
  } else {
    html.setAttribute("data-theme", "dark");
    localStorage.setItem("ifinmail_dark", "1");
  }
  const label = document.getElementById("darkModeLabel");
  if (label) label.textContent = html.getAttribute("data-theme") === "dark" ? "Light" : "Dark";
}
if (localStorage.getItem("ifinmail_dark") === "1") {
  document.documentElement.setAttribute("data-theme", "dark");
}

async function renderSettings() {
  const tmpl = document.getElementById("settingsTmpl");
  document.getElementById("settingsView").innerHTML = tmpl.innerHTML;

  // Load vacation
  try {
    const res = await apiFetch(`${API}/mail/settings/vacation`);
    if (res.ok) {
      const data = await res.json();
      document.getElementById("vacationSubject").value = data.subject || "";
      document.getElementById("vacationBody").value = data.body || "";
      document.getElementById("vacationEnabled").checked = data.enabled;
    }
  } catch {}

  document.getElementById("saveVacation").addEventListener("click", async () => {
    document.getElementById("vacationError").textContent = "";
    try {
      const subject = document.getElementById("vacationSubject").value;
      const body = document.getElementById("vacationBody").value;
      const enabled = document.getElementById("vacationEnabled").checked;
      const res = await apiFetch(`${API}/mail/settings/vacation`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body, enabled }),
      });
      if (!res.ok) { document.getElementById("vacationError").textContent = "Failed to save"; return; }
      document.getElementById("vacationError").style.color = "green";
      document.getElementById("vacationError").textContent = "Saved";
    } catch { document.getElementById("vacationError").textContent = "Network error"; }
  });

  // Load forwarding
  async function loadForwarding() {
    try {
      const res = await apiFetch(`${API}/mail/settings/forwarding`);
      if (res.ok) {
        const rules = await res.json();
        const list = document.getElementById("forwardingList");
        list.innerHTML = "";
        rules.forEach(r => {
          const row = document.createElement("div");
          row.className = "ifinmail-forwarding-row";
          row.innerHTML = `<span>${r.target_email}</span>`;
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Remove";
          del.onclick = async () => {
            await apiFetch(`${API}/mail/settings/forwarding/${r.id}`, {
              method: "DELETE",
            });
            loadForwarding();
          };
          row.appendChild(del);
          list.appendChild(row);
        });
      }
    } catch {}
  }

  loadForwarding();

  document.getElementById("addForwarding").addEventListener("click", async () => {
    const email = document.getElementById("forwardingEmail").value;
    if (!email) return;
    document.getElementById("forwardingError").textContent = "";
    try {
      const res = await apiFetch(`${API}/mail/settings/forwarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_email: email }),
      });
      if (!res.ok) { document.getElementById("forwardingError").textContent = "Failed to add"; return; }
      document.getElementById("forwardingEmail").value = "";
      loadForwarding();
    } catch { document.getElementById("forwardingError").textContent = "Network error"; }
  });

  // Load custom folders
  async function loadSettingsFolders() {
    try {
      const res = await apiFetch(`${API}/mail/folders`);
      if (!res.ok) return;
      const folders = await res.json();
      const list = document.getElementById("settingsFoldersList");
      list.innerHTML = "";
      folders.forEach(f => {
        const row = document.createElement("div");
        row.className = "ifinmail-forwarding-row";
        row.innerHTML = `<span>${f.name}</span>`;
        const del = document.createElement("button");
        del.className = "ifinmail-btn ifinmail-btn-sm";
        del.textContent = "Delete";
        del.onclick = async () => {
          await apiFetch(`${API}/mail/folders/${f.id}`, { method: "DELETE" });
          loadSettingsFolders();
          renderCustomFolders();
        };
        row.appendChild(del);
        list.appendChild(row);
      });
    } catch {}
  }
  loadSettingsFolders();

  document.getElementById("addFolderBtn").addEventListener("click", async () => {
    const name = document.getElementById("settingsFolderName").value.trim();
    if (!name) return;
    document.getElementById("folderError").textContent = "";
    try {
      const res = await apiFetch(`${API}/mail/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) { const d = await res.json(); document.getElementById("folderError").textContent = d.detail || "Failed"; return; }
      document.getElementById("settingsFolderName").value = "";
      loadSettingsFolders();
      renderCustomFolders();
    } catch { document.getElementById("folderError").textContent = "Network error"; }
  });

  // Load domains
  async function loadDomains() {
    try {
      const res = await apiFetch(`${API}/domains`);
      if (!res.ok) return;
      const domains = await res.json();
      const list = document.getElementById("settingsDomainsList");
      list.innerHTML = "";
      domains.forEach(d => {
        const row = document.createElement("div");
        row.className = "ifinmail-forwarding-row";
        row.innerHTML = `<span>${d.domain} ${d.verified ? "✅" : "⏳"}</span>`;
        list.appendChild(row);
      });
    } catch {}
  }
  loadDomains();

  document.getElementById("addDomainBtn").addEventListener("click", async () => {
    const domain = document.getElementById("settingsDomainInput").value.trim();
    if (!domain) return;
    document.getElementById("domainError").textContent = "";
    try {
      const res = await apiFetch(`${API}/domains`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain }),
      });
      if (!res.ok) { const d = await res.json(); document.getElementById("domainError").textContent = d.detail || "Failed"; return; }
      document.getElementById("settingsDomainInput").value = "";
      loadDomains();
    } catch { document.getElementById("domainError").textContent = "Network error"; }
  });

  // Load billing
  async function loadBilling() {
    try {
      const [plansRes, currentRes] = await Promise.all([
        apiFetch(`${API}/billing/plans`),
        apiFetch(`${API}/billing/current`),
      ]);
      if (!plansRes.ok || !currentRes.ok) return;
      const plans = await plansRes.json();
      const current = await currentRes.json();
      document.getElementById("billingInfo").innerHTML = `<p>Current plan: <strong>${current.plan}</strong> (${current.quota_mb} MB / ${current.used_mb} MB used)</p>`;
      const plansContainer = document.getElementById("billingPlans");
      plansContainer.innerHTML = "";
      plans.forEach(p => {
        const btn = document.createElement("button");
        btn.className = "ifinmail-btn" + (p.id === current.plan ? " ifinmail-btn-primary" : "");
        btn.textContent = `${p.name} — $${p.price}/mo`;
        btn.onclick = async () => {
          document.getElementById("billingError").textContent = "";
          const r = await apiFetch(`${API}/billing/subscribe`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plan: p.id }),
          });
          if (r.ok) { showToast("Plan changed to " + p.name); loadBilling(); }
          else { const d = await r.json(); document.getElementById("billingError").textContent = d.detail || "Failed"; }
        };
        plansContainer.appendChild(btn);
      });
    } catch {}
  }
  loadBilling();
}

async function fetchFolderCounts() {
  try {
    const res = await apiFetch(`${API}/mail/folder-counts`);
    if (res.ok) {
      const counts = await res.json();
      document.querySelectorAll(".ifinmail-badge[id^='count-']").forEach(el => {
        const folder = el.id.replace("count-", "");
        el.textContent = counts[folder] > 0 ? counts[folder] : "";
      });
      document.querySelectorAll("#customFoldersSidebar .ifinmail-nav-item").forEach(el => {
        const folder = el.dataset.folder;
        const badge = el.querySelector(".ifinmail-badge");
        if (badge) badge.textContent = counts[folder] > 0 ? counts[folder] : "";
      });
    }
  } catch {}
}

// ── Custom Folders (sidebar) ──

async function renderCustomFolders() {
  const container = document.getElementById("customFoldersSidebar");
  if (!container) return;
  try {
    const res = await apiFetch(`${API}/mail/folders`);
    if (!res.ok) { container.innerHTML = ""; return; }
    const folders = await res.json();
    container.innerHTML = folders.map(f =>
      `<a class="ifinmail-nav-item" data-folder="${f.name}"><span class="ifinmail-nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span> ${f.name} <span class="ifinmail-badge" id="count-${f.name}"></span></a>`
    ).join("");
    container.querySelectorAll(".ifinmail-nav-item").forEach(el => {
      el.addEventListener("click", () => {
        state.folder = el.dataset.folder;
        state.currentMsg = null;
        showView("inbox");
        fetchMessages();
        document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
        el.classList.add("active");
      });
      if (el.dataset.folder === state.folder) el.classList.add("active");
    });
  } catch {}
}

// ── Mark all read ──

async function markAllRead() {
  try {
    const res = await apiFetch(`${API}/mail/mark-all-read?folder=${state.folder}`, { method: "POST" });
    if (res.ok) {
      fetchMessages();
      fetchFolderCounts();
      showToast("All marked as read");
    }
  } catch {}
}

// ── Admin Dashboard ──

async function renderAdmin() {
  const tmpl = document.getElementById("adminTmpl");
  document.getElementById("adminView").innerHTML = tmpl.innerHTML;
  document.getElementById("adminError").textContent = "";
  try {
    const res = await apiFetch(`${API}/admin/stats`);
    if (!res.ok) { document.getElementById("adminError").textContent = "Failed to load stats"; return; }
    const stats = await res.json();
    const cards = document.getElementById("adminCards");
    cards.innerHTML = "";
    const items = [
      { label: "Users", value: stats.total_users },
      { label: "Domains", value: stats.total_domains },
      { label: "Messages", value: stats.total_messages },
      { label: "Attachments", value: stats.total_attachments },
      { label: "Storage", value: (stats.total_storage_bytes / 1024).toFixed(1) + " KB" },
      { label: "Mailboxes", value: stats.total_mailboxes },
    ];
    items.forEach(item => {
      const card = document.createElement("div");
      card.className = "ifinmail-admin-card";
      card.innerHTML = `<div class="ifinmail-admin-card-value">${item.value}</div><div class="ifinmail-admin-card-label">${item.label}</div>`;
      cards.appendChild(card);
    });

    // Users table
    const usersRes = await apiFetch(`${API}/admin/users`);
    if (usersRes.ok) {
      const users = await usersRes.json();
      const table = document.getElementById("adminUsersTable");
      table.innerHTML = "<thead><tr><th>ID</th><th>Email</th><th>Admin</th><th>Created</th></tr></thead><tbody>" +
        users.map(u => `<tr><td>${u.id}</td><td>${u.email}</td><td>${u.is_admin ? "✅" : ""}</td><td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : ""}</td></tr>`).join("") +
        "</tbody>";
    }
  } catch { document.getElementById("adminError").textContent = "Network error"; }
}

// ── Batch operations using bulk API ──

async function batchAction(action, folder) {
  const ids = Array.from(state._selected || []);
  if (!ids.length) return;
  try {
    if (action === "trash") {
      await apiFetch(`${API}/mail/bulk-delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, permanent: state.folder === "TRASH" }),
      });
    } else if (action === "move" && folder) {
      await apiFetch(`${API}/mail/bulk-move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids, folder }),
      });
    } else {
      for (const id of ids) {
        if (action === "star") {
          await apiFetch(`${API}/mail/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ starred: true }) });
        } else if (action === "unstar") {
          await apiFetch(`${API}/mail/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ starred: false }) });
        } else if (action === "read") {
          await apiFetch(`${API}/mail/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ read: true }) });
        } else if (action === "unread") {
          await apiFetch(`${API}/mail/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ read: false }) });
        }
      }
    }
    clearSelection();
    fetchMessages();
  } catch (err) {
    console.error("batchAction error", err);
  }
}

// ── Login / Register / Forgot / Reset ──

function toggleAuth(form) {
  document.getElementById("loginForm").style.display = form === "login" ? "" : "none";
  document.getElementById("registerForm").style.display = form === "register" ? "" : "none";
  document.getElementById("forgotForm").style.display = form === "forgot" ? "" : "none";
  document.getElementById("resetForm").style.display = "none";
}

document.getElementById("showRegister").addEventListener("click", (e) => { e.preventDefault(); toggleAuth("register"); });
document.getElementById("showLogin").addEventListener("click", (e) => { e.preventDefault(); toggleAuth("login"); });
document.getElementById("showForgotPassword").addEventListener("click", (e) => { e.preventDefault(); toggleAuth("forgot"); });
document.getElementById("showLoginFromForgot").addEventListener("click", (e) => { e.preventDefault(); toggleAuth("login"); });

let _registering = false;
document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (_registering) return;
  _registering = true;
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  const email = document.getElementById("registerEmail").value;
  const password = document.getElementById("registerPassword").value;
  document.getElementById("registerError").textContent = "";
  try {
    const res = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("registerError").textContent = data.detail || "Registration failed";
      return;
    }
    document.getElementById("registerError").style.color = "green";
    document.getElementById("registerError").textContent = "Account created! Sign in below.";
    toggleAuth("login");
  } catch {
    document.getElementById("registerError").textContent = "Network error";
  } finally {
    _registering = false;
    btn.disabled = false;
  }
});

let _forgetting = false;
document.getElementById("forgotForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (_forgetting) return;
  _forgetting = true;
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  const email = document.getElementById("forgotEmail").value;
  document.getElementById("forgotError").textContent = "";
  document.getElementById("forgotError").style.color = "";
  try {
    const res = await fetch(`${API}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("forgotError").textContent = data.detail || "Failed to send reset link";
      return;
    }
    document.getElementById("forgotError").style.color = "green";
    document.getElementById("forgotError").textContent = "If that email exists, a reset link has been sent.";
  } catch {
    document.getElementById("forgotError").textContent = "Network error";
  } finally {
    _forgetting = false;
    btn.disabled = false;
  }
});

let _resetting = false;
document.getElementById("resetForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (_resetting) return;
  _resetting = true;
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  const password = document.getElementById("resetPassword").value;
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (!token) {
    document.getElementById("resetError").textContent = "Missing reset token in URL";
    btn.disabled = false;
    _resetting = false;
    return;
  }
  document.getElementById("resetError").textContent = "";
  try {
    const res = await fetch(`${API}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("resetError").textContent = data.detail || "Reset failed";
      return;
    }
    document.getElementById("resetError").style.color = "green";
    document.getElementById("resetError").textContent = "Password reset! Sign in with your new password.";
    document.getElementById("resetForm").style.display = "none";
    document.getElementById("loginForm").style.display = "";
  } catch {
    document.getElementById("resetError").textContent = "Network error";
  } finally {
    _resetting = false;
    btn.disabled = false;
  }
});

// Auto-show reset form if ?token= in URL
(function() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("token")) {
    document.getElementById("loginForm").style.display = "none";
    document.getElementById("resetForm").style.display = "";
  }
})();

let _loggingIn = false;
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (_loggingIn) return;
  _loggingIn = true;
  let btn;
  try {
    btn = e.target.querySelector("button[type=submit]");
    if (btn) btn.disabled = true;
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;
    const errEl = document.getElementById("loginError");
    errEl.textContent = "";

    console.log("Login attempt:", email);
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    console.log("Login response:", res.status, data);
    if (!res.ok) {
      errEl.textContent = data.detail || "Login failed";
      return;
    }
    state.token = data.access_token;
    state.refreshToken = data.refresh_token;
    state.email = email;
    state.isAdmin = data.is_admin || false;
    localStorage.setItem("ifinmail_token", state.token);
    localStorage.setItem("ifinmail_refresh", state.refreshToken);
    localStorage.setItem("ifinmail_email", email);
    localStorage.setItem("ifinmail_is_admin", state.isAdmin);
    state.accounts = state.accounts.filter(a => a.email !== email);
    state.accounts.push({ email, token: state.token, refreshToken: state.refreshToken });
    saveAccounts();
    render();
    connectWS();
    requestNotifyPermission();
  } catch (err) {
    console.error("Login error:", err);
    const errEl = document.getElementById("loginError");
    if (errEl) errEl.textContent = "Network error";
  } finally {
    _loggingIn = false;
    if (btn) btn.disabled = false;
  }
});

function logout() {
  state.accounts = state.accounts.filter(a => a.email !== state.email);
  saveAccounts();
  state.token = null;
  state.email = null;
  state.messages = [];
  localStorage.removeItem("ifinmail_token");
  localStorage.removeItem("ifinmail_email");
  render();
}

// ── Fetch messages ──

async function fetchMessages(append) {
  if (state.loading) return;
  if (append && !state.hasMore) return;

  const list = document.getElementById("messageList");

  if (!append) {
    state.page = 1;
    state.hasMore = true;
    list.innerHTML = '<div class="ifinmail-spinner">Loading...</div>';
  } else {
    state.page++;
  }

  state.loading = true;
  const searchVal = document.getElementById("searchInput")?.value;
  state.searchQuery = searchVal || "";
  const p = new URLSearchParams({ folder: state.folder, per_page: String(state.perPage), page: String(state.page) });
  if (searchVal) p.set("search", searchVal);

  try {
    const res = await apiFetch(`${API}/mail?${p}`);
    if (!res.ok) {
      if (res.status === 401) {
        state.token = null;
        localStorage.removeItem("ifinmail_token");
        render();
        return;
      }
      if (!append) list.innerHTML = '<div class="ifinmail-empty">Failed to load</div>';
      state.loading = false;
      return;
    }
    state.totalCount = parseInt(res.headers.get("X-Total-Count") || "0");
    const msgs = await res.json();
    state.hasMore = state.page * state.perPage < state.totalCount;

    if (append) {
      state.messages.push(...msgs);
    } else {
      state.messages = msgs;
    }

    renderMessageList(append);
    renderPagination();
    updateHash();
  } catch {
    if (!append) list.innerHTML = '<div class="ifinmail-empty">Network error</div>';
  }
  state.loading = false;
}

function renderMessageList(append) {
  const list = document.getElementById("messageList");
  const totalPages = Math.ceil(state.totalCount / state.perPage) || 1;

  const countEl = document.getElementById("searchCount");
  if (countEl) {
    const searchVal = document.getElementById("searchInput")?.value;
    countEl.textContent = searchVal ? `${state.totalCount} result${state.totalCount !== 1 ? "s" : ""}` : "";
  }

  if (!state.messages.length) {
    const labels = { INBOX: "inbox", SENT: "sent mail", DRAFTS: "drafts", TRASH: "trash", SPAM: "spam", ARCHIVE: "archive" };
    list.innerHTML = `<div class="ifinmail-empty">${labels[state.folder] || "folder"} is empty</div>`;
    clearSelection();
    return;
  }

  if (!append) list.innerHTML = "";

  state.messages.forEach(msg => {
    if (append && list.querySelector(`[data-id="${msg.id}"]`)) return;
    const row = document.getElementById("messageRowTmpl").content.cloneNode(true);
    const div = row.querySelector(".ifinmail-row");
    div.dataset.id = msg.id;
    if (!msg.read) div.classList.add("unread");

    const cb = row.querySelector(".ifinmail-row-cb");
    cb.checked = state._selected?.has(msg.id) || false;
    cb.addEventListener("change", () => {
      if (!state._selected) state._selected = new Set();
      if (cb.checked) state._selected.add(msg.id);
      else state._selected.delete(msg.id);
      updateBatchBar();
    });
    cb.addEventListener("click", (e) => e.stopPropagation());

    const dot = row.querySelector(".ifinmail-row-unread-dot");
    dot.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleRead(msg);
    });

    const star = row.querySelector(".ifinmail-row-star");
    star.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (msg.starred ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
    if (msg.starred) star.classList.add("starred");
    star.addEventListener("click", (e) => { e.stopPropagation(); toggleStar(msg); });

    const sender = row.querySelector(".ifinmail-row-sender");
    if (msg.has_attachments) {
      sender.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;flex-shrink:0"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>' + msg.from_addr;
    } else {
      sender.textContent = msg.from_addr;
    }

    row.querySelector(".ifinmail-row-subject").textContent = msg.subject || "(no subject)";
    row.querySelector(".ifinmail-row-date").textContent = formatDate(msg.created_at);

    // For TRASH items, add a Restore button
    if (msg.folder === "TRASH") {
      const restoreBtn = document.createElement("button");
      restoreBtn.className = "ifinmail-btn ifinmail-btn-sm";
      restoreBtn.textContent = "Restore";
      restoreBtn.style.marginLeft = "8px";
      restoreBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        restoreMessage(msg);
        showToast("Restored");
        fetchMessages();
      });
      row.querySelector(".ifinmail-row-date").after(restoreBtn);
    }

    const labelsEl = row.querySelector(".ifinmail-row-labels");
    if (msg.labels) {
      const colors = ["#e74c3c","#e67e22","#f1c40f","#2ecc71","#3498db","#9b59b6","#1abc9c","#e84393"];
      msg.labels.split(",").forEach((l, i) => {
        const tag = document.createElement("span");
        tag.className = "ifinmail-label-badge";
        tag.textContent = l.trim();
        tag.style.background = colors[i % colors.length] + "22";
        tag.style.color = colors[i % colors.length];
        labelsEl.appendChild(tag);
      });
    }
    div.addEventListener("click", () => {
      if (msg.folder === "DRAFTS") {
        showCompose("edit", msg);
      } else {
        openMessage(msg.id);
      }
    });
    if (!append && msg.id === state._highlightId) div.classList.add("unread");
    list.appendChild(row);
  });
  setupScrollSentinel();
  updateBatchBar();
  setupTrashToolbar();
}

function renderPagination() {
  const container = document.getElementById("paginationControls");
  if (!container) return;
  const totalPages = Math.ceil(state.totalCount / state.perPage) || 1;
  if (totalPages <= 1) { container.style.display = "none"; return; }
  container.style.display = "flex";
  container.innerHTML = "";
  const prevBtn = document.createElement("button");
  prevBtn.className = "ifinmail-btn ifinmail-btn-sm";
  prevBtn.textContent = "‹ Prev";
  prevBtn.disabled = state.page <= 1;
  prevBtn.addEventListener("click", () => {
    state.currentMsg = null;
    if (state.page > 1) {
      state.page -= 1;
      fetchMessages();
    }
  });
  container.appendChild(prevBtn);
  const pageInfo = document.createElement("span");
  pageInfo.style.cssText = "margin:0 12px;font-size:13px;color:var(--text-light)";
  pageInfo.textContent = `Page ${state.page} of ${totalPages}`;
  container.appendChild(pageInfo);
  const nextBtn = document.createElement("button");
  nextBtn.className = "ifinmail-btn ifinmail-btn-sm";
  nextBtn.textContent = "Next ›";
  nextBtn.disabled = state.page >= totalPages;
  nextBtn.addEventListener("click", () => { state.currentMsg = null; fetchMessages(true); });
  container.appendChild(nextBtn);
}

function moveTargets(currentFolder) {
  const map = {
    INBOX:   ["ARCHIVE", "SPAM", "TRASH"],
    SENT:    ["TRASH"],
    ARCHIVE: ["INBOX", "SPAM", "TRASH"],
    SPAM:    ["INBOX", "TRASH"],
    TRASH:   ["INBOX"],
    DRAFTS:  ["TRASH"],
  };
  return map[currentFolder] || [];
}

function populateMoveDropdown(dropdown, currentFolder, onClick) {
  dropdown.innerHTML = "";
  const targets = moveTargets(currentFolder);
  // For TRASH, show restore as first option
  if (currentFolder === "TRASH" && state.currentMsg?.previous_folder) {
    const pf = state.currentMsg.previous_folder;
    const div = document.createElement("div");
    div.dataset.folder = pf;
    div.textContent = `Restore to ${pf.charAt(0) + pf.slice(1).toLowerCase()}`;
    div.style.fontWeight = "600";
    div.addEventListener("click", (e) => {
      e.stopPropagation();
      onClick(pf);
    });
    dropdown.appendChild(div);
  }
  targets.forEach(f => {
    const div = document.createElement("div");
    div.dataset.folder = f;
    div.textContent = f.charAt(0) + f.slice(1).toLowerCase();
    div.addEventListener("click", (e) => {
      e.stopPropagation();
      onClick(f);
    });
    dropdown.appendChild(div);
  });
}

function setupBatchBar() {
  const bar = document.getElementById("batchBar");
  if (!bar) return;

  document.getElementById("selectAllCb")?.addEventListener("change", (e) => {
    if (!state._selected) state._selected = new Set();
    if (e.target.checked) {
      state.messages.forEach(m => state._selected.add(m.id));
    } else {
      state._selected.clear();
    }
    // sync all row checkboxes
    document.querySelectorAll(".ifinmail-row-cb").forEach(cb => {
      cb.checked = e.target.checked;
    });
    updateBatchBar();
  });

  document.getElementById("batchCancel")?.addEventListener("click", () => {
    state._selected.clear();
    const cb = document.getElementById("selectAllCb");
    if (cb) { cb.checked = false; cb.indeterminate = false; }
    document.querySelectorAll(".ifinmail-row-cb").forEach(c => c.checked = false);
    updateBatchBar();
  });

  document.getElementById("batchStar")?.addEventListener("click", async () => {
    await batchAction("star");
    showToast("Starred");
  });
  document.getElementById("batchRead")?.addEventListener("click", async () => {
    await batchAction("read");
    showToast("Marked as read");
  });
  document.getElementById("batchUnread")?.addEventListener("click", async () => {
    await batchAction("unread");
    showToast("Marked as unread");
  });
  document.getElementById("batchTrash")?.addEventListener("click", async () => {
    await batchAction("trash");
    showToast("Moved to trash");
  });

  const batchMoveBtn = document.getElementById("batchMoveBtn");
  const batchMoveDd = document.getElementById("batchMoveDropdown");
  if (batchMoveBtn) {
    populateMoveDropdown(batchMoveDd, state.folder, async (f) => {
      await batchAction("move", f);
      showToast(`Moved to ${f}`);
      batchMoveDd.classList.remove("show");
    });
    batchMoveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      batchMoveDd.classList.toggle("show");
    });
    document.addEventListener("click", () => batchMoveDd.classList.remove("show"), { once: true });
  }

  // Move to folder in message view
  const moveBtn = document.getElementById("moveBtn");
  const moveDd = document.getElementById("moveDropdown");
  if (moveBtn && state.currentMsg) {
    populateMoveDropdown(moveDd, state.currentMsg.folder, async (f) => {
      moveDd.classList.remove("show");
      const oldFolder = state.currentMsg.folder;
      await apiFetch(`${API}/mail/${state.currentMsg.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: f }),
      });
      pushUndo({ type: "move", msgId: state.currentMsg.id, oldFolder, newFolder: f });
      state.folder = f;
      showView("inbox");
      fetchMessages();
      showToast(`Moved to ${f}`);
    });
    moveBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      moveDd.classList.toggle("show");
    });
    document.addEventListener("click", () => moveDd.classList.remove("show"), { once: true });
  }
}

function clearSelection() {
  state._selected = new Set();
  const cb = document.getElementById("selectAllCb");
  if (cb) { cb.checked = false; cb.indeterminate = false; }
  document.querySelectorAll(".ifinmail-row-cb").forEach(c => c.checked = false);
  updateBatchBar();
}

function setupTrashToolbar() {
  const container = document.getElementById("trashActions");
  if (!container) return;
  container.style.display = state.folder === "TRASH" ? "flex" : "none";

  document.getElementById("emptyTrashBtn").onclick = async () => {
    if (!confirm("Permanently delete all messages in Trash?")) return;
    const trashMsgs = state.messages.filter(m => m.folder === "TRASH");
    for (const m of trashMsgs) {
      await apiFetch(`${API}/mail/${m.id}?permanent=true`, { method: "DELETE" });
    }
    fetchMessages();
    showToast("Trash emptied");
  };

  document.getElementById("restoreAllBtn").onclick = async () => {
    const trashMsgs = state.messages.filter(m => m.folder === "TRASH");
    for (const m of trashMsgs) {
      const target = m.previous_folder || "INBOX";
      await apiFetch(`${API}/mail/${m.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: target }),
      });
    }
    fetchMessages();
    showToast("All restored");
  };
}

// ── Restore single message from trash (uses previous_folder) ──

async function restoreMessage(msg) {
  const target = msg.previous_folder || "INBOX";
  await apiFetch(`${API}/mail/${msg.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder: target }),
  });
}

function updateBatchBar() {
  const bar = document.getElementById("batchBar");
  if (!bar) return;
  const count = state._selected?.size || 0;
  if (count > 0) {
    bar.style.display = "flex";
    document.getElementById("batchCount").textContent = `${count} selected`;
    // Update select-all checkbox
    const selectAll = document.getElementById("selectAllCb");
    const total = state.messages.length;
    if (selectAll) {
      selectAll.checked = count === total;
      selectAll.indeterminate = count > 0 && count < total;
    }
    // In TRASH, relabel the trash button to "Delete permanently"
    const trashBtn = document.getElementById("batchTrash");
    if (trashBtn) {
      const isTrash = state.folder === "TRASH";
      trashBtn.innerHTML = (isTrash
        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Delete permanently'
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Trash');
    }
  } else {
    bar.style.display = "none";
  }
}

// ── Undo / Redo ──

let _undoStack = [];
let _redoStack = [];

function pushUndo(action) {
  _undoStack.push(action);
  _redoStack = [];
}

async function performUndo() {
  const action = _undoStack.pop();
  if (!action) { showToast("Nothing to undo"); return; }
  _redoStack.push(action);
  try {
    if (action.type === "trash") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: action.prevFolder }),
      });
      fetchMessages();
      showToast("Undo: restored");
    } else if (action.type === "star") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: action.oldVal }),
      });
      renderMessageList();
      showToast("Undo: star");
    } else if (action.type === "read") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read: action.oldVal }),
      });
      renderMessageList();
      showToast("Undo: read");
    } else if (action.type === "move") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: action.oldFolder }),
      });
      fetchMessages();
      showToast("Undo: moved back");
    }
  } catch {}
}

async function performRedo() {
  const action = _redoStack.pop();
  if (!action) { showToast("Nothing to redo"); return; }
  _undoStack.push(action);
  try {
    if (action.type === "trash") {
      await apiFetch(`${API}/mail/${action.msgId}?permanent=false`, { method: "DELETE" });
      fetchMessages();
      showToast("Redo: trashed");
    } else if (action.type === "star") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ starred: !action.oldVal }),
      });
      renderMessageList();
      showToast("Redo: star");
    } else if (action.type === "read") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read: !action.oldVal }),
      });
      renderMessageList();
      showToast("Redo: read");
    } else if (action.type === "move") {
      await apiFetch(`${API}/mail/${action.msgId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: action.newFolder }),
      });
      fetchMessages();
      showToast("Redo: moved");
    }
  } catch {}
}

// ── Keyboard shortcuts for undo/redo ──
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "z") {
    e.preventDefault();
    if (e.shiftKey) performRedo();
    else performUndo();
  }
});



function setupScrollSentinel() {
  if (_sentinelObserver) _sentinelObserver.disconnect();
  const existing = document.getElementById("scrollSentinel");
  if (existing) existing.remove();

  if (!state.hasMore) return;

  const sentinel = document.createElement("div");
  sentinel.id = "scrollSentinel";
  sentinel.style.height = "1px";
  document.getElementById("messageList").after(sentinel);

  _sentinelObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && state.hasMore && !state.loading) {
      fetchMessages(true);
    }
  }, { rootMargin: "200px" });
  _sentinelObserver.observe(sentinel);
}

// ── Message detail ──

async function openMessage(id) {
  try {
    const res = await apiFetch(`${API}/mail/${id}`);
    if (!res.ok) {
      console.warn("openMessage: GET failed", res.status);
      return;
    }
    state.currentMsg = await res.json();
    renderMessageView();
    updateHash();
  } catch (err) {
    console.warn("openMessage error", err);
  }
}

async function renderAttachments() {
  const container = document.getElementById("msgAttachments");
  container.innerHTML = "";
  const msg = state.currentMsg;
  if (!msg?.has_attachments) return;
  try {
    const res = await apiFetch(`${API}/mail/${msg.id}/attachments`, {
      method: "GET",
    });
    if (!res.ok) return;
    const attachments = await res.json();
    if (!attachments.length) return;
    container.innerHTML = '<div class="ifinmail-attachments-title">Attachments</div>';
    attachments.forEach(att => {
      const row = document.getElementById("attachmentRowTmpl").content.cloneNode(true);
      const link = row.querySelector(".ifinmail-attachment-link");
      link.href = `${API}/mail/${msg.id}/attachments/${att.id}/download`;
      link.textContent = att.filename;
      const sizeEl = row.querySelector(".ifinmail-attachment-size");
      sizeEl.textContent = formatSize(att.size);
      container.appendChild(row);
    });
  } catch {}
}

function renderMessageView() {
  const msg = state.currentMsg;
  if (!msg) return;
  document.getElementById("messageView").innerHTML = document.getElementById("messageViewTmpl").innerHTML;
  showView("message");

  document.getElementById("msgSubject").textContent = msg.subject || "(no subject)";
  document.getElementById("msgFrom").textContent = `From: ${msg.from_addr}`;
  document.getElementById("msgTo").textContent = `To: ${msg.to_addrs}`;
  document.getElementById("msgDate").textContent = formatDate(msg.created_at);
  document.getElementById("msgBody").textContent = msg.body_text || "(no content)";

  const starBtn = document.getElementById("starBtn");
  starBtn.innerHTML = (msg.starred
    ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg> Unstar'
    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg> Star');
  starBtn.onclick = () => { toggleStar(msg); showToast(msg.starred ? "Starred" : "Unstarred"); };

  // Archive
  document.getElementById("archiveBtn").onclick = async () => {
    await apiFetch(`${API}/mail/${msg.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ folder: "ARCHIVE" }),
    });
    state.folder = "ARCHIVE";
    showView("inbox");
    fetchMessages();
    showToast("Archived");
  };

  // Reply / Reply-All / Forward
  document.getElementById("replyBtn").onclick = () => showCompose("reply", msg);
  document.getElementById("replyAllBtn").onclick = () => showCompose("replyAll", msg);
  document.getElementById("forwardBtn").onclick = () => showCompose("forward", msg);

  // Trash (with undo)
  document.getElementById("trashBtn").onclick = async () => {
    try {
      const prevFolder = state.folder;
      if (msg.folder === "TRASH") {
        // Permanently delete with undo
        const resp = await apiFetch(`${API}/mail/${msg.id}?permanent=true`, { method: "DELETE" });
        if (resp.ok) {
          showUndoToast("Message permanently deleted", async () => {
            await apiFetch(`${API}/mail/${msg.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ folder: msg.previous_folder || prevFolder }),
            });
            fetchMessages();
          });
          state.folder = prevFolder;
          showView("inbox");
          fetchMessages();
        }
      } else {
        await apiFetch(`${API}/mail/${msg.id}`, { method: "DELETE" });
        pushUndo({ type: "trash", msgId: msg.id, prevFolder: msg.folder, mailbox: true });
        showToast("Moved to trash");
        state.folder = prevFolder;
        showView("inbox");
        fetchMessages();
      }
    } catch {}
  };

  document.getElementById("backBtn").onclick = () => {
    showView("inbox");
    fetchMessages();
  };

  setupBatchBar();
  renderAttachments();
  renderLabels();

  if (!msg.read) markRead(msg.id);
}

function renderLabels() {
  const msg = state.currentMsg;
  const container = document.getElementById("msgLabels");
  if (!container) return;
  container.innerHTML = "";
  const editBtn = document.createElement("button");
  editBtn.className = "ifinmail-btn ifinmail-btn-sm";
  editBtn.textContent = "✎ Labels";
  editBtn.onclick = () => {
    const input = document.createElement("input");
    input.value = msg.labels || "";
    input.placeholder = "label1, label2, ...";
    input.className = "ifinmail-label-input";
    input.style.marginRight = "8px";
    const save = document.createElement("button");
    save.className = "ifinmail-btn ifinmail-btn-primary ifinmail-btn-sm";
    save.textContent = "Save";
    const wrapper = document.createElement("span");
    wrapper.style.display = "inline-flex";
    wrapper.style.alignItems = "center";
    wrapper.style.gap = "4px";
    wrapper.appendChild(input);
    wrapper.appendChild(save);
    container.innerHTML = "";
    container.appendChild(wrapper);
    save.onclick = async () => {
      try {
        const res = await apiFetch(`${API}/mail/${msg.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ labels: input.value }),
        });
        if (res.ok) {
          msg.labels = input.value;
          renderLabels();
        }
      } catch {}
    };
  };
  container.appendChild(editBtn);
  if (msg.labels) {
    const colors = ["#e74c3c","#e67e22","#f1c40f","#2ecc71","#3498db","#9b59b6","#1abc9c","#e84393"];
    msg.labels.split(",").forEach((l, i) => {
      const tag = document.createElement("span");
      tag.className = "ifinmail-label-badge";
      tag.textContent = l.trim();
      tag.style.background = colors[i % colors.length] + "22";
      tag.style.color = colors[i % colors.length];
      container.appendChild(tag);
    });
  }
}

async function markRead(id) {
  try {
    await apiFetch(`${API}/mail/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read: true }),
    });
  } catch {}
}

async function toggleStar(msg) {
  try {
    const res = await apiFetch(`${API}/mail/${msg.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ starred: !msg.starred }),
    });
    if (res.ok) {
      pushUndo({ type: "star", msgId: msg.id, oldVal: msg.starred });
      msg.starred = !msg.starred;
      if (state.currentMsg?.id === msg.id) renderMessageView();
      else renderMessageList();
    }
  } catch {}
}

async function toggleRead(msg) {
  const newRead = !msg.read;
  try {
    await apiFetch(`${API}/mail/${msg.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read: newRead }),
    });
    pushUndo({ type: "read", msgId: msg.id, oldVal: msg.read });
    msg.read = newRead;
    renderMessageList();
    showToast(newRead ? "Marked as read" : "Marked as unread");
  } catch {}
}

// ── Compose ──

let _composeAttachmentIds = [];
let _composeEditId = null;

function showCompose(mode, msg) {
  document.getElementById("composeView").innerHTML = document.getElementById("composeTmpl").innerHTML;
  showView("compose");
  _composeAttachmentIds = [];
  _composeEditId = null;
  const toEl = document.getElementById("composeTo");
  const subjEl = document.getElementById("composeSubject");
  const bodyEl = document.getElementById("composeBody");

  toEl.value = "";
  subjEl.value = "";
  bodyEl.value = "";
  const quoteEl = document.getElementById("composeQuote");
  quoteEl.textContent = "";
  document.getElementById("composeError").textContent = "";
  document.getElementById("composeAttachList").innerHTML = "";

  if (mode === "edit" && msg) {
    _composeEditId = msg.id;
    toEl.value = msg.to_addrs || "";
    subjEl.value = msg.subject || "";
    bodyEl.value = msg.body_text || "";
    document.querySelector(".ifinmail-compose-header h2").textContent = "Edit Draft";
  } else if (mode === "reply" && msg) {
    toEl.value = msg.from_addr;
    subjEl.value = msg.subject?.startsWith("Re:") ? msg.subject : `Re: ${msg.subject}`;
    quoteEl.textContent = `--- Original message ---\nFrom: ${msg.from_addr}\nDate: ${formatDate(msg.created_at)}\nSubject: ${msg.subject}\n\n${msg.body_text || ""}`;
  } else if (mode === "replyAll" && msg) {
    const allTo = [msg.from_addr, ...(msg.to_addrs ? msg.to_addrs.split(",").map(s => s.trim()).filter(s => s !== state.email) : [])];
    toEl.value = [...new Set(allTo)].join(", ");
    subjEl.value = msg.subject?.startsWith("Re:") ? msg.subject : `Re: ${msg.subject}`;
    quoteEl.textContent = `--- Original message ---\nFrom: ${msg.from_addr}\nDate: ${formatDate(msg.created_at)}\nSubject: ${msg.subject}\n\n${msg.body_text || ""}`;
  } else if (mode === "forward" && msg) {
    subjEl.value = msg.subject?.startsWith("Fwd:") ? msg.subject : `Fwd: ${msg.subject}`;
    quoteEl.textContent = `--- Forwarded message ---\nFrom: ${msg.from_addr}\nDate: ${formatDate(msg.created_at)}\nSubject: ${msg.subject}\nTo: ${msg.to_addrs}\n\n${msg.body_text || ""}`;
  }

  if (mode === "reply" || mode === "replyAll" || mode === "forward") {
    bodyEl.focus();
  } else {
    toEl.focus();
  }

  document.getElementById("cancelCompose").onclick = handleCancelCompose;
  document.getElementById("composeForm").onsubmit = handleComposeSubmit;
  document.getElementById("composeTo").addEventListener("input", saveDraft);
  document.getElementById("composeSubject").addEventListener("input", saveDraft);
  document.getElementById("composeBody").addEventListener("input", saveDraft);
  window._composeDirty = true;

  const attachInput = document.getElementById("attachInput");
  const attachBtn = document.getElementById("attachBtn");
  attachBtn.onclick = () => attachInput.click();
  attachInput.onchange = handleAttachSelect;
}

// Delegated click handler for removing compose attachments
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".ifinmail-attach-remove");
  if (!btn) return;
  const attId = parseInt(btn.dataset.attId);
  if (!attId) return;
  try {
    await apiFetch(`${API}/mail/attachments/${attId}`, { method: "DELETE" });
  } catch {}
  _composeAttachmentIds = _composeAttachmentIds.filter(id => id !== attId);
  btn.closest(".ifinmail-attach-item")?.remove();
});

let _composeAutoSaveTimer = null;

function saveDraft() {
  if (_composeAutoSaveTimer) clearTimeout(_composeAutoSaveTimer);
  const to = document.getElementById("composeTo")?.value;
  const subject = document.getElementById("composeSubject")?.value;
  const body = document.getElementById("composeBody")?.value;
  if (!to && !subject && !body) return;
  _composeAutoSaveTimer = setTimeout(() => doSaveDraft(false), 1000);
}

async function doSaveDraft(showToastMsg) {
  const to = document.getElementById("composeTo")?.value;
  const subject = document.getElementById("composeSubject")?.value;
  const body = document.getElementById("composeBody")?.value;
  if (!to && !subject && !body) return;
  try {
    const bodyData = { to: to || "", subject: subject || "", body_text: body || "" };
    if (_composeAttachmentIds.length) bodyData.attachment_ids = _composeAttachmentIds;
    if (_composeEditId) {
      await apiFetch(`${API}/mail/${_composeEditId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyData),
      });
    } else {
      const res = await apiFetch(`${API}/mail`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.assign({}, bodyData, { draft: true })),
      });
      if (res.ok) {
        const data = await res.json();
        _composeEditId = data.id;
      }
    }
    if (showToastMsg) showToast("Draft saved");
  } catch {}
}

async function handleCancelCompose() {
  await doSaveDraft(true);
  showView("inbox");
  fetchMessages();
}

let _composing = false;
async function handleComposeSubmit(e) {
  e.preventDefault();
  if (_composing) return;
  _composing = true;
  const btn = e.target.querySelector("button[type=submit]");
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Sending...";
  const to = document.getElementById("composeTo").value;
  const subject = document.getElementById("composeSubject").value;
  const body = document.getElementById("composeBody").value;
  document.getElementById("composeError").textContent = "";

  try {
    const bodyData = { to, subject, body_text: body };
    if (_composeAttachmentIds.length) bodyData.attachment_ids = _composeAttachmentIds;
    const res = await apiFetch(`${API}/mail`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyData),
    });
    if (!res.ok) {
      const data = await res.json();
      document.getElementById("composeError").textContent = data.detail || "Failed to send";
      await doSaveDraft(false);
      return;
    }
    // If editing a draft, delete it
    if (_composeEditId) {
      await apiFetch(`${API}/mail/${_composeEditId}?permanent=true`, { method: "DELETE" });
    }
    showView("inbox");
    fetchMessages();
    showToast("Message sent");
  } catch (err) {
    document.getElementById("composeError").textContent = "Network error";
    await doSaveDraft(false);
  } finally {
    _composing = false;
    btn.disabled = false;
    btn.textContent = orig;
  }
}

async function handleAttachSelect() {
  const input = document.getElementById("attachInput");
  const list = document.getElementById("composeAttachList");
  const files = Array.from(input.files);
  input.value = "";

  for (const file of files) {
    const item = document.createElement("div");
    item.className = "ifinmail-attach-item";
    item.textContent = `⏳ ${file.name}...`;
    list.appendChild(item);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch(`${API}/mail/attachments`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        item.textContent = `❌ ${file.name}`;
        continue;
      }
      const att = await res.json();
      _composeAttachmentIds.push(att.id);
      item.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg> ' + file.name + ' (' + formatSize(file.size) + ') <button class="ifinmail-btn ifinmail-btn-sm ifinmail-attach-remove" data-att-id="' + att.id + '" style="margin-left:8px;padding:1px 6px;font-size:11px;background:rgba(230,57,70,0.1);color:var(--danger);border:1px solid rgba(230,57,70,0.3);border-radius:4px;cursor:pointer">✕</button>'
    } catch {
      item.textContent = `❌ ${file.name}`;
    }
  }
}

// ── Search ──

document.addEventListener("click", (e) => {
  const toggle = e.target.closest(".ifinmail-pw-toggle");
  if (toggle) {
    const input = document.getElementById(toggle.dataset.target);
    if (input) {
      const isPw = input.type === "password";
      input.type = isPw ? "text" : "password";
      toggle.innerHTML = isPw
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    }
  }
});

document.addEventListener("click", (e) => {
  if (e.target.id === "searchBtn" || e.target.closest("#searchBtn")) {
    e.preventDefault();
    fetchMessages();
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "searchInput" && !e.target.value) {
    fetchMessages();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.target.id === "searchInput" && e.key === "Enter") {
    e.preventDefault();
    fetchMessages();
  }
});

// ── Simple Toast ──

function showToast(message) {
  const existing = document.querySelector(".ifinmail-toast-plain");
  if (existing) existing.remove();
  const el = document.createElement("div");
  el.className = "ifinmail-toast-plain";
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

// ── Refresh button ──

document.addEventListener("click", (e) => {
  if (e.target.id === "refreshBtn" || e.target.closest("#refreshBtn")) {
    e.preventDefault();
    fetchMessages();
  }
});

// ── Undo Toast ──

function showUndoToast(message, undoCallback) {
  const existing = document.getElementById("undoToast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "undoToast";
  toast.className = "ifinmail-toast";
  toast.innerHTML = `<span class="ifinmail-toast-msg">${message}</span><button class="ifinmail-btn ifinmail-btn-sm ifinmail-toast-undo">Undo</button>`;
  document.body.appendChild(toast);

  // Slide in
  requestAnimationFrame(() => toast.classList.add("show"));

  const undoBtn = toast.querySelector(".ifinmail-toast-undo");
  let undone = false;
  undoBtn.onclick = () => {
    undone = true;
    undoCallback();
    toast.remove();
  };

  setTimeout(() => {
    if (!undone) {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }
  }, 10000);
}

// ── Keyboard shortcuts ──

let shortcutsVisible = false;

function showShortcuts() {
  if (shortcutsVisible) return;
  const tmpl = document.getElementById("shortcutsTmpl");
  const clone = tmpl.content.cloneNode(true);
  clone.querySelector("#shortcutsClose").onclick = hideShortcuts;
  clone.querySelector("#shortcutsOverlay").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) hideShortcuts();
  });
  document.body.appendChild(clone);
  shortcutsVisible = true;
}

function hideShortcuts() {
  const el = document.getElementById("shortcutsOverlay");
  if (el) el.remove();
  shortcutsVisible = false;
}

let _addAccountVisible = false;

function showAddAccount() {
  if (_addAccountVisible) return;
  const tmpl = document.getElementById("addAccountTmpl");
  const clone = tmpl.content.cloneNode(true);
  clone.querySelector("#addAccountClose").onclick = hideAddAccount;
  clone.querySelector("#addAccountOverlay").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) hideAddAccount();
  });

  let aaMode = "login";
  function setFormMode(mode) {
    aaMode = mode;
    const tabs = clone.querySelectorAll(".ifinmail-tab");
    tabs.forEach(t => t.classList.toggle("active", t.dataset.aaTab === mode));
    const btn = clone.querySelector("#addAccountForm button[type=submit]");
    btn.textContent = mode === "login" ? "Add & switch" : "Create & switch";
    const errEl = clone.querySelector("#addAccountError");
    if (errEl) errEl.textContent = "";
  }
  clone.querySelectorAll(".ifinmail-tab").forEach(tab => {
    tab.addEventListener("click", () => setFormMode(tab.dataset.aaTab));
  });

  clone.querySelector("#addAccountForm").onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button[type=submit]");
    const email = document.getElementById("addAccountEmail").value;
    const password = document.getElementById("addAccountPassword").value;
    const errEl = document.getElementById("addAccountError");
    if (!email || !password) { errEl.textContent = "Please fill in all fields"; return; }
    btn.disabled = true;
    try {
      const endpoint = aaMode === "login" ? "/auth/login" : "/auth/register";
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { errEl.textContent = data.detail || "Failed"; return; }
      state.accounts = state.accounts.filter(a => a.email !== email);
      state.accounts.push({ email, token: data.access_token, refreshToken: data.refresh_token });
      saveAccounts();
      switchAccount(email, data.access_token, data.refresh_token);
      hideAddAccount();
    } catch { errEl.textContent = "Network error"; }
    finally { btn.disabled = false; }
  };
  document.body.appendChild(clone);
  _addAccountVisible = true;
  setTimeout(() => document.getElementById("addAccountEmail")?.focus(), 50);
}

function hideAddAccount() {
  const el = document.getElementById("addAccountOverlay");
  if (el) el.remove();
  _addAccountVisible = false;
}

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.key === "?") {
    if (shortcutsVisible) { hideShortcuts(); } else { showShortcuts(); }
    return;
  }
  if (shortcutsVisible) {
    if (e.key === "Escape") hideShortcuts();
    return;
  }
  if (!state.token) return;

  switch (e.key) {
    case "n":
      e.preventDefault();
      showCompose();
      break;
    case "r":
      if (state.currentMsg) { e.preventDefault(); showCompose("reply", state.currentMsg); }
      break;
    case "u":
      if (state.currentMsg) { e.preventDefault(); toggleRead(state.currentMsg); }
      break;
    case "#":
      e.preventDefault();
      const trashBtn = document.getElementById("trashBtn");
      if (trashBtn) trashBtn.click();
      break;
    case "Escape":
      if (document.getElementById("composeView").style.display === "block") {
        document.getElementById("cancelCompose").click();
      } else if (document.getElementById("messageView").style.display === "block") {
        document.getElementById("backBtn").click();
      }
      break;
  }
});

// ── Utilities ──

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  if (isToday) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const isThisYear = d.getFullYear() === now.getFullYear();
  if (isThisYear) return d.toLocaleDateString([], { month: "short", day: "numeric" });
  return d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

// ── Init ──

function connectWS() {
  if (!state.token) return;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${window.location.host}/ws?token=${state.token}`);
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.event === "new_mail") {
        if (state.folder === "INBOX" || state.folder === "SENT") {
          fetchMessages();
          fetchFolderCounts();
        }
        // Browser notification
        if (document.hidden && "Notification" in window && Notification.permission === "granted") {
          const from = (msg.data && msg.data.from) || "Someone";
          const subject = (msg.data && msg.data.subject) || "(no subject)";
          new Notification("New mail from " + from, { body: subject, icon: "/static/favicon.ico" });
        }
      }
    } catch {}
  };
  ws.onclose = () => {
    if (state.token) setTimeout(connectWS, 30000);
  };
}

// Request notification permission on login
function requestNotifyPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

render();
connectWS();
requestNotifyPermission();

// ── SPA deep-linking via URL hash ──

function updateHash() {
  const parts = [];
  if (state.folder && state.folder !== "INBOX") parts.push("folder=" + state.folder);
  if (state.currentMsg) parts.push("msg=" + state.currentMsg.id);
  if (state.searchQuery) parts.push("q=" + encodeURIComponent(state.searchQuery || ""));
  const hash = parts.length ? "#" + parts.join("&") : "#";
  if (window.location.hash !== hash) history.replaceState(null, "", hash);
}

// Restore state from hash on load
function restoreFromHash() {
  if (!state.token) return;
  const hash = window.location.hash.slice(1);
  if (!hash) return;
  const params = new URLSearchParams(hash);
  const folder = params.get("folder");
  const msgId = params.get("msg");
  const q = params.get("q");
  if (folder && folder !== state.folder) {
    state.folder = folder;
    state.currentMsg = null;
    showView("inbox");
    fetchMessages();
  }
  if (q) {
    state.searchQuery = q;
    const el = document.getElementById("searchInput");
    if (el) el.value = q;
    setTimeout(() => fetchMessages(), 100);
  }
  if (msgId) {
    setTimeout(() => openMessage(parseInt(msgId)), 200);
  }
}

setTimeout(restoreFromHash, 300);

// ── Auto-save draft on tab close ──
window.addEventListener("beforeunload", () => {
  if (document.getElementById("composeView")?.style.display !== "block") return;
  const to = document.getElementById("composeTo")?.value;
  const subject = document.getElementById("composeSubject")?.value;
  const body = document.getElementById("composeBody")?.value;
  if (!to && !subject && !body) return;
  const bodyData = { to: to || "", subject: subject || "", body_text: body || "" };
  if (_composeAttachmentIds.length) bodyData.attachment_ids = _composeAttachmentIds;
  try {
    if (!_composeEditId) bodyData.draft = true;
    fetch(_composeEditId ? `${API}/mail/${_composeEditId}` : `${API}/mail`, {
      method: _composeEditId ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json", ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}) },
      body: JSON.stringify(bodyData),
      keepalive: true,
    });
  } catch {}
});
