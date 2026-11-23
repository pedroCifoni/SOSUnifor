import { http } from '@/api/client'
import type {
  FiltrosOcorrencias,
  NovaOcorrencia,
  Ocorrencia,
  ResumoOcorrencias,
  StatusOcorrencia,
} from '@/models/ocorrencia'
import { montarQuery } from './paginacao'

async function enviarAnexos(arquivos: File[] | undefined) {
  if (!arquivos?.length) return []
  return Promise.all(arquivos.map((arquivo) => http.enviarArquivo('/arquivos', arquivo)))
}

export const ocorrenciaService = {
  /** Lista as ocorrências visíveis ao usuário logado (paginada por cursor, mais recentes primeiro). */
  listar(filtros: FiltrosOcorrencias = {}): Promise<Ocorrencia[]> {
    const query = montarQuery({
      limite: filtros.limite,
      antes_de: filtros.antesDe,
      antes_id: filtros.antesId,
      status: filtros.status,
      tipo: filtros.tipo,
    })
    return http.get<Ocorrencia[]>(`/ocorrencias${query}`)
  },

  /** Contagens por status e por tipo das ocorrências visíveis ao usuário logado. */
  resumo(): Promise<ResumoOcorrencias> {
    return http.get<ResumoOcorrencias>('/ocorrencias/resumo')
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
