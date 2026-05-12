# Week 10: Minimal Frontend — HTML, CSS & Vanilla JavaScript

**Month 3: Integration & Capstone | Days 55–60**

ifinmail's frontend strategy is deliberately minimal: no React, no Angular, no Vue, no heavy build pipeline. Instead: server-rendered HTML, vanilla JavaScript modules, Web Components only where useful, and strict `.ifinmail-*` CSS prefixing. This week builds the webmail client, admin dashboard, and the internal CSS utility layer that replaces Bootstrap.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Build server-rendered HTML pages for webmail and admin dashboard
- Write vanilla JavaScript modules for interactivity (no framework)
- Implement the `.ifinmail-*` CSS prefixing system
- Use progressive enhancement and degrade safely without JavaScript
- Integrate the frontend with the Week 8 API
- Build a small internal CSS utility layer (no Bootstrap dependency)

---

## Day 1 (Monday): Server-Rendered HTML & The ifinmail CSS System

### Learning Objectives
- Set up a Flask/FastAPI template rendering pipeline
- Structure HTML pages with semantic elements
- Implement the `.ifinmail-*` CSS prefixing system
- Build the internal CSS utility layer (replacing Bootstrap)

### Theory / Reading
- **Server-rendered HTML**: templates rendered on the server, sent as complete pages; no client-side routing
- **Proposal Section 9**: CSS classes MUST use `.ifinmail-*` prefix
- **CSS custom properties**: theming without build tools; `--ifinmail-primary`, `--ifinmail-bg`, etc.
- **Progressive enhancement**: pages work without JavaScript; JS adds interactivity

### Practical Exercise
```bash
# Create the web client directory
mkdir -p ~/ifinmail-web/{templates,static/{css,js,img},components}
cd ~/ifinmail-web
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn jinja2 aiofiles
```

```html
<!-- ~/ifinmail-web/templates/base.html -->
<!DOCTYPE html>
<html lang="en" class="ifinmail-shell">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}ifinmail{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/ifinmail-variables.css">
    <link rel="stylesheet" href="/static/css/ifinmail-reset.css">
    <link rel="stylesheet" href="/static/css/ifinmail-utilities.css">
    <link rel="stylesheet" href="/static/css/ifinmail-layout.css">
    <link rel="stylesheet" href="/static/css/ifinmail-components.css">
    {% block head %}{% endblock %}
</head>
<body class="ifinmail-body">
    <header class="ifinmail-header">
        <div class="ifinmail-header-brand">
            <a href="/" class="ifinmail-logo">ifinmail</a>
        </div>
        <nav class="ifinmail-header-nav">
            <a href="/mail" class="ifinmail-nav-link">Mail</a>
            <a href="/admin" class="ifinmail-nav-link">Admin</a>
        </nav>
        <div class="ifinmail-header-user">
            <span class="ifinmail-user-email">{% block user_email %}user@ifinmail.local{% endblock %}</span>
        </div>
    </header>
    
    <main class="ifinmail-main">
        {% block content %}{% endblock %}
    </main>
    
    <footer class="ifinmail-footer">
        <p>ifinmail — secure, API-first email platform</p>
    </footer>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

```css
/* ~/ifinmail-web/static/css/ifinmail-variables.css */
/* Design tokens — the only place colors, fonts, and spacing are defined. */
:root {
    /* Colors */
    --ifinmail-primary: #2563eb;
    --ifinmail-primary-hover: #1d4ed8;
    --ifinmail-primary-light: #dbeafe;
    --ifinmail-danger: #dc2626;
    --ifinmail-danger-light: #fecaca;
    --ifinmail-success: #16a34a;
    --ifinmail-success-light: #bbf7d0;
    --ifinmail-warning: #f59e0b;
    --ifinmail-warning-light: #fde68a;
    
    --ifinmail-bg: #ffffff;
    --ifinmail-bg-secondary: #f8fafc;
    --ifinmail-bg-tertiary: #f1f5f9;
    
    --ifinmail-text: #0f172a;
    --ifinmail-text-secondary: #475569;
    --ifinmail-text-muted: #94a3b8;
    
    --ifinmail-border: #e2e8f0;
    --ifinmail-border-hover: #cbd5e1;
    
    /* Typography */
    --ifinmail-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --ifinmail-font-mono: "SF Mono", "Fira Code", monospace;
    --ifinmail-font-size-xs: 0.75rem;
    --ifinmail-font-size-sm: 0.875rem;
    --ifinmail-font-size-base: 1rem;
    --ifinmail-font-size-lg: 1.125rem;
    --ifinmail-font-size-xl: 1.25rem;
    --ifinmail-font-size-2xl: 1.5rem;
    
    /* Spacing */
    --ifinmail-space-1: 0.25rem;
    --ifinmail-space-2: 0.5rem;
    --ifinmail-space-3: 0.75rem;
    --ifinmail-space-4: 1rem;
    --ifinmail-space-6: 1.5rem;
    --ifinmail-space-8: 2rem;
    
    /* Borders */
    --ifinmail-radius-sm: 4px;
    --ifinmail-radius-md: 8px;
    --ifinmail-radius-lg: 12px;
    
    /* Shadows */
    --ifinmail-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
    --ifinmail-shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
}
```

```css
/* ~/ifinmail-web/static/css/ifinmail-reset.css */
/* Minimal reset — no normalize.css, no CSS frameworks. */
.ifinmail-shell *,
.ifinmail-shell *::before,
.ifinmail-shell *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

