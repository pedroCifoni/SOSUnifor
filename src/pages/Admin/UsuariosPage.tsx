import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Download, Info, MailWarning, Pencil, Search, Trash2, Users, X } from 'lucide-react'
import { PedidosExclusao } from '@/components/privacidade/PedidosExclusao'
import { CarregarMais } from '@/components/ui/CarregarMais'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { UsuarioFormModal } from '@/components/usuarios/UsuarioFormModal'
import { UsuariosDesativados } from '@/components/usuarios/UsuariosDesativados'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { PERFIL_LABEL, type EdicaoUsuario, type Perfil, type Usuario } from '@/models/usuario'
import { usuarioService, type SituacaoConta } from '@/services/usuarioService'
import { iniciais } from '@/utils/format'

// As contas são criadas pelos próprios usuários (tela "Criar conta"). Aqui o admin só muda o
// perfil, corrige o nome, desativa e reativa contas; e-mail e senha pertencem ao titular.
type Rascunho = Usuario

const LIMITE_POR_PAGINA = 20
const DEBOUNCE_BUSCA_MS = 300
const PERFIS = Object.keys(PERFIL_LABEL) as Perfil[]

function normalizarTexto(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

function combinaComFiltro(
  usuario: Pick<Usuario, 'nome' | 'email' | 'perfil'>,
  busca: string,
  perfil: Perfil | '',
): boolean {
  if (perfil && usuario.perfil !== perfil) return false
  const termo = normalizarTexto(busca.trim())
  if (!termo) return true
  return normalizarTexto(usuario.nome).includes(termo) || normalizarTexto(usuario.email).includes(termo)
}

function houveAlteracao(original: Usuario, atual: Rascunho): boolean {
  return original.nome !== atual.nome || original.perfil !== atual.perfil
}

export function UsuariosPage() {
  const { usuario: eu } = useAuth()
  const toast = useToast()

  const [termoDigitado, setTermoDigitado] = useState('')
  const [buscaAtiva, setBuscaAtiva] = useState('')
  const [perfilFiltro, setPerfilFiltro] = useState<Perfil | ''>('')
  // "ativos": lista editável (rascunho + Salvar). "desativados": só leitura, com Reativar.
  const [situacao, setSituacao] = useState<SituacaoConta>('ativos')

  const [resultados, setResultados] = useState<Usuario[] | null>(null)
  const [totalServidor, setTotalServidor] = useState<number | null>(null)
  const [paginaAtual, setPaginaAtual] = useState(1)
  const [carregando, setCarregando] = useState(true)
  const [carregandoMais, setCarregandoMais] = useState(false)
  const [erroCarregamento, setErroCarregamento] = useState<string | null>(null)

  // Rascunho independente da busca atual para que edições e exclusões não se percam ao filtrar.
  const [originaisPorId, setOriginaisPorId] = useState<Record<string, Usuario>>({})
  const [editadosPorId, setEditadosPorId] = useState<Record<string, Rascunho>>({})
  const [excluidosIds, setExcluidosIds] = useState<string[]>([])

  const [editando, setEditando] = useState<Rascunho | null>(null)
  const [paraExcluir, setParaExcluir] = useState<Rascunho | null>(null)
  const [salvando, setSalvando] = useState(false)
  const [reenviando, setReenviando] = useState<string | null>(null)
  const [exportando, setExportando] = useState<'csv' | 'pdf' | null>(null)

  const requisicaoRef = useRef(0)
  const campoBuscaRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const temporizador = window.setTimeout(() => {
      setBuscaAtiva(termoDigitado.trim())
    }, DEBOUNCE_BUSCA_MS)
    return () => window.clearTimeout(temporizador)
  }, [termoDigitado])

  const registrarOriginais = useCallback((lista: Usuario[]) => {
    setOriginaisPorId((atual) => {
      const proximo = { ...atual }
      for (const usuario of lista) proximo[usuario.id] = usuario
      return proximo
    })
  }, [])

  const carregar = useCallback(async () => {
    const idRequisicao = ++requisicaoRef.current
    setCarregando(true)
    setErroCarregamento(null)
    const filtros = {
      busca: buscaAtiva || undefined,
      perfil: perfilFiltro || undefined,
    }
    try {
      const [lista, resumo] = await Promise.all([
        usuarioService.listar({ ...filtros, limite: LIMITE_POR_PAGINA, pagina: 1 }),
        usuarioService.resumir(filtros),
      ])
      if (requisicaoRef.current !== idRequisicao) return
      setResultados(lista)
      setTotalServidor(resumo.total)
      setPaginaAtual(1)
      registrarOriginais(lista)
    } catch (erro) {
      if (requisicaoRef.current !== idRequisicao) return
      setResultados(null)
      setTotalServidor(null)
      setErroCarregamento(
        erro instanceof Error
          ? erro.message
          : 'Não foi possível carregar os usuários. Verifique se o backend está ligado.',
      )
    } finally {
      if (requisicaoRef.current === idRequisicao) setCarregando(false)
    }
  }, [buscaAtiva, perfilFiltro, registrarOriginais])

  useEffect(() => {
    void carregar()
  }, [carregar])

  async function carregarMais() {
    if (carregandoMais || carregando) return
    const idRequisicao = requisicaoRef.current
    const proximaPagina = paginaAtual + 1
    setCarregandoMais(true)
    try {
      const proximos = await usuarioService.listar({
        busca: buscaAtiva || undefined,
        perfil: perfilFiltro || undefined,
        limite: LIMITE_POR_PAGINA,
        pagina: proximaPagina,
      })
      if (requisicaoRef.current !== idRequisicao) return
      setResultados((atual) => {
        const existentes = new Set((atual ?? []).map((u) => u.id))
        const novos = proximos.filter((u) => !existentes.has(u.id))
        return [...(atual ?? []), ...novos]
      })
      setPaginaAtual(proximaPagina)
      registrarOriginais(proximos)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível carregar mais usuários.')
    } finally {
      if (requisicaoRef.current === idRequisicao) setCarregandoMais(false)
    }
  }

  const excluidosSet = useMemo(() => new Set(excluidosIds), [excluidosIds])

  const mudancas = useMemo(() => {
    const editados = Object.values(editadosPorId).filter((u) => !excluidosSet.has(u.id))
    return {
      editados,
      excluidos: excluidosIds,
      total: editados.length + excluidosIds.length,
    }
  }, [editadosPorId, excluidosIds, excluidosSet])

  const visiveis = useMemo(() => {
    const mapa = new Map<string, Rascunho>()

    for (const usuario of resultados ?? []) {
      if (excluidosSet.has(usuario.id)) continue
      mapa.set(usuario.id, editadosPorId[usuario.id] ?? usuario)
    }

    for (const editado of Object.values(editadosPorId)) {
      if (excluidosSet.has(editado.id) || mapa.has(editado.id)) continue
      if (combinaComFiltro(editado, buscaAtiva, perfilFiltro)) {
        mapa.set(editado.id, editado)
      }
    }

    return [...mapa.values()].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))
  }, [resultados, excluidosSet, editadosPorId, buscaAtiva, perfilFiltro])

  const totalEncontrado = useMemo(() => {
    if (totalServidor === null) return null
    const excluidosNosResultados = (resultados ?? []).filter((u) => excluidosSet.has(u.id)).length
    return Math.max(0, totalServidor - excluidosNosResultados)
  }, [totalServidor, resultados, excluidosSet])

  const temMais = resultados !== null && totalServidor !== null && resultados.length < totalServidor
  const temFiltroAtivo = Boolean(buscaAtiva || perfilFiltro)

  function alterar(id: string, dados: Partial<EdicaoUsuario>) {
    const original = originaisPorId[id] ?? resultados?.find((u) => u.id === id)
    if (!original) return
    setEditadosPorId((atual) => {
      const base = atual[id] ?? original
      const atualizado: Rascunho = { ...base, ...dados }
      if (!houveAlteracao(original, atualizado)) {
        const proximo = { ...atual }
        delete proximo[id]
        return proximo
      }
      return { ...atual, [id]: atualizado }
    })
  }

  async function aplicarEdicao(alvo: Rascunho, dados: EdicaoUsuario) {
    const nome = dados.nome.trim().replace(/\s+/g, ' ')
    if (!nome) throw new Error('Informe o nome.')
    alterar(alvo.id, { nome, perfil: dados.perfil })
    setEditando(null)
  }

  async function salvar() {
    setSalvando(true)
    try {
      await usuarioService.salvarLote({
        atualizacoes: mudancas.editados.map((usuario) => {
          // Só envia o que mudou: a trilha de auditoria registra exatamente os campos alterados.
          const original = originaisPorId[usuario.id]
          return {
            id: usuario.id,
            ...(usuario.nome !== original?.nome && { nome: usuario.nome }),
            ...(usuario.perfil !== original?.perfil && { perfil: usuario.perfil }),
          }
        }),
        exclusoes: mudancas.excluidos,
      })
      toast.sucesso(mudancas.total === 1 ? 'Alteração salva.' : `${mudancas.total} alterações salvas.`)
      setEditadosPorId({})
      setExcluidosIds([])
      await carregar()
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível salvar. Nenhuma alteração foi aplicada.')
    } finally {
      setSalvando(false)
    }
  }

  async function reenviarConfirmacao(alvo: Rascunho) {
    setReenviando(alvo.id)
    try {
      const resposta = await usuarioService.reenviarVerificacao(alvo.id)
      toast.sucesso(resposta.mensagem)
    } catch (err) {
      toast.erro(err instanceof Error ? err.message : 'Não foi possível reenviar a confirmação.')
    } finally {
      setReenviando(null)
    }
  }

  function descartar() {
    setEditadosPorId({})
    setExcluidosIds([])
    toast.info('Alterações descartadas.')
  }

  // Conta anonimizada sai da lista (fica inativa) e de qualquer alteração pendente sobre ela.
  function removerAnonimizado(id: string) {
    if (resultados?.some((u) => u.id === id)) {
      setTotalServidor((total) => (total === null ? total : Math.max(0, total - 1)))
    }
    setResultados((atual) => atual?.filter((u) => u.id !== id) ?? atual)
    setOriginaisPorId((atual) => {
      if (!(id in atual)) return atual
      const proximo = { ...atual }
      delete proximo[id]
      return proximo
    })
    setEditadosPorId((atual) => {
      if (!(id in atual)) return atual
      const proximo = { ...atual }
      delete proximo[id]
      return proximo
    })
    setExcluidosIds((atual) => atual.filter((excluido) => excluido !== id))
  }

  async function exportar(formato: 'csv' | 'pdf') {
    setExportando(formato)
    try {
      const { arquivo, nome } = await usuarioService.exportar(formato, {
        busca: buscaAtiva || undefined,
        perfil: perfilFiltro || undefined,
        situacao,
      })
      const url = URL.createObjectURL(arquivo)
      const link = document.createElement('a')
      link.href = url
      link.download = nome ?? `usuarios.${formato}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast.sucesso(`Lista de usuários (${formato.toUpperCase()}) baixada.`)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível exportar.')
    } finally {
      setExportando(null)
    }
  }

  function limparFiltros() {
    setTermoDigitado('')
    setBuscaAtiva('')
    setPerfilFiltro('')
    campoBuscaRef.current?.focus()
  }

  function aoEnviarBusca(e: FormEvent) {
    e.preventDefault()
    setBuscaAtiva(termoDigitado.trim())
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 pb-24">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {situacao === 'ativos' ? (
          <p className="text-sm text-muted" aria-live="polite">
            {erroCarregamento
              ? 'Não foi possível carregar'
              : totalEncontrado !== null
                ? `${totalEncontrado} ${totalEncontrado === 1 ? 'usuário encontrado' : 'usuários encontrados'}${carregando ? ' · Atualizando…' : ''}`
                : 'Carregando…'}
          </p>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          {(['csv', 'pdf'] as const).map((formato) => (
            <button
              key={formato}
              type="button"
              onClick={() => void exportar(formato)}
              disabled={exportando !== null}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-white px-3 text-xs font-semibold text-brand-900 hover:bg-brand-50 disabled:opacity-60"
            >
              <Download size={14} /> {exportando === formato ? 'Gerando…' : formato.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <p className="flex items-start gap-2 rounded-xl bg-brand-50 px-3 py-2 text-xs text-brand-900">
        <Info size={14} className="mt-0.5 shrink-0 text-brand-500" aria-hidden />
        As contas são criadas pelas próprias pessoas, com o e-mail @edu.unifor.br, na opção “Criar conta” do login. Aqui
        você muda o perfil, corrige o nome, desativa e reativa contas.
      </p>

      <PedidosExclusao onAnonimizado={removerAnonimizado} />

      <section className="space-y-3 rounded-2xl border border-line bg-white p-3 shadow-sm">
        <div role="tablist" aria-label="Situação das contas" className="grid grid-cols-2 gap-1 rounded-xl bg-surface p-1">
          {(
            [
              ['ativos', 'Ativas'],
              ['desativados', 'Desativadas'],
            ] as const
          ).map(([valor, rotulo]) => {
            const selecionada = situacao === valor
            // Trocar de lista com alterações pendentes esconderia o rascunho: salve ou descarte antes.
            const bloqueada = !selecionada && mudancas.total > 0
            return (
              <button
                key={valor}
                type="button"
                role="tab"
                aria-selected={selecionada}
                disabled={bloqueada}
                title={bloqueada ? 'Salve ou descarte as alterações pendentes antes' : undefined}
                onClick={() => setSituacao(valor)}
                className={`h-9 rounded-lg text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  selecionada ? 'bg-white text-brand-900 shadow-sm' : 'text-muted hover:text-brand-900'
                }`}
              >
                {rotulo}
              </button>
            )
          })}
        </div>

        <form role="search" onSubmit={aoEnviarBusca}>
          <label htmlFor="busca-usuarios" className="mb-1.5 block text-xs font-semibold text-brand-900">
            Buscar usuário
          </label>
          <div className="flex h-11 items-center gap-2 rounded-xl border border-line bg-surface px-3 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
            <Search size={17} className="shrink-0 text-muted" aria-hidden="true" />
            <input
              ref={campoBuscaRef}
              id="busca-usuarios"
              type="text"
              inputMode="search"
              enterKeyHint="search"
              value={termoDigitado}
              onChange={(e) => setTermoDigitado(e.target.value)}
              placeholder="Digite nome ou e-mail…"
              className="h-full min-w-0 flex-1 bg-transparent text-sm text-brand-900 outline-none placeholder:text-muted"
            />
            {termoDigitado && (
              <button
                type="button"
                aria-label="Limpar busca"
                onClick={() => {
                  setTermoDigitado('')
                  setBuscaAtiva('')
                  campoBuscaRef.current?.focus()
                }}
                className="rounded-lg p-1 text-muted hover:bg-brand-50 hover:text-brand-900"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </form>

        <div role="group" aria-label="Filtrar por perfil" className="flex flex-wrap gap-1.5">
          <button
            type="button"
            aria-pressed={perfilFiltro === ''}
            onClick={() => setPerfilFiltro('')}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
              perfilFiltro === ''
                ? 'bg-brand-900 text-white'
                : 'bg-surface text-brand-900 hover:bg-brand-50'
            }`}
          >
            Todos
          </button>
          {PERFIS.map((perfil) => {
            const ativo = perfilFiltro === perfil
            return (
              <button
                key={perfil}
                type="button"
                aria-pressed={ativo}
                onClick={() => setPerfilFiltro(ativo ? '' : perfil)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                  ativo
                    ? 'bg-brand-900 text-white'
                    : 'bg-surface text-brand-900 hover:bg-brand-50'
                }`}
              >
                {PERFIL_LABEL[perfil]}
              </button>
            )
          })}
        </div>
      </section>

      {situacao === 'desativados' ? (
        <UsuariosDesativados busca={buscaAtiva} perfil={perfilFiltro} onReativado={() => void carregar()} />
      ) : (
        <>
          {erroCarregamento && (
            <section className="rounded-2xl border border-sos-200 bg-sos-50 p-4 text-sm text-sos-700" role="alert">
              <p className="font-semibold">Não foi possível abrir os usuários.</p>
              <p className="mt-1 text-xs">{erroCarregamento}</p>
              <button
                onClick={() => void carregar()}
                className="mt-3 rounded-lg bg-sos-700 px-3 py-2 text-xs font-semibold text-white hover:bg-sos-800"
              >
                Tentar novamente
              </button>
            </section>
          )}

          {!erroCarregamento && !carregando && resultados !== null && visiveis.length === 0 && (
            <section className="rounded-2xl border border-line bg-white p-8 text-center shadow-sm">
              <Users size={28} className="mx-auto text-muted" aria-hidden="true" />
              <p className="mt-2 text-sm font-semibold text-brand-900">
                {buscaAtiva
                  ? `Nenhum usuário encontrado para “${buscaAtiva}”${perfilFiltro ? ` no perfil ${PERFIL_LABEL[perfilFiltro]}` : ''}.`
                  : perfilFiltro
                    ? `Nenhum usuário encontrado para o perfil ${PERFIL_LABEL[perfilFiltro]}.`
                    : 'Nenhum usuário cadastrado.'}
              </p>
              {temFiltroAtivo && (
                <button
                  type="button"
                  onClick={limparFiltros}
                  className="mt-3 rounded-xl bg-brand-50 px-4 py-2 text-xs font-semibold text-brand-500 hover:bg-brand-100"
                >
                  Limpar filtros
                </button>
              )}
            </section>
          )}

          <ul className="space-y-3">
            {visiveis.map((u) => {
              const proprio = u.id === eu?.id
              const original = originaisPorId[u.id]
              const alterado = Boolean(editadosPorId[u.id])
              return (
                <li
                  key={u.id}
                  className={`rounded-2xl border bg-white p-4 shadow-sm ${alterado ? 'border-amber-400' : 'border-line'}`}
                >
                  <div className="flex items-center gap-3">
                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-brand-900 text-xs font-semibold text-white">
                      {iniciais(u.nome)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-brand-900">
                        {u.nome} {proprio && <span className="text-[11px] font-medium text-muted">(você)</span>}
                        {alterado && (
                          <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-700">
                            ALTERADO
                          </span>
                        )}
                      </p>
                      <p className="truncate text-xs text-muted">{u.email}</p>
                      {u.emailVerificado === false && (
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                          <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">
                            <MailWarning size={12} aria-hidden /> E-mail não confirmado
                          </span>
                          <button
                            type="button"
                            onClick={() => void reenviarConfirmacao(u)}
                            disabled={reenviando === u.id}
                            className="text-[11px] font-semibold text-brand-500 hover:text-brand-900 disabled:opacity-60"
                          >
                            {reenviando === u.id ? 'Enviando…' : 'Reenviar confirmação'}
                          </button>
                        </p>
                      )}
                    </div>
                    <button
                      aria-label={`Editar ${u.nome}`}
                      onClick={() => setEditando(u)}
                      className="rounded-lg p-2 text-brand-500 hover:bg-brand-50"
                    >
                      <Pencil size={18} />
                    </button>
                    <button
                      aria-label={`Desativar ${u.nome}`}
                      disabled={proprio}
                      title={proprio ? 'Você não pode desativar a si mesmo' : undefined}
                      onClick={() => setParaExcluir(u)}
                      className="rounded-lg p-2 text-sos-700 hover:bg-sos-50 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>

                  <div className="mt-3 flex items-center gap-2">
                    <label htmlFor={`perfil-${u.id}`} className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                      Perfil
                    </label>
                    <select
                      id={`perfil-${u.id}`}
                      value={u.perfil}
                      disabled={proprio}
                      title={proprio ? 'Você não pode alterar o seu próprio perfil' : undefined}
                      onChange={(e) => alterar(u.id, { perfil: e.target.value as Perfil })}
                      className="h-9 flex-1 rounded-lg border border-line bg-surface px-2 text-sm text-brand-900 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:opacity-60"
                    >
                      {PERFIS.map((p) => (
                        <option key={p} value={p}>
                          {PERFIL_LABEL[p]}
                        </option>
                      ))}
                    </select>
                    {original && original.perfil !== u.perfil && (
                      <span className="text-[11px] text-muted">era {PERFIL_LABEL[original.perfil]}</span>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>

          <CarregarMais visivel={temMais} carregando={carregandoMais} onClick={() => void carregarMais()} />
        </>
      )}

      {mudancas.total > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white/95 p-3 backdrop-blur">
          <div className="mx-auto flex max-w-2xl items-center gap-2">
            <p className="hidden flex-1 text-xs text-muted sm:block">
              {mudancas.total} {mudancas.total === 1 ? 'alteração pendente' : 'alterações pendentes'}
              {mudancas.excluidos.length > 0 && ` · ${mudancas.excluidos.length} para desativar`}
            </p>
            <button
              onClick={descartar}
              disabled={salvando}
              className="h-11 flex-1 rounded-xl bg-brand-50 text-sm font-semibold text-brand-900 hover:bg-brand-100 disabled:opacity-60 sm:flex-none sm:px-5"
            >
              Descartar
            </button>
            <button
              onClick={() => void salvar()}
              disabled={salvando}
              className="h-11 flex-[2] rounded-xl bg-brand-900 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60 sm:flex-none sm:px-6"
            >
              {salvando ? 'Salvando…' : `Salvar alterações (${mudancas.total})`}
            </button>
          </div>
        </div>
      )}

      {editando && (
        <UsuarioFormModal
          usuario={editando}
          perfilTravado={editando.id === eu?.id}
          onClose={() => setEditando(null)}
          onSubmit={async (dados) => aplicarEdicao(editando, dados)}
        />
      )}

      {paraExcluir && (
        <ConfirmModal
          titulo="Desativar usuário?"
          confirmarLabel="Sim, desativar"
          onCancel={() => setParaExcluir(null)}
          onConfirm={() => {
            const alvo = paraExcluir
            setParaExcluir(null)
            setExcluidosIds((atual) => (atual.includes(alvo.id) ? atual : [...atual, alvo.id]))
            setEditadosPorId((atual) => {
              if (!(alvo.id in atual)) return atual
              const proximo = { ...atual }
              delete proximo[alvo.id]
              return proximo
            })
          }}
        >
          Tem certeza que deseja desativar <strong className="text-brand-900">{paraExcluir.nome}</strong>? A pessoa não
          conseguirá mais entrar, e o histórico das ocorrências continua guardado. Dá para reativar depois, na aba
          “Desativadas”. Só vale depois de clicar em “Salvar
          alterações”.
        </ConfirmModal>
      )}
    </div>
  )
}
