import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { Camera, Download, FileText, KeyRound, LogOut, Mail, Pencil, ShieldCheck, Trash2, User, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { PERFIL_LABEL } from '@/models/usuario'
import { perfilService } from '@/services/perfilService'
import { privacidadeService } from '@/services/privacidadeService'
import { iniciais } from '@/utils/format'

function salvarComoArquivo(conteudo: unknown, nomeArquivo: string) {
  const blob = new Blob([JSON.stringify(conteudo, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = nomeArquivo
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function TrocarSenha({ email }: { email: string }) {
  const toast = useToast()
  const { login } = useAuth()
  const [aberto, setAberto] = useState(false)
  const [senhaAtual, setSenhaAtual] = useState('')
  const [novaSenha, setNovaSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [salvando, setSalvando] = useState(false)

  async function salvar(evento: FormEvent) {
    evento.preventDefault()
    if (novaSenha !== confirmacao) {
      toast.erro('A confirmação não é igual à nova senha.')
      return
    }
    setSalvando(true)
    try {
      const resposta = await perfilService.trocarSenha(senhaAtual, novaSenha)
      // A troca encerra as sessões abertas; esta continua com um login novo, já com a senha nova.
      await login({ email, senha: novaSenha }).catch(() => undefined)
      toast.sucesso(resposta.mensagem)
      setSenhaAtual('')
      setNovaSenha('')
      setConfirmacao('')
      setAberto(false)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível trocar a senha.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <section className="rounded-2xl border border-line bg-white p-4 shadow-sm">
      <button
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        className="flex w-full items-center gap-2 text-left text-sm font-bold text-brand-900"
      >
        <KeyRound size={16} className="text-brand-500" /> Trocar senha
      </button>
      {aberto && (
        <form onSubmit={(e) => void salvar(e)} className="mt-4 space-y-3">
          <Input
            label="Senha atual"
            type="password"
            autoComplete="current-password"
            value={senhaAtual}
            onChange={(e) => setSenhaAtual(e.target.value)}
            required
          />
          <Input
            label="Nova senha (mínimo 8 caracteres)"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
            required
          />
          <Input
            label="Confirme a nova senha"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={confirmacao}
            onChange={(e) => setConfirmacao(e.target.value)}
            required
          />
          <Button type="submit" loading={salvando}>
            Salvar nova senha
          </Button>
        </form>
      )}
    </section>
  )
}

export function PerfilPage() {
  const { usuario, logout, renovarSessao } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [baixando, setBaixando] = useState(false)
  const [confirmarExclusao, setConfirmarExclusao] = useState(false)
  const [exclusaoSolicitadaEm, setExclusaoSolicitadaEm] = useState<string | null>(null)
  const [fotoUrl, setFotoUrl] = useState<string | null>(null)
  const [enviandoFoto, setEnviandoFoto] = useState(false)
  const [nomeAtual, setNomeAtual] = useState<string | null>(null)
  const [editandoNome, setEditandoNome] = useState(false)
  const [nomeEditado, setNomeEditado] = useState('')
  const [salvandoNome, setSalvandoNome] = useState(false)

  // Foto de perfil: vem autenticada (Blob) e vira uma URL local, revogada ao sair da tela.
  useEffect(() => {
    if (!usuario) return
    let ativo = true
    let url: string | null = null
    perfilService
      .consultar()
      .then(async (perfil) => {
        if (!ativo) return
        setNomeAtual(perfil.nome)
        if (perfil.temAvatar) {
          url = await perfilService.urlDoAvatar()
          if (ativo) setFotoUrl(url)
          else URL.revokeObjectURL(url)
        }
      })
      .catch(() => {
        // Sem o perfil, a tela mostra os dados do token.
      })
    return () => {
      ativo = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [usuario])

  // O pedido de exclusão fica gravado no back: ao abrir o Perfil de novo, mostra que já foi feito.
  useEffect(() => {
    if (!usuario) return
    let ativo = true
    privacidadeService
      .situacaoTermos()
      .then((situacao) => {
        if (ativo && situacao.exclusaoSolicitadaEm) setExclusaoSolicitadaEm(situacao.exclusaoSolicitadaEm)
      })
      .catch(() => {
        // Sem a informação, o botão continua disponível; um pedido repetido devolve a data original.
      })
    return () => {
      ativo = false
    }
  }, [usuario])

  if (!usuario) return null

  const perfil = PERFIL_LABEL[usuario.perfil]
  const privilegiado = usuario.perfil !== 'usuario'

  function sair() {
    logout()
    navigate('/login', { replace: true })
  }

  async function baixarMeusDados() {
    setBaixando(true)
    try {
      const dados = await privacidadeService.exportarDados()
      salvarComoArquivo(dados, `meus-dados-unisos-${new Date().toISOString().slice(0, 10)}.json`)
      toast.sucesso('Arquivo com os seus dados gerado.')
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível gerar o arquivo.')
    } finally {
      setBaixando(false)
    }
  }

  async function solicitarExclusao() {
    setConfirmarExclusao(false)
    try {
      const resposta = await privacidadeService.solicitarExclusao()
      setExclusaoSolicitadaEm(resposta.solicitadaEm)
      toast.sucesso(resposta.mensagem)
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível registrar o pedido.')
    }
  }

  async function trocarFoto(evento: ChangeEvent<HTMLInputElement>) {
    const arquivo = evento.target.files?.[0]
    evento.target.value = ''
    if (!arquivo) return
    setEnviandoFoto(true)
    try {
      await perfilService.enviarAvatar(arquivo)
      const novaUrl = await perfilService.urlDoAvatar()
      setFotoUrl((anterior) => {
        if (anterior) URL.revokeObjectURL(anterior)
        return novaUrl
      })
      toast.sucesso('Foto atualizada.')
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível enviar a foto.')
    } finally {
      setEnviandoFoto(false)
    }
  }

  async function removerFoto() {
    try {
      await perfilService.removerAvatar()
      setFotoUrl((anterior) => {
        if (anterior) URL.revokeObjectURL(anterior)
        return null
      })
      toast.sucesso('Foto removida.')
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível remover a foto.')
    }
  }

  async function salvarNome(evento: FormEvent) {
    evento.preventDefault()
    setSalvandoNome(true)
    try {
      const atualizado = await perfilService.atualizarNome(nomeEditado)
      setNomeAtual(atualizado.nome)
      setEditandoNome(false)
      await renovarSessao().catch(() => undefined)
      toast.sucesso('Nome atualizado.')
    } catch (erro) {
      toast.erro(erro instanceof Error ? erro.message : 'Não foi possível salvar o nome.')
    } finally {
      setSalvandoNome(false)
    }
  }

  const nome = nomeAtual ?? usuario.nome

  return (
    <div className="mx-auto max-w-md space-y-5">
      <section className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-white p-6 text-center shadow-sm">
        <div className="relative">
          {fotoUrl ? (
            <img src={fotoUrl} alt="Sua foto de perfil" className="size-20 rounded-full object-cover" />
          ) : (
            <span className="grid size-20 place-items-center rounded-full bg-brand-900 text-2xl font-bold text-white">
              {iniciais(nome)}
            </span>
          )}
          <label
            className="absolute -bottom-1 -right-1 grid size-8 cursor-pointer place-items-center rounded-full border-2 border-white bg-brand-500 text-white shadow hover:bg-brand-700"
            title="Trocar foto"
          >
            <Camera size={15} />
            <span className="sr-only">Trocar foto de perfil</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              disabled={enviandoFoto}
              onChange={(e) => void trocarFoto(e)}
            />
          </label>
        </div>
        {fotoUrl && (
          <button onClick={() => void removerFoto()} className="text-xs font-semibold text-muted hover:text-sos-700">
            Remover foto
          </button>
        )}
        <div>
          <h2 className="text-xl font-bold text-brand-900">{nome}</h2>
          <span
            className={`mt-1 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold ${
              privilegiado ? 'bg-brand-900 text-white' : 'bg-brand-50 text-brand-500'
            }`}
          >
            {privilegiado ? <ShieldCheck size={12} /> : <User size={12} />}
            {perfil}
          </span>
        </div>
      </section>

      <dl className="divide-y divide-line rounded-2xl border border-line bg-white shadow-sm">
        <div className="flex items-center gap-3 p-4">
          <User size={18} className="text-brand-500" />
          {editandoNome ? (
            <form onSubmit={(e) => void salvarNome(e)} className="flex min-w-0 flex-1 items-end gap-2">
              <div className="min-w-0 flex-1">
                <Input
                  label="Nome"
                  value={nomeEditado}
                  onChange={(e) => setNomeEditado(e.target.value)}
                  minLength={3}
                  maxLength={150}
                  required
                  autoFocus
                />
              </div>
              <Button type="submit" loading={salvandoNome} className="!w-auto">
                Salvar
              </Button>
              <button
                type="button"
                aria-label="Cancelar edição do nome"
                onClick={() => setEditandoNome(false)}
                className="grid size-12 place-items-center rounded-xl text-muted hover:bg-surface"
              >
                <X size={18} />
              </button>
            </form>
          ) : (
            <>
              <div className="min-w-0 flex-1">
                <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Nome</dt>
                <dd className="text-sm text-brand-900">{nome}</dd>
              </div>
              <button
                aria-label="Editar nome"
                onClick={() => {
                  setNomeEditado(nome)
                  setEditandoNome(true)
                }}
                className="grid size-9 place-items-center rounded-lg text-brand-500 hover:bg-brand-50"
              >
                <Pencil size={16} />
              </button>
            </>
          )}
        </div>
        <div className="flex items-center gap-3 p-4">
          <Mail size={18} className="text-brand-500" />
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">E-mail institucional</dt>
            <dd className="text-sm text-brand-900">{usuario.email}</dd>
          </div>
        </div>
        <div className="flex items-center gap-3 p-4">
          <ShieldCheck size={18} className="text-brand-500" />
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Perfil de acesso</dt>
            <dd className="text-sm text-brand-900">{perfil}</dd>
          </div>
        </div>
      </dl>

      <TrocarSenha email={usuario.email} />

      <section className="space-y-1 rounded-2xl border border-line bg-white p-4 shadow-sm">
        <h3 className="mb-2 flex items-center gap-2 text-sm font-bold text-brand-900">
          <ShieldCheck size={16} className="text-brand-500" /> Privacidade e seus dados (LGPD)
        </h3>
        <Link
          to="/privacidade"
          className="flex h-11 items-center gap-2 rounded-xl px-3 text-sm font-medium text-brand-900 hover:bg-surface"
        >
          <FileText size={18} className="text-brand-500" /> Política de Privacidade
        </Link>
        <button
          onClick={() => void baixarMeusDados()}
          disabled={baixando}
          className="flex h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-medium text-brand-900 hover:bg-surface disabled:opacity-60"
        >
          <Download size={18} className="text-brand-500" /> {baixando ? 'Gerando arquivo…' : 'Baixar meus dados (.json)'}
        </button>
        {exclusaoSolicitadaEm ? (
          <p className="rounded-xl bg-brand-50 px-3 py-2 text-xs text-brand-900">
            Pedido de exclusão registrado em {new Date(exclusaoSolicitadaEm).toLocaleString('pt-BR')}. A administração
            vai concluí-lo; depois disso esta conta deixa de funcionar.
          </p>
        ) : (
          <button
            onClick={() => setConfirmarExclusao(true)}
            className="flex h-11 w-full items-center gap-2 rounded-xl px-3 text-left text-sm font-medium text-sos-700 hover:bg-sos-50"
          >
            <Trash2 size={18} /> Solicitar exclusão dos meus dados
          </button>
        )}
      </section>

      {confirmarExclusao && (
        <ConfirmModal
          titulo="Solicitar a exclusão dos seus dados?"
          confirmarLabel="Sim, solicitar"
          onCancel={() => setConfirmarExclusao(false)}
          onConfirm={() => void solicitarExclusao()}
        >
          A administração será avisada e vai anonimizar a sua conta: o seu nome e e-mail serão apagados de forma
          irreversível e você não conseguirá mais entrar. As ocorrências que você abriu continuam guardadas como registro
          de segurança, sem identificar você. Se quiser, baixe antes uma cópia dos seus dados.
        </ConfirmModal>
      )}

      <button
        onClick={sair}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-xl border border-line text-sm font-semibold text-sos-700 hover:bg-sos-50"
      >
        <LogOut size={18} /> Sair
      </button>
    </div>
  )
}
