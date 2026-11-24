# Uni SOS e a LGPD (Lei 13.709/2018)

Este documento registra como o Uni SOS trata dados pessoais e o que foi construído para cumprir a Lei Geral de Proteção de Dados. As medidas são proporcionais a um sistema universitário de SOS, chamados e denúncias. **Não substitui a análise jurídica da instituição.**

- **Controlador:** Universidade de Fortaleza (UNIFOR).
- **Operadores (provedores):** Render (API), Neon (PostgreSQL), Vercel (front-end), Brevo (e-mail transacional) e CloudAMQP (RabbitMQ, avisos em tempo real).
- **Política de Privacidade para o usuário:** página pública `/privacidade` (`src/pages/Privacidade/PrivacidadePage.tsx`), com link no login, no menu e em Meu Perfil.
- **Versão dos termos:** `VERSAO_TERMOS` em `backend/app/core/privacidade.py` e em `src/models/privacidade.ts` (precisam ser iguais).

## 1. Inventário de dados

| Dado | Onde fica | Finalidade | Base legal (art. 7º) | Retenção | Quem acessa |
|---|---|---|---|---|---|
| Nome, e-mail institucional, perfil | `credentials` | Identificar a pessoa, login, encaminhamento das ocorrências | IX (legítimo interesse / política institucional) | Enquanto houver vínculo ou até a anonimização a pedido do titular | O próprio titular; admin (lista de usuários). E-mail da equipe só para o admin (minimização). Segurança/técnicos veem o nome do solicitante das ocorrências encaminhadas a eles. |
| Matrícula (contas antigas) | `credentials.matricula` | Identificação acadêmica (campo legado; o cadastro atual não pede) | IX | Igual à conta; apagada na anonimização | Titular (exportação) |
| Hash da senha (Argon2) | `credentials.senha_hash` | Autenticação | IX | Igual à conta; na anonimização é trocado por hash de senha aleatória descartada | Ninguém (nunca é devolvido pela API) |
| Último acesso | `credentials.ultimo_acesso` | Saber quem está online para o alerta de "zona vermelha" do SOS; segurança | IX | Sobrescrito a cada acesso; apagado na anonimização | Uso interno do sistema; exportado ao titular |
| Ciência da política (versão e data) | `credentials.termos_versao`, `termos_aceitos_em` | Comprovar a transparência (art. 6º, VI; art. 9º) | II (obrigação legal) / IX | Igual à conta | Titular (exportação) |
| Data do pedido de exclusão e da anonimização | `credentials.exclusao_solicitada_em`, `anonimizado_em` | Registrar o atendimento do direito do titular | II | Mantidas na conta anonimizada (não identificam ninguém) | Admin |
| Localização GPS (latitude, longitude, precisão) | `ocorrencias` (só em SOS) | Localizar a pessoa em emergência | **VII (proteção da vida e da incolumidade física)** | Mantida com a ocorrência (registro de segurança) | Titular, admin e a equipe de segurança encarregada |
| Título, descrição, local, tipo, status | `ocorrencias` | Atender SOS, chamados e denúncias | VII (SOS); IX (chamados/denúncias) | Mantida como registro de segurança; na eliminação do titular, fica sem identificá-lo | Autor, responsável encaminhado e admin |
| Anexos (fotos/vídeos) | disco da API + `ocorrencias.anexos` | Evidência da ocorrência | IX | Igual à ocorrência | Quem pode ver a ocorrência (download autenticado) |
| Autoria de denúncia anônima | `ocorrencias.autor_id` + `anonima=true` | Permitir que o autor acompanhe a própria denúncia | IX | Igual à ocorrência | **Ninguém além do próprio autor**: a API nunca devolve `autorId`/nome em denúncias anônimas |
| Histórico de atendimento | `eventos_ocorrencia` | Rastreabilidade do atendimento | II / VI (exercício regular de direitos) | Igual à ocorrência | Quem pode ver a ocorrência |
| Notificações | `notificacoes` | Avisar o usuário sobre as ocorrências | IX | **Lidas: apagadas após 180 dias**; não lidas ficam; todas do titular apagadas na anonimização | Destinatário |
| Tokens de redefinição de senha (só o hash SHA-256) | `tokens_redefinicao_senha` | "Esqueci minha senha" e limite de pedidos | IX | Valem 30 min; **apagados 24 h após vencer**; todos do titular apagados na anonimização | Ninguém (uso interno) |
| Registros técnicos de acesso (logs da API) | Render | Segurança e diagnóstico | II / IX | Conforme o provedor | Equipe técnica |

