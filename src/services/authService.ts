import { http } from '@/api/client'
import type { Credenciais, DadosCadastro, LoginResponse } from '@/models/usuario'

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

  /** Autocadastro: a resposta é sempre a mesma, exista ou não conta com o e-mail. */
  cadastrar(dados: DadosCadastro): Promise<MensagemResposta> {
    return http.post<MensagemResposta>('/auth/cadastro', {
      nome: dados.nome,
      email: dados.email,
      senha: dados.senha,
      versao_termos: dados.versaoTermos,
    })
  },

  /** A confirmação exige a senha da conta, além do link recebido por e-mail. */
  verificarEmail(token: string, senha: string): Promise<MensagemResposta> {
    return http.post<MensagemResposta>('/auth/verificar-email', { token, senha })
  },

  reenviarVerificacao(email: string): Promise<MensagemResposta> {
    return http.post<MensagemResposta>('/auth/reenviar-verificacao', { email })
  },
}
