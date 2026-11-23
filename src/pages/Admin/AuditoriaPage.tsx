import { useCallback, useEffect, useRef, useState } from 'react'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { FILTROS_DE_TIPO, ROTULO_DA_ACAO, type FiltrosAuditoria, type RegistroAuditoria } from '@/models/auditoria'
import { auditoriaService } from '@/services/auditoriaService'
import { dataHora } from '@/utils/format'

const LIMITE = 50

/** "2026-11-23" (campo date, horário local) → ISO 8601 do início ou do fim do dia. */
function limiteDoDia(data: string, fimDoDia: boolean): string | undefined {
  if (!data) return undefined
  const [ano, mes, dia] = data.split('-').map(Number)
  const momento = fimDoDia ? new Date(ano, mes - 1, dia, 23, 59, 59, 999) : new Date(ano, mes - 1, dia)
  return momento.toISOString()
}

function descreverAtor(registro: RegistroAuditoria): string {
  if (registro.atorNome) return registro.atorNome
  if (registro.atorId) return 'Conta removida'
  return registro.entidade === 'ocorrencia' ? 'Anônimo' : 'Não identificado'
}

function descreverDetalhes(registro: RegistroAuditoria): string {
  return Object.entries(registro.detalhes)
    .filter(([, valor]) => valor !== null && valor !== '')
    .map(([chave, valor]) => `${chave}: ${String(valor)}`)
    .join(' · ')
}

export function AuditoriaPage() {
  const [tipo, setTipo] = useState('')
  const [desde, setDesde] = useState('')
  const [ate, setAte] = useState('')
  const [itens, setItens] = useState<RegistroAuditoria[] | null>(null)
  const [temMais, setTemMais] = useState(false)
  const [carregandoMais, setCarregandoMais] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  // Descarta respostas de filtros antigos que cheguem depois das novas.
  const requisicao = useRef(0)

  const filtros = useCallback(
    (): FiltrosAuditoria => ({
      limite: LIMITE,
      tipo: tipo || undefined,
      desde: limiteDoDia(desde, false),
      ate: limiteDoDia(ate, true),
    }),
    [tipo, desde, ate],
  )

  useEffect(() => {
    const atual = ++requisicao.current
    setItens(null)
    setErro(null)
    auditoriaService
      .listar(filtros())
      .then((pagina) => {
        if (atual !== requisicao.current) return
        setItens(pagina)
        setTemMais(pagina.length >= LIMITE)
      })
      .catch((e: Error) => {
        if (atual !== requisicao.current) return
        setItens([])
        setTemMais(false)
        setErro(e.message)
      })
  }, [filtros])

  async function carregarMais() {
    const ultimo = itens?.[itens.length - 1]
    if (!ultimo) return
    const atual = requisicao.current
    setCarregandoMais(true)
    try {
      const pagina = await auditoriaService.listar({ ...filtros(), antesDe: ultimo.ocorridoEm, antesId: ultimo.id })
      if (atual !== requisicao.current) return
      setItens((anteriores) => [...(anteriores ?? []), ...pagina])
      setTemMais(pagina.length >= LIMITE)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setCarregandoMais(false)
    }
  }

  const campo =
    'h-11 w-full rounded-xl border border-line bg-surface px-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20'

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted">
        Quem fez o quê, quando e com qual resultado. Senhas, tokens e o conteúdo das denúncias nunca são registrados.
      </p>

      <section className="grid gap-3 sm:grid-cols-3">
        <label className="block text-xs font-semibold text-brand-900">
          <span className="mb-1.5 block">Tipo de ação</span>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} className={campo}>
            {FILTROS_DE_TIPO.map((opcao) => (
              <option key={opcao.valor} value={opcao.valor}>
                {opcao.rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-xs font-semibold text-brand-900">
          <span className="mb-1.5 block">De</span>
          <input type="date" value={desde} max={ate || undefined} onChange={(e) => setDesde(e.target.value)} className={campo} />
        </label>
        <label className="block text-xs font-semibold text-brand-900">
          <span className="mb-1.5 block">Até</span>
          <input type="date" value={ate} min={desde || undefined} onChange={(e) => setAte(e.target.value)} className={campo} />
        </label>
      </section>

      {erro && <p className="rounded-xl bg-sos-50 p-3 text-sm text-sos-700">{erro}</p>}

      <ul className="space-y-2">
        {itens?.map((registro) => {
          const detalhes = descreverDetalhes(registro)
          const sucesso = registro.resultado === 'sucesso'
          return (
            <li key={registro.id} className="rounded-2xl border border-line bg-white p-3 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-brand-900">{ROTULO_DA_ACAO[registro.acao] ?? registro.acao}</p>
                <span
                  className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                    sucesso ? 'bg-emerald-50 text-emerald-700' : 'bg-sos-50 text-sos-700'
                  }`}
                >
                  {sucesso ? 'SUCESSO' : 'ERRO'}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted">
                {dataHora(registro.ocorridoEm)} · {descreverAtor(registro)}
                {registro.entidade && (
                  <>
                    {' · '}
                    {registro.entidade}
                    {registro.entidadeId && <span title={registro.entidadeId}> #{registro.entidadeId.slice(0, 8)}</span>}
                  </>
                )}
              </p>
              {detalhes && <p className="mt-1 break-words text-xs text-brand-900">{detalhes}</p>}
              {registro.erro && <p className="mt-1 break-words text-xs text-sos-700">{registro.erro}</p>}
            </li>
          )
        })}
        {itens === null && <li className="text-sm text-muted">Carregando registros…</li>}
        {itens?.length === 0 && !erro && <li className="text-sm text-muted">Nenhum registro para estes filtros.</li>}
      </ul>

      <CarregarMais visivel={temMais} carregando={carregandoMais} onClick={() => void carregarMais()} />
    </div>
  )
}