## 2. Medidas de segurança existentes (art. 46)

- Senhas com hash Argon2 (`pwdlib`); tokens de redefinição guardados só como hash SHA-256, de uso único e com validade de 30 minutos.
- Autenticação por JWT com expiração; em produção, a API se recusa a subir sem `JWT_SECRET` forte, sem credencial própria do banco e com CORS apontando para `localhost`.
- Autorização por perfil em cada rota (usuário, segurança, técnico, admin) e visibilidade das ocorrências por autor/responsável.
- Denúncia anônima: o nome e o id do autor nunca saem na API.
- Anexos só podem ser citados uma vez e só são baixados por quem pode ver a ocorrência.
- Exclusão lógica de contas (o histórico continua íntegro) e anonimização irreversível a pedido do titular.
- Minimização: o e-mail de outras pessoas só é devolvido ao administrador (`/usuarios/segurancas` e `/usuarios/tecnicos` devolvem `email: null` aos demais perfis).
- HTTPS nos provedores de produção (Vercel, Render, Neon, CloudAMQP com `amqps://`).

## 3. Como atender cada direito do art. 18

| Direito | Como fazer no Uni SOS |
|---|---|
| I - Confirmação da existência de tratamento | Política de Privacidade (`/privacidade`) e "Baixar meus dados" em Meu Perfil. |
| II - Acesso aos dados | Meu Perfil > **Baixar meus dados** (`GET /me/dados`): perfil (inclusive a matrícula das contas antigas), ocorrências que a pessoa abriu (com histórico), notificações recebidas e datas de ciência da política. |
| III - Correção | O titular pede à administração; o admin corrige nome/e-mail em **Usuários**. |
| IV - Anonimização, bloqueio ou eliminação de dados desnecessários | Retenção automática (seção 4) e anonimização a pedido (direito VI). |
| V - Portabilidade | O mesmo arquivo `.json` do direito II, em formato estruturado e aberto. |
| VI - Eliminação | Meu Perfil > **Solicitar exclusão dos meus dados** (`POST /me/solicitar-exclusao`, com confirmação). A data do pedido é gravada (o Perfil a mostra via `GET /me/termos`, campo `exclusaoSolicitadaEm`) e os administradores recebem uma notificação **sem o nome do titular** (quem pediu aparece só na lista de pedidos), para que nada identifique a pessoa depois da anonimização. Em **Usuários > Pedidos de exclusão**, o admin clica em **Anonimizar** (`POST /usuarios/{id}/anonimizar`). |
| VII - Informação sobre compartilhamento | Seção 4 da Política de Privacidade. |
| VIII - Informação sobre não consentir | O tratamento não se baseia em consentimento (bases: proteção da vida, legítimo interesse/política institucional e obrigação legal). A tela de "ciência" registra que a pessoa foi informada, não um consentimento. |
| IX - Revogação do consentimento | Não se aplica pelo mesmo motivo; a pessoa pode pedir a eliminação (VI). |
| Reclamação à ANPD / contato | Canal do encarregado na Política (`VITE_CONTATO_DPO`). |

### O que a anonimização faz

1. `nome` vira `Titular anonimizado`; `email` vira `anonimizado-<uuid aleatório>@anonimizado.invalid` (sem relação com o e-mail original).
2. A senha é trocada pelo hash de uma senha aleatória que é descartada; a conta é desativada; `matricula` e `ultimo_acesso` são apagados.
3. Notificações recebidas e tokens de redefinição da pessoa são apagados.
4. Nos eventos das ocorrências, o nome dela como responsável ("Encaminhada para Fulano;") é trocado por "Titular anonimizado". Só os eventos dela: os encaminhamentos guardam `eventos_ocorrencia.destinatario_id`, então um homônimo não é afetado. Nos eventos antigos (sem esse campo), a troca vale para as ocorrências em que ela é a responsável atual; se não houver outra conta com o mesmo nome, vale para todos.
5. **As ocorrências são mantidas** (registro de segurança e obrigação legal, art. 16, I): o solicitante passa a aparecer como "Titular anonimizado".
6. Regras: o admin não pode anonimizar a si mesmo, não pode anonimizar o último administrador ativo e a mesma conta não é anonimizada duas vezes. A contagem de admins trava as contas de admin ativas (`SELECT ... FOR UPDATE`): dois admins anonimizando um ao outro ao mesmo tempo não deixam o sistema sem administrador.
7. Depois que alguma conta foi anonimizada, as contas iniciais de desenvolvimento não são mais recriadas na subida da API (senão uma conta inicial anonimizada voltaria com a senha padrão).

