/**
 * ifinmail Header Components
 * Profile dropdown toggle with click-outside-to-close and Escape-to-close.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var wrapper = document.getElementById('header-profile-dropdown');
        if (!wrapper) return;

        var button = wrapper.querySelector('button');
        var menu = wrapper.querySelector('.ifinmail-dropdown-menu');

        if (!button || !menu) return;

        function openMenu() {
            menu.classList.add('ifinmail-dropdown-menu--active');
            wrapper.classList.add('ifinmail-dropdown-wrapper--open');
            button.setAttribute('aria-expanded', 'true');
        }

        function closeMenu() {
            menu.classList.remove('ifinmail-dropdown-menu--active');
            wrapper.classList.remove('ifinmail-dropdown-wrapper--open');
            button.setAttribute('aria-expanded', 'false');
        }

        button.addEventListener('click', function (e) {
            e.stopPropagation();
            var isActive = menu.classList.contains('ifinmail-dropdown-menu--active');
            if (isActive) {
                closeMenu();
            } else {
                openMenu();
            }
        });

        document.addEventListener('click', function (e) {
            if (!wrapper.contains(e.target)) {
                closeMenu();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                closeMenu();
            }
        });
    });
})();
