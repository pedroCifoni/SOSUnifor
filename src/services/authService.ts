import { http } from '@/api/client'
import type { Credenciais, LoginResponse } from '@/models/usuario'

export const authService = {
  login(credenciais: Credenciais): Promise<LoginResponse> {
    return http.post<LoginResponse>('/auth/login', credenciais)
  },
}
