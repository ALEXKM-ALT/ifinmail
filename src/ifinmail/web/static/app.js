const API = window.location.origin;
const SSO_REDIRECT = window.location.origin;
const isElectron = typeof window.ifinmail !== "undefined";

let _rawToken = localStorage.getItem("ifinmail_token");
let _rawRefresh = localStorage.getItem("ifinmail_refresh");
let state = {
  token: _rawToken && _rawToken !== "undefined" ? _rawToken : null,
  refreshToken: _rawRefresh && _rawRefresh !== "undefined" ? _rawRefresh : null,
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
  convView: false,
  conversations: [],
  signature: null,
  signatureEnabled: false,
  unifiedView: false,
  unifiedFolder: "INBOX",
  unifiedMessages: [],
  unifiedPerPage: 50,
};

if (isElectron) {
  const api = window.ifinmail;
  api.getApiUrl().then(url => { /* API base from main process if needed */ });
  api.onNavigate(route => {
    const nav = document.querySelector(`[data-folder="${route.replace("/", "")}"]`);
    if (nav) { nav.click(); }
  });
  api.onRefresh(() => fetchMessages());
  api.onThemeChanged(isDark => {
    localStorage.setItem("ifinmail_dark", isDark ? "1" : "0");
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "");
  });
  api.isDarkMode().then(isDark => {
    if (isDark) {
      localStorage.setItem("ifinmail_dark", "1");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  });
  api.onMessageContextAction(action => {
    const msg = state.currentMsg;
    if (!msg) return;
    switch (action) {
      case "reply": showCompose("reply", msg); break;
      case "reply-all": showCompose("reply-all", msg); break;
      case "forward": showCompose("forward", msg); break;
      case "toggle-read": toggleRead(msg); break;
      case "archive": document.getElementById("archiveBtn")?.click(); break;
      case "delete": document.getElementById("trashBtn")?.click(); break;
      case "star": toggleStar(msg); break;
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) fetchFolderCounts();
  });
}

let _refreshing = null;

