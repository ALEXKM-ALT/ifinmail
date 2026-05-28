/**
 * Service Worker for ifinmail — offline read-only cache.
 * Caches: CSS, JS, and static shell assets only.
 * Does NOT cache: authenticated API responses, POST requests, auth tokens, sensitive data.
 */
const CACHE_NAME = 'ifinmail-v0.3.0';
const STATIC_ASSETS = [
    '/static/css/ifinmail-variables.css',
    '/static/css/ifinmail-reset.css',
    '/static/css/ifinmail-utilities.css',
    '/static/css/ifinmail-layout.css',
    '/static/css/ifinmail-components.css',
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

    // Never cache authenticated application endpoints
    if (url.pathname.startsWith('/accounts/') || url.pathname.startsWith('/dns/')) return;

    // Network first, fall back to static cache.
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.ok && url.pathname.startsWith('/static/')) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            })
            .catch(() => {
                return caches.match(event.request).then((cached) => {
                    return cached || new Response('', { status: 503, statusText: 'Offline' });
                });
            })
    );
});
