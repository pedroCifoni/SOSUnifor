interface CarregarMaisProps {
  visivel: boolean
  carregando?: boolean
  onClick: () => void
}

/** Botão "Carregar mais" das listas paginadas por cursor. */
export function CarregarMais({ visivel, carregando, onClick }: CarregarMaisProps) {
  if (!visivel) return null
  return (
    <div className="mt-4 flex justify-center">
      <button
        onClick={onClick}
        disabled={carregando}
        className="h-10 rounded-xl bg-brand-50 px-5 text-xs font-semibold text-brand-500 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {carregando ? 'Carregando…' : 'Carregar mais'}
      </button>
    </div>
  )
}
