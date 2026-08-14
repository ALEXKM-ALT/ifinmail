/* IFINMAIL Mobile - Shared helpers (same localStorage keys as desktop app) */
(function() {
    'use strict';

    const KEYS = {
        emails: 'ifinmail.emails',
        users: 'ifinmail.users',
        session: 'ifinmail.session',
        composePrefill: 'ifinmail.composePrefill'
    };

    function mLoad(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            if (raw === null) return fallback;
            return JSON.parse(raw);
        } catch (e) {
            return fallback;
        }
    }

    function mSave(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {}
    }

    function getEmails() {
        const stored = mLoad(KEYS.emails, null);
        if (stored) return stored;
        return (typeof IFINMAIL_DATA !== 'undefined' && IFINMAIL_DATA.emails) || [];
    }

    function saveEmails(emails) {
        mSave(KEYS.emails, emails);
    }

    function persistEmails(emails) {
        saveEmails(emails);
    }

    function getSession() {
        return mLoad(KEYS.session, null);
    }

    function requireSession() {
        if (!getSession()) window.location.href = 'signin.html';
    }

    function getContacts() {
        return (typeof IFINMAIL_DATA !== 'undefined' && IFINMAIL_DATA.contacts) || [];
    }

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

    const AVATAR_COLORS = ['#E91E63', '#0057cd', '#8BC34A', '#FF5722', '#FF9800', '#16a34a', '#7c3aed', '#0891b2'];

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

    function getEmailById(id) {
        return getEmails().find(function(e) { return e.id === id; }) || null;
    }

    function updateEmail(email) {
        const emails = getEmails();
        const idx = emails.findIndex(function(e) { return e.id === email.id; });
        if (idx !== -1) emails[idx] = email;
        saveEmails(emails);
    }

    function moveEmail(id, folder) {
        const email = getEmailById(id);
        if (!email) return;
        email.folder = folder;
        email.read = true;
        updateEmail(email);
    }

    function getDemoUser(email) {
        if (email === 'alex@example.com') return { name: 'Alex Mwangi', email: 'alex@example.com' };
        if (email === 'alex@ifinmail.com') return { name: 'Alex Mwangi', email: 'alex@ifinmail.com' };
        if (email === 'admin@example.com') return { name: 'Administrator', email: 'admin@example.com' };
        return null;
    }

    function getCreatedUsers() {
        return mLoad(KEYS.users, []);
    }

    window.IFINMAIL_MOBILE = {
        KEYS: KEYS,
        mLoad: mLoad,
        mSave: mSave,
        getEmails: getEmails,
        saveEmails: saveEmails,
        persistEmails: persistEmails,
        getSession: getSession,
        requireSession: requireSession,
        getContacts: getContacts,
        escapeHtml: escapeHtml,
        initials: initials,
        avatarColor: avatarColor,
        formatTime: formatTime,
        formatFullDate: formatFullDate,
        getEmailById: getEmailById,
        updateEmail: updateEmail,
        moveEmail: moveEmail,
        getDemoUser: getDemoUser,
        getCreatedUsers: getCreatedUsers
    };
})();