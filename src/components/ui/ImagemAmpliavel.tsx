import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Maximize2, X } from 'lucide-react'

interface ImagemAmpliavelProps {
  src: string
  alt: string
  className?: string
}

/** Miniatura que mostra a imagem inteira (sem recorte) e abre em tela cheia ao clicar. */
export function ImagemAmpliavel({ src, alt, className = 'h-40' }: ImagemAmpliavelProps) {
  const [aberta, setAberta] = useState(false)

  useEffect(() => {
    if (!aberta) return
    // Captura o Escape antes de outros modais, para fechar só a imagem ampliada.
    const aoTecla = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.stopPropagation()
      setAberta(false)
    }
    window.addEventListener('keydown', aoTecla, true)
    return () => window.removeEventListener('keydown', aoTecla, true)
  }, [aberta])

  return (
    <>
      <button
        type="button"
        onClick={() => setAberta(true)}
        aria-label={`Ampliar ${alt}`}
        className={`group relative block w-full cursor-zoom-in bg-brand-50/40 ${className}`}
      >
        <img src={src} alt={alt} className="size-full object-contain" />
        <span className="absolute bottom-1.5 right-1.5 grid size-7 place-items-center rounded-full bg-black/60 text-white opacity-80 transition group-hover:opacity-100">
          <Maximize2 size={14} />
        </span>
      </button>

      {aberta &&
        createPortal(
          <div
            role="dialog"
            aria-modal="true"
            aria-label={alt}
            className="fixed inset-0 z-50 grid cursor-zoom-out place-items-center bg-black/85 p-4"
            onClick={(e) => {
              e.stopPropagation()
              setAberta(false)
            }}
          >
            <img src={src} alt={alt} className="max-h-full max-w-full rounded-lg object-contain shadow-2xl" />
            <button
              type="button"
              aria-label="Fechar imagem"
              onClick={(e) => {
                e.stopPropagation()
                setAberta(false)
              }}
              className="absolute right-4 top-4 grid size-10 place-items-center rounded-full bg-white/15 text-white hover:bg-white/25"
            >
              <X size={22} />
            </button>
          </div>,
          document.body,
        )}
    </>
  )
}
