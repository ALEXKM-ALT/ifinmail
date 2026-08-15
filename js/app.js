/* IFINMAIL Client - Application logic */
(function() {
    'use strict';

    const STORAGE_KEYS = {
        emails: 'ifinmail.emails',
        settings: 'ifinmail.settings',
        notifications: 'ifinmail.notifications',
        recentSearches: 'ifinmail.recentSearches',
        sidebarCollapsed: 'ifinmail.sidebarCollapsed'
    };

    const AVATAR_COLORS = ['#2563eb', '#16a34a', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d'];

    const state = {
        emails: loadData(STORE_KEYS_EMAILS(), IFINMAIL_DATA.emails),
        contacts: IFINMAIL_DATA.contacts,
        notifications: loadData(STORAGE_KEYS.notifications, IFINMAIL_DATA.notifications),
        settings: loadData(STORAGE_KEYS.settings, IFINMAIL_DATA.settings),
        recentSearches: loadData(STORAGE_KEYS.recentSearches, []),
        user: loadData('ifinmail.session', IFINMAIL_DATA.user),
        currentView: 'inbox',
        currentLabel: null,
        selected: new Set(),
        searchQuery: '',
        searchFilters: null,
        viewingId: null,
        composeDraftId: null,
        composeAttachments: []
    };

    const emailBodyEl = document.getElementById('compose-body');

    const elements = {
        mainContent: document.getElementById('main-content'),
        detailContent: document.getElementById('detail-content'),
        detailPane: document.getElementById('detail-pane'),
        topbarRefresh: document.getElementById('topbar-refresh'),
        topbarFilter: document.getElementById('topbar-filter'),
        sidebar: document.getElementById('sidebar'),
        sidebarToggle: document.getElementById('sidebar-toggle'),
        composeBtn: document.getElementById('compose-btn'),
        composeModal: document.getElementById('compose-modal'),
        composeClose: document.getElementById('compose-close'),
        composeDiscard: document.getElementById('compose-discard'),
        composeSend: document.getElementById('compose-send'),
        composeTo: document.getElementById('compose-to'),
        composeCc: document.getElementById('compose-cc'),
        composeBcc: document.getElementById('compose-bcc'),
        composeSubject: document.getElementById('compose-subject'),
        searchInput: document.getElementById('global-search'),
        searchClear: document.getElementById('search-clear'),
        searchFiltersBtn: document.getElementById('search-filters-btn'),
        searchFiltersModal: document.getElementById('search-filters-modal'),
        filtersClose: document.getElementById('filters-close'),
        filtersReset: document.getElementById('filters-reset'),
        filtersApply: document.getElementById('filters-apply'),
        notificationsBtn: document.getElementById('notifications-btn'),
        notificationsDropdown: document.getElementById('notifications-dropdown'),
        notificationsList: document.getElementById('notifications-list'),
        notificationBadge: document.getElementById('notification-badge'),
        markAllRead: document.getElementById('mark-all-read'),
        helpBtn: document.getElementById('help-btn'),
        helpDropdown: document.getElementById('help-dropdown'),
        settingsBtn: document.getElementById('settings-btn'),
        settingsDropdown: document.getElementById('settings-dropdown'),
        userMenu: document.getElementById('user-menu'),
        avatarBtn: document.getElementById('avatar-btn'),
        userDropdown: document.getElementById('user-dropdown'),
        signOutBtn: document.getElementById('sign-out-btn'),
        inboxBadge: document.getElementById('inbox-badge'),
        draftsBadge: document.getElementById('drafts-badge')
    };

    /* ───────────── Storage helpers ───────────── */

    function STORE_KEYS_EMAILS() { return STORAGE_KEYS.emails; }

    function loadData(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            if (raw === null) return fallback;
            return JSON.parse(raw);
        } catch (e) {
            return fallback;
        }
    }

    function saveData(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {}
    }

    function persistEmails() { saveData(STORAGE_KEYS.emails, state.emails); }
    function persistSettings() { saveData(STORAGE_KEYS.settings, state.settings); }
    function persistNotifications() { saveData(STORAGE_KEYS.notifications, state.notifications); }

    /* ───────────── Utilities ───────────── */

    function escapeHtml(str) {
        return String(str === undefined || str === null ? '' : str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function initials(name) {
        if (!name) return '?';
        return name.trim().split(/\s+/).map(function(w) { return w[0]; }).slice(0, 2).join('').toUpperCase();
    }

    function avatarColor(name) {
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
        }
        return AVATAR_COLORS[hash % AVATAR_COLORS.length];
    }

    function formatTime(iso) {
        const date = new Date(iso);
        const now = new Date();
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        }
        const yesterday = new Date(now);
        yesterday.setDate(now.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
        if (date.getFullYear() === now.getFullYear()) {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        }
        return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function formatFullDate(iso) {
        return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) +
            ', ' + new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }

    function toast(message) {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        const el = document.createElement('div');
        el.className = 'toast';
        el.textContent = message;
        container.appendChild(el);
        setTimeout(function() {
            el.style.transition = 'opacity 0.3s';
            el.style.opacity = '0';
            setTimeout(function() {
                el.remove();
                if (container.children.length === 0) container.remove();
            }, 300);
        }, 2600);
    }

    function setLoading(button, isLoading) {
        const text = button.querySelector('.btn-text');
        const loader = button.querySelector('.btn-loader');
        button.disabled = isLoading;
        if (!text || !loader) return;
        text.style.display = isLoading ? 'none' : 'inline';
        loader.style.display = isLoading ? 'inline-flex' : 'none';
    }

    /* ───────────── Dropdowns ───────────── */

    function toggleDropdown(dropdown) {
        const wasOpen = !dropdown.classList.contains('hidden');
        closeAllDropdowns();
        if (!wasOpen) dropdown.classList.remove('hidden');
    }

    function closeAllDropdowns() {
        [elements.notificationsDropdown, elements.helpDropdown, elements.settingsDropdown, elements.userDropdown]
            .forEach(function(d) { if (d) d.classList.add('hidden'); });
        hideSuggestions();
    }

    document.addEventListener('click', function(e) {
        if (elements.notificationsBtn && !elements.notificationsBtn.contains(e.target) &&
            !elements.notificationsDropdown.contains(e.target)) {
            elements.notificationsDropdown.classList.add('hidden');
        }
        if (elements.helpBtn && !elements.helpBtn.contains(e.target) &&
            !elements.helpDropdown.contains(e.target)) {
            elements.helpDropdown.classList.add('hidden');
        }
        if (elements.settingsBtn && !elements.settingsBtn.contains(e.target) &&
            !elements.settingsDropdown.contains(e.target)) {
            elements.settingsDropdown.classList.add('hidden');
        }
        if (elements.userMenu && !elements.userMenu.contains(e.target)) {
            elements.userDropdown.classList.add('hidden');
        }
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllDropdowns();
            if (!elements.composeModal.classList.contains('hidden')) closeCompose();
            if (!elements.searchFiltersModal.classList.contains('hidden')) {
                elements.searchFiltersModal.classList.add('hidden');
            }
        }
    });

    /* ───────────── Sidebar ───────────── */

    function isMobile() { return window.innerWidth <= 700; }

    function initSidebar() {
        const collapsed = localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === '1';
        if (collapsed && !isMobile()) elements.sidebar.classList.add('collapsed');

        elements.sidebarToggle.addEventListener('click', function() {
            if (isMobile()) {
                elements.sidebar.classList.toggle('open');
            } else {
                elements.sidebar.classList.toggle('collapsed');
                localStorage.setItem(STORAGE_KEYS.sidebarCollapsed, elements.sidebar.classList.contains('collapsed') ? '1' : '0');
            }
        });

        const contactsLink = document.createElement('a');
        contactsLink.href = '#';
        contactsLink.className = 'nav-item';
        contactsLink.dataset.view = 'contacts';
        contactsLink.innerHTML =
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
                '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>' +
                '<circle cx="9" cy="7" r="4"></circle>' +
                '<path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>' +
                '<path d="M16 3.13a4 4 0 0 1 0 7.75"></path>' +
            '</svg>' +
            '<span class="nav-label">Contacts</span>';
        document.querySelector('.sidebar-nav').appendChild(contactsLink);
    }

    /* ───────────── Views ───────────── */

    const VIEW_TITLES = {
        all: 'All Mail',
        unread: 'Unread',
        inbox: 'Inbox',
        starred: 'Starred',
        flagged: 'Flagged',
        snoozed: 'Snoozed',
        sent: 'Sent',
        drafts: 'Drafts',
        archive: 'Archive',
        spam: 'Spam',
        trash: 'Trash',
        contacts: 'Contacts',
        account: 'Account',
        security: 'Security',
        'settings-account': 'Account Settings',
        'settings-mail': 'Mail Settings',
        'settings-notifications': 'Notification Settings',
        'settings-appearance': 'Appearance',
        'settings-security': 'Security Settings'
    };

    function renderView(view, label) {
        const viewChanged = view !== state.currentView || (label || null) !== (state.currentLabel || null);
        state.currentView = view;
        state.currentLabel = label || null;
        if (viewChanged) state.selected.clear();
        updateNavActive();
        updateBadges();

        const main = elements.mainContent;
        if (view === 'contacts') {
            renderContacts(isMobile() ? main : elements.detailContent);
        } else if (view === 'search') {
            renderSearchResults(main);
        } else if (view === 'account' || view === 'security') {
            renderAccountSecurity(isMobile() ? main : elements.detailContent, view);
        } else if (view === 'settings' || view.indexOf('settings-') === 0) {
            renderSettings(isMobile() ? main : elements.detailContent, view);
        } else {
            renderMailList(main, view, label);
        }
    }

    function showDetailEmpty() {
        if (isMobile()) return;
        elements.detailContent.innerHTML =
            '<div class="detail-empty">' +
            '<img src="assets/icon.jpg" class="detail-empty-logo" alt="ifinmail">' +
            '<h3>Select a message to read</h3>' +
            '<p>Choose an email from the list to view it here.</p>' +
            '</div>';
    }

    function updateNavActive() {
        document.querySelectorAll('.nav-item[data-view]').forEach(function(item) {
            item.classList.toggle('active', item.dataset.view === state.currentView);
        });
        document.querySelectorAll('.label-item').forEach(function(item) {
            item.classList.toggle('active', state.currentView === 'label' && item.dataset.label === state.currentLabel);
        });
        document.querySelectorAll('.tab-btn[data-view]').forEach(function(item) {
            item.classList.toggle('active', item.dataset.view === state.currentView);
        });
    }

    function updateBadges() {
        const inboxCount = state.emails.filter(function(e) { return e.folder === 'inbox' && !e.read; }).length;
        const draftsCount = state.emails.filter(function(e) { return e.folder === 'drafts'; }).length;
        if (elements.inboxBadge) {
            elements.inboxBadge.textContent = inboxCount;
            elements.inboxBadge.classList.toggle('hidden', inboxCount === 0);
        }
        if (elements.draftsBadge) {
            elements.draftsBadge.textContent = draftsCount;
            elements.draftsBadge.classList.toggle('hidden', draftsCount === 0);
        }
    }

    function getEmailsForView(view, label) {
        let list = state.emails.slice();

        if (view === 'label') {
            list = list.filter(function(e) { return e.labels.indexOf(label) !== -1; });
        } else if (view === 'starred' || view === 'flagged') {
            list = list.filter(function(e) { return e.starred && e.folder !== 'trash' && e.folder !== 'drafts'; });
        } else if (view === 'all') {
            list = list.filter(function(e) { return e.folder !== 'trash' && e.folder !== 'drafts' && e.folder !== 'spam'; });
        } else if (view === 'unread') {
            list = list.filter(function(e) { return !e.read && e.folder !== 'trash' && e.folder !== 'drafts' && e.folder !== 'spam'; });
        } else if (view === 'search') {
            return list;
        } else {
            list = list.filter(function(e) { return e.folder === view; });
        }

        list.sort(function(a, b) { return new Date(b.date) - new Date(a.date); });
        return list;
    }

    /* ───────────── Mail List ───────────── */

    function renderMailList(container, view, label) {
        const emails = getEmailsForView(view, label);
        const title = view === 'label' ? label.charAt(0).toUpperCase() + label.slice(1) : VIEW_TITLES[view];
        const isDrafts = view === 'drafts';
        const isTrash = view === 'trash';
        const isSent = view === 'sent';

        let html = '';
        html += '<div class="view">';

        html += '<div class="email-toolbar' + (state.selected.size === 0 ? ' hidden' : '') + '" id="email-toolbar">';
        html += '<label class="toolbar-select">';
        html += '<input type="checkbox" id="select-all" aria-label="Select all">';
        html += '</label>';
        if (!isDrafts && !isTrash && !isSent) {
            html += '<button class="toolbar-action" data-action="archive">' + ICONS.archive + '<span>Archive</span></button>';
        }
        html += '<button class="toolbar-action" data-action="delete">' + ICONS.trash + '<span>Delete</span></button>';
        html += '<button class="toolbar-action" data-action="toggle-read">' + ICONS.envelope + '<span>Mark unread</span></button>';
        if (!isDrafts && !isTrash) {
            html += '<button class="toolbar-action" data-action="snooze">' + ICONS.snooze + '<span>Snooze</span></button>';
        }
        html += '<button class="toolbar-action" data-action="star">' + ICONS.star + '<span>Star</span></button>';
        html += '<span class="toolbar-count" id="toolbar-count">' + (state.selected.size > 0 ? state.selected.size + ' selected' : '') + '</span>';
        html += '</div>';

        html += '<div class="list-header">';
        html += '<div>';
        html += '<h2>' + escapeHtml(title) + '</h2>';
        html += '<div class="list-header-sub">' + emails.length + (emails.length === 1 ? ' message' : ' messages') + '</div>';
        html += '</div>';
        html += '<div class="list-header-actions">';
        html += '<button class="icon-btn" id="refresh-btn" title="Refresh">' + ICONS.refresh + '</button>';
        html += '<button class="icon-btn" title="More options">' + ICONS.more + '</button>';
        html += '</div>';
        html += '</div>';

        if (emails.length === 0) {
            html += '<div class="empty-state">';
            html += '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
                '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>' +
                '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>' +
            '</svg>';
            html += '<h3>No messages here</h3>';
            html += '<p>' + (isDrafts ? 'Drafts you save will appear here.' : 'When you receive new mail, it will show up here.') + '</p>';
            html += '</div>';
        } else {
            html += '<div class="email-list">';
            emails.forEach(function(email) {
                html += renderEmailRow(email);
            });
            html += '</div>';
        }

        html += '</div>';
        container.innerHTML = html;

        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', function() {
                toast('Mailbox refreshed');
                renderView(state.currentView, state.currentLabel);
            });
        }

        if (emails.length > 0) {
        container.querySelectorAll('.email-row').forEach(function(row) {
            row.addEventListener('click', function(e) {
                if (e.target.closest('.row-checkbox') || e.target.closest('.row-star')) return;
                const email = getEmail(row.dataset.id);
                if (email && email.folder === 'drafts') {
                    openDraft(email);
                } else {
                    openViewer(row.dataset.id);
                }
            });
        });
        container.querySelectorAll('.row-star').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleStar(btn.dataset.id);
            });
        });
        container.querySelectorAll('.row-checkbox input').forEach(function(cb) {
            cb.addEventListener('change', function() {
                handleSelect(cb.dataset.id, cb.checked);
            });
        });

        const selectAll = document.getElementById('select-all');
            if (selectAll) {
                selectAll.addEventListener('change', function() {
                    const checked = selectAll.checked;
                    emails.forEach(function(email) {
                        if (checked) state.selected.add(email.id);
                        else state.selected.delete(email.id);
                    });
                    updateToolbarState(emails);
                });
            }
        }

        const toolbar = document.getElementById('email-toolbar');
        if (toolbar) {
            toolbar.querySelectorAll('.toolbar-action').forEach(function(btn) {
                btn.addEventListener('click', function() {
                    const action = btn.dataset.action;
                    const ids = Array.from(state.selected);
                    if (ids.length === 0) return;
                    if (action === 'archive') moveEmails(ids, 'archive', 'Archived');
                    else if (action === 'delete') {
                        const inTrash = ids.some(function(id) { return getEmail(id).folder === 'trash'; });
                        if (inTrash) {
                            ids.forEach(function(id) {
                                state.emails = state.emails.filter(function(e) { return e.id !== id; });
                            });
                            persistEmails();
                            toast('Deleted forever');
                            renderView(state.currentView, state.currentLabel);
                        } else {
                            moveEmails(ids, 'trash', 'Moved to trash');
                        }
                    }
                    else if (action === 'toggle-read') {
                        ids.forEach(function(id) {
                            const email = getEmail(id);
                            if (email) email.read = !email.read;
                        });
                        persistEmails();
                        toast('Marked');
                        renderView(state.currentView, state.currentLabel);
                    }
                    else if (action === 'snooze') {
                        moveEmails(ids, 'snoozed', 'Snoozed');
                    }
                    else if (action === 'star') {
                        ids.forEach(function(id) {
                            const email = getEmail(id);
                            if (email) email.starred = !email.starred;
                        });
                        persistEmails();
                        toast('Updated');
                        renderView(state.currentView, state.currentLabel);
                    }
                });
            });
        }

        if (!isMobile()) {
            if (emails.length === 0 || view === 'drafts') {
                showDetailEmpty();
            } else {
                const stillHere = state.viewingId && emails.some(function(e) { return e.id === state.viewingId; });
                if (!stillHere) openViewer(emails[0].id, true);
            }
        }
    }

    function renderEmailRow(email) {
        const sender = email.folder === 'sent' || email.folder === 'drafts'
            ? (email.to.length ? email.to[0].name : '')
            : email.from.name;
        const senderEmail = email.folder === 'sent' || email.folder === 'drafts'
            ? (email.to.length ? email.to[0].email : '')
            : email.from.email;
        const subject = email.subject || '(no subject)';
        const hasAttachment = email.attachments && email.attachments.length > 0;

        let labelsHtml = '';
        (email.labels || []).forEach(function(label) {
            labelsHtml += '<span class="label-chip ' + escapeHtml(label) + '">' + escapeHtml(label) + '</span>';
        });

        return '<div class="email-row' + (email.read ? '' : ' unread') +
            (state.selected.has(email.id) ? ' selected' : '') +
            (state.viewingId === email.id && !isMobile() ? ' active' : '') + '" data-id="' + email.id + '">' +
            '<div class="row-checkbox"><input type="checkbox" data-id="' + email.id + '"' +
            (state.selected.has(email.id) ? ' checked' : '') + '></div>' +
            '<button class="row-star' + (email.starred ? ' starred' : '') + '" data-id="' + email.id + '" aria-label="Star">' +
            ICONS.star + '</button>' +
            '<div class="row-avatar" style="--avatar-color:' + avatarColor(sender) + '">' + escapeHtml(initials(sender)) + '</div>' +
            '<div class="row-main">' +
                '<span class="row-sender">' + escapeHtml(sender) + '</span>' +
                '<span class="row-subject">' + escapeHtml(subject) + '</span>' +
                (email.preview ? '<span class="row-snippet"> - ' + escapeHtml(email.preview) + '</span>' : '') +
                labelsHtml +
            '</div>' +
            '<div class="row-meta">' +
                (hasAttachment ? '<span class="row-attachment">' + ICONS.attach + '</span>' : '') +
                '<span class="row-time">' + formatTime(email.date) + '</span>' +
            '</div>' +
            '</div>';
    }

    function handleSelect(id, checked) {
        if (checked) state.selected.add(id);
        else state.selected.delete(id);
        const row = document.querySelector('.email-row[data-id="' + id + '"]');
        if (row) row.classList.toggle('selected', checked);
        updateToolbarState(getEmailsForView(state.currentView, state.currentLabel));
    }

    function updateToolbarState(emails) {
        const toolbar = document.getElementById('email-toolbar');
        if (!toolbar) return;
        const count = state.selected.size;
        toolbar.classList.toggle('hidden', count === 0);
        const countEl = document.getElementById('toolbar-count');
        if (countEl) countEl.textContent = count + ' selected';
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.checked = emails.length > 0 && emails.every(function(e) { return state.selected.has(e.id); });
        }
    }

    function getEmail(id) {
        return state.emails.find(function(e) { return e.id === id; });
    }

    function toggleStar(id) {
        const email = getEmail(id);
        if (!email) return;
        email.starred = !email.starred;
        persistEmails();
        const btn = document.querySelector('.row-star[data-id="' + id + '"]');
        if (btn) btn.classList.toggle('starred', email.starred);
    }

    function moveEmails(ids, folder, message) {
        ids.forEach(function(id) {
            const email = getEmail(id);
            if (email) {
                email.folder = folder;
                email.read = true;
            }
        });
        persistEmails();
        toast(message);
        renderView(state.currentView, state.currentLabel);
    }

    /* ───────────── Email Viewer ───────────── */

    function openViewer(id, preview) {
        const email = getEmail(id);
        if (!email) return;
        if (!preview && !email.read) {
            email.read = true;
            persistEmails();
            updateBadges();
        }
        state.viewingId = id;
        if (!preview) state.selected.clear();

        const isMobileView = isMobile();
        const target = isMobileView ? elements.mainContent : elements.detailContent;
        const isDraft = email.folder === 'drafts';
        const isTrash = email.folder === 'trash';
        const sender = email.from;
        const senderName = email.folder === 'sent' ? (email.to.length ? email.to[0].name : 'You') : sender.name;
        const senderEmail = email.folder === 'sent' ? (email.to.length ? email.to[0].email : '') : sender.email;
        const recipients = email.to.map(function(r) { return r.name + ' <' + r.email + '>'; }).join(', ');

        let html = '';
        html += '<div class="view">';

        html += '<div class="viewer-header">';
        if (isMobileView) {
            html += '<button class="icon-btn" id="viewer-back" aria-label="Back">' + ICONS.back + '</button>';
        }
        html += '<div class="viewer-title">' + escapeHtml(email.subject || '(no subject)') + '</div>';
        html += '<div class="viewer-header-actions">';
        if (!isDraft && !isTrash) {
            html += '<button class="icon-btn" id="viewer-archive" title="Archive">' + ICONS.archive + '</button>';
        }
        if (!isDraft) {
            html += '<button class="icon-btn" id="viewer-delete" title="' + (isTrash ? 'Delete forever' : 'Delete') + '">' + ICONS.trash + '</button>';
        }
        html += '<button class="icon-btn" title="More options">' + ICONS.more + '</button>';
        html += '</div>';
        html += '</div>';

        html += '<div class="viewer">';
        html += '<div class="viewer-sender">';
        html += '<div class="avatar large" style="--avatar-color:' + avatarColor(senderName) + '">' + escapeHtml(initials(senderName)) + '</div>';
        html += '<div class="sender-details">';
        html += '<div class="sender-name">' + escapeHtml(senderName) +
            ' <span class="sender-email">&lt;' + escapeHtml(senderEmail) + '&gt;</span></div>';
        html += '<div class="recipients">To: ' + escapeHtml(recipients) + '</div>';
        if (email.cc && email.cc.length) {
            html += '<div class="recipients">Cc: ' + escapeHtml(email.cc.map(function(c) { return c.email; }).join(', ')) + '</div>';
        }
        html += '</div>';
        html += '<div class="viewer-date">' + formatFullDate(email.date) + '</div>';
        html += '</div>';

        html += '<div class="viewer-divider"></div>';
        html += '<div class="viewer-body">' + escapeHtml(email.body) + '</div>';

        if (email.attachments && email.attachments.length > 0) {
            html += '<div class="attachments">';
            html += '<div class="attachments-title">Attachments</div>';
            email.attachments.forEach(function(att) {
                html += '<div class="attachment-item">';
                html += '<div class="attachment-icon">' + ICONS.attach + '</div>';
                html += '<div class="attachment-info">';
                html += '<div class="attachment-name">' + escapeHtml(att.name) + '</div>';
                html += '<div class="attachment-size">' + escapeHtml(att.size) + '</div>';
                html += '</div>';
                html += '<div class="attachment-actions">';
                html += '<button class="attachment-btn" data-att="' + escapeHtml(att.name) + '" data-act="preview">Preview</button>';
                html += '<button class="attachment-btn" data-att="' + escapeHtml(att.name) + '" data-act="download">Download</button>';
                html += '</div>';
                html += '</div>';
            });
            html += '</div>';
        }

        if (!isDraft) {
            html += '<div class="viewer-actions-bottom">';
            if (!isTrash) {
                html += '<button class="viewer-action-btn" id="viewer-reply">' + ICONS.reply + ' Reply</button>';
                html += '<button class="viewer-action-btn" id="viewer-forward">' + ICONS.forward + ' Forward</button>';
            } else {
                html += '<button class="viewer-action-btn" id="viewer-restore">' + ICONS.restore + ' Move to inbox</button>';
            }
            html += '</div>';
        }

        html += '</div></div>';

        target.innerHTML = html;

        if (!isMobileView) {
            document.querySelectorAll('.email-row').forEach(function(row) {
                row.classList.toggle('active', row.dataset.id === id);
            });
        }

        const backBtn = document.getElementById('viewer-back');
        if (backBtn) {
            backBtn.addEventListener('click', function() {
                renderView(state.currentView, state.currentLabel);
            });
        }
        const archiveBtn = document.getElementById('viewer-archive');
        if (archiveBtn) {
            archiveBtn.addEventListener('click', function() {
                email.folder = 'archive';
                email.read = true;
                persistEmails();
                toast('Archived');
                renderView(state.currentView, state.currentLabel);
            });
        }
        const deleteBtn = document.getElementById('viewer-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function() {
                if (isTrash) {
                    state.emails = state.emails.filter(function(e) { return e.id !== email.id; });
                    persistEmails();
                    toast('Deleted forever');
                } else {
                    email.folder = 'trash';
                    email.read = true;
                    persistEmails();
                    toast('Moved to trash');
                }
                renderView(state.currentView, state.currentLabel);
            });
        }
        const replyBtn = document.getElementById('viewer-reply');
        if (replyBtn) {
            replyBtn.addEventListener('click', function() {
                openCompose({
                    to: email.from.email,
                    subject: (email.subject.indexOf('Re:') === 0 ? '' : 'Re: ') + email.subject,
                    body: '\n\nOn ' + formatFullDate(email.date) + ', ' + senderName + ' <' + senderEmail + '> wrote:\n> ' + email.body.replace(/\n/g, '\n> ')
                });
            });
        }
        const forwardBtn = document.getElementById('viewer-forward');
        if (forwardBtn) {
            forwardBtn.addEventListener('click', function() {
                openCompose({
                    subject: (email.subject.indexOf('Fwd:') === 0 ? '' : 'Fwd: ') + email.subject,
                    body: '\n\n---------- Forwarded message ----------\nFrom: ' + senderName + ' <' + senderEmail + '>\nDate: ' + formatFullDate(email.date) + '\nSubject: ' + email.subject + '\n\n' + email.body
                });
            });
        }
        const restoreBtn = document.getElementById('viewer-restore');
        if (restoreBtn) {
            restoreBtn.addEventListener('click', function() {
                email.folder = 'inbox';
                email.read = true;
                persistEmails();
                toast('Restored to inbox');
                renderView(state.currentView, state.currentLabel);
            });
        }
        target.querySelectorAll('.attachment-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                toast(btn.dataset.act === 'preview' ? 'Previewing ' + btn.dataset.att : 'Downloading ' + btn.dataset.att);
            });
        });
    }

    /* ───────────── Compose ───────────── */

    function openCompose(prefill) {
        elements.composeTo.value = prefill && prefill.to ? prefill.to : '';
        elements.composeCc.value = '';
        elements.composeBcc.value = '';
        elements.composeSubject.value = prefill && prefill.subject ? prefill.subject : '';
        emailBodyEl.value = prefill && prefill.body ? prefill.body : '';
        state.composeDraftId = null;
        state.composeAttachments = [];
        renderComposeAttachments();
        elements.composeModal.classList.remove('hidden');
        elements.composeTo.focus();
        elements.composeModal.querySelector('.compose-header h3').textContent = 'New Message';
    }

    function openDraft(email) {
        elements.composeTo.value = email.to.map(function(r) { return r.email; }).join(', ');
        elements.composeCc.value = email.cc.map(function(r) { return r.email; }).join(', ');
        elements.composeBcc.value = email.bcc.map(function(r) { return r.email; }).join(', ');
        elements.composeSubject.value = email.subject;
        emailBodyEl.value = email.body;
        state.composeDraftId = email.id;
        state.composeAttachments = (email.attachments || []).slice();
        renderComposeAttachments();
        elements.composeModal.classList.remove('hidden');
        emailBodyEl.focus();
        elements.composeModal.querySelector('.compose-header h3').textContent = 'Edit Draft';
    }

    function closeCompose() {
        const hasContent = elements.composeTo.value.trim() || elements.composeSubject.value.trim() || emailBodyEl.value.trim();
        if (hasContent) {
            saveDraft();
        }
        elements.composeModal.classList.add('hidden');
        state.composeDraftId = null;
        state.composeAttachments = [];
    }

    function saveDraft() {
        let draft;
        if (state.composeDraftId) {
            draft = getEmail(state.composeDraftId);
        }
        if (!draft) {
            draft = {
                id: 'd' + Date.now(),
                folder: 'drafts',
                from: { name: state.user.name, email: state.user.email },
                to: [],
                cc: [],
                bcc: [],
                subject: '',
                preview: '',
                body: '',
                date: new Date().toISOString(),
                read: true,
                starred: false,
                important: false,
                labels: [],
                attachments: [],
                draft: true
            };
            state.emails.push(draft);
        }
        draft.to = elements.composeTo.value.split(',').map(function(s) { return s.trim(); })
            .filter(Boolean).map(function(email) { return { name: email.split('@')[0], email: email }; });
        draft.cc = elements.composeCc.value.split(',').map(function(s) { return s.trim(); })
            .filter(Boolean).map(function(email) { return { name: email, email: email }; });
        draft.bcc = elements.composeBcc.value.split(',').map(function(s) { return s.trim(); })
            .filter(Boolean).map(function(email) { return { name: email, email: email }; });
        draft.subject = elements.composeSubject.value.trim();
        draft.body = emailBodyEl.value;
        draft.date = new Date().toISOString();
        draft.attachments = state.composeAttachments;
        draft.preview = draft.body.split('\n')[0].slice(0, 80);
        persistEmails();
        toast('Draft saved');
    }

    function renderComposeAttachments() {
        let container = elements.composeModal.querySelector('.compose-attachments');
        if (!container) {
            container = document.createElement('div');
            container.className = 'compose-attachments';
            elements.composeModal.querySelector('.compose-body').appendChild(container);
        }
        container.innerHTML = '';
        state.composeAttachments.forEach(function(att) {
            const chip = document.createElement('div');
            chip.className = 'compose-attachment';
            chip.innerHTML = ICONS.attachSmall + '<span>' + escapeHtml(att.name) + ' (' + escapeHtml(att.size) + ')</span>';
            const remove = document.createElement('button');
            remove.innerHTML = '×';
            remove.setAttribute('aria-label', 'Remove attachment');
            remove.addEventListener('click', function() {
                state.composeAttachments = state.composeAttachments.filter(function(a) { return a !== att; });
                renderComposeAttachments();
            });
            chip.appendChild(remove);
            container.appendChild(chip);
        });
    }

    function initCompose() {
        elements.composeBtn.addEventListener('click', function() {
            openCompose();
        });
        elements.composeClose.addEventListener('click', closeCompose);
        elements.composeDiscard.addEventListener('click', function() {
            if (state.composeDraftId) {
                state.emails = state.emails.filter(function(e) { return e.id !== state.composeDraftId; });
                persistEmails();
            }
            elements.composeTo.value = '';
            elements.composeCc.value = '';
            elements.composeBcc.value = '';
            elements.composeSubject.value = '';
            emailBodyEl.value = '';
            state.composeDraftId = null;
            state.composeAttachments = [];
            renderComposeAttachments();
            elements.composeModal.classList.add('hidden');
            if (state.currentView === 'drafts') renderView('drafts');
            toast('Draft discarded');
        });
        elements.composeModal.addEventListener('click', function(e) {
            if (e.target === elements.composeModal) closeCompose();
        });

        const attachBtn = elements.composeModal.querySelector('.tool-btn[title="Attach file"]');
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.style.display = 'none';
        fileInput.addEventListener('change', function() {
            Array.from(fileInput.files).forEach(function(file) {
                const size = file.size / 1024 / 1024;
                state.composeAttachments.push({
                    name: file.name,
                    size: size >= 1 ? size.toFixed(1) + ' MB' : Math.max(1, Math.round(size * 1024)) + ' KB'
                });
            });
            renderComposeAttachments();
            fileInput.value = '';
        });
        elements.composeModal.appendChild(fileInput);
        if (attachBtn) {
            attachBtn.addEventListener('click', function() { fileInput.click(); });
        }

        elements.composeSend.addEventListener('click', function() {
            const toRaw = elements.composeTo.value.trim();
            if (!toRaw) {
                toast('Please enter a recipient');
                elements.composeTo.focus();
                return;
            }
            const subject = elements.composeSubject.value.trim() || '(no subject)';
            const body = emailBodyEl.value;

            setLoading(elements.composeSend, true);
            setTimeout(function() {
                setLoading(elements.composeSend, false);

                const to = toRaw.split(',').map(function(s) { return s.trim(); })
                    .filter(Boolean)
                    .map(function(addr) { return { name: addr.split('@')[0], email: addr }; });

                if (state.composeDraftId) {
                    state.emails = state.emails.filter(function(e) { return e.id !== state.composeDraftId; });
                }

                const sent = {
                    id: 's' + Date.now(),
                    folder: 'sent',
                    from: { name: state.user.name, email: state.user.email },
                    to: to,
                    cc: [],
                    bcc: [],
                    subject: subject,
                    preview: body.split('\n')[0].slice(0, 80),
                    body: body,
                    date: new Date().toISOString(),
                    read: true,
                    starred: false,
                    important: false,
                    labels: [],
                    attachments: state.composeAttachments
                };
                state.emails.push(sent);
                persistEmails();
                toast('Message sent');
                elements.composeModal.classList.add('hidden');
                state.composeDraftId = null;
                state.composeAttachments = [];
                renderView(state.currentView, state.currentLabel);
            }, 900);
        });
    }

    /* ───────────── Search ───────────── */

    const ICON_SEARCH = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>';

    function hideSuggestions() {
        const el = document.getElementById('search-suggestions');
        if (el) el.remove();
    }

    function showSuggestions() {
        hideSuggestions();
        const query = elements.searchInput.value.trim().toLowerCase();

        let recent = state.recentSearches.filter(function(s) {
            return s.toLowerCase().indexOf(query) !== -1;
        }).slice(0, 5);

        let html = '<div id="search-suggestions" class="search-suggestions">';
        if (recent.length > 0) {
            html += '<div class="suggestion-section">Recent searches</div>';
            recent.forEach(function(term) {
                html += '<button class="suggestion-item" data-suggestion="' + escapeHtml(term) + '">' +
                    ICON_SEARCH + '<span>' + escapeHtml(term) + '</span></button>';
            });
        }
        html += '<div class="suggestion-section">Suggestions</div>';
        html += '<button class="suggestion-item" data-suggestion="from:">' + ICON_SEARCH + '<span>From: <span class="suggestion-tag">sender email</span></span></button>';
        html += '<button class="suggestion-item" data-suggestion="to:">' + ICON_SEARCH + '<span>To: <span class="suggestion-tag">recipient email</span></span></button>';
        html += '<button class="suggestion-item" data-suggestion="subject:">' + ICON_SEARCH + '<span>Subject: <span class="suggestion-tag">keywords</span></span></button>';
        html += '<button class="suggestion-item" data-suggestion="has:attachment">' + ICON_SEARCH + '<span>Has attachment</span></button>';
        html += '</div>';

        const container = document.createElement('div');
        container.innerHTML = html;
        const wrapper = elements.searchInput.closest('.search-container');
        wrapper.appendChild(container.firstChild);

        document.getElementById('search-suggestions').querySelectorAll('.suggestion-item').forEach(function(item) {
            item.addEventListener('click', function() {
                const val = item.dataset.suggestion;
                if (val.slice(-1) === ':' || val === 'has:attachment') {
                    const prefix = elements.searchInput.value;
                    elements.searchInput.value = prefix.trim() + (prefix.trim() ? ' ' : '') + val + (val.slice(-1) === ':' ? '' : ' ');
                } else {
                    elements.searchInput.value = val;
                }
                elements.searchInput.focus();
                updateSearchClear();
                showSuggestions();
            });
        });
    }

    function updateSearchClear() {
        elements.searchClear.classList.toggle('hidden', !elements.searchInput.value);
    }

    function doSearch() {
        const query = elements.searchInput.value.trim();
        if (!query && !state.searchFilters) return;
        state.searchQuery = query;

        if (state.recentSearches.indexOf(query) === -1) {
            state.recentSearches.unshift(query);
            state.recentSearches = state.recentSearches.slice(0, 10);
            saveData(STORAGE_KEYS.recentSearches, state.recentSearches);
        }

        const operators = {
            from: null,
            to: null,
            subject: null,
            hasAttachment: false,
            label: null
        };
        let plainQuery = query;

        query.split(/\s+/).forEach(function(token) {
            const match = token.match(/^(from|to|subject|label):(.+)$/);
            if (match) {
                operators[match[1]] = match[2].toLowerCase();
                plainQuery = plainQuery.replace(token, '');
            } else if (token === 'has:attachment') {
                operators.hasAttachment = true;
                plainQuery = plainQuery.replace(token, '');
            }
        });
        plainQuery = plainQuery.trim().toLowerCase();

        const filters = state.searchFilters;
        state.searchResults = {
            query: elements.searchInput.value.trim(),
            operators: operators,
            plainQuery: plainQuery,
            filters: filters
        };

        closeAllDropdowns();
        hideSuggestions();
        renderView('search');
    }

    function renderSearchResults(container) {
        const results = state.searchResults;
        let emails = state.emails.slice();

        const op = results.operators;
        const plain = results.plainQuery;

        emails = emails.filter(function(email) {
            let match = true;

            if (op.from && email.from.email.toLowerCase().indexOf(op.from) === -1 &&
                email.from.name.toLowerCase().indexOf(op.from) === -1) {
                match = false;
            }
            if (op.to) {
                const toMatch = email.to.concat(email.cc, email.bcc).some(function(r) {
                    return r.email.toLowerCase().indexOf(op.to) !== -1;
                });
                if (!toMatch) match = false;
            }
            if (op.subject && email.subject.toLowerCase().indexOf(op.subject) === -1) {
                match = false;
            }
            if (op.label && (email.labels || []).indexOf(op.label) === -1) {
                match = false;
            }
            if (op.hasAttachment && !(email.attachments && email.attachments.length > 0)) {
                match = false;
            }
            if (plain) {
                const haystack = [
                    email.from.name, email.from.email,
                    email.subject, email.preview, email.body,
                    email.to.map(function(r) { return r.name + ' ' + r.email; }).join(' ')
                ].join(' ').toLowerCase();
                if (haystack.indexOf(plain) === -1) match = false;
            }

            if (match && results.filters) {
                const f = results.filters;
                if (f.from && email.from.email.toLowerCase().indexOf(f.from.toLowerCase()) === -1) match = false;
                if (f.to) {
                    const toMatch = email.to.concat(email.cc, email.bcc).some(function(r) {
                        return r.email.toLowerCase().indexOf(f.to.toLowerCase()) !== -1;
                    });
                    if (!toMatch) match = false;
                }
                if (f.subject && email.subject.toLowerCase().indexOf(f.subject.toLowerCase()) === -1) match = false;
                if (f.date && f.date !== 'any' && !dateInRange(email.date, f.date)) match = false;
                if (f.attachment && !(email.attachments && email.attachments.length > 0)) match = false;
                if (f.folder && f.folder !== 'all' && email.folder !== f.folder) match = false;
            }

            return match;
        });

        emails.sort(function(a, b) { return new Date(b.date) - new Date(a.date); });

        let html = '<div class="view">';

        html += '<div class="list-header">';
        html += '<div>';
        html += '<h2>Search results</h2>';
        html += '<div class="list-header-sub">' + emails.length + ' matches for "' + escapeHtml(results.query) + '"</div>';
        html += '</div>';
        html += '<div class="list-header-actions">';
        html += '<button class="icon-btn" id="search-clear-all" title="Clear search">' + ICONS.close + '</button>';
        html += '</div>';
        html += '</div>';

        if (emails.length === 0) {
            html += '<div class="empty-state">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
                '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path></svg>' +
                '<h3>No results found</h3>' +
                '<p>Try a different search term or use the filters.</p></div>';
        } else {
            html += '<div class="email-list">';
            emails.forEach(function(email) {
                html += renderEmailRow(email);
            });
            html += '</div>';
        }
        html += '</div>';

        container.innerHTML = html;

        const clearAll = document.getElementById('search-clear-all');
        if (clearAll) {
            clearAll.addEventListener('click', function() {
                elements.searchInput.value = '';
                updateSearchClear();
                renderView('inbox');
            });
        }

        container.querySelectorAll('.email-row').forEach(function(row) {
            row.addEventListener('click', function(e) {
                if (e.target.closest('.row-checkbox') || e.target.closest('.row-star')) return;
                const email = getEmail(row.dataset.id);
                if (email && email.folder === 'drafts') {
                    openDraft(email);
                } else {
                    openViewer(row.dataset.id);
                }
            });
        });
        container.querySelectorAll('.row-star').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleStar(btn.dataset.id);
            });
        });
        container.querySelectorAll('.row-checkbox input').forEach(function(cb) {
            cb.addEventListener('change', function() {
                handleSelect(cb.dataset.id, cb.checked);
            });
        });
    }

    function dateInRange(iso, range) {
        const date = new Date(iso);
        const now = new Date();
        if (range === 'today') return date.toDateString() === now.toDateString();
        if (range === 'week') {
            const weekAgo = new Date(now);
            weekAgo.setDate(now.getDate() - 7);
            return date >= weekAgo;
        }
        if (range === 'month') {
            return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
        }
        if (range === 'year') return date.getFullYear() === now.getFullYear();
        return true;
    }

    function initSearch() {
        elements.searchInput.addEventListener('input', function() {
            updateSearchClear();
            if (elements.searchInput.value) {
                showSuggestions();
            } else {
                hideSuggestions();
            }
        });
        elements.searchInput.addEventListener('focus', function() {
            if (elements.searchInput.value) showSuggestions();
        });
        elements.searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                doSearch();
            }
        });
        elements.searchClear.addEventListener('click', function() {
            elements.searchInput.value = '';
            updateSearchClear();
            hideSuggestions();
            if (state.currentView === 'search') renderView('inbox');
            elements.searchInput.focus();
        });
        elements.searchFiltersBtn.addEventListener('click', function() {
            elements.searchFiltersModal.classList.remove('hidden');
            loadFiltersIntoForm();
        });
        elements.filtersClose.addEventListener('click', function() {
            elements.searchFiltersModal.classList.add('hidden');
        });
        elements.searchFiltersModal.addEventListener('click', function(e) {
            if (e.target === elements.searchFiltersModal) {
                elements.searchFiltersModal.classList.add('hidden');
            }
        });
        elements.filtersReset.addEventListener('click', function() {
            state.searchFilters = null;
            document.querySelectorAll('#search-filters-modal input[type="text"], #search-filters-modal input[type="checkbox"], #search-filters-modal select')
                .forEach(function(el) {
                    if (el.type === 'checkbox') el.checked = false;
                    else el.value = '';
                });
        });
        elements.filtersApply.addEventListener('click', function() {
            state.searchFilters = {
                from: document.getElementById('filter-from').value.trim(),
                to: document.getElementById('filter-to').value.trim(),
                subject: document.getElementById('filter-subject').value.trim(),
                date: document.getElementById('filter-date').value,
                attachment: document.getElementById('filter-attachment').checked,
                folder: document.getElementById('filter-folder').value
            };
            elements.searchFiltersModal.classList.add('hidden');
            doSearch();
        });
    }

    function loadFiltersIntoForm() {
        const f = state.searchFilters;
        if (!f) return;
        document.getElementById('filter-from').value = f.from || '';
        document.getElementById('filter-to').value = f.to || '';
        document.getElementById('filter-subject').value = f.subject || '';
        document.getElementById('filter-date').value = f.date || 'any';
        document.getElementById('filter-attachment').checked = !!f.attachment;
        document.getElementById('filter-folder').value = f.folder || 'all';
    }

    /* ───────────── Notifications ───────────── */

    function renderNotifications() {
        const list = elements.notificationsList;
        const unread = state.notifications.filter(function(n) { return !n.read; }).length;
        elements.notificationBadge.textContent = unread;
        elements.notificationBadge.classList.toggle('hidden', unread === 0);

        if (state.notifications.length === 0) {
            list.innerHTML = '<div class="dropdown-empty">No notifications</div>';
            return;
        }

        list.innerHTML = '';
        state.notifications.forEach(function(n) {
            const item = document.createElement('button');
            item.className = 'notification-item' + (n.read ? '' : ' unread');
            item.dataset.id = n.id;
            item.innerHTML =
                '<div class="notification-icon">' + escapeHtml(n.icon) + '</div>' +
                '<div class="notification-content">' +
                    '<div class="notification-title">' + escapeHtml(n.title) + '</div>' +
                    '<div class="notification-message">' + escapeHtml(n.message) + '</div>' +
                    '<div class="notification-time">' + escapeHtml(n.time) + '</div>' +
                '</div>';
            item.addEventListener('click', function() {
                if (!n.read) {
                    n.read = true;
                    persistNotifications();
                    renderNotifications();
                }
                toast(n.title + ' - ' + n.message);
            });
            list.appendChild(item);
        });
    }

    function initNotifications() {
        elements.notificationsBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleDropdown(elements.notificationsDropdown);
        });
        elements.markAllRead.addEventListener('click', function() {
            state.notifications.forEach(function(n) { n.read = true; });
            persistNotifications();
            renderNotifications();
            toast('All notifications marked as read');
        });
    }

    /* ───────────── Contacts ───────────── */

    function renderContacts(container) {
        let html = '<div class="view"><div class="contacts-view">';
        html += '<div class="list-header" style="padding-left:0">';
        html += '<div><h2>Contacts</h2>';
        html += '<div class="list-header-sub">' + state.contacts.length + ' contacts</div></div>';
        html += '</div>';
        html += '<input type="text" class="contact-search" id="contact-search" placeholder="Search contacts...">';
        html += '<div id="contact-list">';
        state.contacts.forEach(function(contact) {
            html += renderContactItem(contact);
        });
        html += '</div>';
        html += '</div></div>';

        container.innerHTML = html;

        const search = document.getElementById('contact-search');
        search.addEventListener('input', function() {
            const q = search.value.trim().toLowerCase();
            const list = document.getElementById('contact-list');
            list.innerHTML = '';
            state.contacts.filter(function(c) {
                return c.name.toLowerCase().indexOf(q) !== -1 || c.email.toLowerCase().indexOf(q) !== -1;
            }).forEach(function(c) {
                list.innerHTML += renderContactItem(c);
            });
            if (list.children.length === 0) {
                list.innerHTML = '<div class="empty-state"><p>No contacts found</p></div>';
            }
        });

        const contactsView = container.querySelector('.contacts-view');
        contactsView.addEventListener('click', function(e) {
            const btn = e.target.closest('.contact-btn');
            if (!btn) return;
            const contact = state.contacts.find(function(c) { return c.id === btn.dataset.id; });
            if (!contact) return;
            if (btn.dataset.action === 'email') {
                openCompose({ to: contact.email });
            } else {
                toast('Viewing ' + contact.name);
            }
        });
    }

    function renderContactItem(contact) {
        return '<div class="contact-item">' +
            '<div class="avatar" style="--avatar-color:' + avatarColor(contact.name) + '">' + escapeHtml(initials(contact.name)) + '</div>' +
            '<div class="contact-info">' +
                '<div class="contact-name">' + escapeHtml(contact.name) + '</div>' +
                '<div class="contact-email">' + escapeHtml(contact.email) + '</div>' +
            '</div>' +
            '<div class="contact-actions">' +
                '<button class="contact-btn" data-id="' + contact.id + '" data-action="view">View</button>' +
                '<button class="contact-btn" data-id="' + contact.id + '" data-action="email">' + ICONS.sendSmall + ' Email</button>' +
            '</div>' +
            '</div>';
    }

    /* ───────────── Settings ───────────── */

    function renderSettings(container, view) {
        const settings = state.settings;

        if (view === 'settings-account') {
            container.innerHTML =
                '<div class="view"><div class="settings-view">' +
                '<div class="list-header" style="padding-left:0"><div><h2>Account</h2><div class="list-header-sub">Manage your personal information</div></div></div>' +
                '<div class="settings-section"><h3>Profile</h3>' +
                '<form class="settings-form" id="account-form">' +
                    '<div class="form-group"><label for="acc-name">Full name</label><input type="text" id="acc-name" value="' + escapeHtml(settings.account.name) + '"></div>' +
                    '<div class="form-group"><label for="acc-email">Email address</label><input type="email" id="acc-email" value="' + escapeHtml(settings.account.email) + '"></div>' +
                    '<div class="form-group"><label for="acc-phone">Phone number</label><input type="text" id="acc-phone" value="' + escapeHtml(settings.account.phone || '') + '"></div>' +
                    '<button type="submit" class="btn-primary" style="align-self:flex-start">Save changes</button>' +
                '</form></div>' +
                '<div class="settings-section"><h3>Storage</h3>' +
                    '<div class="settings-meta">' + IFINMAIL_DATA.storage.used + ' of ' + IFINMAIL_DATA.storage.total + ' used</div>' +
                    '<div class="storage-bar"><div class="storage-bar-fill" style="width:' + IFINMAIL_DATA.storage.percent + '%"></div></div>' +
                    '<div class="settings-meta">' + IFINMAIL_DATA.storage.percent + '% full</div>' +
                '</div></div></div>';
            bindSettingsForm('account-form', function(form) {
                settings.account = {
                    name: form.acc_name.value,
                    email: form.acc_email.value,
                    phone: form.acc_phone.value
                };
                persistSettings();
                toast('Account saved');
            });
        }

        else if (view === 'settings-mail') {
            container.innerHTML =
                '<div class="view"><div class="settings-view">' +
                '<div class="list-header" style="padding-left:0"><div><h2>Mail</h2><div class="list-header-sub">Signature, auto-reply and forwarding</div></div></div>' +
                '<div class="settings-section"><h3>Signature</h3>' +
                '<form class="settings-form" id="mail-form">' +
                    '<div class="form-group"><label for="mail-signature">Signature</label><textarea id="mail-signature">' + escapeHtml(settings.mail.signature) + '</textarea></div>' +
                    '<div class="setting-row">' +
                        '<div class="setting-info"><div class="setting-title">Auto-reply</div><div class="setting-desc">Send an automatic reply when you receive mail</div></div>' +
                        '<label class="switch"><input type="checkbox" id="mail-autoreply"' + (settings.mail.autoReply ? ' checked' : '') + '><span class="slider"></span></label>' +
                    '</div>' +
                    '<div class="form-group"><label for="mail-forwarding">Forwarding address</label><input type="email" id="mail-forwarding" placeholder="forward@example.com" value="' + escapeHtml(settings.mail.forwarding) + '"></div>' +
                    '<button type="submit" class="btn-primary" style="align-self:flex-start">Save changes</button>' +
                '</form></div></div></div>';
            bindSettingsForm('mail-form', function(form) {
                settings.mail = {
                    signature: form.mail_signature.value,
                    autoReply: form.mail_autoreply.checked,
                    forwarding: form.mail_forwarding.value
                };
                persistSettings();
                toast('Mail settings saved');
            });
        }

        else if (view === 'settings-notifications') {
            container.innerHTML =
                '<div class="view"><div class="settings-view">' +
                '<div class="list-header" style="padding-left:0"><div><h2>Notifications</h2><div class="list-header-sub">Choose what alerts you receive</div></div></div>' +
                '<div class="settings-section">' +
                '<div class="setting-row">' +
                    '<div class="setting-info"><div class="setting-title">New email alerts</div><div class="setting-desc">Get notified when new mail arrives</div></div>' +
                    '<label class="switch"><input type="checkbox" id="notif-email"' + (settings.notifications.emailAlerts ? ' checked' : '') + '><span class="slider"></span></label>' +
                '</div>' +
                '<div class="setting-row">' +
                    '<div class="setting-info"><div class="setting-title">Security alerts</div><div class="setting-desc">Notify me about suspicious activity</div></div>' +
                    '<label class="switch"><input type="checkbox" id="notif-security"' + (settings.notifications.securityAlerts ? ' checked' : '') + '><span class="slider"></span></label>' +
                '</div>' +
                '<div class="setting-row">' +
                    '<div class="setting-info"><div class="setting-title">Desktop notifications</div><div class="setting-desc">Show notifications on your desktop</div></div>' +
                    '<label class="switch"><input type="checkbox" id="notif-desktop"' + (settings.notifications.desktop ? ' checked' : '') + '><span class="slider"></span></label>' +
                '</div>' +
                '</div></div></div>';

            bindSettingsForm(null, function() {
                settings.notifications = {
                    emailAlerts: document.getElementById('notif-email').checked,
                    securityAlerts: document.getElementById('notif-security').checked,
                    desktop: document.getElementById('notif-desktop').checked
                };
                persistSettings();
                toast('Notification settings saved');
            });
        }

        else if (view === 'settings-appearance') {
            container.innerHTML =
                '<div class="view"><div class="settings-view">' +
                '<div class="list-header" style="padding-left:0"><div><h2>Appearance</h2><div class="list-header-sub">Customize how IFINMAIL looks</div></div></div>' +
                '<div class="settings-section"><h3>Theme</h3>' +
                '<div class="theme-options">' +
                    '<button class="theme-option" data-theme="light">Light</button>' +
                    '<button class="theme-option" data-theme="dark">Dark</button>' +
                    '<button class="theme-option" data-theme="system">System</button>' +
                '</div></div>' +
                '<div class="settings-section"><h3>Density</h3>' +
                '<div class="density-options">' +
                    '<button class="density-option" data-density="comfortable">Comfortable</button>' +
                    '<button class="density-option" data-density="compact">Compact</button>' +
                '</div></div></div></div>';

            container.querySelectorAll('.theme-option').forEach(function(btn) {
                btn.classList.toggle('active', btn.dataset.theme === settings.appearance.theme);
                btn.addEventListener('click', function() {
                    settings.appearance.theme = btn.dataset.theme;
                    persistSettings();
                    applyAppearance();
                    container.querySelectorAll('.theme-option').forEach(function(b) {
                        b.classList.toggle('active', b === btn);
                    });
                    toast('Theme updated');
                });
            });
            container.querySelectorAll('.density-option').forEach(function(btn) {
                btn.classList.toggle('active', btn.dataset.density === settings.appearance.density);
                btn.addEventListener('click', function() {
                    settings.appearance.density = btn.dataset.density;
                    persistSettings();
                    applyAppearance();
                    container.querySelectorAll('.density-option').forEach(function(b) {
                        b.classList.toggle('active', b === btn);
                    });
                    toast('Density updated');
                });
            });
        }

        else if (view === 'settings-security') {
            container.innerHTML =
                '<div class="view"><div class="settings-view">' +
                '<div class="list-header" style="padding-left:0"><div><h2>Security</h2><div class="list-header-sub">Password, 2FA and sessions</div></div></div>' +
                '<div class="settings-section"><h3>Password</h3>' +
                '<form class="settings-form" id="password-form">' +
                    '<div class="form-group"><label for="pwd-current">Current password</label><input type="password" id="pwd-current" placeholder="Enter current password"></div>' +
                    '<div class="form-group"><label for="pwd-new">New password</label><input type="password" id="pwd-new" placeholder="Enter new password"></div>' +
                    '<div class="form-group"><label for="pwd-confirm">Confirm new password</label><input type="password" id="pwd-confirm" placeholder="Confirm new password"></div>' +
                    '<button type="submit" class="btn-primary" style="align-self:flex-start">Update password</button>' +
                '</form></div>' +
                '<div class="settings-section"><h3>Two-factor authentication</h3>' +
                '<div class="setting-row">' +
                    '<div class="setting-info"><div class="setting-title">Two-factor authentication</div><div class="setting-desc">Require a verification code when signing in</div></div>' +
                    '<label class="switch"><input type="checkbox" id="pwd-2fa"' + (settings.security.twoFactor ? ' checked' : '') + '><span class="slider"></span></label>' +
                '</div></div>' +
                '<div class="settings-section"><h3>Active sessions</h3>' +
                    '<div class="session-item">' +
                        '<div class="session-icon">' + ICONS.monitor + '</div>' +
                        '<div class="session-info"><div class="session-device">Chrome on Linux</div><div class="session-meta">Nairobi, Kenya - Current session</div></div>' +
                        '<span class="session-active">Active now</span>' +
                    '</div>' +
                    '<div class="session-item">' +
                        '<div class="session-icon">' + ICONS.smartphone + '</div>' +
                        '<div class="session-info"><div class="session-device">IFINMAIL Mobile</div><div class="session-meta">Nairobi, Kenya - 2 days ago</div></div>' +
                        '<button class="btn-secondary" id="revoke-session">Revoke</button>' +
                    '</div>' +
                '</div>' +
                '<div class="settings-section"><h3>Login history</h3>' +
                    '<div class="login-history-item"><div class="login-location">Nairobi, Kenya</div><div class="login-time">Today, 09:12 AM</div></div>' +
                    '<div class="login-history-item"><div class="login-location">Nairobi, Kenya</div><div class="login-time">Yesterday, 6:45 PM</div></div>' +
                    '<div class="login-history-item"><div class="login-location">Mombasa, Kenya</div><div class="login-time">Aug 10, 11:20 AM</div></div>' +
                '</div></div></div>';

            const passwordForm = document.getElementById('password-form');
            passwordForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const pwdNew = document.getElementById('pwd-new').value;
                const pwdConfirm = document.getElementById('pwd-confirm').value;
                if (pwdNew !== pwdConfirm) {
                    toast('Passwords do not match');
                    return;
                }
                if (pwdNew.length < 8) {
                    toast('Password must be at least 8 characters');
                    return;
                }
                toast('Password updated');
                passwordForm.reset();
            });
            document.getElementById('pwd-2fa').addEventListener('change', function(e) {
                settings.security.twoFactor = e.target.checked;
                persistSettings();
                toast(e.target.checked ? 'Two-factor authentication enabled' : 'Two-factor authentication disabled');
            });
            const revokeBtn = document.getElementById('revoke-session');
            if (revokeBtn) {
                revokeBtn.addEventListener('click', function() {
                    revokeBtn.closest('.session-item').remove();
                    toast('Session revoked');
                });
            }
        }

        else {
            renderSettingsIndex(container);
        }
    }

    function renderSettingsIndex(container) {
        container.innerHTML =
            '<div class="view"><div class="settings-view">' +
            '<div class="list-header" style="padding-left:0"><div><h2>Settings</h2><div class="list-header-sub">Everything you can customize</div></div></div>' +
            '<div class="settings-section" style="padding:8px">' +
                '<button class="dropdown-item" data-goto="settings-account">' + ICONS.person + ' Account</button>' +
                '<button class="dropdown-item" data-goto="settings-mail">' + ICONS.envelope + ' Mail</button>' +
                '<button class="dropdown-item" data-goto="settings-notifications">' + ICONS.bell + ' Notifications</button>' +
                '<button class="dropdown-item" data-goto="settings-appearance">' + ICONS.palette + ' Appearance</button>' +
                '<button class="dropdown-item" data-goto="settings-security">' + ICONS.lock + ' Security</button>' +
            '</div></div></div>';
        container.querySelectorAll('[data-goto]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                renderView(btn.dataset.goto);
            });
        });
    }

    function renderAccountSecurity(container, view) {
        renderSettings(container, view === 'account' ? 'settings-account' : 'settings-security');
    }

    function bindSettingsForm(formId, saveFn) {
        const forms = formId ? [document.getElementById(formId)] : [document];
        const submitFn = function(e) {
            if (e && e.preventDefault) e.preventDefault();
            const form = {};
            const formEl = formId ? document.getElementById(formId) : document;
            formEl.querySelectorAll('input, textarea, select').forEach(function(field) {
                const name = field.id.replace(/-/g, '_');
                form[name] = field;
            });
            saveFn(form);
        };
        forms.forEach(function(f) {
            if (f && f.tagName === 'FORM') {
                f.addEventListener('submit', submitFn);
            } else if (f === document) {
                document.querySelectorAll('.switch input').forEach(function(input) {
                    input.addEventListener('change', submitFn);
                });
            }
        });
    }

    function applyAppearance() {
        const theme = state.settings.appearance.theme;
        if (theme === 'dark') {
            document.body.classList.add('dark');
        } else if (theme === 'light') {
            document.body.classList.remove('dark');
        } else {
            const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.body.classList.toggle('dark', dark);
        }
        document.body.classList.toggle('compact', state.settings.appearance.density === 'compact');
    }

    function applyUser() {
        const user = state.user;
        if (!user) return;
        document.querySelectorAll('.avatar').forEach(function(avatar) {
            avatar.textContent = initials(user.name);
        });
        const nameEl = document.querySelector('.user-details .user-name');
        const emailEl = document.querySelector('.user-details .user-email');
        if (nameEl) nameEl.textContent = user.name;
        if (emailEl) emailEl.textContent = user.email;
    }

    /* ───────────── Init ───────────── */

    function initNavigation() {
        document.querySelectorAll('.nav-item[data-view]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                closeAllDropdowns();
                renderView(item.dataset.view);
                if (isMobile()) elements.sidebar.classList.remove('open');
            });
        });
        document.querySelectorAll('.tab-btn[data-view]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                closeAllDropdowns();
                renderView(item.dataset.view);
            });
        });
        document.querySelectorAll('.label-item').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                closeAllDropdowns();
                renderView('label', item.dataset.label);
                if (isMobile()) elements.sidebar.classList.remove('open');
            });
        });
        document.querySelectorAll('.dropdown-item[data-view]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                closeAllDropdowns();
                renderView(item.dataset.view);
            });
        });
        if (elements.topbarRefresh) {
            elements.topbarRefresh.addEventListener('click', function() {
                toast('Mailbox refreshed');
                renderView(state.currentView, state.currentLabel);
            });
        }
        if (elements.topbarFilter) {
            elements.topbarFilter.addEventListener('click', function() {
                elements.searchFiltersModal.classList.remove('hidden');
                loadFiltersIntoForm();
            });
        }
        const sidebarHelp = document.getElementById('sidebar-help');
        if (sidebarHelp) {
            sidebarHelp.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeAllDropdowns();
                toggleDropdown(elements.helpDropdown);
            });
        }
        elements.avatarBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleDropdown(elements.userDropdown);
        });
        elements.helpBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleDropdown(elements.helpDropdown);
        });
        elements.settingsBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            toggleDropdown(elements.settingsDropdown);
        });
        document.querySelector('.logo').addEventListener('click', function() {
            renderView('inbox');
        });
        elements.signOutBtn.addEventListener('click', function() {
            localStorage.removeItem('ifinmail.session');
            window.location.href = 'auth.html';
        });
    }

    function initKeyboard() {
        document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (e.key === 'c' || e.key === 'C') {
                openCompose();
            } else if (e.key === '/') {
                e.preventDefault();
                elements.searchInput.focus();
            }
        });
    }

    function init() {
        applyAppearance();
        applyUser();
        initSidebar();
        initNavigation();
        initCompose();
        initSearch();
        initNotifications();
        initKeyboard();
        renderNotifications();
        updateBadges();
        renderView('inbox');
    }

    /* ───────────── Icons ───────────── */

    const ICONS = {
        star: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>',
        attach: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>',
        attachSmall: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>',
        archive: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"></polyline><rect x="1" y="3" width="22" height="5"></rect><line x1="10" y1="12" x2="14" y2="12"></line></svg>',
        trash: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>',
        envelope: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"></rect><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"></path></svg>',
        snooze: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
        refresh: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>',
        more: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle></svg>',
        back: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>',
        reply: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 17 4 12 9 7"></polyline><path d="M20 18v-2a4 4 0 0 0-4-4H4"></path></svg>',
        forward: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 17 20 12 15 7"></polyline><path d="M4 18v-2a4 4 0 0 1 4-4h12"></path></svg>',
        restore: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><polyline points="3 3 3 8 8 8"></polyline></svg>',
        close: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
        sendSmall: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>',
        monitor: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>',
        smartphone: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>',
        person: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>',
        bell: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"></path><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"></path></svg>',
        palette: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"></circle><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"></circle><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"></circle><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"></circle><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"></path></svg>',
        lock: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>'
    };

    document.addEventListener('DOMContentLoaded', init);
})();
