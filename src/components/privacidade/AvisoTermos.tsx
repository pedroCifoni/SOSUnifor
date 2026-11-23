import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ShieldCheck, Siren } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { VERSAO_TERMOS } from '@/models/privacidade'
import { privacidadeService } from '@/services/privacidadeService'

/**
 * Pede a ciência da Política de Privacidade quando a versão aceita é diferente da vigente.
 *
 * Decisão (LGPD, art. 7º, VII - proteção da vida): o aviso NUNCA impede um pedido de socorro.
 * - Na tela de um SOS em andamento (/sos/:id) o aviso não aparece.
 * - O usuário pode tocar em "Emergência? Acionar o SOS agora": o aviso sai da frente na tela principal
 *   (onde fica o botão de SOS) e volta a aparecer nas demais telas até ser aceito.
 * - O back-end não exige o aceite em nenhuma rota; o bloqueio é só de interface.
 */
export function AvisoTermos() {
  const { usuario } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [pendente, setPendente] = useState(false)
  const [adiadoPorEmergencia, setAdiadoPorEmergencia] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const usuarioId = usuario?.id

  useEffect(() => {
    setPendente(false)
    setAdiadoPorEmergencia(false)
    if (!usuarioId) return
    let ativo = true
    // Se a consulta falhar, o sistema segue liberado: um erro de rede não pode trancar ninguém fora.
    privacidadeService
      .situacaoTermos()
      .then((situacao) => ativo && setPendente(situacao.pendente))
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [usuarioId])

  if (!usuario || !pendente) return null

  const telaDeEmergencia = pathname.startsWith('/sos/')
  const podeAcionarSos = usuario.perfil === 'usuario'
  const oculto = telaDeEmergencia || (adiadoPorEmergencia && pathname === '/')

  async function aceitar() {
    setEnviando(true)
    try {
      await privacidadeService.aceitarTermos(VERSAO_TERMOS)
      setPendente(false)
      toast.sucesso('Obrigado! Sua ciência da Política de Privacidade foi registrada.')
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível registrar. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  function irParaSos() {
    setAdiadoPorEmergencia(true)
    navigate('/')
  }

  if (oculto) {
    if (telaDeEmergencia) return null
    return (
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 p-3 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <ShieldCheck size={18} className="shrink-0 text-brand-500" />
          <p className="flex-1 text-xs text-ink">Quando puder, leia e aceite a Política de Privacidade.</p>
          <button
            onClick={() => setAdiadoPorEmergencia(false)}
            className="rounded-lg bg-brand-900 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-700"
          >
            Ler agora
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-aviso-termos"
        className="max-h-[90vh] w-full max-w-md space-y-4 overflow-y-auto rounded-3xl bg-white p-6 shadow-xl"
      >
        <span className="mx-auto grid size-12 place-items-center rounded-full bg-brand-50 text-brand-500">
          <ShieldCheck size={24} />
        </span>
        <div className="space-y-2 text-center">
          <h2 id="titulo-aviso-termos" className="text-base font-bold text-brand-900">
            Privacidade dos seus dados
          </h2>
          <p className="text-sm text-muted">Antes de continuar, veja como o Uni SOS usa os seus dados pessoais:</p>
        </div>
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink">
          <li>Usamos nome, e-mail e perfil para o seu acesso ao sistema.</li>
          <li>A localização (GPS) é usada somente quando você aciona o SOS.</li>
          <li>Chamados, denúncias e anexos são vistos apenas pela equipe que atende e pela administração.</li>
          <li>Você pode baixar uma cópia dos seus dados ou pedir a exclusão deles em Meu Perfil.</li>
        </ul>
        <Link to="/privacidade" className="block text-center text-sm font-semibold text-brand-500 underline hover:text-brand-900">
          Ler a Política de Privacidade completa
        </Link>
        <button
          onClick={() => void aceitar()}
          disabled={enviando}
          className="h-12 w-full rounded-xl bg-brand-900 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
        >
          {enviando ? 'Aguarde…' : 'Li e aceito'}
        </button>
        {podeAcionarSos && (
          <button
            onClick={irParaSos}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-xl border border-sos-200 text-sm font-semibold text-sos-700 hover:bg-sos-50"
          >
            <Siren size={18} /> Emergência? Acionar o SOS agora
          </button>
        )}
      </div>
    </div>
  )
}
