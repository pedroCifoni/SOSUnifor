import { useEffect, useState, type FormEvent } from 'react'
import { Camera, MapPin } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { FileUpload } from '@/components/ui/FileUpload'
import { Select } from '@/components/ui/Select'
import { SuccessPanel } from '@/components/ui/SuccessPanel'
import { Textarea } from '@/components/ui/Textarea'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import type { Ocorrencia } from '@/models/ocorrencia'
import type { AreaCampus } from '@/models/areaCampus'
import { areaCampusService } from '@/services/areaCampusService'
import { ocorrenciaService } from '@/services/ocorrenciaService'

export function NovoChamadoPage() {
  const { usuario } = useAuth()
  const toast = useToast()
  const [local, setLocal] = useState('')
  const [areas, setAreas] = useState<AreaCampus[]>([])
  const [descricao, setDescricao] = useState('')
  const [fotos, setFotos] = useState<File[]>([])
  const [enviando, setEnviando] = useState(false)
  const [criada, setCriada] = useState<Ocorrencia | null>(null)

  useEffect(() => {
    void areaCampusService.listar().then((areasCadastradas) => {
      const areasDeAtendimento = areasCadastradas.filter((area) => !area.limiteCampus)
      setAreas(areasDeAtendimento)
      setLocal((atual) => atual || areasDeAtendimento[0]?.nome || '')
    }).catch(() => toast.erro('Não foi possível carregar os locais cadastrados do campus.'))
  }, [toast])

  async function usarLocalizacaoAtual() {
    if (!navigator.geolocation) {
      toast.erro('Seu navegador não oferece localização.')
      return
    }
    navigator.geolocation.getCurrentPosition(async (posicao) => {
      try {
        const localizacao = await areaCampusService.identificar(posicao.coords.latitude, posicao.coords.longitude)
        if (!localizacao.dentroCampus) {
          toast.erro('Você está fora do limite mapeado do campus.')
          return
        }
        setLocal(localizacao.local)
        toast.sucesso(`Local identificado: ${localizacao.local}.`)
      } catch {
        toast.erro('Não foi possível identificar sua área no mapa.')
      }
    }, () => toast.erro('Permita a localização para identificar o local do equipamento.'), { enableHighAccuracy: true, timeout: 10_000 })
  }

  if (criada) {
    return (
      <SuccessPanel
        titulo="Pedido de suporte enviado!"
        mensagem="O administrador receberá a solicitação e a encaminhará para um técnico de informática."
        protocolo={criada.protocolo}
      />
    )
  }

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!usuario) return
    if (descricao.trim().length < 10) {
      toast.erro('Descreva o problema com pelo menos 10 caracteres.')
      return
    }
    if (!local) {
      toast.erro('Selecione ou identifique o local do equipamento.')
      return
    }
    setEnviando(true)
    try {
      setCriada(
        await ocorrenciaService.criar(
          {
            tipo: 'manutencao',
            titulo: descricao.trim().slice(0, 40),
            descricao: descricao.trim(),
            local,
            anexos: fotos,
          },
        ),
      )
      toast.sucesso('Pedido de suporte enviado com sucesso.')
    } catch {
      toast.erro('Não foi possível enviar o pedido de suporte. Tente novamente.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={enviar} className="mx-auto max-w-xl space-y-5" noValidate>
      <section className="rounded-2xl border border-brand-100 bg-brand-50 p-4">
        <h2 className="text-sm font-bold text-brand-900">Suporte técnico de informática</h2>
        <p className="mt-1 text-xs text-ink">Use este formulário para equipamentos ou sistemas com defeito. Não é um alerta SOS.</p>
      </section>

      <div className="space-y-2">
        <Select label="Local do equipamento" options={areas.map((area) => area.nome)} value={local} onChange={(e) => setLocal(e.target.value)} placeholder="Selecione um local" />
        <button type="button" onClick={() => void usarLocalizacaoAtual()} className="inline-flex items-center gap-1 text-xs font-semibold text-brand-500 hover:underline"><MapPin size={14} /> Usar minha localização atual</button>
      </div>

      <Textarea
        label="Descrição do defeito"
        placeholder="Ex.: computador não liga, projetor sem imagem…"
        value={descricao}
        onChange={(e) => setDescricao(e.target.value)}
      />

      <FileUpload
        label="Foto do defeito (opcional)"
        icon={<Camera size={22} />}
        texto="Tirar ou carregar foto"
        accept="image/*"
        arquivos={fotos}
        onChange={setFotos}
      />


      <Button type="submit" loading={enviando} className="bg-brand-500 hover:bg-brand-700">
        Enviar pedido de suporte
      </Button>
    </form>
  )
}
