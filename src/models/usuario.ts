export type Perfil = 'usuario' | 'seguranca' | 'tecnico' | 'admin'

export const PERFIL_LABEL: Record<Perfil, string> = {
  usuario: 'Usuário',
  seguranca: 'Segurança',
  tecnico: 'Técnico de Informática',
  admin: 'Administrador',
}

export interface Usuario {
  id: string
  nome: string
  email: string
  perfil: Perfil
  /** Só na visão do admin (GET /usuarios e respostas do cadastro); ausente nas listas públicas e no token. */
  emailVerificado?: boolean
}

export interface DadosUsuario {
  nome: string
  email: string
  perfil: Perfil
  senha?: string
}

export interface Credenciais {
  email: string
  senha: string
}

export interface LoginResponse {
  token: string
}
