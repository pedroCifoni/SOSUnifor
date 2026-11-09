import { useCallback, useEffect, useState } from 'react'
import { MapPinned, Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { EditorAreasCampus } from '@/components/mapa/EditorAreasCampus'
import { useToast } from '@/hooks/useToast'
import type { AreaCampus, DadosAreaCampus } from '@/models/areaCampus'
import { areaCampusService } from '@/services/areaCampusService'

const AREA_NOVA: DadosAreaCampus = {
  nome: '',
  tipo: 'bloco',
  coordenadas: [],
  limiteCampus: false,
  prioridade: 0,
}

export function AreasCampusPage() {
  const toast = useToast()
  const [areas, setAreas] = useState<AreaCampus[]>([])
  const [areaEmEdicao, setAreaEmEdicao] = useState<AreaCampus | null>(null)
  const [dadosFormulario, setDadosFormulario] = useState<DadosAreaCampus>(AREA_NOVA)
  const [salvando, setSalvando] = useState(false)

  const carregarAreas = useCallback(async () => {
    try {
      setAreas(await areaCampusService.listar())
    } catch {
      toast.erro('Não foi possível carregar as áreas do campus.')
    }
  }, [toast])

  useEffect(() => {
    void carregarAreas()
  }, [carregarAreas])

  function iniciarNovaArea() {
    setAreaEmEdicao(null)
    setDadosFormulario(AREA_NOVA)
  }

  function editarArea(area: AreaCampus) {
    setAreaEmEdicao(area)
    setDadosFormulario({
      nome: area.nome,
      tipo: area.tipo,
      coordenadas: area.coordenadas,
      limiteCampus: area.limiteCampus,
      prioridade: area.prioridade,
    })
  }

  async function salvarArea() {
    if (!dadosFormulario.nome.trim()) {
      toast.erro('Informe o nome da área.')
      return
    }
    if (dadosFormulario.coordenadas.length < 3) {
      toast.erro('Desenhe ao menos três pontos no mapa.')
      return
    }
    setSalvando(true)
    try {
      if (areaEmEdicao) {
        await areaCampusService.atualizar(areaEmEdicao.id, dadosFormulario)
      } else {
        await areaCampusService.criar(dadosFormulario)
      }
      toast.sucesso('Área do campus salva.')
      iniciarNovaArea()
      await carregarAreas()
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível salvar a área.')
    } finally {
      setSalvando(false)
    }
  }

  async function excluirArea(area: AreaCampus) {
    if (!window.confirm(`Excluir a área “${area.nome}”?`)) return
    try {
      await areaCampusService.excluir(area.id)
      toast.sucesso('Área removida.')
      if (areaEmEdicao?.id === area.id) iniciarNovaArea()
      await carregarAreas()
    } catch {
      toast.erro('Não foi possível remover a área.')
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-10">
      <section className="rounded-2xl border border-brand-100 bg-brand-50 p-4">
        <div className="flex gap-3">
          <MapPinned className="mt-0.5 shrink-0 text-brand-500" size={22} />
          <div>
            <h2 className="text-sm font-bold text-brand-900">Mapeamento da Unifor</h2>
            <p className="mt-1 text-xs text-ink">O mapa abre na Universidade de Fortaleza. Cadastre primeiro o limite geral do campus. Depois desenhe cada bloco, portaria, estacionamento e área verde. Fora de um bloco, o SOS informa o bloco mais próximo.</p>
            <a href="https://www.google.com/maps/place/UNIFOR+-+Universidade+de+Fortaleza/@-3.7696382,-38.4798407,16.94z" target="_blank" rel="noreferrer" className="mt-2 inline-block text-xs font-semibold text-brand-500 hover:underline">Conferir a UNIFOR no Google Maps</a>
          </div>
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-brand-900">{areaEmEdicao ? `Editando: ${areaEmEdicao.nome}` : 'Nova área'}</h2>
              {areaEmEdicao && <button onClick={iniciarNovaArea} className="text-xs font-semibold text-brand-500 hover:underline">Cancelar edição</button>}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1 text-xs font-semibold text-brand-900">Nome
                <input value={dadosFormulario.nome} onChange={(evento) => setDadosFormulario((atual) => ({ ...atual, nome: evento.target.value }))} placeholder="Ex.: Bloco D" className="h-10 rounded-lg border border-line px-3 text-sm font-normal focus:border-brand-500 focus:outline-none" />
              </label>
              <label className="grid gap-1 text-xs font-semibold text-brand-900">Tipo
                <select value={dadosFormulario.tipo} onChange={(evento) => setDadosFormulario((atual) => ({ ...atual, tipo: evento.target.value }))} className="h-10 rounded-lg border border-line bg-white px-3 text-sm font-normal focus:border-brand-500 focus:outline-none">
                  <option value="bloco">Bloco</option><option value="estacionamento">Estacionamento</option><option value="portaria">Portaria</option><option value="administracao">Administração</option><option value="area_verde">Área verde</option><option value="area_externa">Área externa</option>
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold text-brand-900">Prioridade
                <input type="number" min="0" max="1000" value={dadosFormulario.prioridade} onChange={(evento) => setDadosFormulario((atual) => ({ ...atual, prioridade: Number(evento.target.value) }))} className="h-10 rounded-lg border border-line px-3 text-sm font-normal focus:border-brand-500 focus:outline-none" />
              </label>
              <label className="flex items-center gap-2 self-end rounded-lg bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-800">
                <input type="checkbox" checked={dadosFormulario.limiteCampus} onChange={(evento) => setDadosFormulario((atual) => ({ ...atual, limiteCampus: evento.target.checked }))} />
                Este é o limite geral do campus
              </label>
            </div>
          </section>

          <EditorAreasCampus key={areaEmEdicao?.id ?? 'nova'} areas={areas} coordenadasIniciais={dadosFormulario.coordenadas} aoAlterarCoordenadas={(coordenadas) => setDadosFormulario((atual) => ({ ...atual, coordenadas }))} />

          <button onClick={() => void salvarArea()} disabled={salvando} className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-900 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
            <Save size={17} /> {salvando ? 'Salvando…' : 'Salvar área desenhada'}
          </button>
        </div>

        <aside className="space-y-3">
          <button onClick={iniciarNovaArea} className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-brand-50 text-sm font-semibold text-brand-900 hover:bg-brand-100"><Plus size={17} /> Nova área</button>
          <h2 className="px-1 text-sm font-bold text-brand-900">Áreas cadastradas ({areas.length})</h2>
          {areas.map((area) => (
            <article key={area.id} className="rounded-xl border border-line bg-white p-3 shadow-sm">
              <p className="text-sm font-semibold text-brand-900">{area.nome}</p>
              <p className="mt-0.5 text-xs text-muted">{area.limiteCampus ? 'Limite geral do campus' : area.tipo} · {area.coordenadas.length} pontos</p>
              <div className="mt-3 flex gap-2"><button onClick={() => editarArea(area)} className="inline-flex h-8 items-center gap-1 rounded-lg bg-brand-50 px-2 text-xs font-semibold text-brand-500 hover:bg-brand-100"><Pencil size={14} /> Editar</button><button onClick={() => void excluirArea(area)} className="inline-flex h-8 items-center gap-1 rounded-lg px-2 text-xs font-semibold text-sos-700 hover:bg-sos-50"><Trash2 size={14} /> Excluir</button></div>
            </article>
          ))}
          {areas.length === 0 && <p className="rounded-xl border border-dashed border-line p-4 text-xs text-muted">Nenhuma área cadastrada. Comece pelo limite da Unifor.</p>}
        </aside>
      </div>
    </div>
  )
}
