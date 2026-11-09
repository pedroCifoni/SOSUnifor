import { http } from '@/api/client'
import type { Seguranca } from '@/models/seguranca'

export const segurancaService = {
  listarNotificados(): Promise<Seguranca[]> {
    return http.get<Seguranca[]>('/segurancas/notificadas')
  },
}