**Limite conhecido:** textos livres (título/descrição das ocorrências) e fotos anexadas podem conter dados pessoais escritos ou fotografados pelo próprio usuário. Eles não são alterados automaticamente; se necessário, o admin avalia caso a caso.

## 4. Retenção automática

Rotina `RetencaoService` (`backend/app/services/retencao_service.py`), chamada por `inicializar_banco()` a cada subida da API (no Render, a cada deploy e a cada vez que a instância acorda). É idempotente: rodar de novo só apaga o que venceu desde a última vez.

| O que | Quando é apagado | Configuração |
|---|---|---|
| Tokens de redefinição de senha | 24 h depois de vencer (a folga preserva os pedidos usados no limite de 3 por hora) | `RETENCAO_TOKENS_VENCIDOS_HORAS` (padrão `24`) |
| Notificações já lidas | 180 dias depois de criadas | `RETENCAO_NOTIFICACOES_LIDAS_DIAS` (padrão `180`) |

**Prazos citados na Política de Privacidade:** a página `/privacidade` informa ao titular "180 dias" (notificações lidas) e "30 minutos" (validade dos links de redefinição, `REDEFINICAO_SENHA_EXPIRA_MINUTOS`). Se mudar `RETENCAO_NOTIFICACOES_LIDAS_DIAS` ou `REDEFINICAO_SENHA_EXPIRA_MINUTOS` no Render, atualize o texto da política e aumente `VERSAO_TERMOS` (back e front) para que os titulares sejam informados do novo prazo (art. 9º).

Não são apagados automaticamente: notificações não lidas, ocorrências, eventos e contas. Quando a verificação de e-mail tiver tokens próprios, inclua-os nesta rotina com a mesma regra.

## 5. Ciência da Política de Privacidade

- Colunas `credentials.termos_versao` e `credentials.termos_aceitos_em`.
- Depois do login, o front consulta `GET /me/termos`; se a versão aceita for diferente da vigente, mostra um aviso que bloqueia o uso com resumo, link para a política e o botão **Li e aceito** (`POST /me/termos`, que só aceita a versão vigente).
- **Decisão sobre o SOS (proteção da vida, art. 7º, VII):** o aviso nunca impede um pedido de socorro. O aviso tem o botão "Emergência? Acionar o SOS agora", que o tira da frente na tela principal (onde fica o botão de SOS); a tela de um SOS em andamento (`/sos/:id`) nunca mostra o aviso; e o back-end não exige o aceite em nenhuma rota (o bloqueio é só de interface).
- Para pedir ciência de novo após mudar a política, aumente `VERSAO_TERMOS` no back e no front.

## 6. Pendências que dependem da instituição

- **Nomear o encarregado (DPO)** (art. 41) e publicar o canal oficial: configurar `VITE_CONTATO_DPO` na Vercel. Enquanto isso, a política mostra um endereço provisório marcado como "a definir".
- **Contratos com os operadores** (art. 39): cláusulas de proteção de dados com Render, Neon, Vercel, Brevo e CloudAMQP, incluindo **transferência internacional** (art. 33), já que parte desses serviços fica fora do Brasil.
- **Relatório de Impacto à Proteção de Dados (RIPD)** (art. 38), recomendado pelo uso de localização e pelo tratamento de denúncias.
- **Validação jurídica** do texto da Política de Privacidade e das bases legais escolhidas.
- **Prazo de guarda das ocorrências**: definir por quanto tempo SOS, chamados e denúncias ficam guardados (hoje, indefinidamente) e se depois disso serão anonimizados ou apagados.
- **Plano de resposta a incidentes** (art. 48): quem avisa a ANPD e os titulares, e em quanto tempo.
- **Anexos:** hoje ficam no disco do servidor; ao migrar para armazenamento externo, incluir o novo provedor na lista de operadores.