async function apiFetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (state.token) opts.headers["Authorization"] = `Bearer ${state.token}`;
  let res = await fetch(url, opts);
  if (res.headers.get("X-Offline")) {
    const banner = document.getElementById("offlineBanner");
    if (banner) banner.style.display = "block";
  }
  if (res.status === 401) {
    if (state.refreshToken && !_refreshing) {
      _refreshing = (async () => {
        try {
          const r = await fetch(`${API}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: state.refreshToken }),
          });
          if (r.ok) {
            const data = await r.json();
            if (!data.access_token) { clearAuth(); render(); return null; }
            state.token = data.access_token;
            localStorage.setItem("ifinmail_token", state.token);
            if (data.is_admin !== undefined) {
              state.isAdmin = data.is_admin;
              localStorage.setItem("ifinmail_is_admin", String(state.isAdmin));
              const adminNav = document.getElementById("adminNav");
              if (adminNav) adminNav.style.display = state.isAdmin ? "" : "none";
            }
            if (state.email) {
              state.accounts = state.accounts.map(a =>
                a.email === state.email ? { ...a, token: state.token, refreshToken: state.refreshToken } : a
              );
              saveAccounts();
            }
          } else {
            clearAuth();
            render();
            return null;
          }
        } catch { clearAuth(); render(); }
      })();
      await _refreshing;
      _refreshing = null;
      if (state.token) {
        opts.headers["Authorization"] = `Bearer ${state.token}`;
        res = await fetch(url, opts);
      }
    } else if (!state.refreshToken) {
      clearAuth();
      render();
    }
  }
  return res;
}

function clearAuth() {
  state.token = null;
  state.refreshToken = null;
  state.email = null;
  state.isAdmin = false;
  localStorage.removeItem("ifinmail_token");
  localStorage.removeItem("ifinmail_refresh");
  localStorage.removeItem("ifinmail_email");
  localStorage.removeItem("ifinmail_is_admin");
  state.accounts = [];
  saveAccounts();
}

function sanitizeStorage() {
  ["ifinmail_token", "ifinmail_refresh"].forEach(k => {
    const v = localStorage.getItem(k);
    if (v === "undefined") localStorage.removeItem(k);
  });
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
  ["loginView", "inboxView", "messageView", "composeView", "settingsView", "adminView", "sandboxView", "dashboardView", "teamsView"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === name + "View" ? "block" : "none";
  });
}

function render() {
  if (!state.token) {
    showView("login");
    const sb = document.getElementById("sidebar");
    if (sb) sb.innerHTML = "";
    return;
  }
  renderSidebar();
  const inboxView = document.getElementById("inboxView");
  const inboxTmpl = document.getElementById("inboxTmpl");
  if (!inboxView || !inboxTmpl) return;
  inboxView.innerHTML = inboxTmpl.innerHTML;
  showView("inbox");
  if (state.unifiedView) {
    fetchUnifiedMessages();
  } else {
    fetchMessages();
  }
  setupBatchBar();
  setupTrashToolbar();
  renderCustomFolders();
  document.getElementById("markAllReadBtn")?.addEventListener("click", markAllRead);
  document.getElementById("convToggleBtn")?.addEventListener("click", toggleConvView);
}

// ── Sidebar ──

function renderSidebar() {
  const tmpl = document.getElementById("sidebarTmpl");
  if (!tmpl) return;
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  sidebar.innerHTML = tmpl.innerHTML;
  const userEmail = document.getElementById("userEmail");
  if (userEmail) userEmail.textContent = state.email;

  const accList = document.getElementById("accountsListSidebar");
  if (accList) {
    const colors = ["#4361ee","#e63946","#2ec4b6","#ff9f1c","#7209b7","#f72585","#06d6a0","#ef476f"];
    state.accounts.forEach((a, i) => {
      const wrapper = document.createElement("div");
      wrapper.className = "ifinmail-account-avatar-wrapper" + (a.email === state.email ? " active" : "");
      const initial = a.email.charAt(0).toUpperCase();
      const color = colors[i % colors.length];
      wrapper.innerHTML = `<div class="ifinmail-account-avatar" style="background:${color}" title="${a.email}">${initial}<span class="ifinmail-account-badge-count" id="badge-${a.email.replace(/[^a-zA-Z0-9]/g, "_")}" style="display:none;position:absolute;top:-4px;right:-4px;background:var(--primary);color:#fff;font-size:9px;font-weight:700;border-radius:8px;min-width:14px;height:14px;line-height:14px;text-align:center;padding:0 3px;border:1px solid var(--card-bg)"></span></div>`;
      wrapper.onclick = () => switchAccount(a.email, a.token, a.refreshToken);
      accList.appendChild(wrapper);
      // Fetch unread count for this account (only if token is present)
      if (a.token) {
        fetch(`${API}/mail?folder=INBOX&per_page=1`, {
          headers: { Authorization: `Bearer ${a.token}` },
        }).then(r => {
          if (!r.ok) return;
          const count = parseInt(r.headers.get("X-Total-Count") || "0");
          const badge = document.getElementById(`badge-${a.email.replace(/[^a-zA-Z0-9]/g, "_")}`);
          if (badge && count > 0) { badge.textContent = count > 99 ? "99+" : count; badge.style.display = ""; }
        }).catch(() => {});
      }
    });
  }
  document.getElementById("accountsAddBtn").onclick = showAddAccount;

  document.querySelectorAll(".ifinmail-nav-item").forEach(el => {
    el.addEventListener("click", () => {
      if (!el.dataset.folder) return;
      if (state.unifiedView) {
        state.unifiedFolder = el.dataset.folder;
        state.unifiedPerPage = 50;
        state.folder = "UNIFIED";
        state.currentMsg = null;
        showView("inbox");
        fetchUnifiedMessages();
        document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
        el.classList.add("active");
        updateHash();
      } else {
        state.folder = el.dataset.folder;
        state.currentMsg = null;
        showView("inbox");
        fetchMessages();
        document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
        el.classList.add("active");
        updateHash();
      }
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
  const sandboxNav = document.getElementById("sandboxNav");
  if (sandboxNav) {
    sandboxNav.addEventListener("click", () => {
      state.currentMsg = null;
      showView("sandbox");
      renderSandbox();
    });
  }
  const orgsNav = document.getElementById("orgsNav");
  if (orgsNav) {
    orgsNav.addEventListener("click", () => {
      state.currentMsg = null;
      showView("teams");
      renderTeams();
    });
  }
  const dashboardNav = document.getElementById("dashboardNav");
  if (dashboardNav) {
    dashboardNav.addEventListener("click", () => {
      state.currentMsg = null;
      showView("dashboard");
      renderDashboard();
    });
  }

  const scheduledNav = document.getElementById("scheduledNav");
  if (scheduledNav) {
    scheduledNav.addEventListener("click", async () => {
      state.currentMsg = null;
      if (!state.token) return showView("login");
      document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
      scheduledNav.classList.add("active");
      showView("settings");
      await renderSettings("scheduled");
      const section = document.getElementById("scheduledSection");
      if (section) section.scrollIntoView({ behavior: "smooth" });
    });
  }

  // Unified Inbox toggle
  const unifiedCheck = document.getElementById("unifiedToggleCheck");
  if (unifiedCheck) {
    unifiedCheck.checked = state.unifiedView;
    unifiedCheck.addEventListener("change", () => {
      state.unifiedView = unifiedCheck.checked;
      if (state.unifiedView) {
        state.unifiedFolder = "INBOX";
        state.unifiedPerPage = 50;
        state.folder = "UNIFIED";
        state.currentMsg = null;
        showView("inbox");
        fetchUnifiedMessages();
        document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
        // Highlight INBOX
        document.querySelector('.ifinmail-nav-item[data-folder="INBOX"]')?.classList.add("active");
      } else {
        state.folder = "INBOX";
        state.currentMsg = null;
        showView("inbox");
        fetchMessages();
        document.querySelectorAll(".ifinmail-nav-item").forEach(n => n.classList.remove("active"));
      }
      updateHash();
    });
  }

  fetchFolderCounts();
  fetchScheduledCount();
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

  // ── Desktop Preferences (Electron only) ──
  const desktopPrefs = document.getElementById("desktopPrefs");
  if (isElectron && desktopPrefs) {
    const api = window.ifinmail;
    desktopPrefs.style.display = "";

    api.getAppVersion().then(v => document.getElementById("prefVersion").textContent = v);
    api.getAutoStart().then(v => document.getElementById("prefAutoStart").checked = v);
    api.getPref("minimizeToTray", true).then(v => document.getElementById("prefMinimizeToTray").checked = v);
    api.getPref("notifications", true).then(v => document.getElementById("prefNotifications").checked = v);
    api.getPref("theme", "system").then(v => document.getElementById("prefTheme").value = v);
    api.getZoom().then(v => {
      const pct = Math.round(v * 100);
      document.getElementById("prefZoom").value = pct;
      document.getElementById("zoomLabel").textContent = pct + "%";
    });

    document.getElementById("prefAutoStart").addEventListener("change", function() {
      api.setAutoStart(this.checked);
    });
    document.getElementById("prefMinimizeToTray").addEventListener("change", function() {
      api.setPref("minimizeToTray", this.checked);
    });
    document.getElementById("prefNotifications").addEventListener("change", function() {
      api.setPref("notifications", this.checked);
    });
    document.getElementById("prefZoom").addEventListener("input", function() {
      const pct = parseInt(this.value);
      document.getElementById("zoomLabel").textContent = pct + "%";
      api.setZoom(pct / 100);
    });
    document.getElementById("prefTheme").addEventListener("change", function() {
      api.setPref("theme", this.value);
      if (this.value === "light") {
        localStorage.setItem("ifinmail_dark", "0");
        document.documentElement.removeAttribute("data-theme");
      } else if (this.value === "dark") {
        localStorage.setItem("ifinmail_dark", "1");
        document.documentElement.setAttribute("data-theme", "dark");
      }
    });
  }

  // ── Signature (Rich Text) ──
  (async () => {
    try {
      const res = await apiFetch(`${API}/mail/settings/signature`);
      if (res.ok) {
        const data = await res.json();
        document.getElementById("signatureEnabled").checked = data.signature_enabled;
        document.getElementById("signatureEditor").innerHTML = data.signature;
        updateSignaturePreview();
      }
    } catch {}

    document.getElementById("signatureEditor").addEventListener("input", updateSignaturePreview);

    // toolbar buttons
    document.querySelectorAll("#sigToolbar .ifinmail-editor-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const cmd = btn.dataset.cmd;
        if (cmd === "createLink") {
          const url = prompt("Enter link URL:", "https://");
          if (url) document.execCommand(cmd, false, url);
        } else {
          document.execCommand(cmd, false, null);
        }
        document.getElementById("signatureEditor").focus();
        updateSignaturePreview();
      });
    });

    document.getElementById("saveSignature").addEventListener("click", async () => {
      const sig = document.getElementById("signatureEditor").innerHTML;
      const enabled = document.getElementById("signatureEnabled").checked;
      try {
        const res = await apiFetch(`${API}/mail/settings/signature`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ signature: sig, signature_enabled: enabled }),
        });
        if (!res.ok) { document.getElementById("signatureError").textContent = "Failed to save"; return; }
        document.getElementById("signatureError").style.color = "green";
        document.getElementById("signatureError").textContent = "Saved";
        state.signature = sig;
        state.signatureEnabled = enabled;
      } catch { document.getElementById("signatureError").textContent = "Network error"; }
    });
  })();

  function updateSignaturePreview() {
    const preview = document.getElementById("signaturePreview");
    const html = document.getElementById("signatureEditor").innerHTML;
    if (preview) preview.innerHTML = html && html !== "<br>" ? html : "<em style='color:var(--text-light)'>No signature</em>";
  }

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
          const label = document.createElement("span");
          label.className = "ifinmail-forwarding-label";
          label.textContent = r.target_email;
          const toggle = document.createElement("label");
          toggle.className = "ifinmail-toggle";
          toggle.innerHTML = `<input type="checkbox" ${r.enabled ? "checked" : ""} data-rule-id="${r.id}"><span class="ifinmail-toggle-slider"></span>`;
          toggle.querySelector("input").addEventListener("change", async function() {
            const res = await apiFetch(`${API}/mail/settings/forwarding/${r.id}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ enabled: this.checked }),
            });
            if (!res.ok) { this.checked = !this.checked; }
          });
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Remove";
          del.onclick = async () => {
            await apiFetch(`${API}/mail/settings/forwarding/${r.id}`, {
              method: "DELETE",
            });
            loadForwarding();
          };
          row.appendChild(label);
          row.appendChild(toggle);
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

  // Load scheduled messages
  async function loadScheduled() {
    try {
      const res = await apiFetch(`${API}/mail/scheduled`);
      if (res.ok) {
        const msgs = await res.json();
        const list = document.getElementById("scheduledList");
        list.innerHTML = "";
        if (!msgs.length) { list.innerHTML = '<p style="color:var(--muted);font-size:13px">No scheduled messages.</p>'; return; }
        msgs.forEach(m => {
          const row = document.createElement("div");
          row.className = "ifinmail-forwarding-row";
          const info = document.createElement("span");
          info.style.flex = "1";
          const dt = new Date(m.scheduled_at);
          const dateStr = dt.toLocaleString();
          const repeatInfo = m.repeat_interval ? ` · <strong>repeats ${m.repeat_interval}</strong>${m.repeat_until ? ` until ${new Date(m.repeat_until).toLocaleDateString()}` : ''}` : '';
          info.innerHTML = `<strong>${m.subject || "(no subject)"}</strong> → ${m.to_addr}<br><span style="font-size:11px;color:var(--muted)">${dateStr} · ${m.status}${repeatInfo}</span>`;
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Cancel";
          del.onclick = async () => {
            await apiFetch(`${API}/mail/scheduled/${m.id}`, { method: "DELETE" });
            loadScheduled();
          };
          row.appendChild(info);
          row.appendChild(del);
          list.appendChild(row);
        });
      }
    } catch {}
  }
  loadScheduled();

  // Load campaigns
  async function loadCampaigns() {
    try {
      const res = await apiFetch(`${API}/mail/campaigns`);
      if (res.ok) {
        const campaigns = await res.json();
        const list = document.getElementById("campaignsList");
        list.innerHTML = "";
        if (!campaigns.length) { list.innerHTML = '<p style="color:var(--muted);font-size:13px">No campaigns yet.</p>'; return; }
        campaigns.forEach(c => {
          const card = document.createElement("div");
          card.className = "ifinmail-forwarding-row";
          card.style.flexWrap = "wrap";
          const header = document.createElement("div");
          header.style.width = "100%";
          header.innerHTML = `<strong>${c.name}</strong><span style="font-size:11px;color:var(--muted);margin-left:8px">${c.steps?.length || 0} steps</span>`;
          card.appendChild(header);
          if (c.steps?.length) {
            const stepsList = document.createElement("div");
            stepsList.style.width = "100%";
            stepsList.style.paddingLeft = "16px";
            stepsList.style.fontSize = "12px";
            stepsList.style.color = "var(--muted)";
            c.steps.forEach((s, i) => {
              stepsList.innerHTML += `<div>Step ${i+1}: "${s.subject || '(no subject)'}" (delay ${s.delay_days}d)</div>`;
            });
            card.appendChild(stepsList);
          }
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Delete";
          del.onclick = async () => {
            await apiFetch(`${API}/mail/campaigns/${c.id}`, { method: "DELETE" });
            loadCampaigns();
          };
          card.appendChild(del);
          list.appendChild(card);
        });
      }
    } catch {}
  }
  loadCampaigns();

  document.getElementById("addCampaignBtn").addEventListener("click", async () => {
    const name = document.getElementById("campaignNameInput").value.trim();
    if (!name) return;
    document.getElementById("campaignError").textContent = "";
    try {
      const res = await apiFetch(`${API}/mail/campaigns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) { document.getElementById("campaignError").textContent = "Failed to create"; return; }
      document.getElementById("campaignNameInput").value = "";
      loadCampaigns();
      showToast("Campaign created. Edit & add steps via API or Swagger UI.");
    } catch { document.getElementById("campaignError").textContent = "Network error"; }
  });

  // ── Filter rules ──
  let _filterConditions = [];
  let _filterActions = [];
  let _editingFilterId = null;

  function renderFilterConditions() {
    const list = document.getElementById("filterConditionsList");
    list.innerHTML = _filterConditions.map((c, i) =>
      `<span style="display:inline-block;background:var(--border);padding:2px 6px;border-radius:4px;margin:2px">${c.field} ${c.operator} "${c.value}" <a href="#" data-idx="${i}" class="remove-filter-cond" style="color:red;text-decoration:none">x</a></span>`
    ).join(" ");
    list.querySelectorAll(".remove-filter-cond").forEach(el => {
      el.onclick = (e) => { e.preventDefault(); _filterConditions.splice(parseInt(el.dataset.idx), 1); renderFilterConditions(); };
    });
  }

  function renderFilterActions() {
    const list = document.getElementById("filterActionsList");
    list.innerHTML = _filterActions.map((a, i) =>
      `<span style="display:inline-block;background:var(--border);padding:2px 6px;border-radius:4px;margin:2px">${a.type}${a.value ? ' "'+a.value+'"' : ''} <a href="#" data-idx="${i}" class="remove-filter-act" style="color:red;text-decoration:none">x</a></span>`
    ).join(" ");
    list.querySelectorAll(".remove-filter-act").forEach(el => {
      el.onclick = (e) => { e.preventDefault(); _filterActions.splice(parseInt(el.dataset.idx), 1); renderFilterActions(); };
    });
  }

  document.getElementById("addFilterCondition").addEventListener("click", () => {
    const field = document.getElementById("filterConditionField").value;
    const op = document.getElementById("filterConditionOp").value;
    const value = document.getElementById("filterConditionValue").value.trim();
    if (!value) return;
    _filterConditions.push({ field, operator: op, value });
    document.getElementById("filterConditionValue").value = "";
    renderFilterConditions();
  });

  document.getElementById("addFilterAction").addEventListener("click", () => {
    const type = document.getElementById("filterActionType").value;
    const value = document.getElementById("filterActionValue").value.trim();
    _filterActions.push({ type, value });
    document.getElementById("filterActionValue").value = "";
    renderFilterActions();
  });

  document.getElementById("saveFilterRule").addEventListener("click", async () => {
    const name = document.getElementById("filterRuleName").value.trim();
    document.getElementById("filterRuleError").textContent = "";
    if (!_filterConditions.length) { document.getElementById("filterRuleError").textContent = "Add at least one condition"; return; }
    if (!_filterActions.length) { document.getElementById("filterRuleError").textContent = "Add at least one action"; return; }
    const body = { name, conditions: _filterConditions, actions: _filterActions };
    const url = _editingFilterId ? `${API}/mail/filters/${_editingFilterId}` : `${API}/mail/filters`;
    const method = _editingFilterId ? "PUT" : "POST";
    try {
      const res = await apiFetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!res.ok) { const d = await res.json(); document.getElementById("filterRuleError").textContent = d.detail || "Failed"; return; }
      _filterConditions = [];
      _filterActions = [];
      _editingFilterId = null;
      document.getElementById("filterRuleName").value = "";
      renderFilterConditions();
      renderFilterActions();
      loadFilterRules();
      document.querySelector("details summary")?.click();
    } catch { document.getElementById("filterRuleError").textContent = "Network error"; }
  });

  async function loadFilterRules() {
    try {
      const res = await apiFetch(`${API}/mail/filters`);
      if (res.ok) {
        const rules = await res.json();
        const list = document.getElementById("filterRulesList");
        list.innerHTML = "";
        if (!rules.length) { list.innerHTML = '<p style="color:var(--muted);font-size:13px">No filter rules.</p>'; return; }
        rules.forEach(r => {
          const card = document.createElement("div");
          card.className = "ifinmail-forwarding-row";
          card.style.flexWrap = "wrap";
          const info = document.createElement("div");
          info.style.flex = "1";
          const condStr = (r.conditions || []).map(c => `${c.field} ${c.operator} "${c.value}"`).join(", ");
          const actStr = (r.actions || []).map(a => `${a.type}${a.value ? ' "'+a.value+'"' : ''}`).join(", ");
          info.innerHTML = `<strong>${r.name || "(unnamed)"}</strong> <span style="font-size:11px;color:var(--muted)">${r.match_logic === "any" ? "ANY" : "ALL"}</span><br><span style="font-size:11px;color:var(--muted)">If ${condStr} → ${actStr}</span>`;
          const toggle = document.createElement("label");
          toggle.className = "ifinmail-toggle";
          toggle.innerHTML = `<input type="checkbox" ${r.enabled ? "checked" : ""} data-rule-id="${r.id}"><span class="ifinmail-toggle-slider"></span>`;
          toggle.querySelector("input").addEventListener("change", async function() {
            const res2 = await apiFetch(`${API}/mail/filters/${r.id}/toggle`, { method: "PUT" });
            if (!res2.ok) { this.checked = !this.checked; }
          });
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Remove";
          del.onclick = async () => {
            await apiFetch(`${API}/mail/filters/${r.id}`, { method: "DELETE" });
            loadFilterRules();
          };
          card.appendChild(info);
          card.appendChild(toggle);
          card.appendChild(del);
          list.appendChild(card);
        });
      }
    } catch {}
  }
  loadFilterRules();

  // Load aliases
  async function loadAliases() {
    try {
      const res = await apiFetch(`${API}/aliases`);
      if (res.ok) {
        const aliases = await res.json();
        const list = document.getElementById("aliasesList");
        list.innerHTML = "";
        if (!aliases.length) { list.innerHTML = '<p style="color:var(--muted);font-size:13px">No aliases.</p>'; return; }
        aliases.forEach(a => {
          const row = document.createElement("div");
          row.className = "ifinmail-forwarding-row";
          const label = document.createElement("span");
          label.style.flex = "1";
          label.innerHTML = `<strong>${a.source}</strong> → ${a.target}`;
          const toggle = document.createElement("label");
          toggle.className = "ifinmail-toggle";
          toggle.innerHTML = `<input type="checkbox" ${a.enabled ? "checked" : ""} data-alias-id="${a.id}"><span class="ifinmail-toggle-slider"></span>`;
          toggle.querySelector("input").addEventListener("change", async function() {
            const r = await apiFetch(`${API}/aliases/${a.id}/toggle`, { method: "PUT" });
            if (!r.ok) { this.checked = !this.checked; }
          });
          const del = document.createElement("button");
          del.className = "ifinmail-btn ifinmail-btn-sm";
          del.textContent = "Remove";
          del.onclick = async () => {
            await apiFetch(`${API}/aliases/${a.id}`, { method: "DELETE" });
            loadAliases();
          };
          row.appendChild(label);
          row.appendChild(toggle);
          row.appendChild(del);
          list.appendChild(row);
        });
      }
    } catch {}
  }
  loadAliases();

  document.getElementById("addAliasBtn").addEventListener("click", async () => {
    const source = document.getElementById("aliasSourceInput").value.trim();
    const target = document.getElementById("aliasTargetInput").value.trim();
    document.getElementById("aliasError").textContent = "";
    if (!source || !target) { document.getElementById("aliasError").textContent = "Fill in both fields"; return; }
    try {
      const res = await apiFetch(`${API}/aliases`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source, target }),
      });
      if (!res.ok) { const d = await res.json(); document.getElementById("aliasError").textContent = d.detail || "Failed"; return; }
      document.getElementById("aliasSourceInput").value = "";
      document.getElementById("aliasTargetInput").value = "";
      loadAliases();
    } catch { document.getElementById("aliasError").textContent = "Network error"; }
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
        const vSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-left:4px"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
        const pSvg = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-left:4px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
        const badge = d.verified ? '<span style="color:var(--success);font-size:11px;">Verified</span>' : '<span style="color:var(--warning);font-size:11px;">Pending</span>';
        row.innerHTML = `<span style="flex:1">${d.domain} ${d.verified ? vSvg : pSvg}</span> ${badge}`;
        const verifyBtn = document.createElement("button");
        verifyBtn.className = "ifinmail-btn ifinmail-btn-sm";
        verifyBtn.textContent = "DNS Wizard";
        verifyBtn.style.marginLeft = "8px";
        verifyBtn.onclick = () => openDomainWizard(d);
        row.appendChild(verifyBtn);
        list.appendChild(row);
      });
    } catch {}
  }
  loadDomains();

  async function openDomainWizard(d) {
    const wizard = document.getElementById("domainWizard");
    wizard.style.display = "block";
    wizard.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-light)">Loading...</div>';

    // Fetch suggested records
    let verifyData;
    try {
      const r = await apiFetch(`${API}/domains/${d.id}/verify`);
      if (!r.ok) { wizard.innerHTML = '<div style="text-align:center;padding:16px;color:var(--error)">Failed to load DNS records</div>'; return; }
      verifyData = await r.json();
    } catch { wizard.innerHTML = '<div style="text-align:center;padding:16px;color:var(--error)">Network error</div>'; return; }

    function statusIcon(ok) {
      return ok
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    }

    function recordRow(rec, ok) {
      const val = rec.type === "MX" ? `${rec.priority} ${rec.value}` : rec.value;
      return `<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)">
        <div style="flex-shrink:0;margin-top:2px">${statusIcon(ok)}</div>
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;font-weight:600;color:var(--text)">${rec.type} Record</div>
          <div style="font-size:12px;color:var(--text-light);word-break:break-all"><strong>Name:</strong> ${rec.name}</div>
          <div style="font-size:12px;color:var(--text-light);word-break:break-all"><strong>Value:</strong> ${val}</div>
          <div style="font-size:11px;color:var(--text-light);margin-top:2px">${rec.purpose}</div>
        </div>
        <button class="ifinmail-btn ifinmail-btn-sm" onclick="navigator.clipboard.writeText('${val.replace(/"/g, '&quot;')}')">Copy</button>
      </div>`;
    }

    function wizardHeader(title, subtitle) {
      return `<div style="margin-bottom:12px"><h4 style="margin:0 0 2px;font-size:15px">${title}</h4><p style="margin:0;font-size:12px;color:var(--text-light)">${subtitle}</p></div>`;
    }

    // Fetch current DNS check status
    let checkData;
    try {
      const r = await apiFetch(`${API}/domains/${d.id}/check-dns`, { method: "POST" });
      if (r.ok) checkData = await r.json();
    } catch {}

    const checks = checkData?.checks || {};

    let html = wizardHeader("DNS Setup", "Add these DNS records at your domain registrar. Changes may take up to 48 hours to propagate.");

    // DNS records table
    html += verifyData.dns_records.map(rec => {
      const key = rec.type === "MX" ? "mx" : rec.type === "TXT" && rec.name.startsWith("default._domainkey") ? "dkim" : rec.name.startsWith("_dmarc") ? "dmarc" : rec.name.startsWith("_verify") ? "ownership" : "spf";
      const check = checks[key] || {};
      const ok = check.ok === true;
      return recordRow(rec, ok);
    }).join("");

    // Check button + status
    const allOk = checks.all_ok === true;
    html += `<div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
      <div>
        ${allOk
          ? '<span style="color:var(--success);font-size:13px;font-weight:600">All DNS records verified! Domain is active.</span>'
          : `<span style="color:var(--text-light);font-size:13px">Status: ${checkData?.verified ? 'Verified' : 'Not verified'}</span>`
        }
      </div>
      <button class="ifinmail-btn ifinmail-btn-primary" id="checkDnsBtn" style="display:inline-flex;align-items:center;gap:6px">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Check DNS Now
      </button>
    </div>`;

    wizard.innerHTML = html;

    document.getElementById("checkDnsBtn").onclick = async () => {
      const btn = document.getElementById("checkDnsBtn");
      btn.disabled = true; btn.textContent = "Checking...";
      try {
        const r = await apiFetch(`${API}/domains/${d.id}/check-dns`, { method: "POST" });
        if (r.ok) {
          const data = await r.json();
          openDomainWizard({ ...d, verified: data.verified });
        } else { showToast("DNS check failed"); }
      } catch { showToast("Network error"); }
      btn.disabled = false; btn.textContent = "Check DNS Now";
    };

    // DKIM key generation
    html += `<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">
      <h4 style="margin:0 0 6px;font-size:14px">DKIM Signing Key</h4>
      <p style="font-size:12px;color:var(--muted);margin:0 0 8px">Generate an RSA key pair for signing outgoing email with DKIM. Publish the DNS record shown after generation.</p>
      <button class="ifinmail-btn ifinmail-btn-primary ifinmail-btn-sm" id="generateDkimBtn">Generate DKIM Key</button>
      <div id="dkimResult" style="margin-top:8px"></div>
    </div>`;
    wizard.innerHTML = html;

    document.getElementById("generateDkimBtn").onclick = async () => {
      const btn = document.getElementById("generateDkimBtn");
      btn.disabled = true; btn.textContent = "Generating...";
      const resultDiv = document.getElementById("dkimResult");
      resultDiv.innerHTML = "";
      try {
        const r = await apiFetch(`${API}/domains/${d.id}/generate-dkim-key`, { method: "POST" });
        if (r.ok) {
          const data = await r.json();
          const rec = data.dns_record;
          resultDiv.innerHTML = `
            <div style="padding:8px;background:var(--bg);border-radius:6px;font-size:12px">
              <p style="margin:0 0 6px;color:var(--success);font-weight:600">Key generated!</p>
              <p style="margin:0 0 4px"><strong>Selector:</strong> ${data.selector}</p>
              <p style="margin:0 0 4px"><strong>DNS Record</strong></p>
              <div style="background:#111;color:#0f0;padding:8px;border-radius:4px;word-break:break-all;font-family:monospace;font-size:11px;margin-bottom:6px">
                <div><strong>Type:</strong> ${rec.type}</div>
                <div><strong>Name:</strong> ${rec.name}</div>
                <div><strong>Value:</strong> ${rec.value}</div>
              </div>
              <button class="ifinmail-btn ifinmail-btn-sm" onclick="navigator.clipboard.writeText('${rec.value.replace(/"/g, '&quot;')}')">Copy Value</button>
            </div>`;
        } else { const e = await r.json(); resultDiv.innerHTML = `<span style="color:var(--error);font-size:12px">${e.detail || "Failed"}</span>`; }
      } catch { resultDiv.innerHTML = `<span style="color:var(--error);font-size:12px">Network error</span>`; }
      btn.disabled = false; btn.textContent = "Generate DKIM Key";
    };
  }

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

  // Load IMAP import config
  async function loadImapConfig() {
    try {
      const res = await apiFetch(`${API}/mail/import/imap`);
      if (!res.ok) return;
      const data = await res.json();
      if (!data) return;
      document.getElementById("imapHost").value = data.host || "imap.gmail.com";
      document.getElementById("imapPort").value = data.port || 993;
      document.getElementById("imapUsername").value = data.username || "";
      document.getElementById("imapUseSSL").checked = data.use_ssl !== false;
      const statusEl = document.getElementById("imapImportStatus");
      if (data.last_run_at) {
        statusEl.innerHTML = `<span style="color:var(--muted)">Last import: ${new Date(data.last_run_at).toLocaleString()} · Status: ${data.last_run_status} · ${data.last_run_count} messages</span>`;
      }
    } catch {}
  }
  loadImapConfig();

  document.getElementById("testImapBtn").addEventListener("click", async () => {
    const btn = document.getElementById("testImapBtn");
    btn.disabled = true; btn.textContent = "Testing...";
    document.getElementById("imapImportStatus").innerHTML = "";
    try {
      const res = await apiFetch(`${API}/mail/import/imap/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: document.getElementById("imapHost").value,
          port: parseInt(document.getElementById("imapPort").value) || 993,
          username: document.getElementById("imapUsername").value,
          password: document.getElementById("imapPassword").value,
          use_ssl: document.getElementById("imapUseSSL").checked,
          folder: "INBOX",
        }),
      });
      const data = await res.json();
      const el = document.getElementById("imapImportStatus");
      if (data.ok) { el.style.color = "var(--success)"; el.textContent = "Connected! " + (data.detail || ""); }
      else { el.style.color = "var(--error)"; el.textContent = data.detail || "Connection failed"; }
    } catch { document.getElementById("imapImportStatus").textContent = "Network error"; }
    btn.disabled = false; btn.textContent = "Test Connection";
  });

  document.getElementById("saveImapBtn").addEventListener("click", async () => {
    document.getElementById("imapImportStatus").innerHTML = "";
    try {
      const res = await apiFetch(`${API}/mail/import/imap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: document.getElementById("imapHost").value,
          port: parseInt(document.getElementById("imapPort").value) || 993,
          username: document.getElementById("imapUsername").value,
          password: document.getElementById("imapPassword").value,
          use_ssl: document.getElementById("imapUseSSL").checked,
          folder: "INBOX",
        }),
      });
      if (!res.ok) { document.getElementById("imapImportStatus").textContent = "Failed to save"; return; }
      // Trigger import
      const runRes = await apiFetch(`${API}/mail/import/imap/run`, { method: "POST" });
      if (runRes.ok) {
        document.getElementById("imapImportStatus").style.color = "var(--success)";
        document.getElementById("imapImportStatus").textContent = "Import started! New messages will appear in your inbox.";
        setTimeout(loadImapConfig, 5000);
      } else { const d = await runRes.json(); document.getElementById("imapImportStatus").textContent = d.detail || "Import failed"; }
    } catch { document.getElementById("imapImportStatus").textContent = "Network error"; }
  });

  // Load API tokens
  async function loadApiTokens() {
    try {
      const res = await apiFetch(`${API}/api-keys`);
      if (!res.ok) return;
      const keys = await res.json();
      const list = document.getElementById("apiTokensList");
      if (!list) return;
      list.innerHTML = keys.length
        ? keys.map(k => `
          <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)">
            <div>
              <strong>${k.name}</strong>
              <div style="font-size:12px;color:var(--muted)">${k.key_prefix}... · ${k.active ? "Active" : "Revoked"}${k.last_used_at ? " · Last used: " + new Date(k.last_used_at).toLocaleDateString() : ""}</div>
            </div>
            ${k.active ? `<button class="ifinmail-btn ifinmail-btn-sm" onclick="revokeApiKey(${k.id})">Revoke</button>` : ""}
          </div>
        `).join("")
        : '<p style="font-size:13px;color:var(--muted)">No API tokens yet.</p>';
    } catch {}
  }
  loadApiTokens();

  document.getElementById("addApiTokenBtn").addEventListener("click", async () => {
    const name = document.getElementById("apiTokenNameInput").value.trim();
    if (!name) return;
    document.getElementById("apiTokenError").textContent = "";
    try {
      const res = await apiFetch(`${API}/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) { const d = await res.json(); document.getElementById("apiTokenError").textContent = d.detail || "Failed"; return; }
      const data = await res.json();
      document.getElementById("apiTokenNameInput").value = "";
      document.getElementById("apiTokenError").style.color = "green";
      document.getElementById("apiTokenError").textContent = `Token created: ${data.full_key} (save this now)`;
      loadApiTokens();
    } catch { document.getElementById("apiTokenError").textContent = "Network error"; }
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
  loadMpesaPayment();
}