.ifinmail-body {
    font-family: var(--ifinmail-font-family);
    font-size: var(--ifinmail-font-size-base);
    color: var(--ifinmail-text);
    background: var(--ifinmail-bg);
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

.ifinmail-shell a {
    color: var(--ifinmail-primary);
    text-decoration: none;
}

.ifinmail-shell a:hover {
    text-decoration: underline;
}
```

```css
/* ~/ifinmail-web/static/css/ifinmail-utilities.css */
/* Internal utility layer — replaces Bootstrap utilities.
   Only the classes we actually use. Nothing unused. */

/* --- Layout --- */
.ifinmail-flex { display: flex; }
.ifinmail-flex-col { flex-direction: column; }
.ifinmail-flex-row { flex-direction: row; }
.ifinmail-flex-wrap { flex-wrap: wrap; }
.ifinmail-items-center { align-items: center; }
.ifinmail-justify-between { justify-content: space-between; }
.ifinmail-justify-center { justify-content: center; }
.ifinmail-flex-1 { flex: 1; }
.ifinmail-gap-2 { gap: var(--ifinmail-space-2); }
.ifinmail-gap-4 { gap: var(--ifinmail-space-4); }
.ifinmail-gap-6 { gap: var(--ifinmail-space-6); }

/* --- Spacing --- */
.ifinmail-p-4 { padding: var(--ifinmail-space-4); }
.ifinmail-p-6 { padding: var(--ifinmail-space-6); }
.ifinmail-px-4 { padding-left: var(--ifinmail-space-4); padding-right: var(--ifinmail-space-4); }
.ifinmail-py-2 { padding-top: var(--ifinmail-space-2); padding-bottom: var(--ifinmail-space-2); }
.ifinmail-py-4 { padding-top: var(--ifinmail-space-4); padding-bottom: var(--ifinmail-space-4); }
.ifinmail-mb-4 { margin-bottom: var(--ifinmail-space-4); }

/* --- Text --- */
.ifinmail-text-sm { font-size: var(--ifinmail-font-size-sm); }
.ifinmail-text-xs { font-size: var(--ifinmail-font-size-xs); }
.ifinmail-text-muted { color: var(--ifinmail-text-muted); }
.ifinmail-text-secondary { color: var(--ifinmail-text-secondary); }
.ifinmail-font-bold { font-weight: 600; }
.ifinmail-truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* --- Visibility --- */
.ifinmail-sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; }
.ifinmail-hidden { display: none; }
```

### Checkpoint Questions
1. Why does ifinmail use CSS custom properties (`--ifinmail-*`) instead of a preprocessor like Sass?
2. What problem does the `.ifinmail-*` prefix solve?
3. How many CSS utility classes should you create? What is the rule for adding a new one?
4. Why use server-rendered HTML instead of a JavaScript SPA?

### Connection to ifinmail
Proposal Section 9.1 mandates: no React, no heavy SPA, prefixed CSS, server-rendered pages where possible. This CSS system is the production foundation. Every UI component in the webmail and admin dashboard uses these tokens and class names.

---

## Day 2 (Tuesday): The Webmail Inbox — HTML + CSS Layout

### Learning Objectives
- Build a three-panel email layout (sidebar, message list, message detail)
- Structure the inbox with semantic HTML
- Make the layout responsive without a framework
- Implement CSS-only interactive states (hover, focus, active, selected)

### Theory / Reading
- **Three-panel layout**: sidebar (mailboxes) | message list (thread list) | message detail (reading pane)
- **Grid vs Flexbox**: use CSS Grid for page-level layout, Flexbox for component-level
- **Responsive**: collapse to single column on mobile using media queries
- **No JavaScript needed** for layout, only for dynamic data loading

### Practical Exercise
```html
<!-- ~/ifinmail-web/templates/mail/inbox.html -->
{% extends "base.html" %}
{% block title %}Inbox — ifinmail{% endblock %}

