import { http } from '@/api/client'
import type { EdicaoUsuario, Perfil, Usuario } from '@/models/usuario'
import { montarQuery } from '@/services/paginacao'

/** Contas ativas (padrão) ou desativadas que podem ser reativadas. */
export type SituacaoConta = 'ativos' | 'desativados'

export interface FiltrosUsuarios {
  busca?: string
  perfil?: Perfil
  situacao?: SituacaoConta
  limite?: number
  pagina?: number
}

export interface ResumoUsuarios {
  total: number
}

/** Alterações do painel de usuários. Contas novas vêm do autocadastro, não daqui. */
export interface LoteUsuarios {
  atualizacoes: Array<Partial<EdicaoUsuario> & { id: string }>
  exclusoes: string[]
}

export const usuarioService = {
  listar(filtros: FiltrosUsuarios = {}): Promise<Usuario[]> {
    const query = montarQuery({
      busca: filtros.busca?.trim() || undefined,
      perfil: filtros.perfil,
      situacao: filtros.situacao,
      limite: filtros.limite,
      pagina: filtros.pagina,
    })
    return http.get<Usuario[]>(`/usuarios${query}`)
  },

  resumir(filtros: Pick<FiltrosUsuarios, 'busca' | 'perfil' | 'situacao'> = {}): Promise<ResumoUsuarios> {
    const query = montarQuery({
      busca: filtros.busca?.trim() || undefined,
      perfil: filtros.perfil,
      situacao: filtros.situacao,
    })
    return http.get<ResumoUsuarios>(`/usuarios/resumo${query}`)
  },

  listarSegurancas(): Promise<Usuario[]> {
    return http.get<Usuario[]>('/usuarios/segurancas')
  },

  listarTecnicos(): Promise<Usuario[]> {
    return http.get<Usuario[]>('/usuarios/tecnicos')
  },

  atualizar(id: string, dados: Partial<EdicaoUsuario>): Promise<Usuario> {
    return http.put<Usuario>(`/usuarios/${id}`, dados)
  },

  excluir(id: string): Promise<void> {
    return http.delete<void>(`/usuarios/${id}`)
  },

  /** Reativa uma conta desativada; ela volta com o mesmo perfil, e-mail e senha. */
  reativar(id: string): Promise<Usuario> {
    return http.post<Usuario>(`/usuarios/${id}/reativar`)
  },

  reenviarVerificacao(id: string): Promise<{ mensagem: string }> {
    return http.post<{ mensagem: string }>(`/usuarios/${id}/reenviar-verificacao`)
  },

  salvarLote(dados: LoteUsuarios): Promise<{ atualizadas: number; excluidas: number }> {
    return http.post('/usuarios/lote', dados)
  },
}