async function fetchFolderCounts() {
  try {
    const res = await apiFetch(`${API}/mail/folder-counts`);
    if (res.ok) {
      const counts = await res.json();
      document.querySelectorAll(".ifinmail-badge[id^='count-']").forEach(el => {
        if (el.id === "count-SCHEDULED") return;
        const folder = el.id.replace("count-", "");
        el.textContent = counts[folder] > 0 ? counts[folder] : "";
      });
      document.querySelectorAll("#customFoldersSidebar .ifinmail-nav-item").forEach(el => {
        const folder = el.dataset.folder;
        const badge = el.querySelector(".ifinmail-badge");
        if (badge) badge.textContent = counts[folder] > 0 ? counts[folder] : "";
      });
      if (isElectron && counts.INBOX !== undefined) {
        window.ifinmail.setBadge(counts.INBOX);
      }
    }
  } catch {}
}

async function fetchScheduledCount() {
  const badge = document.getElementById("count-SCHEDULED");
  if (!badge) return;
  try {
    const res = await apiFetch(`${API}/mail/scheduled`);
    if (res.ok) {
      const msgs = await res.json();
      const pending = msgs.filter(m => m.status === "pending").length;
      badge.textContent = pending > 0 ? pending : "";
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

function toggleConvView() {
  state.convView = !state.convView;
  const btn = document.getElementById("convToggleBtn");
  if (btn) btn.style.opacity = state.convView ? "1" : "0.5";
  showToast(state.convView ? "Conversation view on" : "Flat view");
  fetchMessages();
}

// ── Admin Dashboard ──

async function renderAdmin() {
  const tmpl = document.getElementById("adminTmpl");
  document.getElementById("adminView").innerHTML = tmpl.innerHTML;
  document.getElementById("adminError").textContent = "";

  document.getElementById("adminDateBadge").textContent = "Last 30 days";

  let currentATab = "overview";
  function showATab(name) {
    currentATab = name;
    document.querySelectorAll("[data-atab]").forEach(t => t.classList.toggle("active", t.dataset.atab === name));
    document.querySelectorAll("#adminOverview, #adminUsers, #adminDomains, #adminBilling, #adminSecurity, #adminSystem").forEach(el => {
      el.style.display = el.id === "admin" + name.charAt(0).toUpperCase() + name.slice(1) ? "" : "none";
    });
    if (name === "users") loadAdminUsers();
    if (name === "domains") loadAdminDomains();
    if (name === "billing") loadAdminBilling();
    if (name === "security") loadAdminSecurity();
    if (name === "system") loadAdminSystem();
  }

  document.querySelectorAll("[data-atab]").forEach(tab => {
    tab.addEventListener("click", () => showATab(tab.dataset.atab));
  });

  const trends = {
    Users: "registered", Domains: "custom domains", Messages: "last 7 days",
    Storage: "of 100 GB", Attachments: "total size", Aliases: "this week",
    Mailboxes: "active today", "Active today": "last login",
  };

  const s = (d) => `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px">${d}</svg>`;

  try {
    const res = await apiFetch(`${API}/admin/stats`);
    if (!res.ok) { document.getElementById("adminError").textContent = "Failed to load stats"; return; }
    const stats = await res.json();
    const cards = document.getElementById("adminCards");
    cards.innerHTML = "";
    const items = [
      { label: "Users", value: stats.total_users, trend: `+${stats.users_last_24h} this month`, icon: s('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>') },
      { label: "Domains", value: stats.total_domains, trend: `${stats.total_domains} custom domains`, icon: s('<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>') },
      { label: "Messages", value: stats.total_messages, trend: `${stats.total_messages} total`, icon: s('<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>') },
      { label: "Storage", value: (stats.total_storage_bytes / 1024).toFixed(1) + " KB", trend: "of 100 GB", icon: s('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>') },
      { label: "Attachments", value: stats.total_attachments, trend: `${stats.total_attachments} files`, icon: s('<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>') },
      { label: "Aliases", value: stats.total_aliases, trend: `${stats.total_aliases} created`, icon: s('<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>') },
      { label: "Mailboxes", value: stats.total_mailboxes, trend: `${stats.active_today} active today`, icon: s('<path d="M22 17a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9.5C2 7 4 5 6.5 5H18c2.2 0 4 1.8 4 4v8Z"/><polyline points="15,9 18,9 18,11"/><path d="M6.5 5C9 5 11 7 11 9.5V17a2 2 0 0 1-2 2"/>') },
      { label: "Active today", value: stats.active_today, trend: "last 24 hours", icon: s('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>') },
    ];
    items.forEach(item => {
      const card = document.createElement("div");
      card.className = "ifinmail-admin-stat-card";
      card.innerHTML = `<div class="ifinmail-admin-stat-title">${item.icon} ${item.label}</div><div class="ifinmail-admin-stat-number">${item.value}</div><div class="ifinmail-admin-stat-trend">${item.trend}</div>`;
      cards.appendChild(card);
    });

      if (typeof Chart !== "undefined") {
      const growthRes = await apiFetch(`${API}/admin/stats/growth?days=30`);
      if (growthRes.ok) {
        const growth = await growthRes.json();
        const ctx1 = document.getElementById("adminGrowthChart")?.getContext("2d");
        if (ctx1) {
          new Chart(ctx1, {
            type: "line",
            data: {
              labels: growth.map(g => {
                const d = new Date(g.date + "T00:00:00");
                return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
              }),
              datasets: [{
                label: "New Users",
                data: growth.map(g => g.count),
                borderColor: "#4f46e5",
                backgroundColor: "rgba(79,70,229,0.08)",
                fill: true, tension: 0.3, pointRadius: 3,
              }],
            },
            options: {
              responsive: true, maintainAspectRatio: true,
              plugins: { legend: { display: false } },
              scales: { y: { beginAtZero: true, ticks: { precision: 0, stepSize: 1 } } },
            },
          });
        }
      }

      const volRes = await apiFetch(`${API}/admin/stats/emails?days=7`);
      if (volRes.ok) {
        const vol = await volRes.json();
        const ctx2 = document.getElementById("adminVolumeChart")?.getContext("2d");
        if (ctx2) {
          new Chart(ctx2, {
            type: "bar",
            data: {
              labels: vol.map(v => {
                const d = new Date(v.date + "T00:00:00");
                return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
              }),
              datasets: [{
                label: "Messages",
                data: vol.map(v => v.count),
                backgroundColor: "#7c3aed",
                borderRadius: 6,
              }],
            },
            options: {
              responsive: true, maintainAspectRatio: true,
              plugins: { legend: { display: false } },
              scales: { y: { beginAtZero: true, ticks: { precision: 0, stepSize: 1 } } },
            },
          });
        }
      }
    }

    const auditRes = await apiFetch(`${API}/admin/audit-logs?per_page=10`);
    if (auditRes.ok) {
      const auditData = await auditRes.json();
      const tbody = document.getElementById("adminActivityBody");
      if (tbody) {
        const items = auditData.items || [];
        tbody.innerHTML = items.length
          ? items.map(a => `<tr><td>${a.admin_email || "system"}</td><td>${a.action}</td><td>${a.target_user || a.details || "—"}</td><td>${timeAgo(a.created_at)}</td></tr>`).join("")
          : '<tr><td colspan="4" style="text-align:center;color:var(--text-light)">No recent activity</td></tr>';
      }
    }
  } catch { document.getElementById("adminError").textContent = "Network error"; }
}

function timeAgo(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  return Math.floor(diff / 86400) + "d ago";
}

// ── Admin Users sub-tab ──

let adminUsersPage = 1;
async function loadAdminUsers() {
  // Populate domain dropdown for quick-create
  const domainSel = document.getElementById("adminQuickDomain");
  if (domainSel && !domainSel.options.length) {
    try {
      const r = await apiFetch(`${API}/admin/domains`);
      if (r.ok) {
        const data = await r.json();
        data.items.forEach(d => {
          const opt = document.createElement("option");
          opt.value = d.domain;
          opt.textContent = d.domain;
          domainSel.appendChild(opt);
        });
      }
    } catch {}
  }

  // Quick-create user
  document.getElementById("adminQuickCreateBtn").onclick = async () => {
    const name = document.getElementById("adminQuickName").value.trim();
    const domain = document.getElementById("adminQuickDomain").value;
    const resultEl = document.getElementById("adminQuickResult");
    resultEl.textContent = "";
    if (!name) { resultEl.textContent = "Enter a name"; return; }
    if (!domain) { resultEl.textContent = "No domain available"; return; }
    const parts = name.split(/\s+/);
    const first = parts[0];
    const last = parts.slice(1).join(" ") || first;
    const email = first.toLowerCase() + "." + last.toLowerCase().replace(/\s+/g, "") + "@" + domain;
    const password = Math.random().toString(36).slice(2, 10) + "A1!";
    try {
      const r = await apiFetch(`${API}/admin/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, first_name: first, last_name: last, is_admin: false }),
      });
      if (r.ok) {
        const u = await r.json();
        resultEl.style.color = "var(--success, green)";
        resultEl.innerHTML = `Created <strong>${email}</strong> / <code>${password}</code>`;
        document.getElementById("adminQuickName").value = "";
        loadAdminUsers();
      } else {
        const d = await r.json();
        resultEl.textContent = d.detail || "Failed";
      }
    } catch { resultEl.textContent = "Network error"; }
  };
  const search = document.getElementById("adminUserSearch")?.value || "";
  const url = `${API}/admin/users?page=${adminUsersPage}&per_page=20` + (search ? `&search=${encodeURIComponent(search)}` : "");
  try {
    const res = await apiFetch(url);
    if (!res.ok) return;
    const data = await res.json();
    const table = document.getElementById("adminUsersTable");
    table.innerHTML = "<thead><tr><th>ID</th><th>Email</th><th>Name</th><th>Admin</th><th>Created</th></tr></thead><tbody>" +
      data.items.map(u => `<tr><td>${u.id}</td><td>${u.email}</td><td>${[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}</td><td>${u.is_admin ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>' : ""}</td><td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : ""}</td></tr>`).join("") +
      "</tbody>";
    const pag = document.getElementById("adminUsersPagination");
    pag.innerHTML = "";
    if (data.pagination.total_pages > 1) {
      const prev = document.createElement("button");
      prev.className = "ifinmail-btn ifinmail-btn-sm";
      prev.textContent = "‹ Prev";
      prev.disabled = data.pagination.page <= 1;
      prev.onclick = () => { adminUsersPage--; loadAdminUsers(); };
      pag.appendChild(prev);
      const span = document.createElement("span");
      span.style.cssText = "margin:0 8px;font-size:13px;color:var(--text-light)";
      span.textContent = `Page ${data.pagination.page} of ${data.pagination.total_pages}`;
      pag.appendChild(span);
      const next = document.createElement("button");
      next.className = "ifinmail-btn ifinmail-btn-sm";
      next.textContent = "Next ›";
      next.disabled = data.pagination.page >= data.pagination.total_pages;
      next.onclick = () => { adminUsersPage++; loadAdminUsers(); };
      pag.appendChild(next);
    }
  } catch {}
}

// ── Admin Domains sub-tab ──

async function loadAdminDomains() {
  try {
    const res = await apiFetch(`${API}/admin/domains`);
    if (!res.ok) return;
    const data = await res.json();
    const table = document.getElementById("adminDomainsTable");
    function ck(v) {
      return v
        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-light)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    }
    table.innerHTML = "<thead><tr><th>ID</th><th>Domain</th><th>SPF</th><th>DKIM</th><th>DMARC</th><th>MX</th><th>Verified</th><th>Created</th></tr></thead><tbody>" +
      data.items.map(d => `<tr><td>${d.id}</td><td>${d.domain}</td><td>${ck(d.spf_ok)}</td><td>${ck(d.dkim_ok)}</td><td>${ck(d.dmarc_ok)}</td><td>${ck(d.mx_ok)}</td><td>${ck(d.verified)}</td><td>${d.created_at ? new Date(d.created_at).toLocaleDateString() : ""}</td></tr>`).join("") +
      "</tbody>";
  } catch {}
}

// ── Admin Billing sub-tab ──

async function loadAdminBilling() {
  try {
    const [plansRes, subsRes] = await Promise.all([
      apiFetch(`${API}/admin/billing/plans`),
      apiFetch(`${API}/admin/billing/subscriptions`),
    ]);
    if (plansRes.ok) {
      const plans = await plansRes.json();
      document.getElementById("adminPlansList").innerHTML = plans.map(p =>
        `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border)"><span><strong>${p.name}</strong> (${p.id})</span><span>$${p.price}/mo · ${p.quota_mb}MB</span></div>`
      ).join("");
    }
    if (subsRes.ok) {
      const subs = await subsRes.json();
      document.getElementById("adminSubscriptionsList").innerHTML = `<div style="overflow-x:auto"><table class="ifinmail-admin-table" style="width:100%;font-size:13px"><thead><tr><th>Email</th><th>Plan</th><th>Quota</th><th>Used</th><th>Enabled</th></tr></thead><tbody>` +
        subs.map(s => `<tr><td>${s.email}</td><td>${s.plan || "free"}</td><td>${s.quota_mb}MB</td><td>${s.used_mb}MB</td><td>${s.enabled
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;color:var(--primary)"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
          : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;color:var(--danger)"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'}</td></tr>`).join("") +
        "</tbody></table></div>";
    }
  } catch {}
}

// ── Admin Security sub-tab ──

async function loadAdminSecurity() {
  try {
    const [eventsRes, ipsRes] = await Promise.all([
      apiFetch(`${API}/admin/security/events`),
      apiFetch(`${API}/admin/security/blocked-ips`),
    ]);
    if (eventsRes.ok) {
      const events = await eventsRes.json();
      document.getElementById("adminSecurityEvents").innerHTML = events.length
        ? `<div style="overflow-x:auto"><table class="ifinmail-admin-table" style="width:100%;font-size:13px"><thead><tr><th>Type</th><th>Description</th><th>IP</th><th>Time</th></tr></thead><tbody>` +
          events.map(e => `<tr><td>${e.event_type}</td><td>${e.description || ""}</td><td>${e.ip_address || ""}</td><td>${e.created_at ? new Date(e.created_at).toLocaleString() : ""}</td></tr>`).join("") +
          "</tbody></table></div>"
        : "<p style='color:var(--text-light)'>No security events</p>";
    }
    document.getElementById("adminClearEvents").onclick = async () => {
      await apiFetch(`${API}/admin/security/events`, { method: "DELETE" });
      loadAdminSecurity();
    };
    if (ipsRes.ok) {
      const ips = await ipsRes.json();
      document.getElementById("adminBlockedIPs").innerHTML = ips.length
        ? `<div style="overflow-x:auto"><table class="ifinmail-admin-table" style="width:100%;font-size:13px"><thead><tr><th>IP</th><th>Reason</th><th>TTL (s)</th></tr></thead><tbody>` +
          ips.map(i => `<tr><td>${i.ip}</td><td>${i.reason}</td><td>${i.ttl_seconds}</td></tr>`).join("") +
          "</tbody></table></div>"
        : "<p style='color:var(--text-light)'>No blocked IPs</p>";
    }
  } catch {}
}

// ── Admin System sub-tab ──

async function loadAdminSystem() {
  try {
    const [healthRes, backupsRes] = await Promise.all([
      apiFetch(`${API}/admin/system/health`),
      apiFetch(`${API}/admin/system/backups`),
    ]);
    if (healthRes.ok) {
      const health = await healthRes.json();
      document.getElementById("adminHealthInfo").innerHTML =
        `<p>Status: <strong style="color:${health.status === "ok" ? "var(--success, green)" : "var(--danger, red)"}">${health.status}</strong></p>` +
        `<p>Database: ${health.database === "up"
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;color:var(--success, #00b894)"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
          : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;color:var(--danger)"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'}</p>` +
        `<p>Version: ${health.version}</p>`;
    }
    if (backupsRes.ok) {
      const backups = await backupsRes.json();
      document.getElementById("adminBackupsList").innerHTML = backups.length
        ? `<div style="overflow-x:auto"><table class="ifinmail-admin-table" style="width:100%;font-size:13px"><thead><tr><th>Filename</th><th>Size</th><th>Status</th><th>Created</th></tr></thead><tbody>` +
          backups.map(b => `<tr><td>${b.filename}</td><td>${(b.size_bytes / 1024).toFixed(1)} KB</td><td>${b.status}</td><td>${b.created_at ? new Date(b.created_at).toLocaleString() : ""}</td></tr>`).join("") +
          "</tbody></table></div>"
        : "<p style='color:var(--text-light)'>No backups yet</p>";
    }
    document.getElementById("adminCreateBackup").onclick = async () => {
      const r = await apiFetch(`${API}/admin/system/backup`, { method: "POST" });
      if (r.ok) { showToast("Backup created"); loadAdminSystem(); }
      else { showToast("Backup failed"); }
    };
  } catch {}
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
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("#ssoGoogle") || e.target.closest("#ssoMicrosoft");
  if (!btn) return;
  if (btn.disabled) return;
  const provider = btn.id === "ssoGoogle" ? "google" : "microsoft";
  try {
    const redirect = encodeURIComponent(`${SSO_REDIRECT}/sso-callback`);
    const res = await fetch(`${API}/sso/${provider}/login?redirect_uri=${redirect}`);
    if (!res.ok) { showToast("SSO login failed"); return; }
    const data = await res.json();
    const win = window.open(data.authorize_url, "_blank", "width=600,height=700");
    if (!win) return;
    const handler = (event) => {
      if (event.origin !== window.location.origin) return;
      if (event.data.type === "sso-login") {
        window.removeEventListener("message", handler);
        const d = event.data.payload;
        if (!d.access_token) return;
        state.token = d.access_token;
        state.refreshToken = d.refresh_token;
        state.isAdmin = d.is_admin || false;
        localStorage.setItem("ifinmail_token", state.token);
        localStorage.setItem("ifinmail_refresh", state.refreshToken);
        localStorage.setItem("ifinmail_is_admin", state.isAdmin);
        win.close();
        render();
        connectWS();
        requestNotifyPermission();
        registerPush();
      } else if (event.data.type === "sso-error") {
        window.removeEventListener("message", handler);
        showToast("SSO login failed");
      }
    };
    window.addEventListener("message", handler);
  } catch { showToast("SSO login failed"); }
});
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
    if (!state.token) { errEl.textContent = "Invalid server response"; return; }
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
  state.refreshToken = null;
  state.email = null;
  state.messages = [];
  localStorage.removeItem("ifinmail_token");
  localStorage.removeItem("ifinmail_refresh");
  localStorage.removeItem("ifinmail_email");
  render();
}

// ── Fetch messages ──

async function fetchMessages(append) {
  if (state.loading) return;
  if (append && !state.hasMore) return;

  const list = document.getElementById("messageList");
  if (!list) return;

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

  // Read filter panel values
  const filterFrom = document.getElementById("filterFrom")?.value?.trim();
  const filterTo = document.getElementById("filterTo")?.value?.trim();
  const filterSubject = document.getElementById("filterSubject")?.value?.trim();
  const filterAfter = document.getElementById("filterAfter")?.value;
  const filterBefore = document.getElementById("filterBefore")?.value;
  const filterRead = document.getElementById("filterRead")?.value;
  const filterAttach = document.getElementById("filterAttach")?.checked;
  const filterStarred = document.getElementById("filterStarred")?.checked;

  if (filterFrom) p.set("from", filterFrom);
  if (filterTo) p.set("to", filterTo);
  if (filterSubject) p.set("subject", filterSubject);
  if (filterAfter) p.set("after", filterAfter);
  if (filterBefore) p.set("before", filterBefore);
  if (filterRead) p.set("read", filterRead === "read" ? "true" : "false");
  if (filterAttach) p.set("has_attachment", "true");
  if (filterStarred) p.set("starred", "true");

  const endpoint = state.convView && ["INBOX", "PRIORITY"].includes(state.folder) ? `${API}/mail/conversations` : `${API}/mail`;

  try {
    const res = await apiFetch(`${endpoint}?${p}`);
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
    const data = await res.json();
    state.hasMore = state.page * state.perPage < state.totalCount;

    state._focusIdx = -1;
    if (state.convView && ["INBOX", "PRIORITY"].includes(state.folder)) {
      state.conversations = data;
      state.messages = [];
    } else {
      if (append) {
        state.messages.push(...data);
      } else {
        state.messages = data;
      }
      state.conversations = [];
    }

    renderMessageList(append);
    renderPagination();
    updateHash();
  } catch {
    if (!append) list.innerHTML = '<div class="ifinmail-empty">Network error</div>';
  }
  state.loading = false;
}

// ── Unified Inbox ──

async function fetchUnifiedMessages(append) {
  const list = document.getElementById("messageList");
  const colors = ["#4361ee","#e63946","#2ec4b6","#ff9f1c","#7209b7","#f72585","#06d6a0","#ef476f"];

  if (!append) {
    state.messages = [];
    list.innerHTML = '<div class="ifinmail-spinner">Loading unified inbox...</div>';
  }

  const folder = state.unifiedFolder || "INBOX";
  const pp = state.unifiedPerPage;
  const allMsgs = append ? [...state.unifiedMessages] : [];

  for (let i = 0; i < state.accounts.length; i++) {
    const acc = state.accounts[i];
    try {
      const res = await fetch(`${API}/mail?folder=${folder}&per_page=${pp}`, {
        headers: { Authorization: `Bearer ${acc.token}` },
      });
      if (res.ok) {
        const msgs = await res.json();
        const existingIds = new Set(allMsgs.map(m => `${m._account}_${m.id}`));
        msgs.forEach(m => {
          const key = `${acc.email}_${m.id}`;
          if (!existingIds.has(key)) {
            m._account = acc.email;
            m._accountIndex = i;
            m._accountColor = colors[i % colors.length];
            allMsgs.push(m);
            existingIds.add(key);
          }
        });
      }
    } catch {}
  }

  allMsgs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  state.unifiedMessages = allMsgs;
  state.messages = allMsgs;
  state.totalCount = allMsgs.length;
  renderUnifiedMessageList();
}

function renderUnifiedMessageList() {
  const list = document.getElementById("messageList");
  const countEl = document.getElementById("searchCount");
  if (countEl) countEl.textContent = `${state.messages.length} across ${state.accounts.length} account${state.accounts.length !== 1 ? "s" : ""}`;

  if (!state.messages.length) {
    list.innerHTML = '<div class="ifinmail-empty">No messages across accounts</div>';
    clearSelection();
    return;
  }

  list.innerHTML = "";
  state.messages.forEach(msg => {
    const row = document.getElementById("messageRowTmpl").content.cloneNode(true);
    const div = row.querySelector(".ifinmail-row");
    div.dataset.id = msg.id;
    if (!msg.read) div.classList.add("unread");
    if (msg.priority_score && msg.priority_score >= 2) div.classList.add("priority");

    const cb = row.querySelector(".ifinmail-row-cb");
    cb.checked = state._selected?.has(msg.id) || false;
    cb.addEventListener("change", () => {
      if (!state._selected) state._selected = new Set();
      if (cb.checked) state._selected.add(msg.id);
      else state._selected.delete(msg.id);
      updateBatchBar();
    });
    cb.addEventListener("click", e => e.stopPropagation());

    const dot = row.querySelector(".ifinmail-row-unread-dot");
    dot.addEventListener("click", e => { e.stopPropagation(); toggleRead(msg); });

    const star = row.querySelector(".ifinmail-row-star");
    star.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="' + (msg.starred ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
    if (msg.starred) star.classList.add("starred");
    star.addEventListener("click", e => { e.stopPropagation(); toggleStar(msg); });

    const sender = row.querySelector(".ifinmail-row-sender");
    let senderHtml = `<span class="ifinmail-account-badge" style="background:${msg._accountColor}" title="${msg._account}"></span>`;
    if (msg.priority_score && msg.priority_score >= 2) {
      senderHtml += '<span class="ifinmail-priority-badge" title="Priority: ' + msg.priority_score.toFixed(1) + '">!</span> ';
    }
    if (msg.has_attachments) {
      senderHtml += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;flex-shrink:0"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>';
    }
    senderHtml += msg.from_addr;
    sender.innerHTML = senderHtml;

    row.querySelector(".ifinmail-row-subject").textContent = msg.subject || "(no subject)";
    row.querySelector(".ifinmail-row-date").textContent = formatDate(msg.created_at);

    const labelsEl = row.querySelector(".ifinmail-row-labels");
    if (msg.labels) {
      const lcolors = ["#e74c3c","#e67e22","#f1c40f","#2ecc71","#3498db","#9b59b6","#1abc9c","#e84393"];
      msg.labels.split(",").forEach((l, i) => {
        const tag = document.createElement("span");
        tag.className = "ifinmail-label-badge";
        tag.textContent = l.trim();
        tag.style.background = lcolors[i % lcolors.length] + "22";
        tag.style.color = lcolors[i % lcolors.length];
        labelsEl.appendChild(tag);
      });
    }

    div.addEventListener("click", async () => {
      // Switch to the account this message belongs to
      const acc = state.accounts.find(a => a.email === msg._account);
      if (acc && acc.email !== state.email) {
        await switchAccount(acc.email, acc.token, acc.refreshToken);
        // Re-fetch with that account active
        state.folder = "INBOX";
        state.unifiedView = false;
        const unifiedCheck = document.getElementById("unifiedToggleCheck");
        if (unifiedCheck) unifiedCheck.checked = false;
        fetchMessages();
      }
      if (msg.folder === "DRAFTS") {
        showCompose("edit", msg);
      } else {
        openMessage(msg.id);
      }
    });
    list.appendChild(row);
  });

  // Load more button
  const loadMoreBtn = document.createElement("button");
  loadMoreBtn.className = "ifinmail-btn ifinmail-btn-sm";
  loadMoreBtn.textContent = "Load more";
  loadMoreBtn.style.cssText = "display:block;margin:16px auto;padding:8px 24px";
  loadMoreBtn.addEventListener("click", async () => {
    state.unifiedPerPage += 50;
    loadMoreBtn.textContent = "Loading...";
    loadMoreBtn.disabled = true;
    await fetchUnifiedMessages(true);
    loadMoreBtn.textContent = "Load more";
    loadMoreBtn.disabled = false;
  });
  list.appendChild(loadMoreBtn);

  clearSelection();
}

function filterUnifiedMessages() {
  const q = (document.getElementById("searchInput")?.value || "").toLowerCase();
  if (!q) {
    state.messages = state.unifiedMessages;
  } else {
    state.messages = state.unifiedMessages.filter(m =>
      (m.from_addr || "").toLowerCase().includes(q) ||
      (m.subject || "").toLowerCase().includes(q) ||
      (m.body_text || "").toLowerCase().includes(q)
    );
  }
  renderUnifiedMessageList();
}

function renderConversationList() {
  const list = document.getElementById("messageList");
  const countEl = document.getElementById("searchCount");
  if (countEl) {
    const searchVal = document.getElementById("searchInput")?.value;
    countEl.textContent = searchVal ? `${state.totalCount} conversation${state.totalCount !== 1 ? "s" : ""}` : "";
  }

  if (!state.conversations.length) {
    list.innerHTML = `<div class="ifinmail-empty">${state.folder === "INBOX" ? "inbox" : "folder"} is empty</div>`;
    clearSelection();
    return;
  }

  list.innerHTML = "";
  state.conversations.forEach(conv => {
    const div = document.createElement("div");
    div.className = "ifinmail-conversation";
    div.dataset.convId = conv.id;

    const unreadCount = conv.unread_count || 0;
    const header = document.createElement("div");
    header.className = "ifinmail-conv-header";
    header.innerHTML = `
      <span class="ifinmail-conv-toggle">▸</span>
      <span class="ifinmail-conv-subject">${conv.subject || "(no subject)"}</span>
      <span class="ifinmail-conv-count">${conv.total_count} ${conv.total_count === 1 ? "msg" : "msgs"}</span>
      ${unreadCount > 0 ? `<span class="ifinmail-badge">${unreadCount} unread</span>` : ""}
      <span class="ifinmail-conv-latest">${conv.latest_from}</span>
      <span class="ifinmail-conv-date">${formatDate(conv.latest_at)}</span>
    `;
    div.appendChild(header);

    const body = document.createElement("div");
    body.className = "ifinmail-conv-body";
    body.style.display = "none";

    conv.messages.forEach(msg => {
      const row = document.getElementById("messageRowTmpl").content.cloneNode(true);
      const rowDiv = row.querySelector(".ifinmail-row");
      rowDiv.dataset.id = msg.id;
      if (!msg.read) rowDiv.classList.add("unread");
      if (msg.priority_score && msg.priority_score >= 2) rowDiv.classList.add("priority");

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
      let senderHtml = "";
      if (msg.priority_score && msg.priority_score >= 2) {
        senderHtml = '<span class="ifinmail-priority-badge" title="Priority: ' + msg.priority_score.toFixed(1) + '">!</span> ';
      }
      senderHtml += msg.from_addr;
      sender.innerHTML = senderHtml;

      row.querySelector(".ifinmail-row-subject").textContent = msg.subject || "(no subject)";
      row.querySelector(".ifinmail-row-date").textContent = formatDate(msg.created_at);

      rowDiv.addEventListener("click", () => openMessage(msg.id));
      if (isElectron) {
        rowDiv.addEventListener("contextmenu", (e) => {
          e.preventDefault();
          window.ifinmail.showMessageContextMenu(msg);
        });
      }
      body.appendChild(row);
    });

    div.appendChild(body);

    header.addEventListener("click", () => {
      const isOpen = body.style.display !== "none";
      body.style.display = isOpen ? "none" : "";
      header.querySelector(".ifinmail-conv-toggle").textContent = isOpen ? "▸" : "▾";
    });

    list.appendChild(div);
  });
}

function renderMessageList(append) {
  if (state.conversations.length > 0) {
    renderConversationList();
    return;
  }

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
    if (msg.priority_score && msg.priority_score >= 2) div.classList.add("priority");

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
    let senderHtml = "";
    if (msg.priority_score && msg.priority_score >= 2) {
      senderHtml = '<span class="ifinmail-priority-badge" title="Priority: ' + msg.priority_score.toFixed(1) + '">!</span> ';
    }
    if (msg.has_attachments) {
      senderHtml += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;flex-shrink:0"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>';
    }
    senderHtml += msg.from_addr;
    sender.innerHTML = senderHtml;

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
  const msgList = document.getElementById("messageList");
  if (!msgList) return;
  msgList.after(sentinel);

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
      if (isElectron) {
        link.addEventListener("click", async (e) => {
          e.preventDefault();
          const res = await apiFetch(link.href);
          if (!res.ok) return;
          const blob = await res.blob();
          const buf = await blob.arrayBuffer();
          const result = await window.ifinmail.showSaveDialog({
            defaultPath: att.filename,
            filters: [{ name: "All Files", extensions: ["*"] }],
          });
          if (!result.canceled && result.filePath) {
            await window.ifinmail.writeFile(result.filePath, Array.from(new Uint8Array(buf)));
          }
        });
      }
      const sizeEl = row.querySelector(".ifinmail-attachment-size");
      sizeEl.textContent = formatSize(att.size);
      container.appendChild(row);
    });
  } catch {}
}

function renderMessageView() {
  const msg = state.currentMsg;
  if (!msg) return;
  const mv = document.getElementById("messageView");
  const mvt = document.getElementById("messageViewTmpl");
  if (!mv || !mvt) return;
  mv.innerHTML = mvt.innerHTML;
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

  // Delivery status
  loadDeliveryStatus(msg.id);

  if (!msg.read) markRead(msg.id);
}

async function loadDeliveryStatus(messageId) {
  try {
    const res = await apiFetch(`${API}/mail/${messageId}/deliveries`);
    if (!res.ok) return;
    const deliveries = await res.json();
    const container = document.getElementById("deliveryStatus");
    const list = document.getElementById("deliveryStatusList");
    if (!container || !list || !deliveries.length) return;
    container.style.display = "block";
    list.innerHTML = deliveries.map(d => {
      const statusColor = d.status === "sent" ? "var(--success)" : d.status === "bounced" ? "var(--error)" : d.status === "pending" ? "var(--warning)" : "var(--muted)";
      const opened = d.opened_at ? `<span style="color:var(--success)">Opened ${new Date(d.opened_at).toLocaleString()}</span>` : "";
      const clicked = d.clicked_at ? ` · <span style="color:var(--primary)">Clicked ${new Date(d.clicked_at).toLocaleString()}</span>` : "";
      const bounceInfo = d.bounce_type ? ` · <span style="color:var(--error)">${d.bounce_type}${d.error ? ": " + d.error : ""}</span>` : "";
      return `<div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid var(--border)">
        <span>${d.recipient}</span>
        <span><span style="color:${statusColor};font-weight:600">${d.status}</span> ${opened}${clicked}${bounceInfo}</span>
      </div>`;
    }).join("");
  } catch {}
}

function renderLabels() {
  const msg = state.currentMsg;
  const container = document.getElementById("msgLabels");
  if (!container) return;
  container.innerHTML = "";
  const editBtn = document.createElement("button");
  editBtn.className = "ifinmail-btn ifinmail-btn-sm";
  editBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg> Labels';
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

async function showCompose(mode, msg) {
  const cv = document.getElementById("composeView");
  const ct = document.getElementById("composeTmpl");
  if (!cv || !ct) return;
  cv.innerHTML = ct.innerHTML;
  showView("compose");
  _composeAttachmentIds = [];
  _composeEditId = null;
  const toEl = document.getElementById("composeTo");
  const subjEl = document.getElementById("composeSubject");
  const bodyEl = document.getElementById("composeBody");

  toEl.value = "";
  subjEl.value = "";
  bodyEl.innerHTML = "";
  const quoteEl = document.getElementById("composeQuote");
  quoteEl.textContent = "";
  quoteEl.style.display = "none";
  document.getElementById("composeError").textContent = "";
  document.getElementById("composeAttachList").innerHTML = "";

  async function appendSignature() {
    if (!state.signatureEnabled && !state.signature) {
      try {
        const res = await apiFetch(`${API}/mail/settings/signature`);
        if (res.ok) {
          const data = await res.json();
          state.signature = data.signature;
          state.signatureEnabled = data.signature_enabled;
        }
      } catch {}
    }
    if (state.signatureEnabled && state.signature) {
      const sigHtml = `<div><br></div><div>--<br>${state.signature}</div>`;
      if (bodyEl.innerHTML === "" || bodyEl.innerHTML === "<br>") {
        bodyEl.innerHTML = sigHtml;
      } else {
        bodyEl.insertAdjacentHTML("beforeend", sigHtml);
      }
    }
  }

  if (mode === "edit" && msg) {
    _composeEditId = msg.id;
    toEl.value = msg.to_addrs || "";
    subjEl.value = msg.subject || "";
    bodyEl.innerHTML = msg.body_html || msg.body_text || "";
    document.querySelector(".ifinmail-compose-header h2").textContent = "Edit Draft";
  } else if (mode === "reply" && msg) {
    toEl.value = msg.from_addr;
    subjEl.value = msg.subject?.startsWith("Re:") ? msg.subject : `Re: ${msg.subject}`;
    quoteEl.innerHTML = `<hr><div style="font-size:12px;color:var(--text-light)">On ${formatDate(msg.created_at)}, ${msg.from_addr} wrote:</div><blockquote style="margin:4px 0 0;padding:0 0 0 12px;border-left:2px solid var(--border);color:var(--text-light)">${msg.body_html || msg.body_text || ""}</blockquote>`;
    quoteEl.style.display = "block";
    await appendSignature();
  } else if (mode === "replyAll" && msg) {
    const allTo = [msg.from_addr, ...(msg.to_addrs ? msg.to_addrs.split(",").map(s => s.trim()).filter(s => s !== state.email) : [])];
    toEl.value = [...new Set(allTo)].join(", ");
    subjEl.value = msg.subject?.startsWith("Re:") ? msg.subject : `Re: ${msg.subject}`;
    quoteEl.innerHTML = `<hr><div style="font-size:12px;color:var(--text-light)">On ${formatDate(msg.created_at)}, ${msg.from_addr} wrote:</div><blockquote style="margin:4px 0 0;padding:0 0 0 12px;border-left:2px solid var(--border);color:var(--text-light)">${msg.body_html || msg.body_text || ""}</blockquote>`;
    quoteEl.style.display = "block";
    await appendSignature();
  } else if (mode === "forward" && msg) {
    subjEl.value = msg.subject?.startsWith("Fwd:") ? msg.subject : `Fwd: ${msg.subject}`;
    quoteEl.innerHTML = `<hr><div style="font-size:12px;color:var(--text-light)">---------- Forwarded message ----------<br>From: ${msg.from_addr}<br>Date: ${formatDate(msg.created_at)}<br>Subject: ${msg.subject}<br>To: ${msg.to_addrs}</div><blockquote style="margin:4px 0 0;padding:0 0 0 12px;border-left:2px solid var(--border);color:var(--text-light)">${msg.body_html || msg.body_text || ""}</blockquote>`;
    quoteEl.style.display = "block";
    await appendSignature();
  } else {
    await appendSignature();
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
  const scheduleBtn = document.getElementById("composeScheduleBtn");
  const schedulePanel = document.getElementById("composeSchedulePanel");
  const scheduleAt = document.getElementById("composeScheduleAt");
  scheduleBtn.onclick = () => {
    const show = schedulePanel.style.display === "none";
    schedulePanel.style.display = show ? "flex" : "none";
    if (show) {
      scheduleAt.focus();
      const now = new Date();
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
      scheduleAt.value = now.toISOString().slice(0, 16);
    }
  };
  window._composeDirty = true;

  const attachInput = document.getElementById("attachInput");
  const attachBtn = document.getElementById("attachBtn");
  attachBtn.onclick = () => attachInput.click();
  attachInput.onchange = handleAttachSelect;

  if (isElectron) {
    const composeArea = document.getElementById("composeArea") || attachBtn.closest(".ifinmail-compose");
    if (composeArea) {
      composeArea.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); });
      composeArea.addEventListener("drop", (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        if (files.length) {
          const dt = new DataTransfer();
          files.forEach(f => dt.items.add(f));
          attachInput.files = dt.files;
          handleAttachSelect();
        }
      });
    }
  }

  // ── Org autocomplete for To field ──
  (async () => {
    const res = await apiFetch(`${API}/orgs`);
    if (!res.ok) return;
    const orgs = await res.json();
    const emails = [];
    for (const org of orgs) {
      if (org.email) emails.push(org.email);
      try {
        const r2 = await apiFetch(`${API}/orgs/${org.id}/member-contacts?q=`);
        if (r2.ok) {
          const members = await r2.json();
          members.forEach(m => { if (m.email && !emails.includes(m.email)) emails.push(m.email); });
        }
        const r3 = await apiFetch(`${API}/orgs/${org.id}/contacts`);
        if (r3.ok) {
          const contacts = await r3.json();
          contacts.forEach(c => { if (c.email && !emails.includes(c.email)) emails.push(c.email); });
        }
      } catch {}
    }
    if (!emails.length) return;
    const dl = document.createElement("datalist");
    dl.id = "composeContactsDatalist";
    emails.forEach(e => { const o = document.createElement("option"); o.value = e; dl.appendChild(o); });
    document.body.appendChild(dl);
    toEl.setAttribute("list", "composeContactsDatalist");
  })();
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
  const body = document.getElementById("composeBody")?.innerText;
  if (!to && !subject && !body) return;
  _composeAutoSaveTimer = setTimeout(() => doSaveDraft(false), 1000);
}

