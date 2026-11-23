import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Mail, MailCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'
import { CartaoAcesso } from './CartaoAcesso'

export function EsqueciSenhaPage() {
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [mensagem, setMensagem] = useState<string | null>(null)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setCarregando(true)
    try {
      const resposta = await authService.esqueciSenha(email.trim())
      setMensagem(resposta.mensagem)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível enviar o pedido.')
    } finally {
      setCarregando(false)
    }
  }

  return (
    <CartaoAcesso titulo="Esqueci minha senha" descricao="Enviaremos um link para você criar uma nova senha">
      {mensagem ? (
        <div className="space-y-6 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-brand-50 text-brand-500">
            <MailCheck size={28} />
          </div>
          <p className="text-sm text-brand-900">{mensagem}</p>
          <p className="text-xs text-muted">O link vale por 30 minutos. Confira também a caixa de spam.</p>
        </div>
      ) : (
        <form onSubmit={enviar} className="space-y-4" noValidate>
          <Input
            label="E-mail Institucional"
            type="email"
            autoComplete="username"
            placeholder="nome.sobrenome@unifor.br"
            icon={<Mail size={18} />}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
          <Button type="submit" loading={carregando} disabled={!email.trim()}>
            Enviar link
          </Button>
        </form>
      )}

      <Link to="/login" className="mt-6 flex items-center justify-center gap-1.5 text-sm font-semibold text-brand-500 hover:text-brand-900">
        <ArrowLeft size={16} /> Voltar para o login
      </Link>
    </CartaoAcesso>
  )
}
