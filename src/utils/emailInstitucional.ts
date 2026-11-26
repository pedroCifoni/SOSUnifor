/**
 * Regras do autocadastro. Espelham a validação da API (backend/app/dtos/base.py e auth_dto.py):
 * a API é quem decide; aqui é só para avisar a pessoa antes de enviar.
 */
export const DOMINIO_INSTITUCIONAL = 'edu.unifor.br'
export const TAMANHO_MINIMO_SENHA = 8
export const TAMANHO_MAXIMO_SENHA = 100

const PARTE_LOCAL = /^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?$/

export function normalizarEmail(email: string): string {
  return email.trim().toLowerCase()
}

/** Devolve a mensagem de erro, ou null se o e-mail é um endereço válido do domínio @edu.unifor.br. */
export function problemaNoEmailInstitucional(email: string): string | null {
  const normalizado = normalizarEmail(email)
  const partes = normalizado.split('@')
  if (partes.length !== 2 || !partes[0] || !partes[1]) return 'Informe um e-mail válido.'
  const [parteLocal, dominio] = partes
  if (dominio !== DOMINIO_INSTITUCIONAL) return `Use o seu e-mail institucional (@${DOMINIO_INSTITUCIONAL}).`
  if (!PARTE_LOCAL.test(parteLocal) || parteLocal.includes('..')) return 'Informe um e-mail válido.'
  return null
}

/** Devolve a mensagem de erro, ou null se a senha atende às regras do cadastro. */
export function problemaNaSenha(senha: string, email: string): string | null {
  if (senha.length < TAMANHO_MINIMO_SENHA) return `A senha precisa ter ao menos ${TAMANHO_MINIMO_SENHA} caracteres.`
  if (senha.length > TAMANHO_MAXIMO_SENHA) return `A senha pode ter no máximo ${TAMANHO_MAXIMO_SENHA} caracteres.`
  if (!senha.trim()) return 'A senha não pode ser só espaços.'
  const emailNormalizado = normalizarEmail(email)
  const senhaMinuscula = senha.toLowerCase()
  if (emailNormalizado && (senhaMinuscula === emailNormalizado || senhaMinuscula === emailNormalizado.split('@')[0])) {
    return 'A senha não pode ser igual ao seu e-mail.'
  }
  return null
}
