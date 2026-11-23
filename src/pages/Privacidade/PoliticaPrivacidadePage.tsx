import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import { TextoComPendencias } from '@/components/ui/TextoComPendencias'
import { useAuth } from '@/hooks/useAuth'
import { SECOES_POLITICA, VERSAO_POLITICA } from './politicaPrivacidade'

function dataDaVersao(versao: string) {
  const [ano, mes, dia] = versao.split('-')
  return `${dia}/${mes}/${ano}`
}

/** Página pública: pode ser lida antes do login e a partir do aviso de privacidade. */
export function PoliticaPrivacidadePage() {
  const { usuario } = useAuth()
  const navigate = useNavigate()

  function voltar() {
    if (window.history.length > 1) navigate(-1)
    else navigate(usuario ? '/' : '/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-surface px-4 py-6 sm:py-10">
      <article className="mx-auto w-full max-w-2xl rounded-3xl border border-line bg-white p-6 shadow-sm sm:p-10">
        <button
          type="button"
          onClick={voltar}
          className="-ml-2 mb-4 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-brand-500 hover:bg-brand-50"
        >
          <ArrowLeft size={16} /> Voltar
        </button>

        <header className="mb-8 flex items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-500">
            <ShieldCheck size={22} />
          </span>
          <div>
            <h1 className="text-2xl font-bold text-brand-900">Política de Privacidade</h1>
            <p className="mt-1 text-sm text-muted">Uni SOS · versão de {dataDaVersao(VERSAO_POLITICA)}</p>
          </div>
        </header>

        <div className="space-y-7">
          {SECOES_POLITICA.map((secao) => (
            <section key={secao.titulo}>
              <h2 className="mb-2 text-base font-semibold text-brand-900">{secao.titulo}</h2>
              {secao.paragrafos?.map((paragrafo) => (
                <p key={paragrafo} className="mb-2 text-sm leading-relaxed text-ink">
                  <TextoComPendencias texto={paragrafo} />
                </p>
              ))}
              {secao.itens && (
                <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink marker:text-brand-500">
                  {secao.itens.map((item) => (
                    <li key={item}>
                      <TextoComPendencias texto={item} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>

        {!usuario && (
          <p className="mt-10 text-center text-sm">
            <Link to="/login" className="font-semibold text-brand-500 hover:text-brand-900">
              Ir para o login
            </Link>
          </p>
        )}
      </article>
    </div>
  )
}
