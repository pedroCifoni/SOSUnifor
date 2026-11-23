import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ClipboardList, LayoutDashboard, ShieldAlert, Wrench } from 'lucide-react'
import { OcorrenciaModal } from '@/components/ocorrencias/OcorrenciaModal'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useAuth } from '@/hooks/useAuth'
import { useHoldPress } from '@/hooks/useHoldPress'
import { useNotificacoes } from '@/hooks/useNotificacoes'
import { comparar, useOcorrenciasPaginadas } from '@/hooks/useOcorrenciasPaginadas'
import { useToast } from '@/hooks/useToast'
import { ENCAMINHAR_LABEL, type Ocorrencia } from '@/models/ocorrencia'
import type { Usuario } from '@/models/usuario'
import { ocorrenciaService } from '@/services/ocorrenciaService'
import { usuarioService } from '@/services/usuarioService'
import { areaCampusService } from '@/services/areaCampusService'

const atalhos = [
  { to: '/novo-chamado', label: 'Manutenção', icon: Wrench },
  { to: '/nova-denuncia', label: 'Denúncia', icon: ShieldAlert },
  { to: '/minhas-ocorrencias', label: 'Acompanhar', icon: ClipboardList },
]

// Enquanto o sistema é testado fora do campus, o SOS usa sempre um ponto fixo dentro da UNIFOR (Bloco C)
// e não pede a localização ao navegador. Para usar o GPS real, defina VITE_SOS_USAR_GPS=true.
const USAR_GPS_REAL = import.meta.env.VITE_SOS_USAR_GPS === 'true'
const POSICAO_FIXA_UNIFOR = { latitude: -3.7697319, longitude: -38.4812157, accuracy: 10 }

function obterLocalizacaoAtual(): Promise<Pick<GeolocationCoordinates, 'latitude' | 'longitude' | 'accuracy'>> {
  if (!USAR_GPS_REAL) return Promise.resolve(POSICAO_FIXA_UNIFOR)
  return new Promise((resolver, rejeitar) => {
    if (!navigator.geolocation) {
      rejeitar(new Error('Seu navegador não oferece localização.'))
      return
    }
    navigator.geolocation.getCurrentPosition((posicao) => resolver(posicao.coords), rejeitar, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 15000,
    })
  })
}

