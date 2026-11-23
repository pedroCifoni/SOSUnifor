import { useCallback, useEffect, useState } from 'react'
import type { ResumoOcorrencias } from '@/models/ocorrencia'
import { ocorrenciaService } from '@/services/ocorrenciaService'

/** Contadores das ocorrências visíveis ao usuário, calculados no banco (GET /ocorrencias/resumo). */
export function useResumoOcorrencias(revisao?: unknown, habilitado = true) {
  const [resumo, setResumo] = useState<ResumoOcorrencias | null>(null)

  const recarregar = useCallback(async () => {
    if (!habilitado) return
    try {
      setResumo(await ocorrenciaService.resumo())
    } catch {
      // Mantém o último resumo conhecido; a próxima atualização tenta de novo.
    }
  }, [habilitado])

  useEffect(() => {
    void recarregar()
  }, [recarregar, revisao])

  return { resumo, recarregar }
}
