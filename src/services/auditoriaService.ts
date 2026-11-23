import { http } from '@/api/client'
import type { FiltrosAuditoria, RegistroAuditoria } from '@/models/auditoria'
import { montarQuery } from './paginacao'

export const auditoriaService = {
  /** Trilha de auditoria (só admin), paginada por cursor, mais recentes primeiro. */
  listar(filtros: FiltrosAuditoria = {}): Promise<RegistroAuditoria[]> {
    const query = montarQuery({
      limite: filtros.limite,
      antes_de: filtros.antesDe,
      antes_id: filtros.antesId,
      tipo: filtros.tipo,
      desde: filtros.desde,
      ate: filtros.ate,
    })
    return http.get<RegistroAuditoria[]>(`/auditoria${query}`)
  },
}
