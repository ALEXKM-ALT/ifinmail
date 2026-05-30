/**
 * ifinmail CSRF Token Utility
 * Single source of truth for CSRF token extraction.
 * Include this before any script that needs to make fetch() calls.
 */
(function () {
    'use strict';

    /**
     * Get the CSRF token from the page.
     * Checks the hidden form input first, then falls back to the cookie.
     * @returns {string} CSRF token value or empty string
     */
    function getCSRFToken() {
        // Primary: hidden input rendered by {% csrf_token %} in base.html
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el && el.value) {
            return el.value;
        }

        // Fallback: read from document.cookie
        var name = 'csrftoken';
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var c = cookies[i].trim();
            if (c.indexOf(name + '=') === 0) {
                return decodeURIComponent(c.substring(name.length + 1));
            }
        }

        return '';
    }

    // Expose globally for inline onclick handlers during migration
    window.IfinmailCSRF = { getCSRFToken: getCSRFToken };
})();
