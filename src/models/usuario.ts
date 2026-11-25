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
  /** Só na visão do admin: false para contas desativadas (lista "Desativadas"). */
  ativo?: boolean
}

/** O que o administrador pode alterar numa conta. E-mail e senha são do titular. */
export interface EdicaoUsuario {
  nome: string
  perfil: Perfil
}

/** Formulário do autocadastro (o perfil não é escolhido: toda conta nova é "usuario"). */
export interface DadosCadastro {
  nome: string
  email: string
  senha: string
  versaoTermos: string
}

export interface Credenciais {
  email: string
  senha: string
}

export interface LoginResponse {
  token: string
}
