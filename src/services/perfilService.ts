import { API_URL } from '@/api/config'
import { ErroApi, http } from '@/api/client'
import { tokenStorage } from '@/api/tokenStorage'
import type { Perfil } from '@/models/usuario'

export interface MeuPerfil {
  id: string
  nome: string
  email: string
  perfil: Perfil
  emailVerificadoEm: string | null
  ultimoAcesso: string | null
  temAvatar: boolean
}

async function enviarAvatar(arquivo: File): Promise<MeuPerfil> {
  const token = tokenStorage.get()
  const formulario = new FormData()
  formulario.append('arquivo', arquivo)
  const resposta = await fetch(`${API_URL}/me/avatar`, {
    method: 'PUT',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formulario,
  })
  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => null)
    throw new ErroApi(typeof erro?.detail === 'string' ? erro.detail : 'Não foi possível enviar a foto.', resposta.status)
  }
  return resposta.json()
}

export const perfilService = {
  consultar(): Promise<MeuPerfil> {
    return http.get<MeuPerfil>('/me')
  },

  atualizarNome(nome: string): Promise<MeuPerfil> {
    return http.put<MeuPerfil>('/me', { nome })
  },

  trocarSenha(senhaAtual: string, novaSenha: string): Promise<{ mensagem: string }> {
    return http.put<{ mensagem: string }>('/me/senha', { senha_atual: senhaAtual, nova_senha: novaSenha })
  },

  enviarAvatar,

  removerAvatar(): Promise<MeuPerfil> {
    return http.delete<MeuPerfil>('/me/avatar')
  },

  /** A foto exige o token, então vem como Blob e vira uma URL local (lembre de revogar). */
  async urlDoAvatar(): Promise<string> {
    const arquivo = await http.baixarArquivo(`${API_URL}/me/avatar`)
    return URL.createObjectURL(arquivo)
  },
}
