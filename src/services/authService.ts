import { http } from '@/api/client'
import type { Credenciais, LoginResponse } from '@/models/usuario'

interface MensagemResposta {
  mensagem: string
}

export const authService = {
  login(credenciais: Credenciais): Promise<LoginResponse> {
    return http.post<LoginResponse>('/auth/login', credenciais)
  },

  esqueciSenha(email: string): Promise<MensagemResposta> {
    return http.post<MensagemResposta>('/auth/esqueci-senha', { email })
  },

  redefinirSenha(token: string, novaSenha: string): Promise<MensagemResposta> {
    return http.post<MensagemResposta>('/auth/redefinir-senha', { token, nova_senha: novaSenha })
  },
}
