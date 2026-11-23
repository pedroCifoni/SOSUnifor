import { useEffect, useState } from 'react'
import { Download, FileText, LogOut, Mail, ShieldCheck, Trash2, User } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useAuth } from '@/hooks/useAuth'
import { useToast } from '@/hooks/useToast'
import { PERFIL_LABEL } from '@/models/usuario'
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

export function PerfilPage() {
  const { usuario, logout } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [baixando, setBaixando] = useState(false)
  const [confirmarExclusao, setConfirmarExclusao] = useState(false)
  const [exclusaoSolicitadaEm, setExclusaoSolicitadaEm] = useState<string | null>(null)

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

  return (
    <div className="mx-auto max-w-md space-y-5">
      <section className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-white p-6 text-center shadow-sm">
        <span className="grid size-20 place-items-center rounded-full bg-brand-900 text-2xl font-bold text-white">
          {iniciais(usuario.nome)}
        </span>
        <div>
          <h2 className="text-xl font-bold text-brand-900">{usuario.nome}</h2>
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
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">Nome</dt>
            <dd className="text-sm text-brand-900">{usuario.nome}</dd>
          </div>
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
