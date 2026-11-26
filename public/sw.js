// Service worker do Uni SOS: deixa o app instalável e abre a casca da interface mesmo sem rede.
// Não guarda respostas da API: dados de ocorrências e tokens nunca ficam no cache do navegador.
const VERSAO = 'unisos-v1'
const CASCA = ['/', '/index.html', '/manifest.webmanifest', '/icone-app.svg', '/unifor-logo-vertical.svg']

self.addEventListener('install', (evento) => {
  evento.waitUntil(caches.open(VERSAO).then((cache) => cache.addAll(CASCA)))
  self.skipWaiting()
})

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nomes) => Promise.all(nomes.filter((nome) => nome !== VERSAO).map((nome) => caches.delete(nome))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (evento) => {
  const pedido = evento.request
  const url = new URL(pedido.url)
  // Só o próprio front-end: a API (outra origem) e métodos que alteram dados passam direto.
  if (pedido.method !== 'GET' || url.origin !== self.location.origin) return

  // Navegação (SPA): rede primeiro, para sempre pegar a versão nova; sem rede, a casca em cache.
  if (pedido.mode === 'navigate') {
    evento.respondWith(fetch(pedido).catch(() => caches.match('/index.html')))
    return
  }

  // Arquivos com hash no nome (/assets/*) nunca mudam: cache primeiro.
  if (url.pathname.startsWith('/assets/')) {
    evento.respondWith(
      caches.match(pedido).then(
        (emCache) =>
          emCache ||
          fetch(pedido).then((resposta) => {
            const copia = resposta.clone()
            if (resposta.ok) caches.open(VERSAO).then((cache) => cache.put(pedido, copia))
            return resposta
          }),
      ),
    )
  }
})
