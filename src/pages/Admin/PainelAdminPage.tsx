import { useCallback, useEffect, useMemo, useState } from 'react'
import { OcorrenciaModal } from '@/components/ocorrencias/OcorrenciaModal'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { useNotificacoes } from '@/hooks/useNotificacoes'
import { useOcorrenciasPaginadas } from '@/hooks/useOcorrenciasPaginadas'
import { useResumoOcorrencias } from '@/hooks/useResumoOcorrencias'
import { useToast } from '@/hooks/useToast'
import { ENCAMINHAR_LABEL, TIPO_LABEL, type Ocorrencia } from '@/models/ocorrencia'
import type { Usuario } from '@/models/usuario'
import { ocorrenciaService } from '@/services/ocorrenciaService'
import { usuarioService } from '@/services/usuarioService'
import { tempoRelativo } from '@/utils/format'

// Os SOS pendentes são buscados à parte para ficarem sempre no topo da fila e alimentarem o card.
const LIMITE_SOS_PENDENTES = 200

function formatarContador(valor: number | undefined, limite?: number) {
  if (valor === undefined) return '--'
  if (limite !== undefined && valor >= limite) return `${limite}+`
  return String(valor).padStart(2, '0')
}

export function PainelAdminPage() {
  const toast = useToast()
  const { revisao } = useNotificacoes()
  const { resumo, recarregar: recarregarResumo } = useResumoOcorrencias(revisao)
  const pendentes = useOcorrenciasPaginadas({ status: 'pendente', revisao })
  const [sosPendentes, setSosPendentes] = useState<Ocorrencia[] | null>(null)
  const [selecionada, setSelecionada] = useState<Ocorrencia | null>(null)
  const [segurancas, setSegurancas] = useState<Usuario[]>([])
  const [tecnicos, setTecnicos] = useState<Usuario[]>([])

  const carregarSos = useCallback(async () => {
    try {
      setSosPendentes(await ocorrenciaService.listar({ status: 'pendente', tipo: 'sos', limite: LIMITE_SOS_PENDENTES }))
    } catch {
      setSosPendentes((atual) => atual ?? [])
    }
  }, [])

  useEffect(() => {
    void carregarSos()
    void usuarioService.listarSegurancas().then(setSegurancas)
    void usuarioService.listarTecnicos().then(setTecnicos)
  }, [carregarSos, revisao])

  const { recarregar: recarregarPendentes } = pendentes
  const recarregarTudo = useCallback(() => {
    void recarregarPendentes()
    void carregarSos()
    void recarregarResumo()
  }, [recarregarPendentes, carregarSos, recarregarResumo])

  async function encaminhar(id: string, destinoId?: string) {
    if (!destinoId) return
    try {
      await ocorrenciaService.encaminhar(id, destinoId)
      toast.sucesso('Ocorrência encaminhada.')
      setSelecionada(null)
      recarregarTudo()
    } catch {
      toast.erro('Não foi possível encaminhar a ocorrência.')
    }
  }

  const fila = useMemo(() => {
    const vistos = new Set<string>()
    return [...(sosPendentes ?? []), ...(pendentes.itens ?? [])]
      .filter((o) => (vistos.has(o.id) ? false : (vistos.add(o.id), true)))
      .sort((a, b) => Number(b.tipo === 'sos') - Number(a.tipo === 'sos'))
  }, [sosPendentes, pendentes.itens])
  const carregandoFila = pendentes.itens === null || sosPendentes === null
  const destinosDaOcorrencia = selecionada?.tipo === 'manutencao' ? tecnicos : segurancas

  const cards = [
    {
      label: 'SOS ATIVOS',
      valor: formatarContador(sosPendentes?.length, LIMITE_SOS_PENDENTES),
      cor: 'border-sos-500 text-sos-500',
    },
    { label: 'PENDENTES', valor: formatarContador(resumo?.porStatus.pendente), cor: 'border-brand-500 text-brand-500' },
    { label: 'DENÚNCIAS', valor: formatarContador(resumo?.porTipo.denuncia), cor: 'border-brand-900 text-brand-900' },
  ]

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-3 gap-3">
        {cards.map((c) => (
          <div key={c.label} className={`rounded-2xl border-2 bg-white p-3 sm:p-4 ${c.cor}`}>
            <p className="text-[10px] font-bold tracking-wide">{c.label}</p>
            <p className="text-3xl font-bold">{c.valor}</p>
          </div>
        ))}
      </section>

      <section>
        <h3 className="mb-3 text-sm font-bold text-brand-900">Fila Prioritária</h3>
        <ul className="grid gap-3 md:grid-cols-2">
          {fila.map((o) => {
            const sos = o.tipo === 'sos'
            return (
              <li
                key={o.id}
                className={`rounded-2xl border bg-white p-4 shadow-sm ${sos ? 'border-sos-500' : 'border-line'}`}
              >
                <button
                  onClick={() => setSelecionada(o)}
                  aria-haspopup="dialog"
                  className="mb-3 block w-full text-left"
                >
                <div className="mb-2 flex items-center justify-between">
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                      sos ? 'bg-sos-50 text-sos-700' : 'bg-brand-50 text-brand-500'
                    }`}
                  >
                    {TIPO_LABEL[o.tipo].toUpperCase()}
                  </span>
                  <span className={`text-xs ${sos ? 'font-semibold text-sos-500' : 'text-muted'}`}>
                    {tempoRelativo(o.criadoEm)}
                  </span>
                </div>
                <p className="text-sm font-semibold text-brand-900">{o.titulo}</p>
                <p className="text-xs text-muted">
                  {o.solicitante} · {o.local}
                </p>
                </button>
                <button
                  onClick={() => setSelecionada(o)}
                  className={`h-10 w-full rounded-xl text-xs font-semibold transition ${
                    sos
                      ? 'bg-brand-900 text-white hover:bg-brand-700'
                      : 'bg-brand-50 text-brand-500 hover:bg-brand-100'
                  }`}
                >
                  {ENCAMINHAR_LABEL[o.tipo]}
                </button>
              </li>
            )
          })}
          {carregandoFila && fila.length === 0 && <li className="text-sm text-muted">Carregando fila…</li>}
          {!carregandoFila && fila.length === 0 && (
            <li className="text-sm text-muted">Fila vazia. Nenhuma ocorrência pendente.</li>
          )}
        </ul>
        <CarregarMais
          visivel={pendentes.temMais}
          carregando={pendentes.carregandoMais}
          onClick={() => void pendentes.carregarMais()}
        />
      </section>

      {selecionada && (
        <OcorrenciaModal
          ocorrencia={selecionada}
          onClose={() => setSelecionada(null)}
          destinos={selecionada.status === 'pendente' ? destinosDaOcorrencia : undefined}
          acao={
            selecionada.status === 'pendente'
              ? { label: ENCAMINHAR_LABEL[selecionada.tipo], onClick: (destinoId) => void encaminhar(selecionada.id, destinoId) }
              : undefined
          }
        />
      )}
    </div>
  )
}
