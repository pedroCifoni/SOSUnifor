import type { Ocorrencia } from '@/models/ocorrencia'
import { dataHora } from '@/utils/format'

type Etapa = { titulo: string; detalhe: string; estado: 'feito' | 'atual' }

function criarTitulo(tipo: string) {
  return tipo.replaceAll('_', ' ').replace(/^./, (letra) => letra.toUpperCase())
}

function etapas(ocorrencia: Ocorrencia): Etapa[] {
  const eventos = ocorrencia.eventos ?? [
    { tipo: 'criada', descricao: `Registrado por ${ocorrencia.solicitante}.`, criadoEm: ocorrencia.criadoEm },
  ]
  return eventos.map((evento, indice) => ({
    titulo: criarTitulo(evento.tipo),
    detalhe: `${dataHora(evento.criadoEm)} · ${evento.descricao}`,
    estado: indice === eventos.length - 1 && !['concluido', 'cancelado'].includes(evento.tipo) ? 'atual' : 'feito',
  }))
}

const ponto = { feito: 'bg-emerald-500 border-emerald-500', atual: 'bg-brand-500 border-brand-500' }

export function Timeline({ ocorrencia }: { ocorrencia: Ocorrencia }) {
  const lista = etapas(ocorrencia)
  return (
    <ol className="mt-4 space-y-0">
      {lista.map((etapa, indice) => (
        <li key={`${etapa.titulo}-${indice}`} className="relative flex gap-3 pb-4 last:pb-0">
          {indice < lista.length - 1 && <span aria-hidden className="absolute left-[5px] top-3 h-full w-0.5 bg-emerald-300" />}
          <span className={`relative mt-1 size-3 shrink-0 rounded-full border-2 ${ponto[etapa.estado]}`} />
          <div className="min-w-0">
            <p className={`text-sm font-semibold leading-tight ${etapa.estado === 'atual' ? 'text-brand-500' : 'text-brand-900'}`}>{etapa.titulo}</p>
            <p className="text-xs text-muted">{etapa.detalhe}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
