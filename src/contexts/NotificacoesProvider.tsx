import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import type { Notificacao } from '@/models/notificacao'
import { notificacaoService } from '@/services/notificacaoService'
import { NotificacoesContext } from './notificacoesContext'
import { API_URL } from '@/api/config'
import { tokenStorage } from '@/api/tokenStorage'

const INTERVALO_CONTINGENCIA_MS = 60_000
// O sino mostra só as notificações mais recentes; o contador vem de /notificacoes/resumo.
const LIMITE_NOTIFICACOES = 30

function criarUrlWebSocket(token: string) {
  const base = API_URL.replace(/^http/, 'ws')
  return `${base}/ws/notificacoes?token=${encodeURIComponent(token)}`
}

export function NotificacoesProvider({ children }: { children: ReactNode }) {
  const { usuario } = useAuth()
  const toast = useToast()
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([])
  const [naoLidas, setNaoLidas] = useState(0)
  const [revisao, setRevisao] = useState(0)
  const vistas = useRef<Set<string> | null>(null)
  const usuarioId = usuario?.id

  const atualizar = useCallback(async () => {
    if (!usuarioId) return
    const [lista, resumo] = await Promise.all([
      notificacaoService.listar({ limite: LIMITE_NOTIFICACOES }),
      notificacaoService.resumo().catch(() => null),
    ])
    setNotificacoes(lista)
    // Sem o resumo, conta ao menos as não lidas da página carregada.
    setNaoLidas(resumo?.naoLidas ?? lista.filter((n) => !n.lida).length)

    if (vistas.current === null) {
      vistas.current = new Set(lista.map((n) => n.id))
      return
    }
    const novas = lista.filter((n) => !vistas.current!.has(n.id))
    if (novas.length === 0) return
    novas.forEach((n) => vistas.current!.add(n.id))
    novas.reverse().forEach((n) => toast.notificar(n.tipo === 'concluida' ? 'success' : n.tipo === 'alerta' ? 'error' : 'info', `${n.titulo}: ${n.mensagem}`))
    setRevisao((r) => r + 1)
  }, [usuarioId, toast])

  useEffect(() => {
    vistas.current = null
    if (!usuarioId) {
      setNotificacoes([])
      setNaoLidas(0)
      return
    }
    const atualizarComSeguranca = () => void atualizar().catch(() => undefined)
    atualizarComSeguranca()
    const intervalo = setInterval(atualizarComSeguranca, INTERVALO_CONTINGENCIA_MS)
    const token = tokenStorage.get()
    let websocket: WebSocket | null = null
    let reconexao: ReturnType<typeof setTimeout> | null = null
    let ativo = true

    function conectarTempoReal() {
      if (!token || !ativo) return
      websocket = new WebSocket(criarUrlWebSocket(token))
      websocket.onmessage = atualizarComSeguranca
      websocket.onclose = () => {
        if (ativo) reconexao = setTimeout(conectarTempoReal, 5_000)
      }
    }
    conectarTempoReal()
    return () => {
      ativo = false
      clearInterval(intervalo)
      if (reconexao) clearTimeout(reconexao)
      websocket?.close()
    }
  }, [usuarioId, atualizar])

  const marcarTodasLidas = useCallback(async () => {
    if (!usuarioId) return
    await notificacaoService.marcarTodasLidas()
    setNotificacoes((atual) => atual.map((n) => ({ ...n, lida: true })))
    setNaoLidas(0)
  }, [usuarioId])

  const value = useMemo(
    () => ({ notificacoes, naoLidas, revisao, marcarTodasLidas }),
    [notificacoes, naoLidas, revisao, marcarTodasLidas],
  )

  return <NotificacoesContext.Provider value={value}>{children}</NotificacoesContext.Provider>
}