function sendToOrgEmail(orgId, email) {
  showCompose();
  document.getElementById("composeTo").value = email;
}

async function doSaveDraft(showToastMsg) {
  const to = document.getElementById("composeTo")?.value;
  const subject = document.getElementById("composeSubject")?.value;
  const bodyEl = document.getElementById("composeBody");
  const body = bodyEl?.innerText;
  if (!to && !subject && !body) return;
  try {
    const bodyData = { to: to || "", subject: subject || "", body_text: body || "", body_html: bodyEl?.innerHTML || "" };
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
  if (!btn) { _composing = false; return; }
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Sending...";
  const to = document.getElementById("composeTo").value;
  const subject = document.getElementById("composeSubject").value;
  const composeBodyEl = document.getElementById("composeBody");
  const body = composeBodyEl.innerText;
  const bodyHtml = composeBodyEl.innerHTML;
  document.getElementById("composeError").textContent = "";

  const scheduleAt = document.getElementById("composeScheduleAt");
  const scheduleVal = scheduleAt?.value;

  try {
    if (scheduleVal) {
      let scheduled_at = new Date(scheduleVal).toISOString();
      const tz = document.getElementById("composeScheduleTz")?.value || "local";
      if (tz !== "UTC" && tz !== "local") {
        try {
          const options = { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false };
          const parts = new Intl.DateTimeFormat("en-CA", options).formatToParts(new Date(scheduleVal));
          const get = (t) => parts.find(p => p.type === t)?.value || "0";
          scheduled_at = `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}:00`;
        } catch {}
      }
      const repeat = document.getElementById("composeScheduleRepeat")?.value || "";
      const bodyData = { to_addr: to, subject, body_text: body, body_html: bodyHtml, scheduled_at };
      if (repeat) bodyData.repeat_interval = repeat;
      if (_composeAttachmentIds.length) bodyData.attachment_ids = _composeAttachmentIds;
      const res = await apiFetch(`${API}/mail/schedule`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyData),
      });
      if (!res.ok) {
        const data = await res.json();
        document.getElementById("composeError").textContent = data.detail || "Failed to schedule";
        return;
      }
      schedulePanel.style.display = "none";
      showView("inbox");
      fetchMessages();
      fetchScheduledCount();
      showToast(repeat ? "Recurring email scheduled" : "Email scheduled");
      return;
    }

    const bodyData = { to, subject, body_text: body, body_html: bodyHtml };
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
    item.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;opacity:0.6"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ' + file.name + '...';
    list.appendChild(item);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch(`${API}/mail/attachments`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        item.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:var(--danger)"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ' + file.name;
        continue;
      }
      const att = await res.json();
      _composeAttachmentIds.push(att.id);
      item.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg> ' + file.name + ' (' + formatSize(file.size) + ') <button class="ifinmail-btn ifinmail-btn-sm ifinmail-attach-remove" data-att-id="' + att.id + '" style="margin-left:8px;padding:1px 6px;font-size:11px;background:rgba(230,57,70,0.1);color:var(--danger);border:1px solid rgba(230,57,70,0.3);border-radius:4px;cursor:pointer"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>'
    } catch {
      item.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:var(--danger)"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> ' + file.name;
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
    if (state.unifiedView) {
      filterUnifiedMessages();
    } else {
      fetchMessages();
    }
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "searchInput" && !e.target.value) {
    if (state.unifiedView) {
      state.messages = state.unifiedMessages;
      renderUnifiedMessageList();
    } else {
      fetchMessages();
    }
  }
});
document.addEventListener("keydown", (e) => {
  if (e.target.id === "searchInput" && e.key === "Enter") {
    e.preventDefault();
    if (state.unifiedView) {
      filterUnifiedMessages();
    } else {
      fetchMessages();
    }
  }
});

