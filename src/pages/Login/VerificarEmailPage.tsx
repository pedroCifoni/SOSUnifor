import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Lock, MailX } from 'lucide-react'
import { ErroApi } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'
import { CartaoAcesso } from './CartaoAcesso'
import { ReenviarConfirmacao } from './ReenviarConfirmacao'

function lerTokenDaUrl(): string {
  return new URLSearchParams(window.location.search).get('token') ?? ''
}

/**
 * Confirmação do e-mail. Além do link (que prova a posse do e-mail), pede a senha da conta: assim
 * ninguém consegue cadastrar o e-mail de outra pessoa com uma senha própria e esperar ela confirmar.
 */
export function VerificarEmailPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [token] = useState(lerTokenDaUrl)
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [carregando, setCarregando] = useState(false)
  // Senha errada: o link continua valendo e a pessoa pode tentar de novo.
  const [erroSenha, setErroSenha] = useState<string | null>(null)
  // Link inválido, vencido ou já usado: só um link novo resolve.
  const [erroLink, setErroLink] = useState<string | null>(token ? null : 'Este link de confirmação está incompleto.')

  // Tira o token da barra de endereço, para ele não ficar no histórico do navegador.
  useEffect(() => {
    if (token) window.history.replaceState(null, '', window.location.pathname)
  }, [token])

  async function confirmar(e: FormEvent) {
    e.preventDefault()
    if (!senha) return
    setCarregando(true)
    setErroSenha(null)
    try {
      const resposta = await authService.verificarEmail(token, senha)
      toast.sucesso(resposta.mensagem)
      navigate('/login', { replace: true })
    } catch (err) {
      const mensagem = err instanceof Error ? err.message : 'Não foi possível confirmar o e-mail.'
      if (err instanceof ErroApi && err.codigo === 'senha_nao_confere') setErroSenha(mensagem)
      else setErroLink(mensagem)
    } finally {
      setCarregando(false)
    }
  }

  if (erroLink) {
    return (
      <CartaoAcesso titulo="Link inválido" descricao="Não foi possível confirmar o seu e-mail">
        <div className="space-y-6">
          <div className="space-y-3 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-sos-50 text-sos-700">
              <MailX size={28} />
            </div>
            <p className="text-sm text-brand-900">{erroLink}</p>
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

  return (
    <CartaoAcesso titulo="Confirmar e-mail" descricao="Digite a senha que você escolheu ao criar a conta">
      <form onSubmit={confirmar} className="space-y-4" noValidate>
        <Input
          label="Senha"
          type={mostrarSenha ? 'text' : 'password'}
          autoComplete="current-password"
          icon={<Lock size={18} />}
          value={senha}
          onChange={(e) => {
            setSenha(e.target.value)
            setErroSenha(null)
          }}
          aria-invalid={Boolean(erroSenha)}
          autoFocus
          required
          trailing={
            <button
              type="button"
              aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
              onClick={() => setMostrarSenha((v) => !v)}
              className="text-muted hover:text-brand-900"
            >
              {mostrarSenha ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          }
        />
        {erroSenha && (
          <p role="alert" className="rounded-lg bg-sos-50 px-3 py-2 text-sm text-sos-700">
            {erroSenha}{' '}
            <Link to="/cadastro" className="font-semibold underline">
              Cadastrar de novo
            </Link>
          </p>
        )}
        <Button type="submit" loading={carregando} disabled={!senha}>
          Confirmar e-mail
        </Button>
      </form>

      <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-brand-500 hover:text-brand-900">
        <ArrowLeft size={16} /> Voltar para o login
      </Link>
    </CartaoAcesso>
  )
}
