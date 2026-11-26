# Como contribuir com o Uni SOS

## Fluxo de trabalho

1. Crie uma branch a partir de `main`: `feat/<assunto>`, `fix/<assunto>` ou `docs/<assunto>`.
2. Faça commits pequenos, no padrão abaixo.
3. Antes de abrir o PR, rode localmente o mesmo que o CI roda (seção "Verificações").
4. Abra o Pull Request para `main`. O CI (`.github/workflows/ci.yml`) precisa ficar verde.

## Padrão de commits: Conventional Commits

```
<tipo>(<escopo opcional>): <resumo no imperativo, minúsculo, sem ponto final>

<corpo opcional: o porquê da mudança>
```

| Tipo | Quando usar | Exemplo |
|---|---|---|
| `feat` | Funcionalidade nova | `feat(perfil): troca de senha e foto em /me` |
| `fix` | Correção de defeito | `fix(relatorios): download usa o endereço da API` |
| `refactor` | Mudança interna sem alterar comportamento | `refactor(email): estratégias Brevo e SMTP` |
| `test` | Só testes | `test(sessao): rotação do refresh token` |
| `docs` | Só documentação | `docs: arquitetura e padrões de projeto` |
| `ci` | Pipeline | `ci: lint com ruff no back-end` |
| `chore` | Manutenção (dependências, configs) | `chore: fixa versões do requirements` |
| `perf` | Desempenho | `perf(sos): cache dos polígonos do campus` |

Use `:` depois do tipo (não `/`): `feat: ...`, e não `feat/...`. O `/` fica para o nome das branches.

## Verificações (as mesmas do CI)

Back-end (pasta `backend`, com o PostgreSQL do `docker compose` no ar):

```bash
python -m ruff check .
python -m pytest
```

Front-end (raiz do repositório):

```bash
npm run build
```

## Convenções de código

- **Camadas do back-end:** controller (HTTP) → service (regras e transação) → repository (consultas) → entity.
  Entrada e saída sempre por DTOs Pydantic em `app/dtos`. Erros de negócio são exceções de `app/core/excecoes.py`.
- **Interesses transversais** (auditoria, eventos, desempenho) entram por aspectos (`app/core/aspectos.py`),
  não por código repetido nos services. Veja [docs/POA-e-eventos.md](docs/POA-e-eventos.md).
- **Padrões de projeto** em uso e onde: [docs/PADROES.md](docs/PADROES.md).
- Nomes em português, como o domínio do projeto. Comentários explicam o porquê, não o quê.
- Toda funcionalidade nova vem com teste em `backend/testes/unidade`.
