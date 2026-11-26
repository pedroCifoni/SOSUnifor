import { http } from '@/api/client'
import { API_URL } from '@/api/config'
import type { Credenciais, DadosCadastro, LoginResponse } from '@/models/usuario'

interface MensagemResposta {
  mensagem: string
}

/** Chamadas de sessão sem o interceptador de 401 do cliente (que dispararia o próprio logout). */
async function postarSessao(caminho: string, refreshToken: string): Promise<Response> {
  return fetch(`${API_URL}${caminho}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
}

export const authService = {
  login(credenciais: Credenciais): Promise<LoginResponse> {
    return http.post<LoginResponse>('/auth/login', credenciais)
  },

  /** Troca o refresh token por um par novo (o antigo deixa de valer). Devolve null se a sessão acabou. */
  async renovar(refreshToken: string): Promise<LoginResponse | null> {
    const resposta = await postarSessao('/auth/renovar', refreshToken)
    if (resposta.status === 401) return null
    if (!resposta.ok) throw new Error(`Erro ${resposta.status}`)
    return resposta.json()
  },

  async logout(refreshToken: string): Promise<void> {
    await postarSessao('/auth/logout', refreshToken).catch(() => undefined)
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
