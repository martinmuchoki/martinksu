const CACHE_NAME = "mip-pro-v11-6-3";

const STATIC_ASSETS = [
    "/offline",
    "/manifest.webmanifest",
    "/static/css/v115.css",
    "/static/css/control_center.css",
    "/static/js/v115_charts.js",
    "/static/js/control_center.js",
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

    if (request.method !== "GET") {
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

    event.respondWith(
        caches.match(request).then(cached => {
            if (cached) {
                return cached;
            }

            return fetch(request).then(response => {
                const copy = response.clone();

                caches.open(CACHE_NAME).then(cache => {
                    cache.put(request, copy);
                });

                return response;
            });
        })
    );
});
