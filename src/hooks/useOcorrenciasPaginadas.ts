import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Ocorrencia, StatusOcorrencia, TipoOcorrencia } from '@/models/ocorrencia'
import { ocorrenciaService } from '@/services/ocorrenciaService'
import { useToast } from './useToast'

export const LIMITE_PADRAO = 50

interface Opcoes {
  /** Um ou mais status. Com vários, cada status é paginado separadamente e as páginas são mescladas. */
  status?: StatusOcorrencia | StatusOcorrencia[]
  tipo?: TipoOcorrencia
  limite?: number
  /** Quando false, nada é buscado (ex.: usuário ainda não carregado). */
  habilitado?: boolean
  /**
   * Qualquer valor que, ao mudar, atualiza a primeira página (ex.: revisão das notificações),
   * mantendo as páginas já trazidas por "carregar mais".
   */
  revisao?: unknown
}

interface Fluxo {
  status?: StatusOcorrencia
  itens: Ocorrencia[]
  temMais: boolean
}

// Mesma ordem da API: criado_em DESC, id DESC.
export function comparar(a: Ocorrencia, b: Ocorrencia) {
  const diferenca = Date.parse(b.criadoEm) - Date.parse(a.criadoEm)
  if (diferenca !== 0) return diferenca
  return a.id < b.id ? 1 : a.id > b.id ? -1 : 0
}

/**
 * Troca o trecho coberto pela primeira página nova e mantém os itens mais antigos já carregados
 * (e, com eles, o cursor do fim). Itens que saíram do filtro nesse trecho somem.
 */
function mesclarPrimeiraPagina(anterior: Fluxo | undefined, status: StatusOcorrencia | undefined, pagina: Ocorrencia[], limite: number): Fluxo {
  const ultimo = pagina[pagina.length - 1]
  const primeiroAnterior = anterior?.itens[0]
  // Só junta se a página nova alcança o topo antigo; senão haveria um buraco entre as duas.
  if (!anterior || !primeiroAnterior || pagina.length < limite || !ultimo || comparar(primeiroAnterior, ultimo) > 0) {
    return { status, itens: pagina, temMais: pagina.length >= limite }
  }
  const ids = new Set(pagina.map((o) => o.id))
  const maisAntigos = anterior.itens.filter((o) => !ids.has(o.id) && comparar(o, ultimo) > 0)
  return { status, itens: [...pagina, ...maisAntigos], temMais: maisAntigos.length > 0 ? anterior.temMais : true }
}

/**
 * Lista de ocorrências paginada por cursor (criadoEm + id do último item).
 * "carregarMais" busca a próxima página até a API devolver menos itens que o limite.
 */
export function useOcorrenciasPaginadas({ status, tipo, limite = LIMITE_PADRAO, habilitado = true, revisao }: Opcoes) {
  const listaStatus = useMemo(
    () => (status === undefined ? [undefined] : Array.isArray(status) ? status : [status]),
    // Compara por conteúdo para aceitar arrays literais criados a cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [Array.isArray(status) ? status.join(',') : status],
  )
  const [fluxos, setFluxos] = useState<Fluxo[] | null>(null)
  const [carregandoMais, setCarregandoMais] = useState(false)
  const geracao = useRef(0)
  const toast = useToast()

  const recarregar = useCallback(async () => {
    if (!habilitado) return
    const atual = ++geracao.current
    try {
      const paginas = await Promise.all(listaStatus.map((s) => ocorrenciaService.listar({ status: s, tipo, limite })))
      if (atual !== geracao.current) return
      // Se o filtro mudou, `anterior` é null (zerado no efeito abaixo) e fica só a primeira página.
      setFluxos((anterior) =>
        listaStatus.map((s, i) => mesclarPrimeiraPagina(anterior?.find((f) => f.status === s), s, paginas[i], limite)),
      )
    } catch {
      if (atual === geracao.current) setFluxos((anterior) => anterior ?? [])
    }
  }, [habilitado, listaStatus, tipo, limite])

  useEffect(() => {
    setFluxos(null)
  }, [listaStatus, tipo, limite])

  useEffect(() => {
    void recarregar()
  }, [recarregar, revisao])

  const carregarMais = useCallback(async () => {
    if (!fluxos || carregandoMais) return
    const atual = geracao.current
    setCarregandoMais(true)
    try {
      const novos = await Promise.all(
        fluxos.map(async (fluxo) => {
          const ultimo = fluxo.itens[fluxo.itens.length - 1]
          if (!fluxo.temMais || !ultimo) return fluxo
          const pagina = await ocorrenciaService.listar({
            status: fluxo.status,
            tipo,
            limite,
            antesDe: ultimo.criadoEm,
            antesId: ultimo.id,
          })
          return { ...fluxo, itens: [...fluxo.itens, ...pagina], temMais: pagina.length >= limite }
        }),
      )
      if (atual === geracao.current) setFluxos(novos)
    } catch {
      toast.erro('Não foi possível carregar mais ocorrências.')
    } finally {
      setCarregandoMais(false)
    }
  }, [fluxos, carregandoMais, tipo, limite, toast])

  const itens = useMemo(() => {
    if (!fluxos) return null
    const vistos = new Set<string>()
    const todos = fluxos
      .flatMap((f) => f.itens)
      .filter((o) => (vistos.has(o.id) ? false : (vistos.add(o.id), true)))
      .sort(comparar)
    // Com vários status, só exibe itens até a "fronteira" dos fluxos que ainda têm páginas,
    // para não pular itens de um status que ainda não foram carregados.
    const fronteiras = fluxos.filter((f) => f.temMais && f.itens.length > 0).map((f) => f.itens[f.itens.length - 1])
    if (fluxos.length === 1) return todos
    const fronteira = fronteiras.sort(comparar)[0]
    return fronteira ? todos.filter((o) => comparar(o, fronteira) <= 0) : todos
  }, [fluxos])

  const temMais = fluxos?.some((f) => f.temMais) ?? false

  return { itens, temMais, carregandoMais, carregarMais, recarregar }
}
