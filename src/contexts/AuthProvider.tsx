import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { setRefreshHandler, setUnauthorizedHandler } from '@/api/client'
import { tokenStorage } from '@/api/tokenStorage'
import type { Credenciais } from '@/models/usuario'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'
import { claimsParaUsuario, decodeJwt, expiraEmMs } from '@/utils/jwt'
import { AuthContext } from './authContext'

// Renova o access token um pouco antes de vencer, para nenhuma requisição chegar com ele vencido.
const ANTECEDENCIA_RENOVACAO_MS = 60_000

function carregarTokenValido(): string | null {
  const token = tokenStorage.get()
  const claims = token ? decodeJwt(token) : null
  if (token && claims && expiraEmMs(claims) > 0) return token
  // Access token vencido: o refresh token (se houver) ainda pode renovar a sessão.
  tokenStorage.clearAccess()
  return null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(carregarTokenValido)
  const [restaurando, setRestaurando] = useState(() => token === null && tokenStorage.getRefresh() !== null)
  const renovacaoEmAndamento = useRef<Promise<boolean> | null>(null)
  const toast = useToast()

  const claims = useMemo(() => (token ? decodeJwt(token) : null), [token])
  const usuario = useMemo(() => (claims ? claimsParaUsuario(claims) : null), [claims])
  const expiraEm = claims ? claims.exp * 1000 : null

  const logout = useCallback(() => {
    const refresh = tokenStorage.getRefresh()
    if (refresh) void authService.logout(refresh)
    tokenStorage.clear()
    setToken(null)
  }, [])

  const login = useCallback(async (credenciais: Credenciais) => {
    const { token: novo, refreshToken } = await authService.login(credenciais)
    const novasClaims = decodeJwt(novo)
    if (!novasClaims) throw new Error('Resposta de login inválida.')
    tokenStorage.set(novo)
    if (refreshToken) tokenStorage.setRefresh(refreshToken)
    setToken(novo)
    return claimsParaUsuario(novasClaims)
  }, [])

  /** Uma renovação por vez: várias requisições com 401 ao mesmo tempo esperam a mesma. */
  const renovarSessao = useCallback((): Promise<boolean> => {
    if (renovacaoEmAndamento.current) return renovacaoEmAndamento.current
    const refresh = tokenStorage.getRefresh()
    if (!refresh) return Promise.resolve(false)
    const tentativa = authService
      .renovar(refresh)
      .then((resposta) => {
        if (!resposta || !decodeJwt(resposta.token)) {
          tokenStorage.clear()
          setToken(null)
          return false
        }
        tokenStorage.set(resposta.token)
        if (resposta.refreshToken) tokenStorage.setRefresh(resposta.refreshToken)
        setToken(resposta.token)
        return true
      })
      .catch(() => false) // sem rede: mantém a sessão como está e tenta de novo depois
      .finally(() => {
        renovacaoEmAndamento.current = null
      })
    renovacaoEmAndamento.current = tentativa
    return tentativa
  }, [])

  const sessaoExpirada = useCallback(() => {
    logout()
    toast.info('Sua sessão expirou. Entre novamente.')
  }, [logout, toast])

  useEffect(() => {
    setUnauthorizedHandler(sessaoExpirada)
    setRefreshHandler(renovarSessao)
    return () => {
      setUnauthorizedHandler(null)
      setRefreshHandler(null)
    }
  }, [sessaoExpirada, renovarSessao])

  // Ao abrir o app com o access token vencido, restaura a sessão pelo refresh token.
  useEffect(() => {
    if (!restaurando) return
    void renovarSessao().finally(() => setRestaurando(false))
  }, [restaurando, renovarSessao])

  useEffect(() => {
    if (!claims) return
    const conferir = () => {
      if (expiraEmMs(claims) > ANTECEDENCIA_RENOVACAO_MS) return
      void renovarSessao().then((renovou) => {
        if (!renovou && expiraEmMs(claims) <= 0) sessaoExpirada()
      })
    }
    const timer = setTimeout(conferir, Math.max(0, expiraEmMs(claims) - ANTECEDENCIA_RENOVACAO_MS))
    const intervalo = setInterval(conferir, 30_000)
    document.addEventListener('visibilitychange', conferir)
    window.addEventListener('focus', conferir)
    return () => {
      clearTimeout(timer)
      clearInterval(intervalo)
      document.removeEventListener('visibilitychange', conferir)
      window.removeEventListener('focus', conferir)
    }
  }, [claims, renovarSessao, sessaoExpirada])

  const value = useMemo(
    () => ({ usuario, expiraEm, login, logout, renovarSessao }),
    [usuario, expiraEm, login, logout, renovarSessao],
  )

  // Enquanto restaura a sessão, não renderiza as rotas (evita mandar para o login por engano).
  if (restaurando) return null

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