{% block content %}
<div class="ifinmail-mail-layout">
    <!-- Sidebar: Mailboxes -->
    <aside class="ifinmail-sidebar">
        <button class="ifinmail-btn ifinmail-btn-primary ifinmail-btn-full" type="button">
            + Compose
        </button>
        
        <nav class="ifinmail-mailbox-list" role="navigation" aria-label="Mailboxes">
            <a href="/mail/INBOX" class="ifinmail-mailbox-item ifinmail-mailbox-item--active" aria-current="page">
                <span class="ifinmail-mailbox-icon">&#9993;</span>
                <span class="ifinmail-mailbox-name">Inbox</span>
                <span class="ifinmail-mailbox-count ifinmail-badge">3</span>
            </a>
            <a href="/mail/Sent" class="ifinmail-mailbox-item">
                <span class="ifinmail-mailbox-name">Sent</span>
            </a>
            <a href="/mail/Drafts" class="ifinmail-mailbox-item">
                <span class="ifinmail-mailbox-name">Drafts</span>
                <span class="ifinmail-mailbox-count">2</span>
            </a>
            <a href="/mail/Archive" class="ifinmail-mailbox-item">
                <span class="ifinmail-mailbox-name">Archive</span>
            </a>
            <a href="/mail/Trash" class="ifinmail-mailbox-item">
                <span class="ifinmail-mailbox-name">Trash</span>
            </a>
            <a href="/mail/Junk" class="ifinmail-mailbox-item">
                <span class="ifinmail-mailbox-name">Junk</span>
                <span class="ifinmail-mailbox-count ifinmail-badge ifinmail-badge--danger">1</span>
            </a>
        </nav>
    </aside>
    
    <!-- Message List -->
    <section class="ifinmail-message-list" role="region" aria-label="Message list">
        <div class="ifinmail-message-list-header">
            <div class="ifinmail-flex ifinmail-items-center ifinmail-gap-2">
                <input type="checkbox" class="ifinmail-checkbox" id="select-all" aria-label="Select all messages">
                <button class="ifinmail-btn ifinmail-btn-ghost ifinmail-btn-sm" type="button">Refresh</button>
                <button class="ifinmail-btn ifinmail-btn-ghost ifinmail-btn-sm" type="button">Mark Read</button>
                <button class="ifinmail-btn ifinmail-btn-ghost ifinmail-btn-sm" type="button">Archive</button>
            </div>
            <div class="ifinmail-search">
                <input type="search" class="ifinmail-input" placeholder="Search mail..." aria-label="Search messages">
            </div>
        </div>
        
        <div class="ifinmail-message-cards" role="list">
            {% for msg in messages %}
            <div class="ifinmail-message-card {% if not msg.read %}ifinmail-message-card--unread{% endif %}"
                 role="listitem"
                 tabindex="0"
                 aria-label="{{ msg.subject }} — from {{ msg.sender }}">
                <input type="checkbox" class="ifinmail-checkbox" aria-label="Select message">
                <span class="ifinmail-message-sender ifinmail-truncate">{{ msg.sender }}</span>
                <span class="ifinmail-message-subject ifinmail-truncate">{{ msg.subject }}</span>
                <span class="ifinmail-message-snippet ifinmail-truncate ifinmail-text-muted">{{ msg.snippet }}</span>
                <span class="ifinmail-message-date ifinmail-text-xs ifinmail-text-muted">{{ msg.date }}</span>
            </div>
            {% endfor %}
        </div>
    </section>
    
    <!-- Message Detail (Reading Pane) -->
    <section class="ifinmail-message-detail" role="region" aria-label="Message detail">
        <div class="ifinmail-message-detail-empty">
            <p class="ifinmail-text-muted">Select a message to read</p>
        </div>
    </section>
</div>
{% endblock %}
```

```css
/* ~/ifinmail-web/static/css/ifinmail-layout.css */
/* Three-panel mail layout (proposal Section 4.1 architecture applied to UI). */
.ifinmail-mail-layout {
    display: grid;
    grid-template-columns: 240px 1fr 1fr;
    grid-template-rows: 1fr;
    height: calc(100vh - 56px - 40px);  /* header + footer */
    overflow: hidden;
}

.ifinmail-sidebar {
    border-right: 1px solid var(--ifinmail-border);
    padding: var(--ifinmail-space-4);
    overflow-y: auto;
    background: var(--ifinmail-bg-secondary);
}

.ifinmail-message-list {
    border-right: 1px solid var(--ifinmail-border);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
}

.ifinmail-message-detail {
    overflow-y: auto;
    padding: var(--ifinmail-space-6);
}

/* Responsive: single column on narrow screens */
@media (max-width: 768px) {
    .ifinmail-mail-layout {
        grid-template-columns: 1fr;
    }
    .ifinmail-sidebar,
    .ifinmail-message-list {
        display: none;
    }
    .ifinmail-sidebar.ifinmail-sidebar--open,
    .ifinmail-message-list.ifinmail-message-list--open {
        display: block;
    }
}
```

```css
/* ~/ifinmail-web/static/css/ifinmail-components.css */
/* Reusable UI components — all prefixed with .ifinmail-* */

/* --- Buttons --- */
.ifinmail-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem 1rem;
    border: 1px solid var(--ifinmail-border);
    border-radius: var(--ifinmail-radius-md);
    background: var(--ifinmail-bg);
    color: var(--ifinmail-text);
    font-size: var(--ifinmail-font-size-sm);
    font-weight: 500;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    user-select: none;
}

.ifinmail-btn:hover {
    background: var(--ifinmail-bg-tertiary);
    border-color: var(--ifinmail-border-hover);
}

.ifinmail-btn-primary {
    background: var(--ifinmail-primary);
    color: white;
    border-color: var(--ifinmail-primary);
}
.ifinmail-btn-primary:hover {
    background: var(--ifinmail-primary-hover);
}

