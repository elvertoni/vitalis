{% load static %}/*
 * Service worker do Vitalis.
 *
 * Guarda em cache apenas o que é público e imutável: os ícones do app e a folha de estilo
 * que vem do CDN não passam por aqui. **Nenhuma página é cacheada** — a resposta autenticada
 * carrega laudo, peso e medicação, e deixar isso no disco do aparelho contraria o motivo de
 * o anexo já sair por rota autenticada (ver CLAUDE.md, "Anexos"). Sem rede, o app mostra a
 * página de aviso em vez de conteúdo velho de saúde.
 */

const CACHE = 'vitalis-estatico-v1';
const ASSETS = [
    '{% static "icon-192.png" %}',
    '{% static "icon-512.png" %}',
    '{% static "apple-touch-icon.png" %}',
    '{% static "favicon.svg" %}',
];

self.addEventListener('install', (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const request = event.request;
    if (request.method !== 'GET') {
        return;
    }

    const url = new URL(request.url);
    if (url.origin !== self.location.origin) {
        return;
    }

    // Estático: cache primeiro, rede como reserva. É arquivo versionado pelo WhiteNoise.
    if (url.pathname.startsWith('{% get_static_prefix %}')) {
        event.respondWith(
            caches.match(request).then((hit) => hit || fetch(request).then((response) => {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy));
                return response;
            }))
        );
        return;
    }

    // Navegação: sempre rede. Offline, uma página franca — nunca dado clínico do cache.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request).catch(() => new Response(
                '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">' +
                '<meta name="viewport" content="width=device-width, initial-scale=1">' +
                '<title>Sem conexão · Vitalis</title>' +
                '<style>body{font-family:system-ui,sans-serif;background:#f5f4f0;color:#1a1a1a;' +
                'display:grid;place-items:center;min-height:100vh;margin:0;padding:2rem;text-align:center}' +
                'p{color:#5c5c5a;max-width:32ch;line-height:1.5}</style></head><body><div>' +
                '<h1>Sem conexão</h1><p>O Vitalis não guarda seus dados de saúde no aparelho. ' +
                'Assim que a internet voltar, a tela carrega normalmente.</p></div></body></html>',
                { headers: { 'Content-Type': 'text/html; charset=utf-8' }, status: 503 }
            ))
        );
    }
});
