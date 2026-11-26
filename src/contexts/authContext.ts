import { createContext } from 'react'
import type { Credenciais, Usuario } from '@/models/usuario'

export interface AuthContextValue {
  usuario: Usuario | null
  expiraEm: number | null
  login: (credenciais: Credenciais) => Promise<Usuario>
  logout: () => void
  /** Renova o access token com o refresh token (ex.: para o nome novo aparecer depois de editar o perfil). */
  renovarSessao: () => Promise<boolean>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