// ── Filter panel ──
document.addEventListener("click", (e) => {
  if (e.target.id === "filterToggleBtn" || e.target.closest("#filterToggleBtn")) {
    const panel = document.getElementById("filterPanel");
    panel.style.display = panel.style.display === "none" ? "" : "none";
  }
  if (e.target.id === "applyFiltersBtn" || e.target.closest("#applyFiltersBtn")) {
    e.preventDefault();
    if (state.unifiedView) {
      filterUnifiedMessages();
    } else {
      fetchMessages();
    }
  }
  if (e.target.id === "clearFiltersBtn" || e.target.closest("#clearFiltersBtn")) {
    e.preventDefault();
    document.getElementById("filterFrom").value = "";
    document.getElementById("filterTo").value = "";
    document.getElementById("filterSubject").value = "";
    document.getElementById("filterAfter").value = "";
    document.getElementById("filterBefore").value = "";
    document.getElementById("filterRead").value = "";
    document.getElementById("filterAttach").checked = false;
    document.getElementById("filterStarred").checked = false;
    if (state.unifiedView) {
      state.messages = state.unifiedMessages;
      renderUnifiedMessageList();
    } else {
      fetchMessages();
    }
  }
});

// Admin user search
document.addEventListener("click", (e) => {
  if (e.target.id === "adminUserSearchBtn" || e.target.id === "adminUserRefreshBtn") {
    adminUsersPage = 1;
    loadAdminUsers();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.target.id === "adminUserSearch" && e.key === "Enter") {
    adminUsersPage = 1;
    loadAdminUsers();
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
    if (state.unifiedView) {
      fetchUnifiedMessages();
    } else {
      fetchMessages();
    }
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

// ── List navigation helpers (j/k) ──

function _focusNextMessage(dir) {
  if (!state.messages.length) return;
  if (state._focusIdx === undefined) state._focusIdx = -1;
  const newIdx = Math.max(0, Math.min(state.messages.length - 1, state._focusIdx + dir));
  if (newIdx === state._focusIdx) return;
  state._focusIdx = newIdx;
  _focusRow(state.messages[newIdx].id);
}

function _focusRow(id) {
  document.querySelectorAll(".ifinmail-row").forEach(r => r.classList.remove("ifinmail-row-focused"));
  const row = document.querySelector(`.ifinmail-row[data-id="${id}"]`);
  if (row) {
    row.classList.add("ifinmail-row-focused");
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
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
    if (btn) btn.textContent = mode === "login" ? "Add & switch" : "Create & switch";
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
    case "j":
    case "J":
      e.preventDefault();
      _focusNextMessage(1);
      break;
    case "k":
    case "K":
      e.preventDefault();
      _focusNextMessage(-1);
      break;
    case "Enter":
      if (state._focusIdx >= 0 && state.messages[state._focusIdx]) {
        e.preventDefault();
        const focused = state.messages[state._focusIdx];
        const row = document.querySelector(`.ifinmail-row[data-id="${focused.id}"]`);
        if (row) row.click();
      }
      break;
    case "a":
    case "e":
      if (state._focusIdx >= 0 && state.messages[state._focusIdx]) {
        e.preventDefault();
        const focused = state.messages[state._focusIdx];
        const row = document.querySelector(`.ifinmail-row[data-id="${focused.id}"]`);
        if (row) { state.currentMsg = focused; _focusRow(focused.id); }
        const archiveBtn = document.getElementById("archiveBtn");
        if (archiveBtn) archiveBtn.click();
      }
      break;
    case "s":
      if (state._focusIdx >= 0 && state.messages[state._focusIdx]) {
        e.preventDefault();
        const focused = state.messages[state._focusIdx];
        toggleStar(focused);
      }
      break;
    case "/":
      e.preventDefault();
      const searchInput = document.getElementById("searchInput");
      if (searchInput) searchInput.focus();
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

// ── SSO callback handler ──
if (window.location.pathname === "/sso-callback") {
  const sp = new URLSearchParams(window.location.search);
  const code = sp.get("code");
  const oauthState = sp.get("state");
  const errMsg = sp.get("error");
  if (errMsg) {
    document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:14px;color:#666;text-align:center;padding:24px;">SSO login failed: ${errMsg}.<br>You may close this window.</div>`;
    window.opener?.postMessage({ type: "sso-error" });
  } else if (code && oauthState) {
    (async () => {
      document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:14px;color:#666;">Completing login...</div>`;
      try {
        const res = await fetch(`${API}/sso/callback?code=${code}&state=${oauthState}`);
        if (res.ok) {
          const data = await res.json();
          window.opener?.postMessage({ type: "sso-login", payload: data }, window.location.origin);
          window.close();
        } else {
          const d = await res.json().catch(() => ({}));
          window.opener?.postMessage({ type: "sso-error" });
          document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:14px;color:#666;text-align:center;padding:24px;">SSO login failed: ${d.detail || "Unknown error"}.<br>You may close this window.</div>`;
        }
      } catch {
        window.opener?.postMessage({ type: "sso-error" });
        document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:14px;color:#666;text-align:center;padding:24px;">Network error during SSO login.<br>You may close this window.</div>`;
      }
    })();
  } else {
    document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;font-size:14px;color:#666;">Redirecting...</div>`;
  }
}

// ── Sandbox ──

async function renderSandbox() {
  const tmpl = document.getElementById("sandboxTmpl");
  document.getElementById("sandboxView").innerHTML = tmpl.innerHTML;

  document.getElementById("sandboxForm").onsubmit = async (e) => {
    e.preventDefault();
    const to = document.getElementById("sandboxTo").value;
    const subject = document.getElementById("sandboxSubject").value;
    const body_text = document.getElementById("sandboxBody").value;
    const body_html = document.getElementById("sandboxHtml").value || null;
    document.getElementById("sandboxError").textContent = "";
    try {
      const res = await apiFetch(`${API}/sandbox/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to, subject, body_text, body_html }),
      });
      if (!res.ok) { document.getElementById("sandboxError").textContent = "Failed to capture"; return; }
      document.getElementById("sandboxTo").value = "";
      document.getElementById("sandboxSubject").value = "";
      document.getElementById("sandboxBody").value = "";
      document.getElementById("sandboxHtml").value = "";
      showToast("Captured to sandbox");
      loadSandboxCaptures();
    } catch { document.getElementById("sandboxError").textContent = "Network error"; }
  };

  loadSandboxCaptures();
}

async function loadSandboxCaptures() {
  try {
    const res = await apiFetch(`${API}/sandbox/captures`);
    if (!res.ok) return;
    const captures = await res.json();
    const list = document.getElementById("sandboxCapturesList");
    if (!captures.length) { list.innerHTML = '<p style="color:var(--text-light)">No captures yet</p>'; return; }
    list.innerHTML = captures.map(c => `
      <div class="ifinmail-sandbox-capture">
        <div class="ifinmail-sandbox-capture-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
          <strong>${c.subject || "(no subject)"}</strong>
          <span style="font-size:12px;color:var(--text-light)">${c.to} · ${new Date(c.captured_at).toLocaleTimeString()}</span>
        </div>
        <div class="ifinmail-sandbox-capture-body" style="display:none">${c.body_text || ""}</div>
      </div>
    `).join("");
  } catch {}
}

// ── AI Assistant in Compose ──

function showAIPanel() {
  const existing = document.querySelector(".ifinmail-ai-panel");
  if (existing) { existing.remove(); return; }
  const tmpl = document.getElementById("aiAssistantTmpl");
  const clone = tmpl.content.cloneNode(true);
  const composeAttachments = document.getElementById("composeAttachmentsContainer");
  composeAttachments.after(clone);

  let currentTab = "generate";
  clone.querySelectorAll(".ifinmail-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      currentTab = tab.dataset.aiTab;
      clone.querySelectorAll(".ifinmail-tab").forEach(t => t.classList.toggle("active", t.dataset.aiTab === currentTab));
      document.getElementById("aiGenerateView").style.display = currentTab === "generate" ? "" : "none";
      document.getElementById("aiSummarizeView").style.display = currentTab === "summarize" ? "" : "none";
      document.getElementById("aiTranslateView").style.display = currentTab === "translate" ? "" : "none";
      document.getElementById("aiResult").style.display = "none";
    });
  });

  document.getElementById("aiGenerateBtn").onclick = async () => {
    const prompt = document.getElementById("aiPrompt").value;
    const tone = document.getElementById("aiTone").value || "professional";
    if (!prompt) return;
    const resultEl = document.getElementById("aiResult");
    resultEl.style.display = "block";
    resultEl.textContent = "Generating...";
    try {
      const res = await apiFetch(`${API}/ai/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, tone, subject: document.getElementById("composeSubject")?.value || "", to: document.getElementById("composeTo")?.value || "" }),
      });
      if (!res.ok) { resultEl.textContent = "AI generation failed"; return; }
      const data = await res.json();
      const r = data.result;
      if (r.subject) document.getElementById("composeSubject").value = r.subject;
      if (r.body) document.getElementById("composeBody").innerHTML = r.body;
      resultEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:var(--success)"><polyline points="20 6 9 17 4 12"/></svg> Inserted!';
    } catch { resultEl.textContent = "Network error"; }
  };

  document.getElementById("aiSummarizeBtn").onclick = async () => {
    const body = document.getElementById("composeBody")?.innerText || state.currentMsg?.body_text || "";
    const subject = document.getElementById("composeSubject")?.value || state.currentMsg?.subject || "";
    if (!body) { showToast("No email body to summarize"); return; }
    const resultEl = document.getElementById("aiResult");
    resultEl.style.display = "block";
    resultEl.textContent = "Summarizing...";
    try {
      const res = await apiFetch(`${API}/ai/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject, body }),
      });
      if (!res.ok) { resultEl.textContent = "Summarization failed"; return; }
      const data = await res.json();
      resultEl.textContent = data.result.summary || "No summary generated";
    } catch { resultEl.textContent = "Network error"; }
  };

  document.getElementById("aiTranslateBtn").onclick = async () => {
    const text = document.getElementById("composeBody")?.innerText || state.currentMsg?.body_text || "";
    const target_lang = document.getElementById("aiTargetLang").value;
    if (!text) { showToast("No email body to translate"); return; }
    const resultEl = document.getElementById("aiResult");
    resultEl.style.display = "block";
    resultEl.textContent = "Translating...";
    try {
      const res = await apiFetch(`${API}/ai/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_lang: "auto", target_lang }),
      });
      if (!res.ok) { resultEl.textContent = "Translation failed"; return; }
      const data = await res.json();
      const translated = data.result.translated_text || "";
      if (translated) document.getElementById("composeBody").innerHTML = translated;
      resultEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;color:var(--success)"><polyline points="20 6 9 17 4 12"/></svg> Translation inserted!';
    } catch { resultEl.textContent = "Network error"; }
  };
}

