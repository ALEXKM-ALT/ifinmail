/**
 * ifinmail Setup Wizard — DNS Auto-Configuration
 * Fires DNS provider configuration and updates check indicators.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // Read domain and provider from data attributes on the container
        var container = document.querySelector('[data-setup-dns]');
        if (!container) return;

        var domain = container.dataset.domain;
        var provider = container.dataset.provider;
        if (!domain || !provider) return;

        var configureUrl = container.dataset.configureUrl;
        if (!configureUrl) return;

        var checks = ['a', 'mx', 'spf', 'dkim', 'dmarc'];
        var dnsLabels = {
            a: 'A record configured',
            mx: 'MX record configured',
            spf: 'SPF record configured',
            dkim: 'DKIM record configured',
            dmarc: 'DMARC record configured'
        };

        var csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        var csrfToken = csrfEl ? csrfEl.value : '';

        var formData = new FormData();
        formData.append('domain', domain);
        formData.append('provider', provider);

        fetch(configureUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: formData
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var resultEl = document.getElementById('dns-result-message');
                if (data.success) {
                    checks.forEach(function (c) {
                        var el = document.getElementById('check-' + c);
                        if (el) {
                            el.className = 'ifinmail-dns-check ifinmail-dns-check--pass';
                            var detail = el.querySelector('.ifinmail-dns-check-detail');
                            if (detail) detail.textContent = dnsLabels[c];
                        }
                    });
                    if (resultEl) {
                        resultEl.innerHTML = '<div class="ifinmail-dns-result ifinmail-dns-result--ok"><p>All DNS records configured successfully. Propagation may take a few minutes.</p></div>';
                    }
                } else {
                    if (resultEl) {
                        resultEl.innerHTML = '<div class="ifinmail-dns-result ifinmail-dns-result--err"><p>Configuration failed: ' + (data.message || 'Unknown error') + '</p></div>';
                    }
                }
            })
            .catch(function () {
                var resultEl = document.getElementById('dns-result-message');
                if (resultEl) {
                    resultEl.innerHTML = '<div class="ifinmail-dns-result ifinmail-dns-result--err"><p>Configuration failed. Please try again or configure manually.</p></div>';
                }
            });
    });
})();
