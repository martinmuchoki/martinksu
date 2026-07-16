const CACHE_NAME = "mip-pro-v11-6-3-volume-fix-1";

const STATIC_ASSETS = [
    "/offline",
    "/manifest.webmanifest",
    "/static/css/v115.css",
    "/static/css/control_center.css",
    "/static/js/v115_charts.js",
    "/static/js/control_center.js",
    "/static/js/pwa.js",
    "/static/js/pwa-install.js",
    "/static/pwa/icons/mip-pro-192.png",
    "/static/pwa/icons/mip-pro-512.png"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(STATIC_ASSETS);
        })
    );

    self.skipWaiting();
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        })
    );

    self.clients.claim();
});

self.addEventListener("fetch", event => {
    const request = event.request;
    const url = new URL(request.url);

    if (request.method !== "GET") {
        return;
    }

    /*
     * Never cache APIs, login sessions, dashboard pages,
     * stock pages, or Control Center data.
     */
    if (
        url.pathname.startsWith("/api/") ||
        url.pathname === "/" ||
        url.pathname.startsWith("/stocks/") ||
        url.pathname.startsWith("/control-center") ||
        url.pathname.startsWith("/login") ||
        url.pathname.startsWith("/logout")
    ) {
        event.respondWith(
            fetch(request, {
                cache: "no-store"
            })
        );
        return;
    }

    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(() => {
                return caches.match("/offline");
            })
        );
        return;
    }

    /*
     * Cache only static resources.
     */
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then(cached => {
                if (cached) {
                    return cached;
                }

                return fetch(request).then(response => {
                    if (
                        !response ||
                        response.status !== 200
                    ) {
                        return response;
                    }

                    const copy = response.clone();

                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(request, copy);
                    });

                    return response;
                });
            })
        );
        return;
    }

    event.respondWith(fetch(request));
});
