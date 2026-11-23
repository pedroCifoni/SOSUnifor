function enderecoPadraoDaApi() {
  const protocolo = window.location.protocol === 'https:' ? 'https:' : 'http:'
  return `${protocolo}//${window.location.hostname}:8000`
}

function resolverEnderecoDaApi() {
  const enderecoConfigurado = import.meta.env.VITE_API_URL?.trim()
  if (!enderecoConfigurado) return enderecoPadraoDaApi()

  const api = new URL(enderecoConfigurado)
  const frontendFoiAbertoPorRede = !['localhost', '127.0.0.1'].includes(window.location.hostname)
  const apiApontaParaLoopback = ['localhost', '127.0.0.1'].includes(api.hostname)

  // No celular, 127.0.0.1 é o próprio celular. Mantemos a porta configurada,
  // mas usamos o IP/host do computador que entregou o front-end.
  if (frontendFoiAbertoPorRede && apiApontaParaLoopback) api.hostname = window.location.hostname

  return api.toString().replace(/\/$/, '')
}

export const API_URL = resolverEnderecoDaApi()
