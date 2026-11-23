export type TipoNotificacao = 'criada' | 'encaminhada' | 'concluida' | 'alerta'

export interface Notificacao {
  id: string
  destinatarioId: string
  tipo: TipoNotificacao
  titulo: string
  mensagem: string
  ocorrenciaId: string
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
