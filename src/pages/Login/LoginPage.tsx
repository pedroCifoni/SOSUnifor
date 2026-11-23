import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, Mail, MailWarning } from 'lucide-react'
import { ErroApi } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { ReenviarConfirmacao } from './ReenviarConfirmacao'

export function LoginPage() {
  const { usuario, login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [carregando, setCarregando] = useState(false)
  // E-mail cuja senha conferiu, mas que ainda não foi confirmado: mostra o aviso e o reenvio.
  const [emailNaoConfirmado, setEmailNaoConfirmado] = useState<string | null>(null)

  if (usuario) return <Navigate to={usuario.perfil === 'admin' ? '/admin' : '/'} replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setCarregando(true)
    try {
      const logado = await login({ email, senha })
      navigate(logado.perfil === 'admin' ? '/admin' : '/', { replace: true })
    } catch (err) {
      if (err instanceof ErroApi && err.codigo === 'email_nao_verificado') {
        setEmailNaoConfirmado(email.trim())
      } else {
        setEmailNaoConfirmado(null)
        toast.erro(err instanceof Error ? err.message : 'Não foi possível entrar.')
      }
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-b from-brand-50 to-surface px-4 py-8">
      <div className="w-full max-w-md rounded-3xl border border-line bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src="/unifor-logo-vertical.svg" alt="UNIFOR" className="mb-4 h-20" />
          <h1 className="mt-1 text-2xl font-bold text-brand-900">Central de Reportes</h1>
          <p className="mt-1 text-sm text-muted">Gestão de ocorrências e segurança no campus</p>
        </div>

        <form onSubmit={enviar} className="space-y-4" noValidate>
          <Input
            label="E-mail Institucional"
            type="email"
            autoComplete="username"
            placeholder="nome.sobrenome@unifor.br"
            icon={<Mail size={18} />}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value)
              setEmailNaoConfirmado(null)
            }}
            required
          />
          <Input
            label="Senha"
            type={mostrarSenha ? 'text' : 'password'}
            autoComplete="current-password"
            placeholder="••••••••"
            icon={<Lock size={18} />}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
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

          <div className="-mt-1 text-right">
            <Link to="/esqueci-senha" className="text-xs font-semibold text-brand-500 hover:text-brand-900">
              Esqueci minha senha
            </Link>
          </div>

          <Button type="submit" loading={carregando} disabled={!email || !senha}>
            Entrar
          </Button>
        </form>

        {emailNaoConfirmado && (
          <section className="mt-4 space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-4" role="alert">
            <div className="flex items-start gap-2 text-sm text-amber-800">
              <MailWarning size={18} className="mt-0.5 shrink-0" aria-hidden />
              <div>
                <p className="font-semibold">Confirme o seu e-mail para entrar</p>
                <p className="mt-1 text-xs">
                  Enviamos um link de confirmação para <strong className="break-all">{emailNaoConfirmado}</strong>. Abra o
                  e-mail e clique em “Confirmar e-mail”. Não encontrou? Peça um novo.
                </p>
              </div>
            </div>
            <ReenviarConfirmacao key={emailNaoConfirmado} email={emailNaoConfirmado} />
          </section>
        )}

        <p className="mt-6 text-center text-[11px] text-muted">
          Diretoria de Tecnologia da Informação · UNIFOR
          <br />
          <Link to="/privacidade" className="font-semibold text-brand-500 hover:text-brand-900">
            Política de Privacidade
          </Link>
        </p>
        <p className="mt-2 text-center text-[11px]">
          <Link to="/privacidade" className="font-semibold text-brand-500 hover:text-brand-900">
            Política de Privacidade
          </Link>
        </p>
      </div>
    </div>
  )
}
