/**
 * ifinmail Keyboard Shortcuts & Sidebar Modal
 * - G+D → Dashboard, G+L → Logs, G+B → Branding
 * - System Info modal in sidebar footer
 * - Escape closes sidebar and modal
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        // ── System Info Modal ──
        var trigger = document.getElementById('sidebar-more-trigger');
        var overlay = document.getElementById('system-info-modal');
        var closeBtn = document.getElementById('system-info-modal-close');
        var actionBtn = document.getElementById('system-info-modal-action-btn');

        if (trigger && overlay) {
            function openModal() {
                overlay.classList.add('ifinmail-modal-overlay--active');
                document.body.style.overflow = 'hidden';
            }

            function closeModal() {
                overlay.classList.remove('ifinmail-modal-overlay--active');
                document.body.style.overflow = '';
            }

            trigger.addEventListener('click', openModal);
            if (closeBtn) closeBtn.addEventListener('click', closeModal);
            if (actionBtn) actionBtn.addEventListener('click', closeModal);

            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    closeModal();
                }
            });
        }

        // ── Keyboard Shortcuts ──
        var shortcutKeys = {};

        // Resolve a Django URL name to an actual path from a data attribute
        function resolveUrl(key) {
            var el = document.getElementById('shortcut-url-' + key);
            return el ? el.dataset.path : null;
        }

        document.addEventListener('keydown', function (e) {
            var activeTag = document.activeElement.tagName.toLowerCase();
            if (activeTag === 'input' || activeTag === 'textarea' || document.activeElement.isContentEditable) {
                return;
            }

            // Escape: close sidebar modal if open
            if (e.key === 'Escape' && overlay && overlay.classList.contains('ifinmail-modal-overlay--active')) {
                if (typeof closeModal_shortcuts === 'function') {
                    overlay.classList.remove('ifinmail-modal-overlay--active');
                    document.body.style.overflow = '';
                }
                return;
            }

            // Track modifier keys
            shortcutKeys[e.key.toLowerCase()] = true;

            if (shortcutKeys['g']) {
                var target = null;
                if (e.key.toLowerCase() === 'd') target = resolveUrl('dashboard');
                else if (e.key.toLowerCase() === 'l') target = resolveUrl('logs');
                else if (e.key.toLowerCase() === 'b') target = resolveUrl('branding');

                if (target) {
                    window.location.href = target;
                }
            }
        });

        document.addEventListener('keyup', function (e) {
            shortcutKeys[e.key.toLowerCase()] = false;
        });

        // Expose for the overlay Escape handler (closure reference)
        window._sidebarOverlay = overlay;
    });
})();
