export type TipoNotificacao = 'criada' | 'encaminhada' | 'concluida' | 'alerta' | 'privacidade'

export interface Notificacao {
  id: string
  destinatarioId: string
  tipo: TipoNotificacao
  titulo: string
  mensagem: string
  /** Vazio nos avisos que não tratam de uma ocorrência (ex.: pedido de exclusão de dados). */
  ocorrenciaId: string | null
  criadaEm: string
  lida: boolean
}

/** Filtros e cursor (keyset) aceitos por GET /notificacoes. */
export interface FiltrosNotificacoes {
  limite?: number
  antesDe?: string
  antesId?: string
}

/** Resposta de GET /notificacoes/resumo. */
export interface ResumoNotificacoes {
  naoLidas: number
}
