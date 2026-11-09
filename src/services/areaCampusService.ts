import { http } from '@/api/client'
import type { AreaCampus, DadosAreaCampus, LocalizacaoIdentificada } from '@/models/areaCampus'

export const areaCampusService = {
  listar(): Promise<AreaCampus[]> {
    return http.get<AreaCampus[]>('/areas-campus')
  },

  criar(dados: DadosAreaCampus): Promise<AreaCampus> {
    return http.post<AreaCampus>('/areas-campus', dados)
  },

  atualizar(id: string, dados: DadosAreaCampus): Promise<AreaCampus> {
    return http.put<AreaCampus>(`/areas-campus/${id}`, dados)
  },

  excluir(id: string): Promise<void> {
    return http.delete<void>(`/areas-campus/${id}`)
  },

  identificar(latitude: number, longitude: number): Promise<LocalizacaoIdentificada> {
    return http.post<LocalizacaoIdentificada>('/areas-campus/identificar', { latitude, longitude })
  },
}
