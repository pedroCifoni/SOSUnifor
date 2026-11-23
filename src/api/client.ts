import { API_URL } from './config'
import { tokenStorage } from './tokenStorage'

/** Erro devolvido pela API. `codigo` identifica casos que a tela trata de um jeito próprio. */
export class ErroApi extends Error {
  readonly status: number
  readonly codigo?: string

  constructor(mensagem: string, status: number, codigo?: string) {
    super(mensagem)
    this.name = 'ErroApi'
    this.status = status
    this.codigo = codigo
  }
}

let aoNaoAutorizado: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null) {
  aoNaoAutorizado = handler
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = tokenStorage.get()
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(body !== undefined && { 'Content-Type': 'application/json' }),
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && token) aoNaoAutorizado?.()

  if (!res.ok) {
    const erro = await res.json().catch(() => null)
    throw new ErroApi(
      erro?.detail ?? erro?.message ?? `Erro ${res.status}`,
      res.status,
      typeof erro?.codigo === 'string' ? erro.codigo : undefined,
    )
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const http = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  async enviarArquivo(path: string, arquivo: File): Promise<{ nome: string; url?: string; tipo?: string }> {
    const token = tokenStorage.get()
    const formulario = new FormData()
    formulario.append('arquivo', arquivo)
    const resposta = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formulario,
    })
    if (!resposta.ok) {
      const erro = await resposta.json().catch(() => null)
      throw new Error(erro?.detail ?? erro?.message ?? `Erro ${resposta.status}`)
    }
    return resposta.json()
  },
  async baixarArquivo(url: string): Promise<Blob> {
    const token = tokenStorage.get()
    const resposta = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : undefined })
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`)
    return resposta.blob()
  },
}