.ifinmail-btn-ghost {
    background: transparent;
    border-color: transparent;
}
.ifinmail-btn-ghost:hover {
    background: var(--ifinmail-bg-tertiary);
}

.ifinmail-btn-sm { padding: 0.25rem 0.5rem; font-size: var(--ifinmail-font-size-xs); }
.ifinmail-btn-full { width: 100%; }

/* --- Inputs --- */
.ifinmail-input {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--ifinmail-border);
    border-radius: var(--ifinmail-radius-sm);
    font-size: var(--ifinmail-font-size-sm);
    font-family: inherit;
    color: var(--ifinmail-text);
    background: var(--ifinmail-bg);
    width: 100%;
}

.ifinmail-input:focus {
    outline: none;
    border-color: var(--ifinmail-primary);
    box-shadow: 0 0 0 3px var(--ifinmail-primary-light);
}

.ifinmail-checkbox {
    width: 16px;
    height: 16px;
    accent-color: var(--ifinmail-primary);
    flex-shrink: 0;
}

/* --- Message Cards --- */
.ifinmail-message-card {
    display: grid;
    grid-template-columns: 24px 1fr 100px;
    grid-template-rows: auto auto;
    gap: 0 var(--ifinmail-space-3);
    padding: var(--ifinmail-space-3) var(--ifinmail-space-4);
    border-bottom: 1px solid var(--ifinmail-border);
    cursor: pointer;
    transition: background 0.1s;
}

.ifinmail-message-card:hover {
    background: var(--ifinmail-bg-secondary);
}

.ifinmail-message-card--unread {
    background: var(--ifinmail-primary-light);
}

.ifinmail-message-card .ifinmail-checkbox {
    grid-row: 1 / -1;
    align-self: center;
}

.ifinmail-message-sender {
    font-weight: 600;
    grid-column: 2;
}

.ifinmail-message-subject {
    grid-column: 2;
}

.ifinmail-message-snippet {
    grid-column: 2;
}

.ifinmail-message-date {
    grid-row: 1;
    grid-column: 3;
    justify-self: end;
}

/* --- Badge --- */
.ifinmail-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    border-radius: 10px;
    background: var(--ifinmail-bg-tertiary);
    font-size: var(--ifinmail-font-size-xs);
    font-weight: 600;
}

.ifinmail-badge--danger {
    background: var(--ifinmail-danger-light);
    color: var(--ifinmail-danger);
}
```

### Checkpoint Questions
1. Why use CSS Grid for the three-panel layout instead of Flexbox?
2. How does the CSS-only responsive approach handle mobile?
3. What does `aria-current="page"` communicate to assistive technology?
4. Why nest the message card grid within the main layout grid?

### Connection to ifinmail
This is the webmail client that proposal Section 9 describes. No React. No Vue. No npm build step. Just HTML, CSS custom properties, and the `.ifinmail-*` prefixing convention. The three-panel layout matches the architecture diagram in Section 4.1.

---

## Day 3 (Wednesday): Vanilla JavaScript — Dynamic Inbox

### Learning Objectives
- Write vanilla JavaScript modules (ES modules)
- Fetch messages from the ifinmail API and render them
- Implement infinite scroll for the message list
- Handle optimistic UI updates (mark read, archive)
- Use the Service Worker API for offline caching (where safe)

### Theory / Reading
- **ES modules**: `import`/`export` in the browser; no bundler needed
- **Fetch API**: native HTTP client; replaces jQuery.ajax and axios
- **Optimistic UI**: update the DOM immediately, then confirm with the server
- **Service Worker**: intercept network requests for offline caching; proposal Section 8.4 mentions "offline read-only cache where safe"

### Practical Exercise
```javascript
// ~/ifinmail-web/static/js/ifinmail-api.js
/**
 * API client for ifinmail — zero dependencies.
 * Matches the API contract from Week 8.
 */
const API_BASE = '/v1';

class IfinmailAPI {
    constructor(token = null) {
        this.token = token;
    }
    