// Add AI button to compose after rendering
const origShowCompose = showCompose;
showCompose = function(mode, msg) {
  origShowCompose.call(this, mode, msg);
  const actions = document.querySelector(".ifinmail-compose-actions");
  if (actions) {
    const aiBtn = document.createElement("button");
    aiBtn.type = "button";
    aiBtn.className = "ifinmail-btn";
    aiBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a4 4 0 0 1 4 4v2h2a4 4 0 0 1 4 4v2a4 4 0 0 1-4 4h-2v2a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4v-2H6a4 4 0 0 1-4-4v-2a4 4 0 0 1 4-4h2V6a4 4 0 0 1 4-4z"/></svg> AI';
    aiBtn.onclick = showAIPanel;
    actions.prepend(aiBtn);
  }
};

// ── Intelligence button in message view ──

const origRenderMessageView = renderMessageView;
renderMessageView = function() {
  origRenderMessageView.call(this);
  const actions = document.querySelector(".ifinmail-message-actions");
  if (actions) {
    const intelBtn = document.createElement("button");
    intelBtn.className = "ifinmail-btn";
    intelBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> Analyze';
    intelBtn.onclick = async () => {
      const msg = state.currentMsg;
      if (!msg) return;
      const resultEl = document.getElementById("msgBody");
      const origText = resultEl.textContent;
      resultEl.textContent = "Analyzing...";
      try {
        const res = await apiFetch(`${API}/intelligence/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subject: msg.subject || "", body_text: msg.body_text || "", body_html: msg.body_html || "" }),
        });
        if (!res.ok) { resultEl.textContent = "Analysis failed"; return; }
        const data = await res.json();
        const analysis = `
── Intelligence Report ──
Spam Probability: ${data.spam_probability}
Sentiment: ${data.sentiment}
Language: ${data.language}
Business Score: ${data.business_score}
Word Count: ${data.word_count}
Summary: ${data.summary}
`;
        const pre = document.createElement("pre");
        pre.style.cssText = "background:var(--unread-bg);padding:12px;border-radius:8px;font-size:13px;line-height:1.6;margin-top:12px";
        pre.textContent = analysis;
        resultEl.parentNode.insertBefore(pre, resultEl);
        resultEl.textContent = origText;
      } catch { resultEl.textContent = origText; }
    };
    actions.appendChild(intelBtn);
  }
};

// ── Teams (tabbed full-page layout) ──

let teamsOrgId = null;

function showTeamsTab(tab) {
  document.querySelectorAll(".ifinmail-teams-tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".ifinmail-teams-tab-content").forEach(c => c.classList.remove("active"));
  const tabBtn = document.querySelector(`[data-teams-tab="${tab}"]`);
  const tabContent = document.getElementById(`teams${tab.charAt(0).toUpperCase() + tab.slice(1)}Tab`);
  if (tabBtn) tabBtn.classList.add("active");
  if (tabContent) tabContent.classList.add("active");
}

async function renderTeams() {
  const tmpl = document.getElementById("teamsTmpl");
  document.getElementById("teamsView").innerHTML = tmpl.innerHTML;

  document.getElementById("teamsDeleteBtn").onclick = () => teamsDeleteOrg();
  document.getElementById("teamsSaveBtn").onclick = () => teamsSaveOrg();
  document.getElementById("teamsTestEmailBtn").onclick = () => sendTestEmail();
  document.getElementById("teamsCreateForm").onsubmit = async (e) => {
    e.preventDefault();
    await teamsCreateOrg();
  };

  document.querySelectorAll(".ifinmail-teams-tab").forEach(btn => {
    btn.onclick = () => showTeamsTab(btn.dataset.teamsTab);
  });

  await loadTeamsOrgSelector();
}

async function loadTeamsOrgSelector() {
  try {
    const res = await apiFetch(`${API}/orgs`);
    if (!res.ok) return;
    const orgs = await res.json();
    const select = document.getElementById("teamsOrgSelect");
    const noOrg = document.getElementById("teamsNoOrg");
    const orgView = document.getElementById("teamsOrgView");

    select.innerHTML = orgs.map(o =>
      `<option value="${o.id}">${o.name} (${o.role})</option>`
    ).join("");

    if (!orgs.length) {
      noOrg.style.display = "block";
      orgView.style.display = "none";
      select.innerHTML = '<option value="">No organizations</option>';
      return;
    }
    noOrg.style.display = "none";
    orgView.style.display = "block";
    const currentId = parseInt(select.value);
    if (currentId) await loadTeamsOrg(currentId);
  } catch {}
}

async function switchTeamsOrg(orgId) {
  if (orgId) await loadTeamsOrg(parseInt(orgId));
}

async function loadTeamsOrg(orgId) {
  teamsOrgId = orgId;
  try {
    const res = await apiFetch(`${API}/orgs/${orgId}`);
    if (!res.ok) { showToast("Failed to load org"); return; }
    const org = await res.json();

    // Organization tab
    document.getElementById("teamsOrgName").value = org.name || "";
    document.getElementById("teamsMailingList").value = org.email || "";
    document.getElementById("teamsOrgIdDisplay").value = org.id || "";
    document.getElementById("teamsOrgCreated").value = org.created_at ? new Date(org.created_at).toLocaleDateString() : "";
    document.getElementById("teamsOrgRole").value = org.my_role || "";
    const roleDisplay = document.getElementById("teamsOrgRole");
    roleDisplay.value = org.my_role || "";
    roleDisplay.style.color = org.my_role === "owner" ? "#d97706" : "var(--text)";
    roleDisplay.style.fontWeight = org.my_role === "owner" ? "600" : "400";

    const roleBadge = document.getElementById("teamsRoleBadge");
    if (roleBadge) roleBadge.textContent = "Role: " + (org.my_role || "member");

    const isOwner = org.my_role === "owner";
    const isAdmin = org.my_role === "admin";
    const deleteSection = document.getElementById("teamsDeleteSection");
    if (deleteSection) deleteSection.style.display = isOwner ? "" : "none";

    // Member chips in org tab
    const chipsEl = document.getElementById("teamsMemberChips");
    const countEl = document.getElementById("teamsMemberSummaryCount");
    if (chipsEl && org.members) {
      const ownerRole = (r) => r === "owner" ? "owner" : "";
      chipsEl.innerHTML = org.members.map(m =>
        `<span class="ifinmail-teams-chip">
          ${m.email || "User #" + m.user_id}
          <span class="ifinmail-teams-chip-role ${ownerRole(m.role)}">${m.role}</span>
        </span>`
      ).join("");
    }
    if (countEl && org.members) countEl.textContent = `(${org.members.length})`;

    // Members tab
    const mlist = document.getElementById("teamsMembersList");
    document.getElementById("teamsMemberCount").textContent = `(${org.members.length})`;
    mlist.innerHTML = org.members.map(m => {
      const isOwnerMember = m.role === "owner";
      return `<li class="ifinmail-teams-member-item">
        <div class="ifinmail-teams-member-info">
          <strong>${m.email || "User #" + m.user_id}</strong>
          <span class="ifinmail-teams-member-role ${isOwnerMember ? "owner" : ""}">${m.role}</span>
        </div>
        <div class="ifinmail-teams-member-actions">
          ${isOwner && !isOwnerMember
            ? `<select class="ifinmail-teams-role-select" onchange="changeMemberRole(${orgId},${m.id},this.value)">
                <option value="member" ${m.role === "member" ? "selected" : ""}>Member</option>
                <option value="admin" ${m.role === "admin" ? "selected" : ""}>Admin</option>
               </select>
               <button class="ifinmail-btn ifinmail-btn-sm" onclick="removeOrgMember(${orgId},${m.user_id})">Remove</button>`
            : isOwner && isOwnerMember
              ? `<button class="ifinmail-btn ifinmail-btn-sm" onclick="transferOwnership(${orgId},${m.user_id})">Transfer</button>`
              : ""}
        </div>
      </li>`;
    }).join("");

    document.getElementById("teamsInviteCard").style.display = "none";

    // Contacts tab
    await loadOrgContacts(orgId);
    document.getElementById("teamsAddContactCard").style.display = "none";

    // Shared inbox tab
    const activeFilter = document.querySelector("#teamsInboxTab .ifinmail-teams-filter-group .active");
    const filter = activeFilter ? activeFilter.dataset.filter : "";
    await loadOrgSharedInbox(orgId, filter);

    // Select this org in the dropdown
    const select = document.getElementById("teamsOrgSelect");
    if (select) select.value = orgId;
  } catch {}
}

async function teamsCreateOrg() {
  const name = document.getElementById("teamsCreateName").value.trim();
  const email = document.getElementById("teamsCreateEmail").value.trim() || null;
  if (!name) return;
  document.getElementById("teamsCreateError").textContent = "";
  try {
    const res = await apiFetch(`${API}/orgs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email }),
    });
    if (!res.ok) {
      const d = await res.json();
      document.getElementById("teamsCreateError").textContent = d.detail || "Failed";
      return;
    }
    document.getElementById("teamsCreateName").value = "";
    document.getElementById("teamsCreateEmail").value = "";
    showToast(`Organization "${name}" created`);
    await loadTeamsOrgSelector();
  } catch {
    document.getElementById("teamsCreateError").textContent = "Network error";
  }
}

function showCreateOrg() {
  document.getElementById("teamsNoOrg").style.display = "block";
  document.getElementById("teamsOrgView").style.display = "none";
}

async function teamsSaveOrg() {
  if (!teamsOrgId) return;
  const name = document.getElementById("teamsOrgName").value.trim();
  const email = document.getElementById("teamsMailingList").value.trim() || "";
  try {
    const res = await apiFetch(`${API}/orgs/${teamsOrgId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name || undefined, email: email || "" }),
    });
    if (res.ok) {
      showToast("Organization saved");
      await loadTeamsOrg(teamsOrgId);
      await loadTeamsOrgSelector();
    } else {
      const d = await res.json();
      showToast(d.detail || "Failed to save");
    }
  } catch { showToast("Network error"); }
}

async function teamsDeleteOrg() {
  if (!teamsOrgId) return;
  if (!confirm("Delete this organization? This will remove all members and data.")) return;
  try {
    const res = await apiFetch(`${API}/orgs/${teamsOrgId}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Organization deleted");
      teamsOrgId = null;
      await loadTeamsOrgSelector();
    }
  } catch { showToast("Network error"); }
}

function showTeamsInvite() {
  const card = document.getElementById("teamsInviteCard");
  card.style.display = card.style.display === "none" ? "block" : "none";
}

async function teamsSendInvite() {
  if (!teamsOrgId) return;
  const email = document.getElementById("teamsInviteEmail")?.value;
  if (!email) { showToast("Please enter an email address"); return; }
  const role = document.getElementById("teamsInviteRole")?.value || "member";
  try {
    const res = await apiFetch(`${API}/orgs/${teamsOrgId}/invite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.invited) {
        showToast("Invited!");
      } else {
        const link = data.accept_url || `${API}/?accept_invite=${data.invite_token}`;
        showToast(`Invite sent! Share this link with ${email}`);
        if (navigator.clipboard) {
          try {
            await navigator.clipboard.writeText(link);
            showToast(`Invite link copied to clipboard`);
          } catch {}
        }
      }
      document.getElementById("teamsInviteEmail").value = "";
      await loadTeamsOrg(teamsOrgId);
    } else {
      const d = await res.json();
      showToast(d.detail || "Failed");
    }
  } catch { showToast("Network error"); }
}

function statusBadge(status) {
  const colors = { pending: "var(--warning)", assigned: "var(--primary)", resolved: "var(--success)" };
  const bg = colors[status] || "var(--text-light)";
  return '<span class="ifinmail-teams-badge ' + status + '">' + status + '</span>';
}

function teamsFilterInbox(btn) {
  document.querySelectorAll("#teamsInboxTab .ifinmail-teams-filter-group .ifinmail-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  if (teamsOrgId) loadOrgSharedInbox(teamsOrgId, btn.dataset.filter);
}

async function loadOrgSharedInbox(orgId, statusFilter) {
  try {
    let url = API + "/orgs/" + orgId + "/shared-inbox?limit=20";
    if (statusFilter) url += "&status=" + statusFilter;
    const res = await apiFetch(url);
    if (!res.ok) return;
    const data = await res.json();
    const el = document.getElementById("teamsInboxMessages");
    if (!el) return;
    if (!data.items.length) {
      el.innerHTML = '<div class="ifinmail-teams-empty"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="display:block;margin:0 auto 12px;opacity:0.4"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>No messages yet<br><small>When someone emails your mailing list, messages will appear here</small></div>';
      return;
    }
    el.innerHTML = data.items.map(m =>
      '<div class="ifinmail-teams-message-item" onclick="viewSharedInboxMessage(' + orgId + ',' + m.id + ')">' +
        '<div class="ifinmail-teams-message-subject">' + (m.subject || "(no subject)") + '</div>' +
        '<div class="ifinmail-teams-message-meta">' +
          '<span>From: ' + m.from_email + '</span>' +
          statusBadge(m.status) +
          '<span>' + new Date(m.created_at).toLocaleDateString() + '</span>' +
          (m.assignee_email ? '<span><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:2px"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> ' + m.assignee_email + '</span>' : '') +
        '</div>' +
      '</div>'
    ).join("");
  } catch {}
}

async function viewSharedInboxMessage(orgId, msgId) {
  showView("message");
  renderSharedInboxMessageView(orgId, msgId);
}

async function renderSharedInboxMessageView(orgId, msgId) {
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId);
    if (!res.ok) { showToast("Failed to load message"); return; }
    const msg = await res.json();

    const orgRes = await apiFetch(API + "/orgs/" + orgId);
    const org = orgRes.ok ? await orgRes.json() : { members: [] };

    let assignHtml = "";
    if (msg.assigned_to) {
      assignHtml = '<p style="font-size:13px;color:var(--text-light);margin:8px 0">Assigned to: <strong>' + (msg.assignee_email || "User #" + msg.assigned_to) + '</strong> <button class="ifinmail-btn ifinmail-btn-sm" onclick="unassignSharedInbox(' + orgId + ',' + msgId + ')">Unassign</button></p>';
    }

    let assignSelectHtml = '<select id="siAssignSelect" class="ifinmail-input" style="width:auto;margin-bottom:0;font-size:13px">';
    assignSelectHtml += org.members.map(m => '<option value="' + m.user_id + '">' + (m.email || "User #" + m.user_id) + "</option>").join("");
    assignSelectHtml += '</select>';
    assignSelectHtml += '<button class="ifinmail-btn ifinmail-btn-sm" onclick="assignSharedInbox(' + orgId + ',' + msgId + ')">Assign</button>';

    let notesHtml = "";
    if (msg.notes && msg.notes.length) {
      notesHtml = '<div style="margin-top:8px">' + msg.notes.map(n =>
        '<div style="padding:8px 12px;background:var(--row-hover);border-radius:6px;margin-bottom:6px;font-size:13px">' +
          '<span style="color:var(--text-light);font-size:11px">' + (n.user_email || "User") + ' · ' + new Date(n.created_at).toLocaleString() + '</span>' +
          '<p style="margin:4px 0 0;color:var(--text)">' + n.note + '</p>' +
        '</div>'
      ).join("") + '</div>';
    }

    document.getElementById("messageView").innerHTML =
      '<div style="max-width:700px;margin:0 auto;padding:24px">' +
        '<button class="ifinmail-btn ifinmail-btn-sm" onclick="goBackToTeams()" style="margin-bottom:16px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px"><polyline points="15 18 9 12 15 6"/></svg> Back to teams</button>' +
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">' +
          statusBadge(msg.status) +
          '<span style="font-size:12px;color:var(--text-light)">' + new Date(msg.created_at).toLocaleString() + '</span>' +
        '</div>' +
        '<h3>' + (msg.subject || "(no subject)") + '</h3>' +
        '<p style="font-size:13px;color:var(--text-light)">From: ' + msg.from_email + '<br>To: ' + (msg.to_email || "—") + '</p>' +
        '<hr style="border:none;border-top:1px solid var(--border);margin:12px 0">' +
        '<div style="white-space:pre-wrap;font-size:14px;line-height:1.6">' + (msg.body_text || "(no content)") + '</div>' +
        '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">' +
        '<div style="margin-bottom:8px">' +
          '<h4 style="font-size:13px;color:var(--text-light);margin:0 0 8px">Assignment</h4>' +
          assignHtml +
          (org.my_role === "owner" || org.my_role === "admin" ? '<div style="display:flex;gap:8px;margin-top:4px">' + assignSelectHtml + '</div>' : "") +
        '</div>' +
        '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">' +
        '<div style="margin-bottom:8px">' +
          '<h4 style="font-size:13px;color:var(--text-light);margin:0 0 8px">Reply</h4>' +
          '<textarea id="siReplyBody" class="ifinmail-input" placeholder="Type your reply..." rows="4" style="resize:vertical;width:100%;margin-bottom:8px"></textarea>' +
          '<button class="ifinmail-btn ifinmail-btn-primary ifinmail-btn-sm" onclick="replySharedInbox(' + orgId + ',' + msgId + ')">Send Reply</button>' +
          '<button class="ifinmail-btn ifinmail-btn-sm" style="margin-left:8px" onclick="resolveSharedInbox(' + orgId + ',' + msgId + ')">Mark Resolved</button>' +
        '</div>' +
        '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">' +
        '<div>' +
          '<h4 style="font-size:13px;color:var(--text-light);margin:0 0 8px">Internal Notes</h4>' +
          notesHtml +
          '<div style="display:flex;gap:8px;margin-top:8px">' +
            '<input type="text" id="siNoteInput" class="ifinmail-input" placeholder="Add internal note" style="flex:1;margin-bottom:0">' +
            '<button class="ifinmail-btn ifinmail-btn-sm" onclick="addSharedInboxNote(' + orgId + ',' + msgId + ')">Add Note</button>' +
          '</div>' +
        '</div>' +
      '</div>';
  } catch { showToast("Error loading message"); }
}

async function assignSharedInbox(orgId, msgId) {
  const sel = document.getElementById("siAssignSelect");
  if (!sel) return;
  const userId = parseInt(sel.value);
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId + "/assign", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });
    if (res.ok) { showToast("Assigned"); renderSharedInboxMessageView(orgId, msgId); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); }
  } catch { showToast("Network error"); }
}

async function unassignSharedInbox(orgId, msgId) {
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId + "/unassign", { method: "POST" });
    if (res.ok) { showToast("Unassigned"); renderSharedInboxMessageView(orgId, msgId); }
  } catch { showToast("Network error"); }
}

async function replySharedInbox(orgId, msgId) {
  const body = document.getElementById("siReplyBody")?.value;
  if (!body || !body.trim()) { showToast("Reply cannot be empty"); return; }
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId + "/reply", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body_text: body }),
    });
    if (res.ok) { showToast("Reply sent"); renderSharedInboxMessageView(orgId, msgId); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); }
  } catch { showToast("Network error"); }
}

async function resolveSharedInbox(orgId, msgId) {
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId + "/status", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "resolved" }),
    });
    if (res.ok) { showToast("Marked resolved"); renderSharedInboxMessageView(orgId, msgId); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); }
  } catch { showToast("Network error"); }
}

async function addSharedInboxNote(orgId, msgId) {
  const input = document.getElementById("siNoteInput");
  if (!input || !input.value.trim()) return;
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/shared-inbox/" + msgId + "/notes", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: input.value.trim() }),
    });
    if (res.ok) { input.value = ""; renderSharedInboxMessageView(orgId, msgId); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); }
  } catch { showToast("Network error"); }
}

function goBackToTeams() {
  showView("teams");
  renderTeams();
}

async function loadOrgContacts(orgId) {
  const res = await apiFetch(`${API}/orgs/${orgId}/contacts`);
  if (!res.ok) return;
  const contacts = await res.json();
  const list = document.getElementById("teamsContactsList");
  if (!list) return;
  list.innerHTML = contacts.length
    ? contacts.map(c => `
      <li class="ifinmail-teams-contact-item">
        <div>
          <strong>${c.email}</strong>
          <div style="font-size:13px;color:var(--text-light)">${c.name || ""}</div>
        </div>
        <button class="ifinmail-btn ifinmail-btn-sm" onclick="deleteOrgContact(${orgId}, ${c.id})">Remove</button>
      </li>
    `).join("")
    : '<div class="ifinmail-teams-empty">No contacts yet</div>';
}

function showTeamsAddContact() {
  const card = document.getElementById("teamsAddContactCard");
  card.style.display = card.style.display === "none" ? "block" : "none";
}

async function teamsAddContact() {
  if (!teamsOrgId) return;
  const email = document.getElementById("teamsContactEmail")?.value;
  const name = document.getElementById("teamsContactName")?.value;
  if (!email) { showToast("Please enter an email address"); return; }
  const res = await apiFetch(`${API}/orgs/${teamsOrgId}/contacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name: name || null }),
  });
  if (res.ok) {
    document.getElementById("teamsContactEmail").value = "";
    document.getElementById("teamsContactName").value = "";
    showToast("Contact added");
    await loadOrgContacts(teamsOrgId);
  } else {
    const d = await res.json();
    showToast(d.detail || "Failed");
  }
}

