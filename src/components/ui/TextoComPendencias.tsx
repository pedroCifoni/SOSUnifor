import { Fragment } from 'react'

const PENDENCIA = /(\[A DEFINIR:[^\]]*\])/g

/** Destaca trechos "[A DEFINIR: ...]" para que não passem despercebidos antes da publicação. */
export function TextoComPendencias({ texto }: { texto: string }) {
  return (
    <>
      {texto.split(PENDENCIA).map((parte, i) =>
        parte.startsWith('[A DEFINIR:') ? (
          <mark key={i} className="rounded bg-amber-100 px-1 text-amber-900">
            {parte}
          </mark>
        ) : (
          <Fragment key={i}>{parte}</Fragment>
        ),
      )}
    </>
  )
}