    async request(method, path, body = null) {
        const headers = { 'Accept': 'application/json' };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        if (body) {
            headers['Content-Type'] = 'application/json';
        }
        
        const response = await fetch(`${API_BASE}${path}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : null,
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new IfinmailError(error.code, error.message, response.status);
        }
        
        return response.json();
    }
    
    get(path) { return this.request('GET', path); }
    post(path, body) { return this.request('POST', path, body); }
    put(path, body) { return this.request('PUT', path, body); }
    delete(path) { return this.request('DELETE', path); }
    
    // Mail API
    async getMessages(mailbox = 'INBOX', page = 1, limit = 50) {
        return this.get(`/mail/messages?mailbox=${mailbox}&page=${page}&limit=${limit}`);
    }
    
    async getMessage(id) {
        return this.get(`/mail/messages/${id}`);
    }
    
    async sendMessage(data) {
        return this.post('/mail/messages', data);
    }
    
    // Admin API
    async getDNSHealth(domainId) {
        return this.get(`/admin/domains/${domainId}/dns-health`);
    }
}

class IfinmailError extends Error {
    constructor(code, message, status) {
        super(message);
        this.code = code;
        this.status = status;
    }
}

export { IfinmailAPI, IfinmailError };
```

```javascript
// ~/ifinmail-web/static/js/mail-inbox.js
/**
 * Inbox controller — renders message list, handles interactions.
 * Vanilla JS, no framework. Progressive enhancement.
 */
import { IfinmailAPI } from './ifinmail-api.js';

class InboxController {
    constructor(container, api) {
        this.container = container;
        this.api = api;
        this.page = 1;
        this.loading = false;
        this.hasMore = true;
        
        this.init();
    }
    
    init() {
        this.messageList = this.container.querySelector('.ifinmail-message-cards');
        this.loadMoreTrigger = this.container.querySelector('.ifinmail-load-more');
        
        // Infinite scroll
        this.container.addEventListener('scroll', () => this.handleScroll());
        
        // Load first page
        this.loadMessages();
    }
    
    async loadMessages() {
        if (this.loading || !this.hasMore) return;
        
        this.loading = true;
        this.showLoading(true);
        
        try {
            const data = await this.api.getMessages('INBOX', this.page);
            this.renderMessages(data.messages);
            this.hasMore = data.has_more;
            this.page++;
        } catch (error) {
            this.showError('Failed to load messages. Please try again.');
        } finally {
            this.loading = false;
            this.showLoading(false);
        }
    }
    
    renderMessages(messages) {
        const fragment = document.createDocumentFragment();
        
        for (const msg of messages) {
            const card = this.createMessageCard(msg);
            fragment.appendChild(card);
        }
        
        this.messageList.appendChild(fragment);
    }
    
    createMessageCard(msg) {
        const card = document.createElement('div');
        card.className = `ifinmail-message-card ${msg.flags.includes('\\Seen') ? '' : 'ifinmail-message-card--unread'}`;
        card.setAttribute('role', 'listitem');
        card.setAttribute('tabindex', '0');
        card.dataset.messageId = msg.id;
        
        card.innerHTML = `
            <input type="checkbox" class="ifinmail-checkbox" aria-label="Select message">
            <span class="ifinmail-message-sender ifinmail-truncate">${this.escapeHtml(msg.sender)}</span>
            <span class="ifinmail-message-subject ifinmail-truncate">${this.escapeHtml(msg.subject)}</span>
            <span class="ifinmail-message-snippet ifinmail-truncate ifinmail-text-muted">${this.escapeHtml(msg.snippet)}</span>
            <span class="ifinmail-message-date ifinmail-text-xs ifinmail-text-muted">${this.formatDate(msg.received_at)}</span>
        `;
        
        // Click to read
        card.addEventListener('click', (e) => {
            if (e.target.type === 'checkbox') return;
            this.openMessage(msg.id, card);
        });
        
        return card;
    }
    
    openMessage(messageId, card) {
        // Remove unread styling (optimistic update)
        card.classList.remove('ifinmail-message-card--unread');
        
        // Navigate or open in reading pane
        window.location.hash = `#message/${messageId}`;
        this.loadMessageDetail(messageId);
    }
    
    async loadMessageDetail(messageId) {
        const detailPane = document.querySelector('.ifinmail-message-detail');
        detailPane.classList.add('ifinmail-message-detail--loading');
        
        try {
            const msg = await this.api.getMessage(messageId);
            detailPane.innerHTML = this.renderMessageDetail(msg);
        } catch (error) {
            detailPane.innerHTML = '<p class="ifinmail-error">Failed to load message.</p>';
        } finally {
            detailPane.classList.remove('ifinmail-message-detail--loading');
        }
    }
    
    renderMessageDetail(msg) {
        return `
            <div class="ifinmail-message-full">
                <h2 class="ifinmail-message-full-subject">${this.escapeHtml(msg.subject)}</h2>
                <div class="ifinmail-message-full-meta">
                    <span class="ifinmail-font-bold">${this.escapeHtml(msg.sender)}</span>
                    <span class="ifinmail-text-muted">to ${this.escapeHtml(msg.to.join(', '))}</span>
                    <span class="ifinmail-text-muted">${this.formatDate(msg.received_at)}</span>
                </div>
                <div class="ifinmail-message-full-body">${this.escapeHtml(msg.body_text)}</div>
            </div>
        `;
    }
    
    handleScroll() {
        const { scrollTop, scrollHeight, clientHeight } = this.container;
        if (scrollHeight - scrollTop - clientHeight < 200) {
            this.loadMessages();
        }
    }
    
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    formatDate(isoString) {
        const date = new Date(isoString);
        // If today, show time; otherwise show date
        const today = new Date();
        if (date.toDateString() === today.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    
    showLoading(visible) {
        const existing = this.container.querySelector('.ifinmail-loading');
        if (visible && !existing) {
            const loader = document.createElement('div');
            loader.className = 'ifinmail-loading';
            loader.textContent = 'Loading...';
            this.messageList.appendChild(loader);
        } else if (!visible && existing) {
            existing.remove();
        }
    }
    
    showError(message) {
        const error = document.createElement('div');
        error.className = 'ifinmail-error';
        error.textContent = message;
        this.messageList.appendChild(error);
    }
}

// Initialize when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.ifinmail-message-list');
    if (!container) return;  // Not on the mail page
    
    const api = new IfinmailAPI();
    new InboxController(container, api);
});

export { InboxController };
```

### Checkpoint Questions
1. Why use ES modules (`import`/`export`) instead of a bundler like webpack?
2. What is optimistic UI updating and what is its risk?
3. How does the `escapeHtml` function prevent XSS?
4. Why does the Service Worker only cache "read-only" data?

### Connection to ifinmail
This JavaScript is the full interactivity layer — no framework, no build step, no npm. The `IfinmailAPI` class is the same contract every official client uses. The `escapeHtml` function and CSP headers (Week 8) are the frontend security baseline.

---

## Day 4 (Thursday): Admin Dashboard — Deliverability & Domain Management

### Learning Objectives
- Build the admin dashboard with deliverability metrics
- Render charts and status indicators with vanilla JS
- Implement DNS health checking UI
- Build domain and user management forms
- Connect admin pages to the Admin API from Week 8

### Theory / Reading
- **Admin dashboard**: proposal Section 6.5 deliverability dashboard + Section 7.2 Admin API
- **Status indicators**: PASS (green), WARN (yellow), FAIL (red) — the DNS health standard
- **Forms without JS**: server-side form handling with progressive enhancement via `fetch`

### Practical Exercise
```html
<!-- ~/ifinmail-web/templates/admin/dashboard.html -->
{% extends "base.html" %}
{% block title %}Admin Dashboard — ifinmail{% endblock %}

{% block content %}
<div class="ifinmail-admin-layout">
    <nav class="ifinmail-admin-nav">
        <a href="/admin" class="ifinmail-admin-nav-item ifinmail-admin-nav-item--active">Overview</a>
        <a href="/admin/domains" class="ifinmail-admin-nav-item">Domains</a>
        <a href="/admin/users" class="ifinmail-admin-nav-item">Users</a>
        <a href="/admin/mailboxes" class="ifinmail-admin-nav-item">Mailboxes</a>
        <a href="/admin/deliverability" class="ifinmail-admin-nav-item">Deliverability</a>
        <a href="/admin/audit-logs" class="ifinmail-admin-nav-item">Audit Logs</a>
    </nav>
    
