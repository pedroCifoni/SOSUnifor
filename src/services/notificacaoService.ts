import { http } from '@/api/client'
import type { FiltrosNotificacoes, Notificacao, ResumoNotificacoes } from '@/models/notificacao'
import { montarQuery } from './paginacao'

export const notificacaoService = {
  /** Lista as notificações do usuário logado (paginada por cursor, mais recentes primeiro). */
  listar(filtros: FiltrosNotificacoes = {}): Promise<Notificacao[]> {
    const query = montarQuery({ limite: filtros.limite, antes_de: filtros.antesDe, antes_id: filtros.antesId })
    return http.get<Notificacao[]>(`/notificacoes${query}`)
  },

  resumo(): Promise<ResumoNotificacoes> {
    return http.get<ResumoNotificacoes>('/notificacoes/resumo')
  },

  marcarTodasLidas(): Promise<void> {
    return http.patch<void>('/notificacoes/lidas')
  },
}
