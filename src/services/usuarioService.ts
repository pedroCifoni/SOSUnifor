import { http } from '@/api/client'
import type { DadosUsuario, Usuario } from '@/models/usuario'

export interface LoteUsuarios {
  criacoes: DadosUsuario[]
  atualizacoes: Array<Partial<DadosUsuario> & { id: string }>
  exclusoes: string[]
}

export const usuarioService = {
  listar(): Promise<Usuario[]> {
    return http.get<Usuario[]>('/usuarios')
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

  salvarLote(dados: LoteUsuarios): Promise<{ criadas: number; atualizadas: number; excluidas: number }> {
    return http.post('/usuarios/lote', dados)
  },
}