    <section class="ifinmail-admin-content">
        <h1 class="ifinmail-admin-title">Platform Overview</h1>
        
        <!-- Stats Cards -->
        <div class="ifinmail-stats-grid">
            {% for stat in stats %}
            <div class="ifinmail-stat-card">
                <span class="ifinmail-stat-value">{{ stat.value }}</span>
                <span class="ifinmail-stat-label ifinmail-text-secondary">{{ stat.label }}</span>
            </div>
            {% endfor %}
        </div>
        
        <!-- DNS Health Summary -->
        <div class="ifinmail-admin-section">
            <h2 class="ifinmail-admin-section-title">DNS Health by Domain</h2>
            <div class="ifinmail-domain-health-list">
                {% for domain in domains %}
                <div class="ifinmail-domain-health">
                    <span class="ifinmail-domain-health-name ifinmail-font-bold">{{ domain.name }}</span>
                    
                    <div class="ifinmail-domain-health-checks">
                        {% for check in domain.checks %}
                        <span class="ifinmail-health-indicator ifinmail-health-indicator--{{ check.status | lower }}"
                              title="{{ check.check }}: {{ check.message }}">
                            {{ check.check | upper }}
                        </span>
                        {% endfor %}
                    </div>
                    
                    {% if domain.warnings %}
                    <div class="ifinmail-domain-health-warnings">
                        {% for warning in domain.warnings %}
                        <p class="ifinmail-admin-warning">{{ warning }}</p>
                        {% endfor %}
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- Deliverability Metrics -->
        <div class="ifinmail-admin-section">
            <h2 class="ifinmail-admin-section-title">Deliverability (Last 24h)</h2>
            <div class="ifinmail-metrics-grid">
                <div class="ifinmail-metric">
                    <span class="ifinmail-metric-label">Delivery Rate</span>
                    <span class="ifinmail-metric-value ifinmail-text-success">99.7%</span>
                </div>
                <div class="ifinmail-metric">
                    <span class="ifinmail-metric-label">Bounce Rate</span>
                    <span class="ifinmail-metric-value">0.2%</span>
                </div>
                <div class="ifinmail-metric">
                    <span class="ifinmail-metric-label">Spam Complaint Rate</span>
                    <span class="ifinmail-metric-value">0.01%</span>
                </div>
                <div class="ifinmail-metric">
                    <span class="ifinmail-metric-label">Avg Delivery Time</span>
                    <span class="ifinmail-metric-value">1.2s</span>
                </div>
            </div>
        </div>
        
