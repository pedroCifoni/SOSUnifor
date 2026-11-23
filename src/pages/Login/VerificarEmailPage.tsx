import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader2, MailX } from 'lucide-react'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'
import { CartaoAcesso } from './CartaoAcesso'
import { ReenviarConfirmacao } from './ReenviarConfirmacao'

function lerTokenDaUrl(): string {
  return new URLSearchParams(window.location.search).get('token') ?? ''
}

export function VerificarEmailPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [token] = useState(lerTokenDaUrl)
  const [erro, setErro] = useState<string | null>(token ? null : 'Este link de confirmação está incompleto.')
  // O link é de uso único: no modo estrito do React o efeito roda duas vezes, e a segunda chamada falharia.
  const jaEnviado = useRef(false)

  useEffect(() => {
    if (!token || jaEnviado.current) return
    jaEnviado.current = true
    // Tira o token da barra de endereço, para ele não ficar no histórico do navegador.
    window.history.replaceState(null, '', window.location.pathname)
    authService
      .verificarEmail(token)
      .then((resposta) => {
        toast.sucesso(resposta.mensagem)
        navigate('/login', { replace: true })
      })
      .catch((err: unknown) => {
        setErro(err instanceof Error ? err.message : 'Não foi possível confirmar o e-mail.')
      })
  }, [token, toast, navigate])

  if (!erro) {
    return (
      <CartaoAcesso titulo="Confirmando e-mail" descricao="Só um instante">
        <div className="flex justify-center py-4 text-brand-500" role="status" aria-live="polite">
          <Loader2 size={32} className="animate-spin" aria-hidden />
          <span className="sr-only">Confirmando o seu e-mail…</span>
        </div>
      </CartaoAcesso>
    )
  }

  return (
    <CartaoAcesso titulo="Link inválido" descricao="Não foi possível confirmar o seu e-mail">
      <div className="space-y-6">
        <div className="space-y-3 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sos-50 text-sos-700">
            <MailX size={28} />
          </div>
          <p className="text-sm text-brand-900">{erro}</p>
          <p className="text-xs text-muted">Informe o seu e-mail para receber um novo link de confirmação.</p>
        </div>
        <ReenviarConfirmacao />
      </div>

      <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-brand-500 hover:text-brand-900">
        <ArrowLeft size={16} /> Voltar para o login
      </Link>
    </CartaoAcesso>
  )
}
