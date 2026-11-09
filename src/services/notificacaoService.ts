import { http } from '@/api/client'
import type { Notificacao } from '@/models/notificacao'

export const notificacaoService = {
  listar(_usuarioId: string): Promise<Notificacao[]> {
    return http.get<Notificacao[]>('/notificacoes')
  },

  marcarTodasLidas(_usuarioId: string): Promise<void> {
    return http.patch<void>('/notificacoes/lidas')
  },
}
