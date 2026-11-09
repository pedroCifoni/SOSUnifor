import { http } from '@/api/client'
import type { NovaOcorrencia, Ocorrencia, StatusOcorrencia } from '@/models/ocorrencia'

async function enviarAnexos(arquivos: File[] | undefined) {
  if (!arquivos?.length) return []
  return Promise.all(arquivos.map((arquivo) => http.enviarArquivo('/arquivos', arquivo)))
}

export const ocorrenciaService = {
  listar(): Promise<Ocorrencia[]> {
    return http.get<Ocorrencia[]>('/ocorrencias')
  },

  listarPorAutor(_autorId: string): Promise<Ocorrencia[]> {
    return http.get<Ocorrencia[]>('/ocorrencias')
  },

  listarPorResponsavel(_responsavelId: string): Promise<Ocorrencia[]> {
    return http.get<Ocorrencia[]>('/ocorrencias')
  },

  buscarPorId(id: string): Promise<Ocorrencia> {
    return http.get<Ocorrencia>(`/ocorrencias/${id}`)
  },

  async criar(dados: NovaOcorrencia): Promise<Ocorrencia> {
    const anexos = await enviarAnexos(dados.anexos)
    return http.post<Ocorrencia>('/ocorrencias', { ...dados, anexos })
  },

  encaminhar(id: string, responsavelId: string): Promise<Ocorrencia> {
    return http.patch<Ocorrencia>(`/ocorrencias/${id}/encaminhar`, { responsavelId })
  },

  atualizarStatus(id: string, status: StatusOcorrencia): Promise<Ocorrencia> {
    return http.patch<Ocorrencia>(`/ocorrencias/${id}/status`, { status })
  },
}
