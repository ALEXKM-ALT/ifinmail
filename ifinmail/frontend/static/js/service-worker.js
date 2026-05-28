/**
 * Service Worker for ifinmail — offline read-only cache.
 * Caches: CSS, JS, images, and previously-read messages.
 * Does NOT cache: POST requests, auth tokens, sensitive data.
 */
const CACHE_NAME = 'ifinmail-v0.3.0';
const STATIC_ASSETS = [
    '/',
    '/offline',
    '/static/css/ifinmail-variables.css',
    '/static/css/ifinmail-reset.css',
    '/static/css/ifinmail-utilities.css',
    '/static/css/ifinmail-layout.css',
    '/static/css/ifinmail-components.css',
    '/static/js/ifinmail-api.js',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Never cache POST/PUT/DELETE or API writes
    if (event.request.method !== 'GET') return;

    // Never cache auth endpoints
    if (url.pathname.startsWith('/v1/auth/')) return;

    // Network first, fall back to cache, fall back to offline page
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.ok && (url.pathname.startsWith('/static/') ||
                    url.pathname.startsWith('/v1/mail/'))) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    return cached || caches.match('/offline');
                });
            })
    );
});
