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

export const STATUS_LABEL: Record<StatusOcorrencia, string> = {
  pendente: 'Pendente',
  aguardando_aceite: 'Aguardando aceite',
  em_atendimento: 'Em atendimento',
  cancelado: 'Cancelado',
  concluido: 'Concluído',
}

export const ENCAMINHAR_LABEL: Record<TipoOcorrencia, string> = {
  sos: 'Encaminhar Patrulha',
  manutencao: 'Encaminhar à Segurança',
  denuncia: 'Encaminhar para Análise',
}

export const TIPO_LABEL: Record<TipoOcorrencia, string> = {
  sos: 'Alerta SOS',
  manutencao: 'Manutenção',
  denuncia: 'Denúncia',
}
