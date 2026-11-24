import { http } from '@/api/client'
import type { DadosUsuario, Perfil, Usuario } from '@/models/usuario'
import { montarQuery } from '@/services/paginacao'

export interface FiltrosUsuarios {
  busca?: string
  perfil?: Perfil
  limite?: number
  pagina?: number
}

export interface ResumoUsuarios {
  total: number
}

export interface LoteUsuarios {
  criacoes: DadosUsuario[]
  atualizacoes: Array<Partial<DadosUsuario> & { id: string }>
  exclusoes: string[]
}

export const usuarioService = {
  listar(filtros: FiltrosUsuarios = {}): Promise<Usuario[]> {
    const query = montarQuery({
      busca: filtros.busca?.trim() || undefined,
      perfil: filtros.perfil,
      limite: filtros.limite,
      pagina: filtros.pagina,
    })
    return http.get<Usuario[]>(`/usuarios${query}`)
  },

  resumir(filtros: Pick<FiltrosUsuarios, 'busca' | 'perfil'> = {}): Promise<ResumoUsuarios> {
    const query = montarQuery({
      busca: filtros.busca?.trim() || undefined,
      perfil: filtros.perfil,
    })
    return http.get<ResumoUsuarios>(`/usuarios/resumo${query}`)
  },

  listarSegurancas(): Promise<Usuario[]> {
    return http.get<Usuario[]>('/usuarios/segurancas')
  },

  listarTecnicos(): Promise<Usuario[]> {
    return http.get<Usuario[]>('/usuarios/tecnicos')
  },

  criar(dados: DadosUsuario): Promise<Usuario> {
    return http.post<Usuario>('/usuarios', dados)
  },

  atualizar(id: string, dados: Partial<DadosUsuario>): Promise<Usuario> {
    return http.put<Usuario>(`/usuarios/${id}`, dados)
  },

  excluir(id: string): Promise<void> {
    return http.delete<void>(`/usuarios/${id}`)
  },

  reenviarVerificacao(id: string): Promise<{ mensagem: string }> {
    return http.post<{ mensagem: string }>(`/usuarios/${id}/reenviar-verificacao`)
  },

  salvarLote(dados: LoteUsuarios): Promise<{ criadas: number; atualizadas: number; excluidas: number; idsCriados: string[] }> {
    return http.post('/usuarios/lote', dados)
  },
}
