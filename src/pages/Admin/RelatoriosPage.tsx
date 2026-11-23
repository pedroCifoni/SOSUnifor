import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { http } from '@/api/client'
import { useToast } from '@/hooks/useToast'

type Formato = 'csv' | 'pdf'

function salvarArquivo(arquivo: Blob, nome: string) {
  const url = URL.createObjectURL(arquivo)
  const link = document.createElement('a')
  link.href = url
  link.download = nome
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function RelatoriosPage() {
  const toast = useToast()
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [tipo, setTipo] = useState('')
  const [status, setStatus] = useState('')
  const [baixando, setBaixando] = useState<Formato | null>(null)

  async function baixar(formato: Formato) {
    if (de && ate && de > ate) {
      toast.erro('A data inicial não pode ser posterior à data final.')
      return
    }
    const parametros = new URLSearchParams()
    if (de) parametros.set('de', de)
    if (ate) parametros.set('ate', ate)
    if (tipo) parametros.set('tipo', tipo)
    if (status) parametros.set('status', status)
    setBaixando(formato)
    try {
      const sufixo = parametros.toString()
      const resposta = await http.baixarArquivoComNome(`/relatorios/ocorrencias.${formato}${sufixo ? `?${sufixo}` : ''}`)
      salvarArquivo(resposta.arquivo, resposta.nome ?? `ocorrencias.${formato}`)
      toast.sucesso(`Relatório ${formato.toUpperCase()} baixado.`)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível baixar o relatório.')
    } finally {
      setBaixando(null)
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-bold text-brand-900">Relatórios de ocorrências</h2>
        <p className="mt-1 text-sm text-muted">Exporte somente as informações necessárias para acompanhamento.</p>
      </div>
      <div className="space-y-4 rounded-2xl border border-line bg-white p-4 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="De" type="date" value={de} onChange={(event) => setDe(event.target.value)} />
          <Input label="Até" type="date" value={ate} onChange={(event) => setAte(event.target.value)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-xs font-semibold text-brand-900">Tipo
            <select value={tipo} onChange={(event) => setTipo(event.target.value)} className="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20">
              <option value="">Todos</option>
              <option value="sos">SOS</option>
              <option value="manutencao">Manutenção</option>
              <option value="denuncia">Denúncia</option>
            </select>
          </label>
          <label className="block text-xs font-semibold text-brand-900">Status
            <select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-1 h-12 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20">
              <option value="">Todos</option>
              <option value="pendente">Pendente</option>
              <option value="aguardando_aceite">Aguardando aceite</option>
              <option value="em_atendimento">Em atendimento</option>
              <option value="concluido">Concluído</option>
              <option value="cancelado">Cancelado</option>
            </select>
          </label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Button type="button" variant="secondary" loading={baixando === 'csv'} disabled={baixando !== null} onClick={() => void baixar('csv')}>Baixar CSV</Button>
          <Button type="button" loading={baixando === 'pdf'} disabled={baixando !== null} onClick={() => void baixar('pdf')}>Baixar PDF</Button>
        </div>
      </div>
    </section>
  )
}