async function deleteOrgContact(orgId, contactId) {
  const res = await apiFetch(`${API}/orgs/${orgId}/contacts/${contactId}`, { method: "DELETE" });
  if (res.ok) { showToast("Contact removed"); await loadOrgContacts(orgId); }
}

async function removeOrgMember(orgId, userId) {
  try {
    const res = await apiFetch(`${API}/orgs/${orgId}/remove/${userId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (res.ok) { showToast("Removed"); await loadTeamsOrg(orgId); }
  } catch {}
}

async function sendToAllMembers() {
  if (!teamsOrgId) return;
  try {
    const res = await apiFetch(`${API}/orgs/${teamsOrgId}`);
    if (!res.ok) { showToast("Failed to load org"); return; }
    const org = await res.json();
    const emails = (org.members || []).map(m => m.email).filter(Boolean);
    if (!emails.length) { showToast("No members with email addresses"); return; }
    showCompose();
    document.getElementById("composeTo").value = emails.join(", ");
    showToast(`Composing to ${emails.length} member${emails.length > 1 ? "s" : ""}`);
  } catch { showToast("Network error"); }
}

async function sendTestEmail() {
  if (!teamsOrgId) return;
  const btn = document.getElementById("teamsTestEmailBtn");
  btn.disabled = true;
  btn.textContent = "Sending...";
  try {
    const res = await apiFetch(`${API}/orgs/${teamsOrgId}/test-email`, { method: "POST" });
    if (res.ok) {
      showToast("Test email sent! Check Shared Inbox tab.");
      const filter = document.querySelector("#teamsInboxTab .ifinmail-teams-filter-group .active");
      await loadOrgSharedInbox(teamsOrgId, filter ? filter.dataset.filter : "");
      showTeamsTab("inbox");
    } else {
      const d = await res.json();
      showToast(d.detail || "Failed to send test email");
    }
  } catch { showToast("Network error"); }
  btn.disabled = false;
  btn.textContent = "Send Test Email";
}

async function changeMemberRole(orgId, memberId, role) {
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/members/" + memberId + "/role", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (res.ok) { showToast("Role changed to " + role); await loadTeamsOrg(orgId); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); await loadTeamsOrg(orgId); }
  } catch { showToast("Network error"); }
}

async function transferOwnership(orgId, userId) {
  if (!confirm("Transfer ownership? You will become an admin.")) return;
  try {
    const res = await apiFetch(API + "/orgs/" + orgId + "/transfer/" + userId, { method: "POST" });
    if (res.ok) { showToast("Ownership transferred"); await loadTeamsOrgSelector(); }
    else { const d = await res.json(); showToast(d.detail || "Failed"); }
  } catch { showToast("Network error"); }
}

async function leaveOrg(orgId) {
  try {
    const res = await apiFetch(`${API}/orgs/${orgId}/leave`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (res.ok) { showToast("Left organization"); await loadTeamsOrgSelector(); }
  } catch {}
}

// ── Communication Dashboard ──

async function renderDashboard() {
  const tmpl = document.getElementById("dashboardTmpl");
  document.getElementById("dashboardView").innerHTML = tmpl.innerHTML;
  const btns = document.querySelectorAll("#dashboardPeriod button");
  btns.forEach(b => {
    b.onclick = () => {
      btns.forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      renderDashboardContent(b.value);
    };
  });
  renderDashboardContent(document.querySelector("#dashboardPeriod .active")?.value || "30");
}

async function renderDashboardContent(days) {
  await Promise.all([
    loadDashboardVolume(days),
    loadDashboardTopContacts(days),
    loadDashboardDeliverability(days),
    loadDashboardTracking(days),
    loadDashboardContactEngagement(),
    loadDashboardCampaignStats(),
  ]);
}

async function loadDashboardVolume(days) {
  const res = await apiFetch(`${API}/analytics/volume?days=${days}`);
  if (!res.ok) return;
  const data = await res.json();
  const cards = document.getElementById("dashboardCards");
  cards.innerHTML = [
    '<div class="ifinmail-dashboard-card"><div class="ifinmail-dashboard-card-top"></div><div class="ifinmail-dashboard-card-body"><div class="ifinmail-dashboard-card-value">' + data.total + '</div><div class="ifinmail-dashboard-card-label">Total Messages</div></div></div>',
    ...data.by_folder.map(f => '<div class="ifinmail-dashboard-card"><div class="ifinmail-dashboard-card-top" style="background:' + (f.folder === 'INBOX' ? 'var(--primary)' : f.folder === 'SENT' ? '#00b894' : f.folder === 'DRAFTS' ? '#fdcb6e' : f.folder === 'TRASH' ? '#e17055' : f.folder === 'SPAM' ? '#e84393' : '#6c5ce7') + '"></div><div class="ifinmail-dashboard-card-body"><div class="ifinmail-dashboard-card-value">' + f.count + '</div><div class="ifinmail-dashboard-card-label">' + f.folder + '</div></div></div>'),
  ].join("");
  const maxFolder = Math.max(...data.by_folder.map(f => f.count), 1);
  document.getElementById("dashboardFolderChart").innerHTML = data.by_folder.length
    ? data.by_folder.map(f =>
        '<div class="ifinmail-dashboard-bar"><span class="ifinmail-dashboard-bar-label">' + f.folder + '</span><div class="ifinmail-dashboard-bar-track"><div class="ifinmail-dashboard-bar-fill" style="width:' + (f.count / maxFolder * 100) + '%;background:' + (f.folder === 'INBOX' ? 'var(--primary)' : f.folder === 'SENT' ? '#00b894' : f.folder === 'DRAFTS' ? '#fdcb6e' : f.folder === 'TRASH' ? '#e17055' : f.folder === 'SPAM' ? '#e84393' : '#6c5ce7') + '"></div></div><span class="ifinmail-dashboard-bar-count">' + f.count + '</span></div>'
      ).join("")
    : '<div class="ifinmail-dashboard-empty">No messages yet</div>';
  const maxDaily = Math.max(...data.daily.map(d => d.count), 1);
  document.getElementById("dashboardDailyChart").innerHTML = data.daily.length
    ? data.daily.map(d =>
        '<div class="ifinmail-dashboard-bar ifinmail-dashboard-bar-sm"><span class="ifinmail-dashboard-bar-label" style="min-width:auto;font-size:11px">' + d.date.slice(5) + '</span><div class="ifinmail-dashboard-bar-track"><div class="ifinmail-dashboard-bar-fill" style="width:' + (d.count / maxDaily * 100) + '%;background:var(--primary)"></div></div><span class="ifinmail-dashboard-bar-count">' + d.count + '</span></div>'
      ).join("")
    : '<div class="ifinmail-dashboard-empty">No daily data</div>';
}

async function loadDashboardTopContacts(days) {
  const res = await apiFetch(`${API}/analytics/top-contacts?days=${days}&limit=10`);
  if (!res.ok) return;
  const data = await res.json();
  const maxS = Math.max(...data.senders.map(s => s.count), 1);
  const maxR = Math.max(...data.recipients.map(r => r.count), 1);
  document.getElementById("dashboardTopSenders").innerHTML = data.senders.length
    ? data.senders.map(s =>
        '<div class="ifinmail-dashboard-bar ifinmail-dashboard-bar-sm"><span class="ifinmail-dashboard-bar-label" style="min-width:0;flex:1">' + s.email + '</span><div class="ifinmail-dashboard-bar-track" style="flex:2"><div class="ifinmail-dashboard-bar-fill" style="width:' + (s.count / maxS * 100) + '%"></div></div><span class="ifinmail-dashboard-bar-count">' + s.count + '</span></div>'
      ).join("")
    : '<div class="ifinmail-dashboard-empty">No inbound messages</div>';
  document.getElementById("dashboardTopRecipients").innerHTML = data.recipients.length
    ? data.recipients.map(r =>
        '<div class="ifinmail-dashboard-bar ifinmail-dashboard-bar-sm"><span class="ifinmail-dashboard-bar-label" style="min-width:0;flex:1">' + r.email + '</span><div class="ifinmail-dashboard-bar-track" style="flex:2"><div class="ifinmail-dashboard-bar-fill" style="width:' + (r.count / maxR * 100) + '%"></div></div><span class="ifinmail-dashboard-bar-count">' + r.count + '</span></div>'
      ).join("")
    : '<div class="ifinmail-dashboard-empty">No sent messages</div>';
}

async function loadDashboardDeliverability(days) {
  const res = await apiFetch(`${API}/analytics/deliverability?days=${days}`);
  if (!res.ok) return;
  const data = await res.json();
  document.getElementById("dashboardDeliverability").innerHTML = data.total
    ? [
        '<div class="ifinmail-dashboard-row"><span class="ifinmail-dashboard-row-label">Total deliveries</span><span class="ifinmail-dashboard-row-value">' + data.total + '</span></div>',
        '<div class="ifinmail-dashboard-row"><span class="ifinmail-dashboard-row-label">Opened</span><span class="ifinmail-dashboard-row-value">' + data.opened + ' <span style="font-weight:400;color:var(--text-light)">(' + data.open_rate + '%)</span></span></div>',
        '<div class="ifinmail-dashboard-row"><span class="ifinmail-dashboard-row-label">Clicked</span><span class="ifinmail-dashboard-row-value">' + data.clicked + ' <span style="font-weight:400;color:var(--text-light)">(' + data.click_rate + '%)</span></span></div>',
        ...Object.entries(data.by_status).map(([s, c]) => '<div class="ifinmail-dashboard-row"><span class="ifinmail-dashboard-row-label">' + s + '</span><span class="ifinmail-dashboard-row-value">' + c + '</span></div>'),
      ].join("")
    : '<div class="ifinmail-dashboard-empty">No delivery data yet</div>';
}

async function loadDashboardTracking(days) {
  await Promise.all([
    loadTrackingSummary(days),
    loadTrackingHourly(days),
    loadTrackingDevices(days),
    loadTrackingLocations(days),
  ]);
}

async function loadTrackingSummary(days) {
  const res = await apiFetch(`${API}/analytics/tracking/summary?days=${days}`);
  if (!res.ok) return;
  const d = await res.json();
  const el = document.getElementById("dashboardTrackingSummary");
  if (!el) return;
  el.innerHTML = d.total_deliveries
    ? [
        '<div class="ifinmail-tracking-card"><span class="ifinmail-tracking-stat">' + d.total_opens + '</span><span class="ifinmail-tracking-label">Total Opens</span></div>',
        '<div class="ifinmail-tracking-card"><span class="ifinmail-tracking-stat">' + d.unique_opens + '</span><span class="ifinmail-tracking-label">Unique Opens</span></div>',
        '<div class="ifinmail-tracking-card"><span class="ifinmail-tracking-stat">' + d.open_rate + '%</span><span class="ifinmail-tracking-label">Open Rate</span></div>',
        '<div class="ifinmail-tracking-card"><span class="ifinmail-tracking-stat">' + d.click_rate + '%</span><span class="ifinmail-tracking-label">Click Rate</span></div>',
        '<div class="ifinmail-tracking-card"><span class="ifinmail-tracking-stat">' + d.click_to_open_rate + '%</span><span class="ifinmail-tracking-label">Click-to-Open</span></div>',
      ].join("")
    : '<div class="ifinmail-dashboard-empty">No tracking data yet</div>';
}

async function loadTrackingHourly(days) {
  const canvas = document.getElementById("hourlyChartCanvas");
  if (!canvas) return;
  const res = await apiFetch(`${API}/analytics/tracking/hourly?days=${days}`);
  if (!res.ok) return;
  const d = await res.json();
  if (typeof Chart === "undefined") return;
  if (window._hourlyChart) window._hourlyChart.destroy();
  window._hourlyChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: d.labels,
      datasets: [
        { label: "Opens", data: d.opens, backgroundColor: "rgba(54,162,235,0.7)", borderRadius: 4 },
        { label: "Clicks", data: d.clicks, backgroundColor: "rgba(75,192,192,0.7)", borderRadius: 4 },
      ],
    },
    options: { responsive: true, plugins: { legend: { position: "top" } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } } } },
  });
}

async function loadTrackingDevices(days) {
  const res = await apiFetch(`${API}/analytics/tracking/devices?days=${days}`);
  if (!res.ok) return;
  const d = await res.json();
  if (typeof Chart === "undefined") return;

  function makePie(id, label, data, colors) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (window[id + "_chart"]) window[id + "_chart"].destroy();
    if (data.length === 0) { document.getElementById(canvas.parentElement.id).innerHTML = '<div class="ifinmail-dashboard-empty">No data</div>'; return; }
    window[id + "_chart"] = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: data.map(i => i.name),
        datasets: [{ label, data: data.map(i => i.count), backgroundColor: colors || ["#36a2eb","#ff6384","#ffcd56","#4bc0c0","#9966ff","#c9cbcf"] }],
      },
      options: { responsive: true, plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } } } },
    });
  }

  makePie("devicesChartCanvas", "Devices", d.devices);
  makePie("osChartCanvas", "OS", d.os);
  makePie("browsersChartCanvas", "Browsers", d.browsers);
}

async function loadTrackingLocations(days) {
  const res = await apiFetch(`${API}/analytics/tracking/locations?days=${days}`);
  if (!res.ok) return;
  const d = await res.json();
  const el = document.getElementById("dashboardLocations");
  if (!el) return;
  if (!d.cities || d.cities.length === 0) { el.innerHTML = '<div class="ifinmail-dashboard-empty">No location data yet</div>'; return; }
  el.innerHTML = '<table class="ifinmail-table"><thead><tr><th>City</th><th>Country</th><th>Events</th></tr></thead><tbody>' +
    d.cities.map(c => '<tr><td>' + c.city + '</td><td>' + c.country + '</td><td>' + c.count + '</td></tr>').join("") +
    '</tbody></table>';
}

function exportReport(format) {
  const days = document.querySelector("#dashboardPeriod .active")?.value || "30";
  const token = localStorage.getItem("ifinmail_token");
  const url = `${API}/analytics/export/${format}?days=${days}`;
  const a = document.createElement("a");
  a.href = url;
  a.download = `analytics_report_${new Date().toISOString().slice(0,10)}.${format}`;
  const xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  xhr.setRequestHeader("Authorization", `Bearer ${token}`);
  xhr.responseType = "blob";
  xhr.onload = function() {
    if (xhr.status === 200) {
      const blob = xhr.response;
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `analytics_report_${new Date().toISOString().slice(0,10)}.${format}`;
      link.click();
      URL.revokeObjectURL(link.href);
    }
  };
  xhr.send();
}

// ── M-Pesa Payment in Billing settings ──
async function loadMpesaPayment() {
  const plansContainer = document.getElementById("billingPlans");
  if (!plansContainer || document.getElementById("mpesaSection")) return;
  try {
    const res = await apiFetch(`${API}/payments/plans`);
    if (!res.ok) return;
    const plans = await res.json();
    const section = document.createElement("section");
    section.className = "ifinmail-settings-section";
    section.id = "mpesaSection";
    section.innerHTML = '<h3>Mobile Money (M-Pesa)</h3>';
    plans.forEach(p => {
      const div = document.createElement("div");
      div.style.cssText = "display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)";
      div.innerHTML = `
        <div>
          <strong>${p.name}</strong>
          <span style="font-size:12px;color:var(--text-light)"> ${p.features.join(" · ")}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span style="font-size:13px;font-weight:600">KSh ${p.price_mobile.toLocaleString()}</span>
          <button class="ifinmail-btn ifinmail-btn-sm ifinmail-btn-primary" onclick="payWithMpesa('${p.name}', ${p.price_mobile})">Pay with M-Pesa</button>
        </div>
      `;
      section.appendChild(div);
    });
    plansContainer.parentNode.insertBefore(section, plansContainer.nextSibling);
  } catch {}
}

async function payWithMpesa(plan, amount) {
  const phone = prompt("Enter M-Pesa phone number (e.g. 254712345678):");
  if (!phone || !phone.match(/^254\d{9}$/)) { showToast("Enter a valid Safaricom number (254XXXXXXXXX)"); return; }
  try {
    const res = await apiFetch(`${API}/payments/mpesa/stkpush`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, amount, account_ref: `ifinmail-${plan}` }),
    });
    if (!res.ok) { showToast("Payment request failed"); return; }
    const data = await res.json();
    if (data.success) {
      showToast("STK push sent! Check your phone to complete payment.");
      // Poll for status
      const poll = setInterval(async () => {
        const r = await apiFetch(`${API}/payments/mpesa/status/${data.checkout_request_id}`);
        if (r.ok) {
          const s = await r.json();
          if (s.status === "completed") { clearInterval(poll); showToast("Payment received!"); }
          else if (s.status === "failed") { clearInterval(poll); showToast("Payment failed"); }
        }
      }, 3000);
      setTimeout(() => clearInterval(poll), 60000);
    } else {
      showToast(data.message || "Payment failed");
    }
  } catch { showToast("Network error"); }
}

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

let _ws = null;
function connectWS() {
  if (!state.token || state.token === "undefined") return;
  if (_ws) { _ws.onclose = null; _ws.close(); _ws = null; }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  _ws = new WebSocket(`${proto}//${window.location.host}/ws?token=${state.token}`);
  _ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.event === "new_mail") {
        if (state.folder === "INBOX" || state.folder === "SENT") {
          fetchMessages();
          fetchFolderCounts();
        }
        if (document.hidden) {
          const from = (msg.data && msg.data.from) || "Someone";
          const subject = (msg.data && msg.data.subject) || "(no subject)";
          sendNotification("New mail from " + from, { body: subject, icon: "/static/favicon.ico" });
        }
      }
    } catch {}
  };
  _ws.onclose = (e) => {
    if (e.code === 4001) {
      clearAuth();
      render();
      return;
    }
    if (state.token) setTimeout(connectWS, 30000);
  };
}

