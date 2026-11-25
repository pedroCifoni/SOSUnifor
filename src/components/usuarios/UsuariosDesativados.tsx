import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RotateCcw, UserX } from 'lucide-react'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useToast } from '@/hooks/useToast'
import { PERFIL_LABEL, type Perfil, type Usuario } from '@/models/usuario'
import { usuarioService } from '@/services/usuarioService'
import { iniciais } from '@/utils/format'

const LIMITE_POR_PAGINA = 20

interface UsuariosDesativadosProps {
  busca: string
  perfil: Perfil | ''
  /** Chamado depois de reativar, para a lista de contas ativas ser recarregada. */
  onReativado: (usuario: Usuario) => void
}

/**
 * Contas desativadas pelo admin, com a opção de reativar. A reativação é imediata (com confirmação),
 * não entra no rascunho de "Salvar alterações". Contas anonimizadas (LGPD) não aparecem aqui.
 */
export function UsuariosDesativados({ busca, perfil, onReativado }: UsuariosDesativadosProps) {
  const toast = useToast()
  const [lista, setLista] = useState<Usuario[] | null>(null)
  const [total, setTotal] = useState<number | null>(null)
  const [pagina, setPagina] = useState(1)
  const [carregando, setCarregando] = useState(true)
  const [carregandoMais, setCarregandoMais] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [paraReativar, setParaReativar] = useState<Usuario | null>(null)
  const [reativando, setReativando] = useState<string | null>(null)
  const requisicaoRef = useRef(0)

  const filtros = useMemo(
    () => ({ busca: busca || undefined, perfil: perfil || undefined, situacao: 'desativados' as const }),
    [busca, perfil],
  )

  const carregar = useCallback(async () => {
    const idRequisicao = ++requisicaoRef.current
    setCarregando(true)
    setErro(null)
    try {
      const [primeira, resumo] = await Promise.all([
        usuarioService.listar({ ...filtros, limite: LIMITE_POR_PAGINA, pagina: 1 }),
        usuarioService.resumir(filtros),
      ])
      if (requisicaoRef.current !== idRequisicao) return
      setLista(primeira)
      setTotal(resumo.total)
      setPagina(1)
    } catch (err) {
      if (requisicaoRef.current !== idRequisicao) return
      setLista(null)
      setErro(err instanceof Error ? err.message : 'Não foi possível carregar as contas desativadas.')
    } finally {
      if (requisicaoRef.current === idRequisicao) setCarregando(false)
    }
  }, [filtros])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function carregarMais() {
    if (carregando || carregandoMais) return
    const idRequisicao = requisicaoRef.current
    setCarregandoMais(true)
    try {
      const proxima = await usuarioService.listar({ ...filtros, limite: LIMITE_POR_PAGINA, pagina: pagina + 1 })
      if (requisicaoRef.current !== idRequisicao) return
      setLista((atual) => {
        const existentes = new Set((atual ?? []).map((u) => u.id))
        return [...(atual ?? []), ...proxima.filter((u) => !existentes.has(u.id))]
      })
      setPagina((atual) => atual + 1)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível carregar mais contas.')
    } finally {
      if (requisicaoRef.current === idRequisicao) setCarregandoMais(false)
    }
  }

  async function reativar(alvo: Usuario) {
    setParaReativar(null)
    setReativando(alvo.id)
    try {
      const reativada = await usuarioService.reativar(alvo.id)
      setLista((atual) => atual?.filter((u) => u.id !== alvo.id) ?? atual)
      setTotal((atual) => (atual === null ? atual : Math.max(0, atual - 1)))
      toast.sucesso(`${alvo.nome} foi reativado(a) e já pode entrar de novo.`)
      onReativado(reativada)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível reativar a conta.')
    } finally {
      setReativando(null)
    }
  }

  const temMais = lista !== null && total !== null && lista.length < total

  return (
    <>
      <p className="text-sm text-muted" aria-live="polite">
        {erro
          ? 'Não foi possível carregar'
          : total !== null
            ? `${total} ${total === 1 ? 'conta desativada' : 'contas desativadas'}${carregando ? ' · Atualizando…' : ''}`
            : 'Carregando…'}
      </p>

      {erro && (
        <section className="rounded-2xl border border-sos-200 bg-sos-50 p-4 text-sm text-sos-700" role="alert">
          <p className="font-semibold">Não foi possível abrir as contas desativadas.</p>
          <p className="mt-1 text-xs">{erro}</p>
          <button
            onClick={() => void carregar()}
            className="mt-3 rounded-lg bg-sos-700 px-3 py-2 text-xs font-semibold text-white hover:bg-sos-800"
          >
            Tentar novamente
          </button>
        </section>
      )}

      {!erro && !carregando && lista?.length === 0 && (
        <section className="rounded-2xl border border-line bg-white p-8 text-center shadow-sm">
          <UserX size={28} className="mx-auto text-muted" aria-hidden="true" />
          <p className="mt-2 text-sm font-semibold text-brand-900">
            {busca || perfil ? 'Nenhuma conta desativada encontrada com esses filtros.' : 'Nenhuma conta desativada.'}
          </p>
        </section>
      )}

      <ul className="space-y-3">
        {(lista ?? []).map((u) => (
          <li key={u.id} className="rounded-2xl border border-line bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-full bg-slate-300 text-xs font-semibold text-white">
                {iniciais(u.nome)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-brand-900">
                  {u.nome}
                  <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">
                    DESATIVADA
                  </span>
                </p>
                <p className="truncate text-xs text-muted">{u.email}</p>
                <p className="mt-0.5 text-[11px] text-muted">Perfil: {PERFIL_LABEL[u.perfil]}</p>
              </div>
              <button
                type="button"
                onClick={() => setParaReativar(u)}
                disabled={reativando === u.id}
                className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl bg-brand-50 px-3 text-xs font-semibold text-brand-500 hover:bg-brand-100 disabled:opacity-60"
              >
                <RotateCcw size={14} aria-hidden /> {reativando === u.id ? 'Reativando…' : 'Reativar'}
              </button>
            </div>
          </li>
        ))}
      </ul>

      <CarregarMais visivel={temMais} carregando={carregandoMais} onClick={() => void carregarMais()} />

      {paraReativar && (
        <ConfirmModal
          tom="neutro"
          titulo="Reativar conta?"
          confirmarLabel="Sim, reativar"
          onCancel={() => setParaReativar(null)}
          onConfirm={() => void reativar(paraReativar)}
        >
          <strong className="text-brand-900">{paraReativar.nome}</strong> volta a entrar no sistema com o mesmo perfil (
          {PERFIL_LABEL[paraReativar.perfil]}), e-mail e senha de antes.
        </ConfirmModal>
      )}
    </>
  )
}
