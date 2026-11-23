import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'
import { CartaoAcesso } from './CartaoAcesso'

const TAMANHO_MINIMO = 6

function lerTokenDaUrl(): string {
  return new URLSearchParams(window.location.search).get('token') ?? ''
}

export function RedefinirSenhaPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [token] = useState(lerTokenDaUrl)

  // Tira o token da barra de endereço, para ele não ficar no histórico do navegador.
  useEffect(() => {
    if (token) window.history.replaceState(null, '', window.location.pathname)
  }, [token])
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [carregando, setCarregando] = useState(false)

  const senhaCurta = senha.length > 0 && senha.length < TAMANHO_MINIMO
  const senhasDiferentes = confirmacao.length > 0 && senha !== confirmacao

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (senha.length < TAMANHO_MINIMO || senha !== confirmacao) return
    setCarregando(true)
    try {
      const resposta = await authService.redefinirSenha(token, senha)
      toast.sucesso(resposta.mensagem)
      navigate('/login', { replace: true })
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível alterar a senha.')
    } finally {
      setCarregando(false)
    }
  }

  if (!token) {
    return (
      <CartaoAcesso titulo="Link inválido" descricao="Este link de redefinição está incompleto ou já foi usado">
        <Link
          to="/esqueci-senha"
          className="inline-flex h-12 w-full items-center justify-center rounded-xl bg-brand-900 px-4 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
        >
          Pedir um novo link
        </Link>
      </CartaoAcesso>
    )
  }

  const alternarVisibilidade = (
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
    <CartaoAcesso titulo="Criar nova senha" descricao="Escolha uma senha que você não use em outros sites">
      <form onSubmit={enviar} className="space-y-4" noValidate>
        <Input
          label="Nova senha"
          type={mostrarSenha ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder={`Ao menos ${TAMANHO_MINIMO} caracteres`}
          icon={<Lock size={18} />}
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          required
          autoFocus
          trailing={alternarVisibilidade}
        />
        {senhaCurta && <p className="-mt-2 text-xs text-red-600">A senha deve ter ao menos {TAMANHO_MINIMO} caracteres.</p>}
        <Input
          label="Confirme a nova senha"
          type={mostrarSenha ? 'text' : 'password'}
          autoComplete="new-password"
          placeholder="Repita a senha"
          icon={<Lock size={18} />}
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          required
        />
        {senhasDiferentes && <p className="-mt-2 text-xs text-red-600">As senhas não conferem.</p>}
        <Button type="submit" loading={carregando} disabled={senha.length < TAMANHO_MINIMO || senha !== confirmacao}>
          Salvar nova senha
        </Button>
      </form>

      <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-brand-500 hover:text-brand-900">
        <ArrowLeft size={16} /> Voltar para o login
      </Link>
    </CartaoAcesso>
  )
}
