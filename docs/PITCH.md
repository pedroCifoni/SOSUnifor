# Roteiro do pitch — Uni SOS (10 minutos)

Objetivo: mostrar, em ordem lógica, **o problema → a solução funcionando → como foi construída**,
tocando explicitamente cada critério da ficha de avaliação. Cada bloco tem um dono e um tempo fixo.

## Linha do tempo

| Tempo | Bloco | Quem | O que dizer / mostrar |
|---|---|---|---|
| 0:00–1:00 | **Problema** | Pessoa 1 | Campus grande, emergência sem canal único: quem eu chamo? onde estou? alguém viu? Manutenção e denúncias espalhadas em e-mails. |
| 1:00–1:30 | **Solução em uma frase** | Pessoa 1 | "Segure o botão SOS por 2 s: o sistema descobre o prédio pelo GPS e avisa a segurança em tempo real." Perfis: usuário, admin, segurança, técnico. |
| 1:30–6:30 | **Demonstração (fluxo completo)** | Pessoa 2 dirige, Pessoa 1 narra | Roteiro abaixo. |
| 6:30–8:30 | **Arquitetura e engenharia** | Pessoa 3 | Diagrama de contêineres (`docs/ARQUITETURA.md`), por que monólito modular + eventos, POA, padrões, Flyway/Docker. |
| 8:30–9:30 | **Requisitos não funcionais** | Pessoa 3 | Desempenho (teste de carga), segurança/LGPD, escalabilidade, PWA. |
| 9:30–10:00 | **Fechamento** | Pessoa 1 | Impacto + próximos passos. Agradecer e abrir para perguntas. |

## Demonstração (5 min) — fluxo completo

Preparar antes: `docker compose up`, navegador com 3 abas (usuário no **celular**, segurança, admin) e
o Mailpit (`http://localhost:8025`) aberto. Contas de demo já confirmadas.

1. **Cadastro e verificação** (40 s) — criar conta `@unifor.br` → e-mail chega no Mailpit → abrir link,
   digitar a senha → conta ativa → **e-mail e notificação de boas-vindas** (evento `usuario.ativado`
   consumido pela fila `unisos.reacoes`). *Critérios: autenticação, verificação de e-mail, eventos.*
2. **Perfil** (30 s) — trocar foto, corrigir o nome, trocar a senha; mostrar "Baixar meus dados" (LGPD).
   *Critério: gestão de perfil, upload, LGPD.*
3. **SOS** (60 s) — no celular, segurar o botão → local identificado no mapa do campus → na aba da
   segurança o alerta aparece **sem recarregar** (WebSocket + RabbitMQ). *Critérios: notificações,
   comunicação entre serviços, UX responsiva.*
4. **Triagem pelo admin** (60 s) — painel → encaminhar um chamado ao técnico → técnico conclui → quem
   abriu recebe o aviso. Denúncia anônima: mostrar que o nome não aparece em lugar nenhum.
5. **Gestão e relatórios** (60 s) — usuários: busca, filtro por perfil, mudar perfil (atribuição),
   **exportar CSV/PDF**; relatório de ocorrências em PDF; **tela de auditoria** (gerada pelos aspectos).
   *Critérios: CRUD, busca, exportação PDF/CSV, relatórios gerais, POA.*
6. **Bastidores** (30 s) — painel do RabbitMQ (`http://localhost:15672`): exchange `unisos.eventos` e
   filas; `GET /health/ready` mostrando banco e broker; Swagger em `/docs`.

**Plano B:** vídeo gravado da demonstração completa (sem cortes) no notebook e no celular, para o caso
de rede ou Docker falharem.

## Bloco de arquitetura (2 min) — falas-chave

- "Escolhemos um **monólito modular em camadas, orientado a eventos**. Uma transação grava a ocorrência,
  o histórico e as notificações juntos; o SOS não depende de rede entre serviços. A API é stateless (JWT),
  então escala com réplicas sincronizadas pelo RabbitMQ."
- "Interesses transversais estão em **aspectos**: `@auditar`, `@publicar_evento`, `medir_desempenho`.
  O código de negócio não sabe que é auditado."
- "**Padrões de projeto**: Strategy + Adapter + Factory no e-mail (Brevo em produção, SMTP no local) e na
  exportação CSV/PDF; Observer nos eventos; Repository, DTO, Singleton, Facade." (`docs/PADROES.md`)
- "Banco PostgreSQL versionado com **Flyway**; tudo sobe com **`docker compose up`**: front, API, banco,
  RabbitMQ e Mailpit. CI no GitHub Actions roda lint e ~140 testes a cada push."

## Requisitos não funcionais (1 min)

| RNF | Evidência a mostrar |
|---|---|
| Desempenho (< 2 s) | Resultado do Locust (`docs/DESEMPENHO.md`): p95 por rota |
| Segurança | Argon2, JWT + refresh token com rotação, bloqueio após 5 falhas de login, headers OWASP |
| LGPD | Termos versionados, exportar dados, pedido de exclusão → anonimização, retenção automática |
| Escalabilidade | API stateless, réplicas + RabbitMQ, cache dos polígonos do campus |
| Multiplataforma / UX | PWA instalável no celular, layout mobile-first |

## Checklist da ficha (marcar no ensaio)

- [ ] Login, recuperação de senha, perfis, JWT, verificação de e-mail
- [ ] CRUD, busca, upload, exportação PDF/CSV, atribuição de perfil
- [ ] POA (aspectos) — mostrar a auditoria
- [ ] Arquitetura justificada (monólito modular + eventos)
- [ ] 3+ padrões de projeto nomeados com o arquivo
- [ ] Notificações, comunicação por eventos, relatórios
- [ ] RabbitMQ: produção e consumo (`usuario.ativado`, `ocorrencia.criada`)
- [ ] PostgreSQL + Flyway; Docker com todos os contêineres
- [ ] Camadas, DTOs, validações, commits padronizados (`CONTRIBUTING.md`)
- [ ] Terminar em 10 min (ensaiar com cronômetro pelo menos 2 vezes)

## Dicas de apresentação

- Uma ideia por slide; no máximo 6 slides fora a demo.
- Quem não está falando opera o computador — nunca digitar senha ao vivo com a tela projetada.
- Antecipar perguntas: "por que não microsserviços?", "e se o RabbitMQ cair?" (fallback: a auditoria vai
  direto ao banco e os observadores rodam no processo), "como garantem o anonimato da denúncia?".
