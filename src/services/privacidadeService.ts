import { http } from '@/api/client'
import type { PedidoExclusao, SituacaoTermos, SolicitacaoExclusao } from '@/models/privacidade'

export const privacidadeService = {
  situacaoTermos(): Promise<SituacaoTermos> {
    return http.get<SituacaoTermos>('/me/termos')
  },

  aceitarTermos(versao: string): Promise<SituacaoTermos> {
    return http.post<SituacaoTermos>('/me/termos', { versao })
  },

  /** Cópia dos dados do titular (JSON), para o botão "Baixar meus dados". */
  exportarDados(): Promise<unknown> {
    return http.get<unknown>('/me/dados')
  },

  solicitarExclusao(): Promise<SolicitacaoExclusao> {
    return http.post<SolicitacaoExclusao>('/me/solicitar-exclusao', { confirmar: true })
  },

  listarPedidosExclusao(): Promise<PedidoExclusao[]> {
    return http.get<PedidoExclusao[]>('/usuarios/pedidos-exclusao')
  },

  anonimizar(usuarioId: string): Promise<{ id: string; nome: string; anonimizadoEm: string }> {
    return http.post(`/usuarios/${usuarioId}/anonimizar`)
  },
}
