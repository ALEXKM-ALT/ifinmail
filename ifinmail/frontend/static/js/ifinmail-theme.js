(function () {
    'use strict';

    var STORAGE_KEY = 'ifinmail-theme';
    var ATTR = 'data-theme';
    var LIGHT_MOON = '☾';  /* first-quarter moon */
    var DARK_SUN = '☀';    /* sun */

    var html = document.documentElement;
    var btn = document.getElementById('ifinmail-theme-toggle');
    if (!btn) return;

    var current = localStorage.getItem(STORAGE_KEY) ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

    function setTheme(theme) {
        if (theme === 'dark') {
            html.setAttribute(ATTR, 'dark');
            btn.innerHTML = DARK_SUN;
        } else {
            html.removeAttribute(ATTR);
            btn.innerHTML = LIGHT_MOON;
        }
        localStorage.setItem(STORAGE_KEY, theme);
    }

    setTheme(current);

    btn.addEventListener('click', function () {
        var next = html.hasAttribute(ATTR) ? 'light' : 'dark';
        setTheme(next);
    });
})();
