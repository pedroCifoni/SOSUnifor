/**
 * Versão vigente da Política de Privacidade. Precisa ser igual a VERSAO_TERMOS do back-end
 * (backend/app/core/privacidade.py). Ao mudar o texto de forma relevante, aumente nos dois lugares.
 */
export const VERSAO_TERMOS = '2026-11'
export const DATA_TERMOS = 'novembro de 2026'

/** Canal do encarregado (DPO). Configure VITE_CONTATO_DPO com o endereço oficial indicado pela UNIFOR. */
export const CONTATO_DPO_PADRAO = 'encarregado-a-definir@unifor.br'
export const CONTATO_DPO = import.meta.env.VITE_CONTATO_DPO?.trim() || CONTATO_DPO_PADRAO
export const CONTATO_DPO_PROVISORIO = CONTATO_DPO === CONTATO_DPO_PADRAO

/** Resposta de GET/POST /me/termos. */
export interface SituacaoTermos {
  versaoAtual: string
  versaoAceita: string | null
  aceitosEm: string | null
  pendente: boolean
}

/** Resposta de POST /me/solicitar-exclusao. */
export interface SolicitacaoExclusao {
  mensagem: string
  solicitadaEm: string
}

/** Item de GET /usuarios/pedidos-exclusao (somente admin). */
export interface PedidoExclusao {
  id: string
  nome: string
  email: string
  perfil: string
  ativo: boolean
  solicitadaEm: string
}
