const KEY = 'sos-unifor:token'
const KEY_RENOVACAO = 'sos-unifor:refresh-token'

function ler(chave: string): string | null {
  try {
    return localStorage.getItem(chave)
  } catch {
    return null
  }
}

function gravar(chave: string, valor: string): void {
  try {
    localStorage.setItem(chave, valor)
  } catch {
    return
  }
}

function remover(chave: string): void {
  try {
    localStorage.removeItem(chave)
  } catch {
    return
  }
}

export const tokenStorage = {
  get(): string | null {
    return ler(KEY)
  },
  set(token: string): void {
    gravar(KEY, token)
  },
  /** Refresh token: renova o access token (JWT curto) sem pedir a senha de novo. */
  getRefresh(): string | null {
    return ler(KEY_RENOVACAO)
  },
  setRefresh(token: string): void {
    gravar(KEY_RENOVACAO, token)
  },
  clearAccess(): void {
    remover(KEY)
  },
  clear(): void {
    remover(KEY)
    remover(KEY_RENOVACAO)
  },
}
