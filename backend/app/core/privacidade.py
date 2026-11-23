"""Constantes da adequação à LGPD (Lei 13.709/2018).

`VERSAO_TERMOS` precisa ser igual à constante de mesmo nome no front (src/models/privacidade.ts).
Ao mudar a Política de Privacidade de forma relevante, aumente a versão nos dois lugares: todos
os usuários verão de novo o aviso de ciência no próximo acesso.
"""

VERSAO_TERMOS = "2026-11"

# Valores gravados no lugar do nome e do e-mail quando o titular é anonimizado.
NOME_ANONIMIZADO = "Titular anonimizado"
DOMINIO_ANONIMIZADO = "anonimizado.invalid"
