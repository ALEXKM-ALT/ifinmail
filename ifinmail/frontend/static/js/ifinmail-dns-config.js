/**
 * ifinmail DNS Configuration Page
 * Handles: domain registration modal, DNS record copy, SMTP proxy toggle,
 * smart host toggle, hop count, and DNS status refresh.
 * Requires: ifinmail-csrf.js loaded first.
 */
(function () {
    'use strict';

    var csrf = window.IfinmailCSRF;

    /* ── Helpers ───────────────────────────────────────────── */

    function show(el) { if (el) el.classList.remove('ifinmail-hidden'); }
    function hide(el) { if (el) el.classList.add('ifinmail-hidden'); }
    function isHidden(el) { return el && el.classList.contains('ifinmail-hidden'); }

    /* ── Register Domain Modal ─────────────────────────────── */

    function openRegisterModal() {
        var overlay = document.getElementById('register-domain-modal');
        if (!overlay) return;
        overlay.classList.add('ifinmail-modal-overlay--active');
        document.body.classList.add('ifinmail-body--no-scroll');
        var input = document.getElementById('new-domain-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        resetFormState();
    }

    function closeRegisterModal() {
        var overlay = document.getElementById('register-domain-modal');
        if (!overlay) return;
        overlay.classList.remove('ifinmail-modal-overlay--active');
        document.body.classList.remove('ifinmail-body--no-scroll');
    }

    function resetFormState() {
        var parentGroup = document.getElementById('parent-domain-group');
        var ipGroup = document.getElementById('ip-address-group');
        var parentSelect = document.getElementById('parent-domain-select');
        var ipInput = document.getElementById('new-domain-ip');
        var result = document.getElementById('register-result');
        hide(parentGroup);
        hide(ipGroup);
        if (parentSelect) parentSelect.value = '';
        if (ipInput) ipInput.value = '';
        hide(result);
        if (result) result.textContent = '';
    }

    function onDomainInput() {
        var input = document.getElementById('new-domain-input');
        var parentGroup = document.getElementById('parent-domain-group');
        var ipGroup = document.getElementById('ip-address-group');
        if (!input || !parentGroup || !ipGroup) return;

        var val = input.value.trim();
        if (!val) {
            hide(parentGroup);
            hide(ipGroup);
            return;
        }

        if (val.indexOf('.') !== -1) {
            // User is typing an FQDN — hide parent dropdown, show IP if subdomain detected
            hide(parentGroup);
            var parts = val.split('.');
            if (parts.length > 2) { show(ipGroup); } else { hide(ipGroup); }
        } else {
            // Short label — show parent dropdown
            show(parentGroup);
            var parentSelect = document.getElementById('parent-domain-select');
            var hasParent = parentSelect && parentSelect.value;
            if (hasParent) { show(ipGroup); } else { hide(ipGroup); }
        }
    }

    function onParentSelect() {
        var input = document.getElementById('new-domain-input');
        var ipGroup = document.getElementById('ip-address-group');
        if (!input || !ipGroup) return;
        var val = input.value.trim();
        if (val && val.indexOf('.') === -1) {
            var parentSelect = document.getElementById('parent-domain-select');
            if (parentSelect && parentSelect.value) { show(ipGroup); } else { hide(ipGroup); }
        }
    }

    function validateIP(ip) {
        if (!ip) return false;
        var parts = ip.split('.');
        if (parts.length !== 4) return false;
        for (var i = 0; i < 4; i++) {
            var n = parseInt(parts[i], 10);
            if (isNaN(n) || n < 0 || n > 255 || parts[i] !== String(n)) return false;
        }
        return true;
    }

    function registerDomain() {
        var domainInput = document.getElementById('new-domain-input');
        var parentSelect = document.getElementById('parent-domain-select');
        var ipInput = document.getElementById('new-domain-ip');
        var result = document.getElementById('register-result');
        var registerBtn = document.querySelector('[data-action="register-domain"]');
        if (!domainInput || !result || !registerBtn) return;

        var domain = domainInput.value.trim();
        if (!domain) return;

        var parentDomain = '';
        var ipAddress = '';

        if (parentSelect && !isHidden(parentSelect.closest('.ifinmail-form-group'))) {
            parentDomain = parentSelect.value;
        }
        if (ipInput && !isHidden(ipInput.closest('.ifinmail-form-group'))) {
            ipAddress = ipInput.value.trim();
        }

        // Client-side validation
        var isSubdomain = (domain.indexOf('.') === -1 && parentDomain) ||
                          (domain.indexOf('.') !== -1 && domain.split('.').length > 2);
        if (isSubdomain && !ipAddress) {
            show(result);
            result.textContent = 'Error: IP address is required for subdomains';
            return;
        }
        if (ipAddress && !validateIP(ipAddress)) {
            show(result);
            result.textContent = 'Error: Invalid IP address format';
            return;
        }

        show(result);
        result.textContent = 'Registering\u2026';
        registerBtn.disabled = true;

        var formData = new FormData();
        formData.append('domain', domain);
        if (parentDomain) formData.append('parent_domain', parentDomain);
        if (ipAddress) formData.append('ip_address', ipAddress);

        fetch(registerBtn.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                registerBtn.disabled = false;
                if (data.status === 'ok') {
                    var lines = ['Domain: ' + data.domain, 'Created: ' + (data.created ? 'Yes (new)' : 'No (existing)'), 'Records:'];
                    data.records.forEach(function (r) {
                        lines.push('  ' + r.type + ' ' + r.name + ' \u2192 ' + r.value);
                    });
                    result.textContent = lines.join('\n');
                    setTimeout(function () { location.reload(); }, 2000);
                } else {
                    result.textContent = 'Error: ' + (data.error || 'Unknown');
                }
            })
            .catch(function () {
                registerBtn.disabled = false;
                result.textContent = 'Request failed. Please try again.';
            });
    }

    /* ── Clipboard ─────────────────────────────────────────── */

    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(function () {
            var btn = document.querySelector('[data-action="copy-spf"]');
            if (btn) {
                var orig = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(function () { btn.textContent = orig; }, 1500);
            }
        }).catch(function () {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.setAttribute('readonly', '');
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        });
    }

    function editRecord() {
        alert('DNS record editing is managed through your provider. Use the DNS Toolbox to copy the current record value and paste it into your provider dashboard.');
    }

    /* ── Toggle controls ───────────────────────────────────── */

    function toggleSMTPProxy() {
        var toggleUrl = document.querySelector('[data-action="toggle-proxy"]');
        if (!toggleUrl) return;

        fetch(toggleUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    var switchEl = document.querySelector('[data-action="toggle-proxy"] .ifinmail-switch');
                    if (switchEl) switchEl.classList.toggle('ifinmail-switch--on', data.enabled);
                    alert('SMTP Proxy: ' + (data.enabled ? 'enabled' : 'disabled') + '. ' + (data.note || ''));
                }
            });
    }

    function toggleSmartHost() {
        var toggleUrl = document.querySelector('[data-action="toggle-relay"]');
        if (!toggleUrl) return;

        fetch(toggleUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    var switchEl = document.querySelector('[data-action="toggle-relay"] .ifinmail-switch');
                    if (switchEl) switchEl.classList.toggle('ifinmail-switch--on', data.enabled);
                    alert('Smart Host Relay: ' + (data.enabled ? 'enabled' : 'disabled') + '. ' + (data.note || ''));
                }
            });
    }

    function setHopCount(value) {
        var hopUrl = document.querySelector('[data-action="set-hop-count"]');
        if (!hopUrl) return;

        var formData = new FormData();
        formData.append('value', value);

        fetch(hopUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    var label = document.getElementById('hop-count-label');
                    if (label) label.textContent = data.value;
                }
            });
    }

    function refreshDNSStatus() {
        var btn = document.querySelector('[data-action="refresh-dns"]');
        if (!btn) return;
        btn.disabled = true;
        var originalText = btn.textContent;
        btn.textContent = 'Refreshing\u2026';

        var statusUrl = btn.dataset.url;
        fetch(statusUrl)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btn.disabled = false;
                btn.textContent = originalText;
                if (data && data.status) {
                    console.log('DNS refresh complete:', data.status);
                }
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = originalText;
            });
    }

    /* ── Init ──────────────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        // Move modal to body to escape any scroll container / overflow constraints
        var modalOverlay = document.getElementById('register-domain-modal');
        if (modalOverlay && modalOverlay.parentNode !== document.body) {
            document.body.appendChild(modalOverlay);
        }

        var modalClose = document.getElementById('register-modal-close');

        // "Register New Domain" button and empty-state action both use toggle-register
        var toggleBtns = document.querySelectorAll('[data-action="toggle-register"]');
        for (var i = 0; i < toggleBtns.length; i++) {
            toggleBtns[i].addEventListener('click', function (e) {
                e.preventDefault();
                openRegisterModal();
            });
        }

        if (modalClose) {
            modalClose.addEventListener('click', closeRegisterModal);
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', function (e) {
                if (e.target === modalOverlay) closeRegisterModal();
            });
        }

        // Escape key closes modal
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('ifinmail-modal-overlay--active')) {
                closeRegisterModal();
            }
        });

        // Dynamic form behavior
        var domainInput = document.getElementById('new-domain-input');
        var parentSelect = document.getElementById('parent-domain-select');
        if (domainInput) domainInput.addEventListener('input', onDomainInput);
        if (parentSelect) parentSelect.addEventListener('change', onParentSelect);

        // Register domain (footer button)
        var registerBtns = document.querySelectorAll('[data-action="register-domain"]');
        for (var j = 0; j < registerBtns.length; j++) {
            registerBtns[j].addEventListener('click', function (e) {
                e.preventDefault();
                registerDomain();
            });
        }

        // Register domain form submit (Enter key inside form)
        var regForm = document.getElementById('register-domain-form-inner');
        if (regForm) {
            regForm.addEventListener('submit', function (e) {
                e.preventDefault();
                registerDomain();
            });
        }

        // Other data-action handlers
        var handlers = {
            'copy-spf': function () {
                var el = document.querySelector('[data-action="copy-spf"]');
                if (el) copyToClipboard(el.dataset.value);
            },
            'edit-record': editRecord,
            'toggle-proxy': toggleSMTPProxy,
            'toggle-relay': toggleSmartHost,
            'refresh-dns': refreshDNSStatus,
            'close-register-modal': closeRegisterModal
        };

        Object.keys(handlers).forEach(function (action) {
            var fn = handlers[action];
            var els = document.querySelectorAll('[data-action="' + action + '"]');
            for (var k = 0; k < els.length; k++) {
                (function (handler) {
                    els[k].addEventListener('click', function (e) {
                        e.preventDefault();
                        handler();
                    });
                })(fn);
            }
        });

        // Hop count slider — real-time label update + change handler
        var hopSlider = document.getElementById('hop-count-slider');
        if (hopSlider) {
            hopSlider.addEventListener('input', function () {
                var label = document.getElementById('hop-count-label');
                if (label) label.textContent = this.value;
            });
            hopSlider.addEventListener('change', function () {
                setHopCount(this.value);
            });
        }
    });
})();
