/**
 * ifinmail Logs Page
 * Handles: filter by log level, live log view toggle.
 */
(function () {
    'use strict';

    var liveInterval = null;

    function filterByLevel() {
        var select = document.getElementById('log-level-filter');
        if (!select) return;
        var level = select.value;
        var url = new URL(window.location.href);
        if (level) {
            url.searchParams.set('level', level);
        } else {
            url.searchParams.delete('level');
        }
        url.searchParams.delete('page');
        window.location.href = url.toString();
    }

    function toggleLiveView() {
        var btn = document.getElementById('live-toggle');
        var liveUrlEl = document.querySelector('[data-action="live-logs"]');
        if (!btn || !liveUrlEl) return;

        if (liveInterval) {
            clearInterval(liveInterval);
            liveInterval = null;
            btn.textContent = 'Live View';
            btn.classList.remove('ifinmail-btn--primary');
            return;
        }

        btn.textContent = 'Pause';
        btn.classList.add('ifinmail-btn--primary');

        liveInterval = setInterval(function () {
            var level = document.getElementById('log-level-filter');
            var levelParam = level && level.value ? '?level=' + encodeURIComponent(level.value) : '';
            fetch(liveUrlEl.dataset.url + levelParam)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!liveInterval) return;
                    console.log('Live log update:', (data.rows || []).length, 'entries');
                });
        }, 5000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var filterSelect = document.getElementById('log-level-filter');
        if (filterSelect) {
            filterSelect.addEventListener('change', filterByLevel);
        }

        var liveBtn = document.getElementById('live-toggle');
        if (liveBtn) {
            liveBtn.addEventListener('click', function (e) {
                e.preventDefault();
                toggleLiveView();
            });
        }
    });
})();
