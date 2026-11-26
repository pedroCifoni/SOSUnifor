import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Lock, Mail, MailCheck, User } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/hooks/useAuth'
import { VERSAO_TERMOS } from '@/models/privacidade'
import { authService } from '@/services/authService'
import {
  DOMINIO_INSTITUCIONAL,
  TAMANHO_MAXIMO_SENHA,
  TAMANHO_MINIMO_SENHA,
  normalizarEmail,
  problemaNaSenha,
  problemaNoEmailInstitucional,
} from '@/utils/emailInstitucional'
import { CartaoAcesso } from './CartaoAcesso'
import { ReenviarConfirmacao } from './ReenviarConfirmacao'

/** Autocadastro com e-mail @edu.unifor.br. A conta nasce com o perfil "usuario" e precisa confirmar o e-mail. */
export function CadastroPage() {
  const { usuario } = useAuth()
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [cienteDaPolitica, setCienteDaPolitica] = useState(false)
  const [tentouEnviar, setTentouEnviar] = useState(false)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [enviadoPara, setEnviadoPara] = useState<{ email: string; mensagem: string } | null>(null)

  if (usuario) return <Navigate to="/" replace />

  const nomeLimpo = nome.trim().replace(/\s+/g, ' ')
  const problemaNome = nomeLimpo.length < 3 || !/\p{L}/u.test(nomeLimpo) ? 'Informe o seu nome.' : null
  const problemaEmail = problemaNoEmailInstitucional(email)
  const problemaSenha = problemaNaSenha(senha, email)
  const problemaConfirmacao = senha !== confirmacao ? 'As senhas não são iguais.' : null
  const problemaPolitica = cienteDaPolitica ? null : 'Confirme que leu a Política de Privacidade.'
  const formularioValido = !problemaNome && !problemaEmail && !problemaSenha && !problemaConfirmacao && !problemaPolitica

  // Mostra os erros de cada campo só depois que a pessoa mexeu nele, ou ao tentar enviar.
  const erroDe = (valor: string, problema: string | null) => ((tentouEnviar || valor) && problema) || undefined

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setTentouEnviar(true)
    setErro(null)
    if (!formularioValido) return
    setCarregando(true)
    try {
      const destino = normalizarEmail(email)
      const resposta = await authService.cadastrar({ nome: nomeLimpo, email: destino, senha, versaoTermos: VERSAO_TERMOS })
      // Não guarda a senha na tela depois do envio.
      setSenha('')
      setConfirmacao('')
      setEnviadoPara({ email: destino, mensagem: resposta.mensagem })
    } catch (err) {
      setErro(err instanceof Error ? err.message : 'Não foi possível criar a conta. Tente novamente.')
    } finally {
      setCarregando(false)
    }
  }

  if (enviadoPara) {
    return (
      <CartaoAcesso titulo="Confirme o seu e-mail" descricao="Falta só um passo para ativar a conta">
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-2xl bg-brand-50 p-4 text-sm text-brand-900" role="status">
            <MailCheck size={20} className="mt-0.5 shrink-0 text-brand-500" aria-hidden />
            <div className="space-y-2">
              <p>{enviadoPara.mensagem}</p>
              <p className="text-xs text-muted">
                Verifique a caixa de entrada de <strong className="break-all text-brand-900">{enviadoPara.email}</strong>{' '}
                (e o spam). O link vale por 48 horas.
              </p>
            </div>
          </div>
          <p className="text-center text-xs text-muted">Não chegou?</p>
          <ReenviarConfirmacao email={enviadoPara.email} />
          <Link
            to="/login"
            className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-brand-900 px-4 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
          >
            Ir para o login
          </Link>
        </div>
      </CartaoAcesso>
    )
  }

  const botaoMostrarSenha = (
    <button
      type="button"
      aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}
      onClick={() => setMostrarSenha((v) => !v)}
      className="text-muted hover:text-brand-900"
    >
      {mostrarSenha ? <EyeOff size={18} /> : <Eye size={18} />}
    </button>
  )

  return (
    <CartaoAcesso titulo="Criar conta" descricao={`Use o seu e-mail institucional @${DOMINIO_INSTITUCIONAL}`}>
      <form onSubmit={enviar} className="space-y-4" noValidate>
        <Campo erro={erroDe(nome, problemaNome)}>
          <Input
            label="Nome completo"
            autoComplete="name"
            icon={<User size={18} />}
            value={nome}
            maxLength={150}
            onChange={(e) => setNome(e.target.value)}
            aria-invalid={Boolean(erroDe(nome, problemaNome))}
            required
          />
        </Campo>
        <Campo erro={erroDe(email, problemaEmail)}>
          <Input
            label="E-mail institucional"
            type="email"
            autoComplete="email"
            inputMode="email"
            placeholder={`nome.sobrenome@${DOMINIO_INSTITUCIONAL}`}
            icon={<Mail size={18} />}
            value={email}
            maxLength={150}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={Boolean(erroDe(email, problemaEmail))}
            required
          />
        </Campo>
        <Campo erro={erroDe(senha, problemaSenha)} dica={`Mínimo de ${TAMANHO_MINIMO_SENHA} caracteres.`}>
          <Input
            label="Senha"
            type={mostrarSenha ? 'text' : 'password'}
            autoComplete="new-password"
            icon={<Lock size={18} />}
            value={senha}
            maxLength={TAMANHO_MAXIMO_SENHA}
            onChange={(e) => setSenha(e.target.value)}
            aria-invalid={Boolean(erroDe(senha, problemaSenha))}
            trailing={botaoMostrarSenha}
            required
          />
        </Campo>
        <Campo erro={erroDe(confirmacao, problemaConfirmacao)}>
          <Input
            label="Confirme a senha"
            type={mostrarSenha ? 'text' : 'password'}
            autoComplete="new-password"
            icon={<Lock size={18} />}
            value={confirmacao}
            maxLength={TAMANHO_MAXIMO_SENHA}
            onChange={(e) => setConfirmacao(e.target.value)}
            aria-invalid={Boolean(erroDe(confirmacao, problemaConfirmacao))}
            required
          />
        </Campo>

        <div>
          <label className="flex cursor-pointer items-start gap-2 text-xs text-ink">
            <input
              type="checkbox"
              checked={cienteDaPolitica}
              onChange={(e) => setCienteDaPolitica(e.target.checked)}
              className="mt-0.5 size-4 shrink-0 accent-brand-900"
            />
            <span>
              Li e estou ciente da{' '}
              <Link to="/privacidade" target="_blank" rel="noopener" className="font-semibold text-brand-500 underline hover:text-brand-900">
                Política de Privacidade
              </Link>
              .
            </span>
          </label>
          {tentouEnviar && problemaPolitica && <p className="mt-1 text-xs text-sos-700">{problemaPolitica}</p>}
        </div>

        {erro && (
          <p role="alert" className="rounded-lg bg-sos-50 px-3 py-2 text-sm text-sos-700">
            {erro}
          </p>
        )}

        <Button type="submit" loading={carregando}>
          Criar conta
        </Button>
      </form>

      <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-brand-500 hover:text-brand-900">
        <ArrowLeft size={16} /> Já tenho conta
      </Link>
    </CartaoAcesso>
  )
}

function Campo({ erro, dica, children }: { erro?: string; dica?: string; children: ReactNode }) {
  return (
    <div>
      {children}
      {erro ? (
        <p className="mt-1 text-xs text-sos-700">{erro}</p>
      ) : (
        dica && <p className="mt-1 text-xs text-muted">{dica}</p>
      )}
    </div>
  )
}
