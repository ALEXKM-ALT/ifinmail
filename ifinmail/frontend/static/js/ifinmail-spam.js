/**
 * ifinmail Spam Filtering Page
 * Handles: add provider modal, add provider, set sensitivity.
 * Requires: ifinmail-csrf.js loaded first.
 */
(function () {
    'use strict';

    var csrf = window.IfinmailCSRF;

    function openAddProviderModal() {
        var overlay = document.getElementById('add-provider-modal');
        if (!overlay) return;
        overlay.classList.add('ifinmail-modal-overlay--active');
        document.body.classList.add('ifinmail-body--no-scroll');
        var hostInput = document.getElementById('provider-host');
        if (hostInput) {
            hostInput.value = '';
            hostInput.focus();
        }
    }

    function closeAddProviderModal() {
        var overlay = document.getElementById('add-provider-modal');
        if (!overlay) return;
        overlay.classList.remove('ifinmail-modal-overlay--active');
        document.body.classList.remove('ifinmail-body--no-scroll');
    }

    function addProvider() {
        var host = document.getElementById('provider-host');
        var ptype = document.getElementById('provider-type');
        var addUrl = document.querySelector('[data-action="add-provider"]');
        if (!host || !ptype || !addUrl) return;

        var hostVal = host.value.trim();
        if (!hostVal) return;

        var formData = new FormData();
        formData.append('host', hostVal);
        formData.append('type', ptype.value);

        fetch(addUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    function setSensitivity(level) {
        var sensUrl = document.querySelector('[data-action="set-sensitivity"]');
        if (!sensUrl) return;

        var formData = new FormData();
        formData.append('level', level);

        fetch(sensUrl.dataset.url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf.getCSRFToken() },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown'));
                }
            })
            .catch(function () { alert('Request failed'); });
    }

    document.addEventListener('DOMContentLoaded', function () {
        // Move modal to body to escape any scroll container / overflow constraints
        var modalOverlay = document.getElementById('add-provider-modal');
        if (modalOverlay && modalOverlay.parentNode !== document.body) {
            document.body.appendChild(modalOverlay);
        }

        // Open modal
        var toggleBtns = document.querySelectorAll('[data-action="toggle-add-provider"]');
        for (var i = 0; i < toggleBtns.length; i++) {
            toggleBtns[i].addEventListener('click', function (e) {
                e.preventDefault();
                openAddProviderModal();
            });
        }

        // Close modal
        var closeBtn = document.getElementById('add-provider-modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', closeAddProviderModal);
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', function (e) {
                if (e.target === modalOverlay) closeAddProviderModal();
            });
        }
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('ifinmail-modal-overlay--active')) {
                closeAddProviderModal();
            }
        });

        // data-action handlers
        var handlers = {
            'close-add-provider': closeAddProviderModal,
            'add-provider': addProvider
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

        // Sensitivity slider: real-time label update (client-side only)
        var slider = document.getElementById('sensitivity-slider');
        if (slider) {
            slider.addEventListener('input', function () {
                var label = document.getElementById('sensitivity-label');
                if (label) label.textContent = parseFloat(this.value).toFixed(1);
            });
            slider.addEventListener('change', function () {
                setSensitivity(this.value);
            });
        }

        // Add provider form submit
        var addForm = document.getElementById('add-provider-form-inner');
        if (addForm) {
            addForm.addEventListener('submit', function (e) {
                e.preventDefault();
                addProvider();
            });
        }
    });
})();
