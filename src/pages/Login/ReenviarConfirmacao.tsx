import { useState, type FormEvent } from 'react'
import { Mail, MailCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useToast } from '@/hooks/useToast'
import { authService } from '@/services/authService'

/**
 * Pede um novo link de confirmação de e-mail. Com `email`, usa o endereço já digitado (tela de login);
 * sem ele, mostra o campo para a pessoa informar.
 */
export function ReenviarConfirmacao({ email }: { email?: string }) {
  const toast = useToast()
  const [digitado, setDigitado] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [mensagem, setMensagem] = useState<string | null>(null)
  const destino = (email ?? digitado).trim()

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!destino) return
    setCarregando(true)
    try {
      const resposta = await authService.reenviarVerificacao(destino)
      setMensagem(resposta.mensagem)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível reenviar o e-mail.')
    } finally {
      setCarregando(false)
    }
  }

  if (mensagem) {
    return (
      <div className="flex items-start gap-2 rounded-xl bg-brand-50 p-3 text-xs text-brand-900" role="status">
        <MailCheck size={16} className="mt-0.5 shrink-0 text-brand-500" aria-hidden />
        <p>
          {mensagem} O link vale por 48 horas. Confira também a caixa de spam.
        </p>
      </div>
    )
  }

  return (
    <form onSubmit={enviar} className="space-y-3" noValidate>
      {email === undefined && (
        <Input
          label="E-mail Institucional"
          type="email"
          autoComplete="username"
          placeholder="nome.sobrenome@edu.unifor.br"
          icon={<Mail size={18} />}
          value={digitado}
          onChange={(e) => setDigitado(e.target.value)}
          required
        />
      )}
      <Button type="submit" variant="secondary" loading={carregando} disabled={!destino}>
        Reenviar e-mail de confirmação
      </Button>
    </form>
  )
}