// Request notification permission on login
function requestNotifyPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function updateOfflineBanner() {
  const banner = document.getElementById("offlineBanner");
  if (!banner) return;
  banner.style.display = navigator.onLine ? "none" : "block";
}

async function registerPush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try {
    window.addEventListener("online", updateOfflineBanner);
    window.addEventListener("offline", updateOfflineBanner);
    const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
    await navigator.serviceWorker.ready;
    updateOfflineBanner();
    let sub = await reg.pushManager.getSubscription();
    if (sub) {
      // Unsubscribe if no longer valid
      const resp = await apiFetch("/api/push/vapid-public-key");
      if (!resp.ok) return;
      const { public_key } = await resp.json();
      const keyMatch = btoa(String.fromCharCode(...new Uint8Array(sub.options.applicationServerKey))) === public_key;
      if (!keyMatch) {
        await sub.unsubscribe();
        sub = null;
      }
    }
    if (!sub) {
      const resp = await apiFetch("/api/push/vapid-public-key");
      if (!resp.ok) return;
      const { public_key } = await resp.json();
      const keyBuf = Uint8Array.from(atob(public_key), (c) => c.charCodeAt(0));
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBuf,
      });
    }
    const subJson = sub.toJSON();
    await apiFetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: subJson.endpoint,
        keys: subJson.keys,
      }),
    });
  } catch {}
}

function sendNotification(title, opts) {
  if (isElectron) {
    window.ifinmail.showNotification({ title, body: (opts && opts.body) || "" });
    return;
  }
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification(title, opts);
  }
}

(async function init() {
  sanitizeStorage();
  // Re-read state after sanitizing
  state.token = state.token && state.token !== "undefined" ? state.token : null;
  state.refreshToken = state.refreshToken && state.refreshToken !== "undefined" ? state.refreshToken : null;
  if (state.token && state.refreshToken) {
    try {
      const r = await fetch(`${API}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      if (r.ok) {
        const data = await r.json();
        if (!data.access_token) { clearAuth(); render(); return; }
        state.token = data.access_token;
        localStorage.setItem("ifinmail_token", state.token);
      } else {
        clearAuth();
      }
    } catch {
      clearAuth();
    }
  }

  // Check SSO availability
  try {
    const ssoRes = await fetch(`${API}/sso/status`);
    if (ssoRes.ok) {
      const ssoData = await ssoRes.json();
      const googleBtn = document.getElementById("ssoGoogle");
      const msBtn = document.getElementById("ssoMicrosoft");
      if (googleBtn) {
        if (!ssoData.google) { googleBtn.disabled = true; googleBtn.title = "Google SSO not configured"; googleBtn.style.opacity = "0.4"; }
      }
      if (msBtn) {
        if (!ssoData.microsoft) { msBtn.disabled = true; msBtn.title = "Microsoft SSO not configured"; msBtn.style.opacity = "0.4"; }
      }
    }
  } catch {}

  render();
  connectWS();
  requestNotifyPermission();
})();

// ── SPA deep-linking via URL hash ──

function updateHash() {
  const parts = [];
  if (state.folder && state.folder !== "INBOX") parts.push("folder=" + state.folder);
  if (state.currentMsg) parts.push("msg=" + state.currentMsg.id);
  if (state.searchQuery) parts.push("q=" + encodeURIComponent(state.searchQuery || ""));
  const fp = document.getElementById("filterPanel");
  const filterOpen = fp && fp.style.display !== "none";
  if (filterOpen) parts.push("filter=1");
  const filterFrom = document.getElementById("filterFrom")?.value?.trim();
  const filterTo = document.getElementById("filterTo")?.value?.trim();
  const filterSubject = document.getElementById("filterSubject")?.value?.trim();
  const filterAfter = document.getElementById("filterAfter")?.value;
  const filterBefore = document.getElementById("filterBefore")?.value;
  const filterRead = document.getElementById("filterRead")?.value;
  const filterAttach = document.getElementById("filterAttach")?.checked;
  const filterStarred = document.getElementById("filterStarred")?.checked;
  if (filterFrom) parts.push("from=" + encodeURIComponent(filterFrom));
  if (filterTo) parts.push("to=" + encodeURIComponent(filterTo));
  if (filterSubject) parts.push("subj=" + encodeURIComponent(filterSubject));
  if (filterAfter) parts.push("after=" + filterAfter);
  if (filterBefore) parts.push("before=" + filterBefore);
  if (filterRead) parts.push("read=" + filterRead);
  if (filterAttach) parts.push("attach=1");
  if (filterStarred) parts.push("starred=1");
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
  // Restore filters
  const fp = document.getElementById("filterPanel");
  const hasFilter = params.has("filter") || params.has("from") || params.has("to") || params.has("subj") || params.has("after") || params.has("before") || params.has("read") || params.has("attach") || params.has("starred");
  if (hasFilter && fp) {
    fp.style.display = "";
    const fv = (id) => document.getElementById(id);
    const from = params.get("from");
    const to = params.get("to");
    const subj = params.get("subj");
    const after = params.get("after");
    const before = params.get("before");
    const read = params.get("read");
    const attach = params.get("attach");
    const starred = params.get("starred");
    if (from && fv("filterFrom")) fv("filterFrom").value = from;
    if (to && fv("filterTo")) fv("filterTo").value = to;
    if (subj && fv("filterSubject")) fv("filterSubject").value = subj;
    if (after && fv("filterAfter")) fv("filterAfter").value = after;
    if (before && fv("filterBefore")) fv("filterBefore").value = before;
    if (read && fv("filterRead")) fv("filterRead").value = read;
    if (attach && fv("filterAttach")) fv("filterAttach").checked = true;
    if (starred && fv("filterStarred")) fv("filterStarred").checked = true;
    setTimeout(() => fetchMessages(), 100);
  }
  if (msgId) {
    setTimeout(() => openMessage(parseInt(msgId)), 200);
  }
}

setTimeout(restoreFromHash, 300);

// ── Accept org invite from URL ──
(async () => {
  const sp = new URLSearchParams(window.location.search);
  const inviteToken = sp.get("accept_invite");
  if (!inviteToken) return;
  if (!state.token) {
    showToast("Log in to accept the invitation");
    return;
  }
  try {
    const res = await apiFetch(`${API}/orgs/accept-invite?token=${inviteToken}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      showToast(`Joined ${data.organization_name || "organization"}!`);
      history.replaceState(null, "", window.location.pathname);
    } else {
      const d = await res.json();
      showToast(d.detail || "Failed to accept invite");
    }
  } catch { showToast("Network error"); }
})();

// ── Auto-save draft on tab close ──
window.addEventListener("beforeunload", () => {
  if (document.getElementById("composeView")?.style.display !== "block") return;
  const to = document.getElementById("composeTo")?.value;
  const subject = document.getElementById("composeSubject")?.value;
  const bodyEl = document.getElementById("composeBody");
  const body = bodyEl?.innerText;
  if (!to && !subject && !body) return;
  const bodyData = { to: to || "", subject: subject || "", body_text: body || "", body_html: bodyEl?.innerHTML || "" };
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

// ── Dashboard: Contact Engagement ──

async function loadDashboardContactEngagement() {
  try {
    const res = await apiFetch(`${API}/analytics/contact-engagement?days=90`);
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById("dashboardContactEngagement");
    if (!container) return;
    const contacts = data.contacts || [];
    if (!contacts.length) { container.innerHTML = '<p style="color:var(--muted);font-size:13px">No contact engagement data yet.</p>'; return; }
    const top = contacts.slice(0, 20);
    let html = `<div style="display:flex;flex-wrap:wrap;gap:12px">`;
    top.forEach(c => {
      const color = c.engagement_score >= 50 ? "var(--success)" : c.engagement_score >= 20 ? "var(--warning)" : "var(--muted)";
      html += `<div class="ifinmail-engagement-card" data-contact-id="${c.id}" style="cursor:pointer;flex:1;min-width:160px;padding:10px;border:1px solid var(--border);border-radius:8px" onclick="showContactEngagementDetail(${c.id})">
        <div style="font-size:13px"><strong>${c.name || c.email}</strong></div>
        <div style="font-size:11px;color:var(--muted)">${c.email}</div>
        <div style="margin-top:4px;font-size:20px;font-weight:700;color:${color}">${c.engagement_score}%</div>
        <div style="font-size:11px;color:var(--muted)">Sent: ${c.total_sent} · Opens: ${c.total_opens} · Clicks: ${c.total_clicks}</div>
      </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;
  } catch {}
}

async function showContactEngagementDetail(contactId) {
  try {
    const res = await apiFetch(`${API}/contacts/${contactId}/engagement`);
    if (!res.ok) { showToast("Failed to load engagement detail"); return; }
    const data = await res.json();
    let html = `<div class="ifinmail-overlay" id="engagementDetailOverlay" style="display:flex" onclick="if(event.target===this)closeEngagementDetail()">`;
    html += `<div class="ifinmail-dialog" style="max-width:700px;max-height:80vh;overflow-y:auto">`;
    html += `<div class="ifinmail-dialog-header">
      <h3>${data.name || data.email}</h3>
      <button class="ifinmail-btn ifinmail-btn-back" onclick="closeEngagementDetail()"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
    </div>`;
    html += `<div class="ifinmail-dialog-body">`;
    html += `<div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap">
      <div style="padding:8px 12px;background:var(--bg);border-radius:6px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:${data.engagement_score >= 50 ? 'var(--success)' : data.engagement_score >= 20 ? 'var(--warning)' : 'var(--muted)'}">${data.engagement_score}%</div>
        <div style="font-size:11px;color:var(--muted)">Engagement</div>
      </div>
      <div><strong>Total sent:</strong> ${data.total_sent}<br><strong>Opens:</strong> ${data.total_opens}<br><strong>Clicks:</strong> ${data.total_clicks}</div>
    </div>`;
    if (!data.deliveries.length) {
      html += '<p style="color:var(--muted)">No deliveries yet.</p>';
    } else {
      html += `<table style="width:100%;border-collapse:collapse;font-size:12px">`;
      html += `<thead><tr style="border-bottom:2px solid var(--border)"><th style="text-align:left;padding:4px 6px">Date</th><th style="text-align:left;padding:4px 6px">Subject</th><th style="text-align:center;padding:4px 6px">Status</th><th style="text-align:center;padding:4px 6px">Opened</th><th style="text-align:center;padding:4px 6px">Clicked</th></tr></thead><tbody>`;
      data.deliveries.forEach(d => {
        const opened = d.opened_at ? '<span style="color:var(--success)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><polyline points="20 6 9 17 4 12"/></svg></span>' : '—';
        const clicked = d.clicked_at ? '<span style="color:var(--primary)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><polyline points="20 6 9 17 4 12"/></svg></span>' : '—';
        html += `<tr style="border-bottom:1px solid var(--border)">
          <td style="padding:4px 6px;white-space:nowrap">${new Date(d.sent_at).toLocaleDateString()}</td>
          <td style="padding:4px 6px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${d.subject || '(no subject)'}</td>
          <td style="text-align:center;padding:4px 6px">${d.status}</td>
          <td style="text-align:center;padding:4px 6px">${opened}</td>
          <td style="text-align:center;padding:4px 6px">${clicked}</td>
        </tr>`;
      });
      html += `</tbody></table>`;
    }
    html += `</div></div></div>`;
    const existing = document.getElementById("engagementDetailOverlay");
    if (existing) existing.remove();
    document.body.insertAdjacentHTML("beforeend", html);
  } catch { showToast("Network error"); }
}

function closeEngagementDetail() {
  const el = document.getElementById("engagementDetailOverlay");
  if (el) el.remove();
}

// ── Dashboard: Campaign Analytics ──

async function loadDashboardCampaignStats() {
  try {
    const res = await apiFetch(`${API}/analytics/campaign-stats`);
    if (!res.ok) return;
    const data = await res.json();
    const container = document.getElementById("dashboardCampaignStats");
    if (!container) return;
    const campaigns = data.campaigns || [];
    if (!campaigns.length) { container.innerHTML = '<p style="color:var(--muted);font-size:13px">No campaign data yet.</p>'; return; }
    let html = "";
    campaigns.forEach(c => {
      html += `<div style="margin-bottom:16px;padding:12px;border:1px solid var(--border);border-radius:8px">
        <h4 style="margin:0 0 8px;font-size:14px">${c.name} (${c.total_steps} steps)</h4>`;
      c.steps.forEach(s => {
        const rate = s.sent > 0 ? Math.round((s.opened + s.clicked) / (s.sent * 2) * 100) : 0;
        html += `<div style="display:flex;gap:12px;font-size:12px;padding:4px 0;border-bottom:1px solid var(--border)">
          <span style="flex:1">Step ${s.order}: "${s.subject || '(no subject)'}"</span>
          <span>Sent: ${s.sent}</span>
          <span style="color:var(--primary)">Opened: ${s.opened}</span>
          <span style="color:var(--success)">Clicked: ${s.clicked}</span>
        </div>`;
      });
      html += `</div>`;
    });
    container.innerHTML = html;
  } catch {}
}

// ── API Key Management ──

async function revokeApiKey(keyId) {
  try {
    const res = await apiFetch(`${API}/api-keys/${keyId}`, { method: "DELETE" });
    if (res.ok) showToast("API key revoked");
    const settingsView = document.getElementById("settingsView");
    if (settingsView && settingsView.style.display !== "none") renderSettings();
  } catch { showToast("Network error"); }
}
