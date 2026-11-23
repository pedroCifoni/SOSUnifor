import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ExternalLink, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { RESUMO_POLITICA, VERSAO_POLITICA } from '@/pages/Privacidade/politicaPrivacidade'
import { privacidadeService } from '@/services/privacidadeService'

/**
 * Aviso de privacidade exibido no primeiro acesso e sempre que a política mudar de versão.
 * O tratamento não se baseia em consentimento; aqui o usuário declara ciência (LGPD, art. 9º),
 * e o backend guarda a versão e a data.
 */
export function AvisoPrivacidade() {
  const { usuario, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [pendente, setPendente] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const usuarioId = usuario?.id

  useEffect(() => {
    if (!usuarioId) return
    let ativo = true
    // Se a consulta falhar, o aviso não bloqueia o uso (o SOS precisa continuar acessível); volta no próximo acesso.
    privacidadeService
      .situacao()
      .then((situacao) => ativo && setPendente(situacao.pendente))
      .catch(() => ativo && setPendente(false))
    return () => {
      ativo = false
    }
  }, [usuarioId])

  if (!pendente) return null

  async function confirmar() {
    setEnviando(true)
    try {
      const situacao = await privacidadeService.registrarCiencia(VERSAO_POLITICA)
      setPendente(situacao.pendente)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível registrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  function sair() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-end bg-black/50 sm:place-items-center sm:p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="aviso-privacidade-titulo"
        className="max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white p-6 shadow-xl sm:max-w-md sm:rounded-3xl"
      >
        <span className="mb-3 grid size-12 place-items-center rounded-xl bg-brand-50 text-brand-500">
          <ShieldCheck size={24} />
        </span>
        <h2 id="aviso-privacidade-titulo" className="text-lg font-bold text-brand-900">
          Sua privacidade no Uni SOS
        </h2>
        <p className="mt-1 text-sm text-muted">Antes de continuar, veja como usamos seus dados pessoais:</p>

        <ul className="mt-4 space-y-2.5 text-sm leading-relaxed text-ink">
          {RESUMO_POLITICA.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brand-500" />
              {item}
            </li>
          ))}
        </ul>

        <Link
          to="/privacidade"
          target="_blank"
          rel="noopener"
          className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-500 hover:text-brand-900"
        >
          Ler a Política de Privacidade completa <ExternalLink size={14} />
        </Link>

        <div className="mt-6 space-y-2">
          <Button onClick={confirmar} loading={enviando}>
            Li e estou ciente
          </Button>
          <button
            type="button"
            onClick={sair}
            className="h-11 w-full rounded-xl text-sm font-semibold text-muted hover:bg-surface"
          >
            Sair
          </button>
        </div>
      </div>
    </div>
  )
}
