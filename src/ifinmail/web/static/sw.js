const CACHE = "ifinmail-v1";
const STATIC_CACHE = "ifinmail-static-v1";
const API_CACHE = "ifinmail-api-v1";

const STATIC_ASSETS = [
  "/",
  "/static/styles.css",
  "/static/app.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE && k !== STATIC_CACHE && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (url.pathname === "/sw.js") return;

  if (url.pathname.startsWith("/static/") || url.pathname === "/") {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  if (url.pathname.startsWith("/auth/") || url.pathname.startsWith("/admin/")) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  if (
    url.pathname.startsWith("/mail/") ||
    url.pathname.startsWith("/contacts") ||
    url.pathname.startsWith("/templates") ||
    url.pathname.startsWith("/settings") ||
    url.pathname.startsWith("/search")
  ) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }
});

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("Offline", { status: 503 });
  }
}

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok && response.type === "basic") {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      const headers = new Headers(cached.headers);
      headers.set("X-Offline", "1");
      return new Response(cached.body, {
        status: cached.status,
        statusText: cached.statusText,
        headers,
      });
    }
    if (request.headers.get("Accept")?.includes("application/json")) {
      return new Response(JSON.stringify({ offline: true, error: "You are offline" }), {
        status: 503,
        headers: { "Content-Type": "application/json", "X-Offline": "1" },
      });
    }
    return new Response("Offline", { status: 503 });
  }
}

self.addEventListener("push", (event) => {
  let data = { event: "push", data: {} };
  try {
    data = event.data ? event.data.json() : data;
  } catch {}
  const payload = data.data || {};
  let title = "ifinmail";
  let body = "";
  let tag = "ifinmail-push";
  switch (data.event) {
    case "new_mail":
      title = payload.from || "New email";
      body = payload.subject || "(no subject)";
      tag = `mail-${payload.message_id || Date.now()}`;
      break;
    case "autoreply.sent":
      title = "Auto-reply sent";
      body = payload.to || "";
      break;
    case "mail.sent":
      title = "Email sent";
      body = `To: ${payload.to || ""} - ${payload.subject || ""}`;
      break;
    default:
      body = data.event;
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      icon: "/static/favicon.ico",
      data: { url: "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(clients.openWindow(url));
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "CLEAR_CACHE") {
    caches.delete(STATIC_CACHE);
    caches.delete(API_CACHE);
    event.ports[0]?.postMessage({ success: true });
  }
});
