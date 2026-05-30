/**
 * ifinmail Registration Flow
 * Handles all registration steps:
 *   - step_profile: email format validation
 *   - step_password: strength meter, requirements, visibility toggle, confirm match
 *   - step_verify: resend button disable
 *   - step_username: async availability check, submit disable
 *
 * Each section activates only when its DOM elements are present,
 * so the single file is safe to load on every registration page.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initProfileStep();
        initPasswordStep();
        initVerifyStep();
        initUsernameStep();
    });

    // ── Common: disable submit button on form submit ──
    function bindSubmitDisable(formSelector, btnId) {
        var form = document.querySelector(formSelector);
        var btn = document.getElementById(btnId);
        if (!form || !btn) return;
        form.addEventListener('submit', function () {
            btn.disabled = true;
            btn.classList.add('ifinmail-btn--loading');
        });
    }

    // ── Step 1: Profile (email validation) ──
    function initProfileStep() {
        var email = document.getElementById('email');
        var hint = document.getElementById('email-hint');
        if (!email || !hint) return;

        email.addEventListener('input', function () {
            var val = email.value.trim();
            if (!val) {
                hint.textContent = '';
                hint.className = 'ifinmail-field-hint';
                return;
            }
            if (val.length > 254) {
                hint.textContent = 'Email address is too long';
                hint.className = 'ifinmail-field-hint ifinmail-field-hint--err';
                return;
            }
            if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
                hint.textContent = 'Enter a valid email address';
                hint.className = 'ifinmail-field-hint ifinmail-field-hint--err';
                return;
            }
            hint.textContent = 'Valid email format';
            hint.className = 'ifinmail-field-hint ifinmail-field-hint--ok';
        });

        bindSubmitDisable('.ifinmail-form-submit', 'submit-btn');
    }

    // ── Step 2: Password ──
    function initPasswordStep() {
        var pw = document.getElementById('password');
        var pw2 = document.getElementById('password2');
        if (!pw) return; // not on password step

        var fill = document.getElementById('pw-fill');
        var text = document.getElementById('pw-text');
        var toggle = document.getElementById('pw-toggle');
        var match = document.getElementById('pw-match');

        var reqs = {
            length: document.querySelector('[data-req="length"]'),
            lower: document.querySelector('[data-req="lower"]'),
            upper: document.querySelector('[data-req="upper"]'),
            digit: document.querySelector('[data-req="digit"]'),
            special: document.querySelector('[data-req="special"]')
        };

        // Password visibility toggle
        if (toggle) {
            var eye = toggle.querySelector('.ifinmail-pw-toggle__eye');
            var eyeOff = toggle.querySelector('.ifinmail-pw-toggle__eye-off');
            toggle.addEventListener('click', function () {
                var isPw = pw.type === 'password';
                pw.type = isPw ? 'text' : 'password';
                if (pw2) pw2.type = isPw ? 'text' : 'password';
                if (eye) eye.style.display = isPw ? 'none' : '';
                if (eyeOff) eyeOff.style.display = isPw ? '' : 'none';
            });
        }

        function updateReq(name, met) {
            if (reqs[name]) reqs[name].classList.toggle('ifinmail-pw-reqs__item--met', met);
        }

        function updateMatch() {
            if (!match) return;
            if (!pw2.value) {
                match.textContent = '';
                match.className = 'ifinmail-pw-match';
                return;
            }
            if (pw.value === pw2.value) {
                match.textContent = 'Passwords match';
                match.className = 'ifinmail-pw-match ifinmail-pw-match--ok';
            } else {
                match.textContent = 'Passwords do not match';
                match.className = 'ifinmail-pw-match ifinmail-pw-match--err';
            }
        }

        function updateMeter() {
            var val = pw.value;
            var score = 0;
            if (val.length >= 8) score += 25;
            if (val.length >= 12) score += 15;
            if (/[a-z]/.test(val)) score += 15;
            if (/[A-Z]/.test(val)) score += 15;
            if (/[0-9]/.test(val)) score += 15;
            if (/[^a-zA-Z0-9]/.test(val)) score += 15;

            if (val.length === 0) score = 0;

            if (fill) fill.style.width = score + '%';
            if (text) {
                if (score < 30) {
                    if (fill) fill.style.background = '#dc2626';
                    text.textContent = 'Weak';
                } else if (score < 55) {
                    if (fill) fill.style.background = '#d97706';
                    text.textContent = 'Fair';
                } else if (score < 80) {
                    if (fill) fill.style.background = '#059669';
                    text.textContent = 'Good';
                } else {
                    if (fill) fill.style.background = '#059669';
                    text.textContent = 'Strong';
                }
            }

            updateReq('length', val.length >= 8);
            updateReq('lower', /[a-z]/.test(val));
            updateReq('upper', /[A-Z]/.test(val));
            updateReq('digit', /[0-9]/.test(val));
            updateReq('special', /[^a-zA-Z0-9]/.test(val));

            updateMatch();
        }

        pw.addEventListener('input', updateMeter);
        if (pw2) pw2.addEventListener('input', updateMatch);

        bindSubmitDisable('.ifinmail-form-submit', 'submit-btn');
    }

    // ── Step 3: Verify ──
    function initVerifyStep() {
        bindSubmitDisable('.ifinmail-reg-verify-actions form', 'resend-btn');
    }

    // ── Step 4: Username ──
    function initUsernameStep() {
        var input = document.getElementById('username');
        if (!input) return;

        var preview = document.getElementById('preview-local');
        var avail = document.getElementById('avail-indicator');
        var currentRequest = null;

        input.addEventListener('input', function () {
            if (preview) preview.textContent = input.value || 'username';
            var val = input.value.trim().toLowerCase();

            if (val.length >= 3) {
                if (avail) {
                    avail.innerHTML = '<span class="ifinmail-reg-availability__checking"><span class="ifinmail-spinner-xs"></span> Checking...</span>';
                }

                if (currentRequest) currentRequest.abort();
                clearTimeout(window._availTimer);

                window._availTimer = setTimeout(function () {
                    var xhr = new XMLHttpRequest();
                    currentRequest = xhr;
                    xhr.open('GET', '/accounts/registration/check-username/?username=' + encodeURIComponent(val), true);
                    xhr.onreadystatechange = function () {
                        if (xhr.readyState === 4 && xhr.status === 200) {
                            if (xhr === currentRequest || !currentRequest) {
                                var data = JSON.parse(xhr.responseText);
                                if (avail) {
                                    if (data.available) {
                                        avail.innerHTML = '<span class="ifinmail-reg-availability__ok">Available</span>';
                                    } else {
                                        avail.innerHTML = '<span class="ifinmail-reg-availability__taken">Taken</span>';
                                    }
                                }
                            }
                        }
                    };
                    xhr.onerror = function () {
                        if (avail) avail.innerHTML = '';
                    };
                    xhr.send();
                }, 400);
            } else {
                if (avail) avail.innerHTML = '';
                if (currentRequest) {
                    currentRequest.abort();
                    currentRequest = null;
                }
            }
        });

        bindSubmitDisable('.ifinmail-form-submit', 'submit-btn');
    }
})();
