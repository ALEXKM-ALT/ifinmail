/**
 * ifinmail User Management Page
 * Handles: kill all other user sessions.
 * Requires: ifinmail-csrf.js loaded first.
 */
(function () {
    'use strict';

    var csrf = window.IfinmailCSRF;

    function killOtherSessions() {
        var killUrl = document.querySelector('[data-action="kill-sessions"]');
        if (!killUrl) return;

        if (!confirm('Terminate all user sessions except your own? All other users will be logged out.')) return;

        fetch(killUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    alert('Terminated: ' + (data.killed || 0) + ' sessions');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.querySelector('[data-action="kill-sessions"]');
        if (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                killOtherSessions();
            });
        }
    });
})();
