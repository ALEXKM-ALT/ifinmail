/**
 * ifinmail Dashboard Actions
 * Handles: force rescan, TLS info display, log purge, and quick actions.
 * Requires: ifinmail-csrf.js loaded first.
 */
(function () {
    'use strict';

    var csrf = window.IfinmailCSRF;

    /**
     * Trigger a DNS/TLS rescan and reload on success.
     */
    function forceRescan() {
        var btn = document.querySelector('[data-action="rescan"]');
        if (!btn) return;

        btn.disabled = true;
        var originalText = btn.textContent;
        btn.textContent = 'Scanning…';

        fetch(btn.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btn.textContent = data.status === 'ok' ? 'Rescan Complete' : 'Rescan Failed';
                btn.disabled = false;
                setTimeout(function () { btn.textContent = originalText; }, 3000);
                if (data.status === 'ok') location.reload();
            })
            .catch(function () {
                btn.textContent = 'Request Failed';
                btn.disabled = false;
                setTimeout(function () { btn.textContent = originalText; }, 3000);
            });
    }

    /**
     * Show TLS certificate details in an alert.
     * Reads data from a <script type="application/json"> element (json_script).
     */
    function showTLSInfo() {
        var tlsData = {};
        var el = document.getElementById('tls-info-data');
        if (el) {
            try { tlsData = JSON.parse(el.textContent); } catch (e) { /* use empty */ }
        }

        var msg = 'TLS Certificate Info\n\n';
        if (tlsData.issuer) msg += 'Issuer: ' + tlsData.issuer + '\n';
        if (tlsData.sans && tlsData.sans.length) msg += 'Domains: ' + tlsData.sans.join(', ') + '\n';
        if (tlsData.expiry_days !== undefined && tlsData.expiry_days !== null) {
            msg += 'Expires in: ' + tlsData.expiry_days + ' days\n';
        } else {
            msg += 'No certificate found\n';
        }
        alert(msg);
    }

    /**
     * Purge archived audit logs with confirmation.
     */
    function purgeLogs() {
        var purgeUrl = document.querySelector('[data-action="purge-logs"]');
        if (!purgeUrl) return;
        var url = purgeUrl.dataset.url;
        var confirmMsg = purgeUrl.dataset.confirm || 'Delete all archived audit logs?';

        if (!confirm(confirmMsg)) return;

        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    alert('Purged: ' + (data.deleted || 0) + ' entries');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    // Attach click handlers
    document.addEventListener('DOMContentLoaded', function () {
        var rescanBtn = document.querySelector('[data-action="rescan"]');
        if (rescanBtn) {
            rescanBtn.addEventListener('click', function (e) {
                e.preventDefault();
                forceRescan();
            });
        }

        var tlsBtn = document.querySelector('[data-action="tls-info"]');
        if (tlsBtn) {
            tlsBtn.addEventListener('click', function (e) {
                e.preventDefault();
                showTLSInfo();
            });
        }

        var purgeBtn = document.querySelector('[data-action="purge-logs"]');
        if (purgeBtn) {
            purgeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                purgeLogs();
            });
        }
    });

    // Expose for legacy onclick handlers during migration
    window.IfinmailDashboard = {
        forceRescan: forceRescan,
        showTLSInfo: showTLSInfo,
        purgeLogs: purgeLogs
    };
})();
