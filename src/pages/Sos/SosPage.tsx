import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BellRing, MapPin, Navigation, Phone } from 'lucide-react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useToast } from '@/hooks/useToast'
import type { Ocorrencia } from '@/models/ocorrencia'
import { ocorrenciaService } from '@/services/ocorrenciaService'

function mensagemDoAtendimento(status: Ocorrencia['status']) {
  if (status === 'pendente') return 'O administrador recebeu o SOS e fará a triagem.'
  if (status === 'aguardando_aceite') return 'A equipe responsável foi acionada e ainda precisa aceitar o atendimento.'
  if (status === 'em_atendimento') return 'A equipe responsável aceitou o atendimento.'
  if (status === 'concluido') return 'O atendimento foi concluído.'
  return 'Este SOS foi cancelado como alarme falso.'
}

function enderecoDoMapa(latitude: number, longitude: number) {
  const margem = 0.0015
  return `https://www.openstreetmap.org/export/embed.html?bbox=${longitude - margem}%2C${latitude - margem}%2C${longitude + margem}%2C${latitude + margem}&layer=mapnik&marker=${latitude}%2C${longitude}`
}

export function SosPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [ocorrencia, setOcorrencia] = useState<Ocorrencia | null>(null)
  const [confirmando, setConfirmando] = useState(false)

  useEffect(() => {
    let ativo = true
    ocorrenciaService.buscarPorId(id).then((ocorrenciaAtual) => {
      if (ativo) setOcorrencia(ocorrenciaAtual)
    }).catch(() => {
      if (!ativo) return
      toast.erro('Alerta SOS não encontrado.')
      navigate('/', { replace: true })
    })
    return () => { ativo = false }
  }, [id, navigate, toast])

  async function cancelar() {
    if (!ocorrencia) return
    try {
      await ocorrenciaService.atualizarStatus(ocorrencia.id, 'cancelado')
      toast.info('SOS cancelado. O administrador foi informado.')
      navigate('/', { replace: true })
    } catch {
      toast.erro('Não foi possível cancelar o SOS.')
    }
  }

  if (!ocorrencia) return <p className="py-16 text-center text-sm text-muted">Carregando alerta…</p>

  const possuiCoordenadas = ocorrencia.latitude !== undefined && ocorrencia.longitude !== undefined

  return (
    <div className="space-y-5">
      <section className="flex items-center gap-4 rounded-2xl bg-sos-500 p-4 text-white">
        <span className="relative grid size-12 shrink-0 place-items-center rounded-full bg-white text-sos-500"><BellRing size={22} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-lg font-bold leading-tight">SOS acionado</p>
          <p className="text-xs text-white/90">Protocolo {ocorrencia.protocolo} · {mensagemDoAtendimento(ocorrencia.status)}</p>
        </div>
        <StatusBadge status={ocorrencia.status} />
      </section>

      <section className="overflow-hidden rounded-2xl border border-line bg-white shadow-sm">
        <div className="flex items-center gap-2 px-4 pt-4"><MapPin size={18} className="text-brand-500" /><h2 className="text-sm font-bold text-brand-900">Local registrado</h2></div>
        {possuiCoordenadas ? (
          <iframe title="Mapa do local registrado no SOS" src={enderecoDoMapa(ocorrencia.latitude!, ocorrencia.longitude!)} className="m-4 h-56 w-[calc(100%-2rem)] rounded-xl border-0" loading="lazy" />
        ) : (
          <p className="m-4 rounded-xl bg-amber-50 p-4 text-sm text-amber-800">O GPS não foi obtido neste SOS. Informe sua localização ao administrador ou ligue para a segurança.</p>
        )}
        <div className="flex items-start gap-2 px-4 pb-4"><Navigation size={16} className="mt-0.5 shrink-0 text-brand-500" /><div><p className="text-sm font-semibold text-brand-900">{ocorrencia.local}</p><p className="text-xs text-muted">Posição registrada no momento do acionamento; não há rastreamento contínuo.</p></div></div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2">
        <a href="tel:190" className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand-900 text-sm font-semibold text-white hover:bg-brand-700"><Phone size={18} /> Emergência: ligar 190</a>
        {confirmando ? <div className="flex gap-2"><button onClick={cancelar} className="h-12 flex-1 rounded-xl bg-sos-500 text-sm font-semibold text-white hover:bg-sos-700">Confirmar cancelamento</button><button onClick={() => setConfirmando(false)} className="h-12 flex-1 rounded-xl bg-brand-50 text-sm font-semibold text-brand-900">Voltar</button></div> : (
          ocorrencia.status === 'pendente' && <button onClick={() => setConfirmando(true)} className="h-12 rounded-xl border border-line text-sm font-semibold text-sos-700 hover:bg-sos-50">Cancelar SOS (alarme falso)</button>
        )}
      </div>
    </div>
  )
}
