export type ResultadoAuditoria = 'sucesso' | 'erro'

/** Um item de GET /auditoria (trilha de auditoria; só administradores). */
export interface RegistroAuditoria {
  id: string
  /** Tipo do evento: "auditoria.usuario.criar", "ocorrencia.criada"… */
  tipo: string
  /** Tipo sem o prefixo "auditoria.". */
  acao: string
  versao: number
  ocorridoEm: string
  atorId: string | null
  atorNome: string | null
  entidade: string | null
  entidadeId: string | null
  resultado: ResultadoAuditoria
  requestId: string | null
  /** "broker" (gravado pelo consumidor do RabbitMQ) ou "direto" (fallback sem broker). */
  origem: string
  detalhes: Record<string, string | number | boolean | null>
  erro: string | null
}

/** Filtros e cursor (keyset) aceitos por GET /auditoria. */
export interface FiltrosAuditoria {
  limite?: number
  antesDe?: string
  antesId?: string
  /** Prefixo do tipo (ex.: "auditoria.usuario"). */
  tipo?: string
  /** Início e fim do período, em ISO 8601. */
  desde?: string
  ate?: string
}

export const FILTROS_DE_TIPO: { valor: string; rotulo: string }[] = [
  { valor: '', rotulo: 'Todas as ações e eventos' },
  { valor: 'auditoria.ocorrencia', rotulo: 'Ações em ocorrências' },
  { valor: 'auditoria.usuario', rotulo: 'Ações em usuários' },
  { valor: 'auditoria.auth', rotulo: 'Redefinição de senha' },
  { valor: 'ocorrencia.', rotulo: 'Eventos de ocorrência' },
]

export const ROTULO_DA_ACAO: Record<string, string> = {
  'ocorrencia.criar': 'Criou ocorrência',
  'ocorrencia.encaminhar': 'Encaminhou ocorrência',
  'ocorrencia.mudar_status': 'Mudou status da ocorrência',
  'usuario.criar': 'Criou usuário',
  'usuario.editar': 'Editou usuário',
  'usuario.excluir': 'Excluiu usuário',
  'usuario.salvar_em_lote': 'Salvou usuários em lote',
  'auth.redefinir_senha': 'Redefiniu a senha',
  'ocorrencia.criada': 'Evento: ocorrência criada',
  'ocorrencia.encaminhada': 'Evento: ocorrência encaminhada',
  'ocorrencia.status_alterado': 'Evento: status alterado',
}
