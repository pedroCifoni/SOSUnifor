import { useCallback, useState } from 'react'
import { Wrench } from 'lucide-react'
import { OcorrenciaModal } from '@/components/ocorrencias/OcorrenciaModal'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/hooks/useAuth'
import { useNotificacoes } from '@/hooks/useNotificacoes'
import { useOcorrenciasPaginadas } from '@/hooks/useOcorrenciasPaginadas'
import { useResumoOcorrencias } from '@/hooks/useResumoOcorrencias'
import { useToast } from '@/hooks/useToast'
import { STATUS_ABERTOS, type Ocorrencia } from '@/models/ocorrencia'
import { ocorrenciaService } from '@/services/ocorrenciaService'
import { tempoRelativo } from '@/utils/format'

export function TecnicoHomePage() {
  const { usuario } = useAuth()
  const toast = useToast()
  const { revisao } = useNotificacoes()
  const [selecionada, setSelecionada] = useState<Ocorrencia | null>(null)
  const habilitado = !!usuario
  const { resumo, recarregar: recarregarResumo } = useResumoOcorrencias(revisao, habilitado)
  const abertosPaginados = useOcorrenciasPaginadas({ status: STATUS_ABERTOS, habilitado, revisao })
  // "Concluídos recentemente" mostra só os 5 mais recentes.
  const concluidosRecentes = useOcorrenciasPaginadas({ status: 'concluido', limite: 5, habilitado, revisao })

  const { recarregar: recarregarAbertos } = abertosPaginados
  const { recarregar: recarregarConcluidos } = concluidosRecentes
  const carregarChamados = useCallback(() => {
    void recarregarAbertos()
    void recarregarConcluidos()
    void recarregarResumo()
  }, [recarregarAbertos, recarregarConcluidos, recarregarResumo])

  async function atualizarAtendimento(id: string, status: 'em_atendimento' | 'concluido') {
    try {
      await ocorrenciaService.atualizarStatus(id, status)
      toast.sucesso(status === 'em_atendimento' ? 'Suporte técnico aceito.' : 'Suporte técnico concluído.')
      setSelecionada(null)
      carregarChamados()
    } catch {
      toast.erro('Não foi possível concluir o suporte.')
    }
  }

  const abertos = abertosPaginados.itens ?? []
  const concluidos = concluidosRecentes.itens ?? []
  const totalAbertos = resumo ? STATUS_ABERTOS.reduce((soma, s) => soma + resumo.porStatus[s], 0) : undefined
  const totalConcluidos = resumo?.porStatus.concluido

  return (
    <div className="space-y-6">
      <section className="flex items-start gap-3 rounded-2xl border border-brand-100 bg-brand-50 p-4">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-white text-brand-500 shadow-sm"><Wrench size={22} /></span>
        <div>
          <h2 className="text-xl font-bold text-brand-900">Olá, {usuario?.nome.split(' ')[0]}</h2>
          <p className="mt-1 text-sm text-ink">Chamados de suporte técnico encaminhados para você.</p>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border-2 border-brand-500 bg-white p-4 text-brand-500">
          <p className="text-[10px] font-bold tracking-wide">EM ABERTO</p>
          <p className="text-3xl font-bold">{totalAbertos === undefined ? '--' : String(totalAbertos).padStart(2, '0')}</p>
        </div>
        <div className="rounded-2xl border-2 border-emerald-500 bg-white p-4 text-emerald-700">
          <p className="text-[10px] font-bold tracking-wide">CONCLUÍDOS</p>
          <p className="text-3xl font-bold">{totalConcluidos === undefined ? '--' : String(totalConcluidos).padStart(2, '0')}</p>
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-bold text-brand-900">Pedidos para atendimento</h3>
        {abertosPaginados.itens === null ? (
          <p className="py-8 text-center text-sm text-muted">Carregando pedidos…</p>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {abertos.map((ocorrencia) => (
              <li key={ocorrencia.id}>
                <button
                  onClick={() => setSelecionada(ocorrencia)}
                  aria-haspopup="dialog"
                  className="w-full rounded-2xl border border-line bg-white p-4 text-left shadow-sm transition hover:border-brand-500 hover:shadow"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1 rounded bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-500"><Wrench size={12} /> SUPORTE TÉCNICO</span>
                    <span className="text-xs text-muted">{tempoRelativo(ocorrencia.criadoEm)}</span>
                  </div>
                  <p className="text-sm font-semibold text-brand-900">{ocorrencia.titulo}</p>
                  <p className="mt-1 text-xs text-muted">{ocorrencia.solicitante} · {ocorrencia.local}</p>
                </button>
              </li>
            ))}
            {abertos.length === 0 && <li className="text-sm text-muted">Nenhum pedido técnico encaminhado no momento.</li>}
          </ul>
        )}
        <CarregarMais
          visivel={abertosPaginados.temMais}
          carregando={abertosPaginados.carregandoMais}
          onClick={() => void abertosPaginados.carregarMais()}
        />
      </section>

      {selecionada && (
        <OcorrenciaModal
          ocorrencia={selecionada}
          onClose={() => setSelecionada(null)}
          acao={
            selecionada.status === 'concluido'
              ? undefined
              : selecionada.status === 'aguardando_aceite'
                ? { label: 'Aceitar suporte', onClick: () => void atualizarAtendimento(selecionada.id, 'em_atendimento') }
                : { label: 'Concluir suporte', onClick: () => void atualizarAtendimento(selecionada.id, 'concluido') }
          }
        />
      )}

      {concluidos.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-bold text-brand-900">Concluídos recentemente</h3>
          <ul className="space-y-2">
            {concluidos.map((ocorrencia) => (
              <li key={ocorrencia.id}>
                <button onClick={() => setSelecionada(ocorrencia)} className="flex w-full items-center justify-between rounded-xl border border-line bg-white p-3 text-left hover:border-brand-500">
                  <span><span className="block text-sm font-semibold text-brand-900">{ocorrencia.titulo}</span><span className="block text-xs text-muted">{ocorrencia.local}</span></span>
                  <StatusBadge status={ocorrencia.status} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