        <!-- Recent Alerts -->
        <div class="ifinmail-admin-section">
            <h2 class="ifinmail-admin-section-title">Recent Security Events</h2>
            <div class="ifinmail-event-list">
                {% for event in events %}
                <div class="ifinmail-event-item ifinmail-event-item--{{ event.severity }}">
                    <span class="ifinmail-event-time ifinmail-text-xs ifinmail-text-muted">{{ event.time }}</span>
                    <span class="ifinmail-event-description">{{ event.description }}</span>
                </div>
                {% endfor %}
            </div>
        </div>
    </section>
</div>
{% endblock %}
```

```css
/* Admin dashboard styles (add to ifinmail-components.css) */
.ifinmail-admin-layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    min-height: calc(100vh - 100px);
}

.ifinmail-admin-nav {
    background: var(--ifinmail-bg-secondary);
    border-right: 1px solid var(--ifinmail-border);
    padding: var(--ifinmail-space-4);
    display: flex;
    flex-direction: column;
    gap: var(--ifinmail-space-1);
}

.ifinmail-admin-nav-item {
    padding: var(--ifinmail-space-2) var(--ifinmail-space-3);
    border-radius: var(--ifinmail-radius-sm);
    color: var(--ifinmail-text-secondary);
    font-size: var(--ifinmail-font-size-sm);
}

.ifinmail-admin-nav-item:hover {
    background: var(--ifinmail-bg-tertiary);
    color: var(--ifinmail-text);
}

.ifinmail-admin-nav-item--active {
    background: var(--ifinmail-primary-light);
    color: var(--ifinmail-primary);
    font-weight: 600;
}

.ifinmail-stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--ifinmail-space-4);
    margin-bottom: var(--ifinmail-space-6);
}

.ifinmail-stat-card {
    background: var(--ifinmail-bg-secondary);
    border: 1px solid var(--ifinmail-border);
    border-radius: var(--ifinmail-radius-md);
    padding: var(--ifinmail-space-4);
    text-align: center;
}

.ifinmail-stat-value {
    display: block;
    font-size: var(--ifinmail-font-size-2xl);
    font-weight: 700;
    color: var(--ifinmail-primary);
}

.ifinmail-health-indicator {
    display: inline-block;
    padding: 2px 8px;
    border-radius: var(--ifinmail-radius-sm);
    font-size: var(--ifinmail-font-size-xs);
    font-weight: 600;
}

.ifinmail-health-indicator--pass {
    background: var(--ifinmail-success-light);
    color: var(--ifinmail-success);
}

.ifinmail-health-indicator--warn {
    background: var(--ifinmail-warning-light);
    color: var(--ifinmail-warning);
}

.ifinmail-health-indicator--fail {
    background: var(--ifinmail-danger-light);
    color: var(--ifinmail-danger);
}

.ifinmail-admin-warning {
    color: var(--ifinmail-warning);
    font-size: var(--ifinmail-font-size-sm);
    margin-top: var(--ifinmail-space-1);
}
```

### Checkpoint Questions
1. Why is the DNS health indicator color-coded? What does each color communicate?
2. How should the admin dashboard handle real-time updates vs page refreshes?
3. What audit events should be visible to admins?
4. How does the admin page degrade without JavaScript?

### Connection to ifinmail
This is the deliverability dashboard from proposal Section 6.5. Domain admins check DNS health here. The warnings (yellow indicators) flag problems before they cause delivery failures. Security events from Section 11's "Security event" entity appear in the recent alerts.

---

## Day 5 (Friday): Web Components for Reusable UI & Service Worker

### Learning Objectives
- Build a Web Component (custom element) for the message card
- Understand Shadow DOM encapsulation within `.ifinmail-*` scope
- Implement a Service Worker for offline caching of messages
- Add push notification support via the WebSocket/Event API

### Theory / Reading
- **Web Components**: custom elements + shadow DOM + HTML templates; native browser API, no framework needed
- **Shadow DOM**: encapsulated styles that do not leak out; fits within `.ifinmail-*` scoping
- **Service Worker**: background script that intercepts fetch, caches responses, enables offline access
- **Proposal Section 8.4**: "Service Worker for offline read-only cache where safe"

### Practical Exercise
```javascript
// ~/ifinmail-web/static/js/components/ifinmail-message-card.js
/**
 * <ifinmail-message-card> — reusable message card component.
 * Uses Shadow DOM for encapsulation. No framework.
 */
class IfinmailMessageCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }
    
    static get observedAttributes() {
        return ['sender', 'subject', 'snippet', 'date', 'unread', 'message-id'];
    }
    
    connectedCallback() {
        this.render();
    }
    
    attributeChangedCallback() {
        this.render();
    }
    
    render() {
        const sender = this.getAttribute('sender') || '';
        const subject = this.getAttribute('subject') || '';
        const snippet = this.getAttribute('snippet') || '';
        const date = this.getAttribute('date') || '';
        const unread = this.hasAttribute('unread');
        
        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: grid;
                    grid-template-columns: 24px 1fr 100px;
                    gap: 0 var(--ifinmail-space-3, 0.75rem);
                    padding: var(--ifinmail-space-3, 0.75rem) var(--ifinmail-space-4, 1rem);
                    border-bottom: 1px solid var(--ifinmail-border, #e2e8f0);
                    cursor: pointer;
                    background: var(--unread-bg, transparent);
                }
                :host(:hover) {
                    background: var(--ifinmail-bg-secondary, #f8fafc);
                }
                :host([unread]) {
                    --unread-bg: var(--ifinmail-primary-light, #dbeafe);
                }
                .sender {
                    font-weight: 600;
                    grid-column: 2;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .subject {
                    grid-column: 2;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .snippet {
                    grid-column: 2;
                    color: var(--ifinmail-text-muted, #94a3b8);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    font-size: 0.875rem;
                }
                .date {
                    grid-row: 1;
                    grid-column: 3;
                    justify-self: end;
                    font-size: 0.75rem;
                    color: var(--ifinmail-text-muted, #94a3b8);
                }
            </style>
            <input type="checkbox" class="checkbox" aria-label="Select message">
            <span class="sender">${this.escape(sender)}</span>
            <span class="subject">${this.escape(subject)}</span>
            <span class="snippet">${this.escape(snippet)}</span>
            <span class="date">${this.escape(date)}</span>
        `;
        
        this.shadowRoot.querySelector('.checkbox').addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        this.addEventListener('click', () => {
            this.dispatchEvent(new CustomEvent('message-open', {
                bubbles: true,
                detail: { messageId: this.getAttribute('message-id') }
            }));
        });
    }
    
    escape(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

customElements.define('ifinmail-message-card', IfinmailMessageCard);
```

```javascript
// ~/ifinmail-web/static/js/service-worker.js
/**
 * Service Worker for ifinmail — offline read-only cache.
 * Caches: CSS, JS, images, and previously-read messages.
 * Does NOT cache: POST requests, auth tokens, sensitive data.
 */
const CACHE_NAME = 'ifinmail-v0.1.0';
const STATIC_ASSETS = [
    '/',
    '/static/css/ifinmail-variables.css',
    '/static/css/ifinmail-reset.css',
    '/static/css/ifinmail-utilities.css',
    '/static/css/ifinmail-layout.css',
    '/static/css/ifinmail-components.css',
    '/static/js/ifinmail-api.js',
    '/static/js/mail-inbox.js',
    '/offline',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    
    // Never cache POST/PUT/DELETE or API writes
    if (event.request.method !== 'GET') return;
    
    // Never cache auth endpoints
    if (url.pathname.startsWith('/v1/auth/')) return;
    
    // Strategy: network first, fall back to cache, fall back to offline page
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Cache successful GET responses for static assets and mail reads
                if (response.ok && (url.pathname.startsWith('/static/') || 
                    url.pathname.startsWith('/v1/mail/'))) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    return cached || caches.match('/offline');
                });
            })
    );
});
```

### Checkpoint Questions
1. When should ifinmail use Web Components vs plain HTML templates?
2. Why does the Service Worker only cache "read-only" data? What is the risk of caching writes?
3. How does Shadow DOM encapsulation interact with the `.ifinmail-*` CSS prefixing system?
4. Why use `self.skipWaiting()` and `self.clients.claim()` in the Service Worker?

### Connection to ifinmail
Web Components are the "where useful" exception in proposal Section 9.1. The Service Worker enables the "offline read-only cache" from Section 8.4. Both are native browser APIs — no framework, no build step, no npm dependency.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Build the Complete Webmail Client

Create a fully functional webmail client in a single HTML file (no server needed for the demo):

1. Three-panel layout with sidebar, message list, and reading pane
2. Mock API responses (5 sample messages) using `Promise`-based delays
3. Message list with unread indicators and click-to-read
4. Reading pane that shows full message when selected
5. Compose button that opens a compose panel
6. All CSS prefixed with `.ifinmail-*`
7. No frameworks, no build tools, no CDN dependencies

**Stretch goal**: Add a working search bar that filters messages by subject.

### Week 10 Self-Assessment

Before moving to Week 11, confirm you can:
- [ ] Build server-rendered HTML pages with Jinja2 templates
- [ ] Implement the `.ifinmail-*` CSS prefixing system with custom properties
- [ ] Write vanilla JavaScript modules that call the ifinmail API
- [ ] Implement infinite scroll and optimistic UI updates without a framework
- [ ] Build a deliverability dashboard with DNS health indicators
- [ ] Create a Web Component with Shadow DOM
- [ ] Write a Service Worker for offline caching

---

## Week 10 Resource Index

| Resource | Location |
|---|---|
| CSS design tokens | `code/static/css/ifinmail-variables.css` |
| CSS utility layer | `code/static/css/ifinmail-utilities.css` |
| Component styles | `code/static/css/ifinmail-components.css` |
| API client (JS) | `code/static/js/ifinmail-api.js` |
| Inbox controller | `code/static/js/mail-inbox.js` |
| Web component | `code/static/js/components/ifinmail-message-card.js` |
| Service Worker | `code/static/js/service-worker.js` |
| HTML templates | `code/templates/` |

---

*Week 10 of 12 — Minimal Frontend for ifinmail Platform Engineering*
