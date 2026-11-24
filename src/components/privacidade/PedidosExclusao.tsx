import { useCallback, useEffect, useState } from 'react'
import { ShieldCheck, UserX } from 'lucide-react'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useAuth } from '@/hooks/useAuth'
import { useNotificacoes } from '@/hooks/useNotificacoes'
import { useToast } from '@/hooks/useToast'
import type { PedidoExclusao } from '@/models/privacidade'
import { PERFIL_LABEL, type Perfil } from '@/models/usuario'
import { privacidadeService } from '@/services/privacidadeService'

interface PedidosExclusaoProps {
  /** Chamado depois de anonimizar, para a lista de usuários tirar a conta desativada. */
  onAnonimizado: (usuarioId: string) => void
}

/** Pedidos de eliminação de dados (LGPD, art. 18, VI) feitos pelos titulares na tela de Perfil. */
export function PedidosExclusao({ onAnonimizado }: PedidosExclusaoProps) {
  const { usuario: eu } = useAuth()
  const { revisao } = useNotificacoes()
  const toast = useToast()
  const [pedidos, setPedidos] = useState<PedidoExclusao[]>([])
  const [paraAnonimizar, setParaAnonimizar] = useState<PedidoExclusao | null>(null)

  const carregar = useCallback(async () => {
    try {
      setPedidos(await privacidadeService.listarPedidosExclusao())
    } catch {
      setPedidos([])
    }
  }, [])

  useEffect(() => {
    void carregar()
  }, [carregar, revisao])

  async function anonimizar(pedido: PedidoExclusao) {
    setParaAnonimizar(null)
    try {
      await privacidadeService.anonimizar(pedido.id)
      toast.sucesso('Conta anonimizada. As ocorrências foram mantidas sem identificar a pessoa.')
      setPedidos((atual) => atual.filter((p) => p.id !== pedido.id))
      onAnonimizado(pedido.id)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível anonimizar a conta.')
    }
  }

  if (pedidos.length === 0) return null

  return (
    <section className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-4">
      <h2 className="flex items-center gap-2 text-sm font-bold text-brand-900">
        <ShieldCheck size={16} className="text-amber-700" /> Pedidos de exclusão de dados (LGPD) · {pedidos.length}
      </h2>
      <p className="text-xs text-ink">
        Anonimizar apaga de forma irreversível o nome e o e-mail, invalida a senha e desativa a conta. As ocorrências
        continuam guardadas, sem identificar a pessoa.
      </p>
      <ul className="space-y-2">
        {pedidos.map((pedido) => {
          const proprio = pedido.id === eu?.id
          return (
            <li key={pedido.id} className="flex items-center gap-3 rounded-xl bg-white p-3 shadow-sm">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-brand-900">
                  {pedido.nome} {!pedido.ativo && <span className="text-[11px] font-medium text-muted">(conta desativada)</span>}
                </p>
                <p className="truncate text-xs text-muted">
                  {pedido.email} · {PERFIL_LABEL[pedido.perfil as Perfil] ?? pedido.perfil}
                </p>
                <p className="text-[11px] text-muted">Pedido em {new Date(pedido.solicitadaEm).toLocaleString('pt-BR')}</p>
              </div>
              <button
                onClick={() => setParaAnonimizar(pedido)}
                disabled={proprio}
                title={proprio ? 'Outro administrador precisa atender o seu pedido' : undefined}
                className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-sos-700 px-3 text-xs font-semibold text-white hover:bg-sos-800 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <UserX size={14} /> Anonimizar
              </button>
            </li>
          )
        })}
      </ul>

      {paraAnonimizar && (
        <ConfirmModal
          titulo="Anonimizar esta conta?"
          confirmarLabel="Sim, anonimizar"
          onCancel={() => setParaAnonimizar(null)}
          onConfirm={() => void anonimizar(paraAnonimizar)}
        >
          Os dados de <strong className="text-brand-900">{paraAnonimizar.nome}</strong> serão substituídos de forma
          irreversível e a conta será desativada. Esta ação não pode ser desfeita.
        </ConfirmModal>
      )}
    </section>
  )
}