export function HomePage() {
  const { usuario } = useAuth()
  const toast = useToast()
  const { revisao } = useNotificacoes()
  const [selecionada, setSelecionada] = useState<Ocorrencia | null>(null)
  const [segurancas, setSegurancas] = useState<Usuario[]>([])
  const [tecnicos, setTecnicos] = useState<Usuario[]>([])
  const navigate = useNavigate()

  const atendimento = usuario?.perfil === 'admin'

  // Admin: fila de pendentes (paginada). Demais perfis: os 3 chamados mais recentes (sem SOS), para o resumo da home.
  const filaPendentes = useOcorrenciasPaginadas({ status: 'pendente', habilitado: !!usuario && atendimento, revisao })
  const recentesManutencao = useOcorrenciasPaginadas({ tipo: 'manutencao', limite: 3, habilitado: !!usuario && !atendimento, revisao })
  const recentesDenuncia = useOcorrenciasPaginadas({ tipo: 'denuncia', limite: 3, habilitado: !!usuario && !atendimento, revisao })
  const { recarregar: recarregarFila } = filaPendentes

  async function encaminhar(id: string, destinoId?: string) {
    if (!destinoId) return
    try {
      await ocorrenciaService.encaminhar(id, destinoId)
      toast.sucesso('Ocorrência encaminhada.')
      setSelecionada(null)
      void recarregarFila()
    } catch {
      toast.erro('Não foi possível encaminhar a ocorrência.')
    }
  }

  useEffect(() => {
    if (atendimento) {
      void usuarioService.listarSegurancas().then(setSegurancas)
      void usuarioService.listarTecnicos().then(setTecnicos)
    }
  }, [atendimento])

  const acionarSos = useCallback(async () => {
    if (!usuario) return
    try {
      let latitude: number | undefined
      let longitude: number | undefined
      let precisaoMetros: number | undefined
      let local = 'Localização não obtida'
      try {
        const posicao = await obterLocalizacaoAtual()
        latitude = posicao.latitude
        longitude = posicao.longitude
        precisaoMetros = posicao.accuracy
        const localizacao = await areaCampusService.identificar(latitude, longitude)
        if (!localizacao.dentroCampus) {
          toast.erro('Você está muito longe do campus para ativar o SOS. Em emergência, ligue para 190.')
          return
        }
        local = localizacao.local
      } catch {
        toast.info('Não foi possível obter o GPS. O SOS será enviado para avaliação do administrador.')
      }
      const sos = await ocorrenciaService.criar(
        { titulo: 'Acionamento de Emergência', local, tipo: 'sos', latitude, longitude, precisaoMetros },
      )
      toast.sucesso('SOS acionado. O administrador foi alertado.')
      navigate(`/sos/${sos.id}`)
    } catch {
      toast.erro('Não foi possível acionar o SOS. Ligue para a Segurança.')
    }
  }, [usuario, navigate, toast])

  const { progresso, iniciar, cancelar } = useHoldPress(acionarSos, 2000)

  const minhas = atendimento
    ? [...(filaPendentes.itens ?? [])].sort((a, b) => Number(b.tipo === 'sos') - Number(a.tipo === 'sos'))
    : [...(recentesManutencao.itens ?? []), ...(recentesDenuncia.itens ?? [])].sort(comparar).slice(0, 3)

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-bold text-brand-900">Olá, {usuario?.nome.split(' ')[0]}</h2>
        <p className="text-sm text-muted">Precisa de ajuda imediata no campus?</p>
      </section>

      {!atendimento && (
      <section className="flex flex-col items-center gap-3 py-2">
        <button
          onPointerDown={iniciar}
          onPointerUp={cancelar}
          onPointerLeave={cancelar}
          onContextMenu={(e) => e.preventDefault()}
          aria-label="Segure por 2 segundos para acionar a segurança"
          className="relative grid size-44 touch-none select-none place-items-center rounded-full bg-sos-500 text-white shadow-[0_0_0_14px_rgba(225,29,46,0.12),0_0_0_28px_rgba(225,29,46,0.06)] transition active:scale-95"
          style={{ background: `conic-gradient(var(--color-sos-700) ${progresso * 360}deg, var(--color-sos-500) 0)` }}
        >
          <span className="grid size-[10.5rem] place-items-center rounded-full bg-sos-500">
            <span className="text-center">
              <span className="block text-4xl font-bold leading-none">SOS</span>
              <span className="mt-1 block text-[10px] font-semibold tracking-widest">EMERGÊNCIA</span>
            </span>
          </span>
        </button>
        <p className="text-xs font-semibold text-sos-500">Pressione por 2 segundos para acionar a segurança</p>
      </section>
      )}

      <section className="grid grid-cols-3 gap-3">
        {atalhos.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            className="flex flex-col items-center gap-2 rounded-2xl border border-line bg-white p-4 text-xs font-semibold text-brand-900 shadow-sm transition hover:border-brand-500 hover:shadow"
          >
            <span className="grid size-10 place-items-center rounded-xl bg-brand-50 text-brand-500">
              <Icon size={20} />
            </span>
            {label}
          </Link>
        ))}
      </section>

      {usuario?.perfil === 'admin' && (
        <Link
          to="/admin"
          className="flex items-center gap-3 rounded-2xl bg-brand-900 p-4 text-sm font-semibold text-white hover:bg-brand-700"
        >
          <LayoutDashboard size={20} /> Abrir Painel de Monitoramento
        </Link>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold text-brand-900">Últimas Ocorrências</h3>
          {!atendimento && (
            <Link to="/minhas-ocorrencias" className="text-xs font-semibold text-brand-500">
              Ver todas
            </Link>
          )}
        </div>
        <ul className="space-y-3">
          {minhas.map((o) => (
            <li key={o.id}>
              <button
                onClick={() => setSelecionada(o)}
                aria-haspopup="dialog"
                className="w-full rounded-2xl border border-line bg-white p-4 text-left shadow-sm transition hover:border-brand-500"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[11px] text-muted">{o.protocolo}</p>
                    <p className="truncate text-sm font-semibold text-brand-900">{o.titulo}</p>
                    <p className="truncate text-xs text-muted">{o.local}</p>
                  </div>
                  <StatusBadge status={o.status} />
                </div>
              </button>
            </li>
          ))}
          {minhas.length === 0 && (
            <li className="text-sm text-muted">
              {atendimento ? 'Fila vazia. Nenhuma ocorrência pendente.' : 'Nenhuma ocorrência ainda.'}
            </li>
          )}
        </ul>
        {atendimento && (
          <CarregarMais
            visivel={filaPendentes.temMais}
            carregando={filaPendentes.carregandoMais}
            onClick={() => void filaPendentes.carregarMais()}
          />
        )}
      </section>

      {selecionada && (
        <OcorrenciaModal
          ocorrencia={selecionada}
          onClose={() => setSelecionada(null)}
          destinos={atendimento && selecionada.status === 'pendente' ? (selecionada.tipo === 'manutencao' ? tecnicos : segurancas) : undefined}
          acao={
            atendimento && selecionada.status === 'pendente'
              ? { label: ENCAMINHAR_LABEL[selecionada.tipo], onClick: (destinoId) => void encaminhar(selecionada.id, destinoId) }
              : undefined
          }
        />
      )}
    </div>
  )
}
