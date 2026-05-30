/**
 * ifinmail Login Page
 * Disables submit button during form submission to prevent double-submit.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('submit-btn');
        if (!btn) return;
        var form = btn.closest('form');
        if (form) {
            form.addEventListener('submit', function () {
                btn.disabled = true;
                btn.classList.add('ifinmail-btn--loading');
            });
        }
    });
})();
