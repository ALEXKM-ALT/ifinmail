/**
 * ifinmail Branding Page
 * Color picker sync, font preview, save/reset branding.
 * Requires: ifinmail-csrf.js loaded first.
 */
(function () {
    'use strict';

    var csrf = window.IfinmailCSRF;

    function setupColorSync(pickerId, inputId, variableName, callback) {
        var picker = document.getElementById(pickerId);
        var input = document.getElementById(inputId);
        if (!picker || !input) return;

        picker.addEventListener('input', function () {
            input.value = picker.value.toUpperCase();
            if (variableName) {
                document.documentElement.style.setProperty(variableName, picker.value);
            }
            if (callback) callback(picker.value);
        });

        input.addEventListener('input', function () {
            var val = input.value.trim();
            if (val.charAt(0) !== '#') val = '#' + val;
            if (/^#[0-9A-F]{6}$/i.test(val)) {
                picker.value = val;
                if (variableName) {
                    document.documentElement.style.setProperty(variableName, val);
                }
                if (callback) callback(val);
            }
        });
    }

    function previewFonts() {
        var heading = document.getElementById('heading-font');
        var body = document.getElementById('body-font');
        var previewHeading = document.querySelector('.ifinmail-codebox h3');
        var previewBody = document.querySelector('.ifinmail-codebox p');
        if (previewHeading && heading) previewHeading.style.fontFamily = heading.value + ', sans-serif';
        if (previewBody && body) previewBody.style.fontFamily = body.value + ', sans-serif';
    }

    function saveBranding() {
        var saveUrl = document.querySelector('[data-action="save-branding"]');
        if (!saveUrl) return;
        var url = saveUrl.dataset.url;

        var formData = new FormData();
        formData.append('primary_color', document.getElementById('primary-color-input').value);
        formData.append('secondary_color', document.getElementById('secondary-color-input').value);
        formData.append('accent_color', document.getElementById('accent-color-input').value);
        formData.append('heading_font', document.getElementById('heading-font').value);
        formData.append('body_font', document.getElementById('body-font').value);
        var favInput = document.querySelector('#favicon-form input[type=file]');
        if (favInput && favInput.files.length > 0) {
            formData.append('favicon', favInput.files[0]);
        }

        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    alert('Branding saved successfully. Some changes may require a page refresh.');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    function resetBranding() {
        var resetUrl = document.querySelector('[data-action="reset-branding"]');
        if (!resetUrl) return;
        var url = resetUrl.dataset.url;

        if (!confirm('Reset all branding to system defaults?')) return;
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() }
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    alert('Branding reset to defaults.');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    document.addEventListener('DOMContentLoaded', function () {
        setupColorSync('primary-color-picker', 'primary-color-input', '--ifinmail-color-primary', function (color) {
            document.documentElement.style.setProperty('--ifinmail-primary', color);
            document.documentElement.style.setProperty('--ifinmail-secondary', color);
            var btn = document.getElementById('preview-primary-btn');
            if (btn) btn.style.backgroundColor = color;
        });

        setupColorSync('secondary-color-picker', 'secondary-color-input', '--ifinmail-color-surface-2');
        setupColorSync('accent-color-picker', 'accent-color-input', '--ifinmail-success', function (color) {
            var badge = document.getElementById('preview-accent-badge');
            if (badge) {
                badge.style.backgroundColor = color + '1A';
                badge.style.color = color;
                badge.style.borderColor = color + '33';
            }
        });

        // Attach event listeners
        var fontSelectors = document.querySelectorAll('#heading-font, #body-font');
        for (var i = 0; i < fontSelectors.length; i++) {
            fontSelectors[i].addEventListener('change', previewFonts);
        }

        var saveBtn = document.querySelector('[data-action="save-branding"]');
        if (saveBtn) saveBtn.addEventListener('click', function (e) { e.preventDefault(); saveBranding(); });

        var resetBtn = document.querySelector('[data-action="reset-branding"]');
        if (resetBtn) resetBtn.addEventListener('click', function (e) { e.preventDefault(); resetBranding(); });
    });
})();
