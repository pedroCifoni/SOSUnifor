import { http } from '@/api/client'

export interface SituacaoPrivacidade {
  versaoVigente: string
  versaoCiente: string | null
  cienteEm: string | null
  pendente: boolean
}

export const privacidadeService = {
  situacao(): Promise<SituacaoPrivacidade> {
    return http.get<SituacaoPrivacidade>('/privacidade/situacao')
  },

  registrarCiencia(versao: string): Promise<SituacaoPrivacidade> {
    return http.post<SituacaoPrivacidade>('/privacidade/ciencia', { versao })
  },
}
