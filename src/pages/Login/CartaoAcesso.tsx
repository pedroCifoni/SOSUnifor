import type { ReactNode } from 'react'

/** Moldura das telas públicas de acesso (recuperação e redefinição de senha). */
export function CartaoAcesso({ titulo, descricao, children }: { titulo: string; descricao: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-gradient-to-b from-brand-50 to-surface px-4 py-8">
      <div className="w-full max-w-md rounded-3xl border border-line bg-white p-6 shadow-sm sm:p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <img src="/unifor-logo-vertical.svg" alt="UNIFOR" className="mb-4 h-20" />
          <h1 className="mt-1 text-2xl font-bold text-brand-900">{titulo}</h1>
          <p className="mt-1 text-sm text-muted">{descricao}</p>
        </div>
        {children}
        <p className="mt-6 text-center text-[11px] text-muted">Diretoria de Tecnologia da Informação · UNIFOR</p>
      </div>
    </div>
  )
}
