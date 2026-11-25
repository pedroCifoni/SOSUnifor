import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

/**
 * "Voltar" que nunca prende o usuário: volta uma página no histórico do app e, se esta for
 * a primeira página aberta (link direto, nova aba, recarregar), vai para `destinoPadrao`.
 *
 * Use no lugar de um <Link> fixo para a página anterior: um link fixo empilha uma página nova,
 * e o "voltar" dela traz de volta a página de onde se saiu (ida e volta sem fim).
 */
export function useVoltar(destinoPadrao: string) {
  const navigate = useNavigate()
  const { key } = useLocation()

  return useCallback(() => {
    // O React Router dá a chave "default" à primeira entrada do histórico desta aba.
    if (key === 'default') navigate(destinoPadrao, { replace: true })
    else navigate(-1)
  }, [key, navigate, destinoPadrao])
}
