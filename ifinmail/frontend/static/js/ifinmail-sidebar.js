/**
 * ifinmail Sidebar Manager
 * Handles mobile sidebar toggle for the admin sidebar.
 * Toggles via `data-sidebar-toggle` button.
 */
(function () {
    'use strict';

    var toggles = document.querySelectorAll('[data-sidebar-toggle]');

    var toggleSidebar = function () {
        var nav = document.querySelector('.ifinmail-admin-nav');
        if (nav) {
            nav.classList.toggle('ifinmail-admin-nav--open');
        }
    };

    var closeSidebar = function () {
        var nav = document.querySelector('.ifinmail-admin-nav');
        if (nav) {
            nav.classList.remove('ifinmail-admin-nav--open');
        }
    };

    // Attach toggle handlers
    for (var i = 0; i < toggles.length; i++) {
        toggles[i].addEventListener('click', function (e) {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    // Close sidebar on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeSidebar();
        }
    });

    // Close sidebar when clicking outside
    document.addEventListener('click', function (e) {
        var nav = document.querySelector('.ifinmail-admin-nav');
        if (!nav) return;

        if (nav.classList.contains('ifinmail-admin-nav--open')) {
            var isToggle = e.target.closest('[data-sidebar-toggle]');
            var isNav = e.target.closest('.ifinmail-admin-nav');
            if (!isToggle && !isNav) {
                closeSidebar();
            }
        }
    });
})();
