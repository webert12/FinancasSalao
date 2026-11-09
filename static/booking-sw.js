// Network only: do not store appointments, session tokens or customer data.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
 if(event.request.mode !== 'navigate' || event.request.method !== 'GET') return;
 event.respondWith(fetch(event.request).catch(() => new Response(
  '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Sem conexão</title><body style="font-family:system-ui;padding:24px"><h1>Sem conexão</h1><p>Conecte-se à internet para consultar horários e agendar.</p><button onclick="location.reload()">Tentar novamente</button></body></html>',
  {status:503,headers:{'Content-Type':'text/html; charset=utf-8'}})));
});
