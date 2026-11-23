export interface Anexo {
  nome: string
  url?: string
  tipo?: string
}

export type TipoOcorrencia = 'sos' | 'manutencao' | 'denuncia'

export type StatusOcorrencia = 'pendente' | 'aguardando_aceite' | 'em_atendimento' | 'concluido' | 'cancelado'

export interface Ocorrencia {
  id: string
  protocolo: string
  titulo: string
  descricao?: string
  local: string
  tipo: TipoOcorrencia
  status: StatusOcorrencia
  solicitante: string
  autorId?: string
  anonima?: boolean
  anexos?: Anexo[]
  responsavelId?: string
  latitude?: number
  longitude?: number
  precisaoMetros?: number
  criadoEm: string
  eventos?: EventoOcorrencia[]
}

export interface EventoOcorrencia {
  tipo: string
  descricao: string
  criadoEm: string
}

export interface NovaOcorrencia {
  titulo: string
  descricao?: string
  local: string
  tipo: TipoOcorrencia
  anonima?: boolean
  anexos?: File[]
  latitude?: number
  longitude?: number
  precisaoMetros?: number
}

/** Filtros e cursor (keyset) aceitos por GET /ocorrencias. */
export interface FiltrosOcorrencias {
  limite?: number
  /** criadoEm do último item da página anterior (usar junto com antesId). */
  antesDe?: string
  /** id do último item da página anterior (usar junto com antesDe). */
  antesId?: string
  status?: StatusOcorrencia
  tipo?: TipoOcorrencia
}

/** Resposta de GET /ocorrencias/resumo (contagens feitas no banco). */
export interface ResumoOcorrencias {
  total: number
  porStatus: Record<StatusOcorrencia, number>
  porTipo: Record<TipoOcorrencia, number>
}

/** Status considerados "em aberto" (ainda exigem ação). */
export const STATUS_ABERTOS: StatusOcorrencia[] = ['pendente', 'aguardando_aceite', 'em_atendimento']

export const STATUS_LABEL: Record<StatusOcorrencia, string> = {
  pendente: 'Pendente',
  aguardando_aceite: 'Aguardando aceite',
  em_atendimento: 'Em atendimento',
  cancelado: 'Cancelado',
  concluido: 'Concluído',
}

export const ENCAMINHAR_LABEL: Record<TipoOcorrencia, string> = {
  sos: 'Encaminhar Patrulha',
  manutencao: 'Encaminhar ao Técnico',
  denuncia: 'Encaminhar para Análise',
}

export const TIPO_LABEL: Record<TipoOcorrencia, string> = {
  sos: 'Alerta SOS',
  manutencao: 'Manutenção',
  denuncia: 'Denúncia',
}
