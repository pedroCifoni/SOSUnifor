/**
 * Texto da Política de Privacidade do Uni SOS.
 *
 * Ao alterar qualquer trecho, troque VERSAO_POLITICA para a data da mudança e faça o mesmo em
 * backend/app/services/privacidade_service.py (VERSAO_POLITICA_PRIVACIDADE). Os usuários verão o aviso de novo.
 *
 * Trechos entre "[A DEFINIR: ...]" dependem de informações da UNIFOR (encarregado, prazos etc.)
 * e aparecem destacados na tela até serem preenchidos. O texto deve ser validado pelo encarregado
 * de dados (DPO) da instituição antes de ir para produção.
 */

export const VERSAO_POLITICA = '2026-11-23'

export interface SecaoPolitica {
  titulo: string
  paragrafos?: string[]
  itens?: string[]
}

/** Resumo exibido no aviso do primeiro acesso. */
export const RESUMO_POLITICA: string[] = [
  'Usamos seu nome, e-mail institucional e perfil para identificar você e encaminhar suas ocorrências à equipe certa.',
  'No SOS, registramos sua localização (GPS) no momento do acionamento para que a segurança chegue até você.',
  'Fotos, vídeos e descrições que você enviar são vistos apenas pela equipe responsável pelo atendimento e pela administração.',
  'Em denúncias anônimas, seu nome não é exibido à equipe, mas o sistema guarda internamente quem enviou.',
  'Você pode pedir acesso, correção ou exclusão dos seus dados ao encarregado de dados da UNIFOR.',
]

export const SECOES_POLITICA: SecaoPolitica[] = [
  {
    titulo: '1. Quem trata seus dados',
    paragrafos: [
      'O Uni SOS é o sistema de reporte de ocorrências e segurança do campus da Universidade de Fortaleza (UNIFOR). A UNIFOR é a controladora dos dados pessoais tratados nesta plataforma, nos termos da Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 — LGPD).',
      'Controladora: [A DEFINIR: razão social, CNPJ e endereço].',
      'Encarregado pelo tratamento de dados (DPO): [A DEFINIR: nome e e-mail de contato].',
    ],
  },
  {
    titulo: '2. Quais dados coletamos',
    itens: [
      'Dados de cadastro: nome, e-mail institucional e perfil de acesso (usuário, segurança, técnico ou administrador). A senha é guardada apenas de forma cifrada (hash) e ninguém tem acesso a ela.',
      'Dados das ocorrências: título, descrição, local informado, tipo (SOS, manutenção ou denúncia), situação e o histórico de atendimento.',
      'Anexos: fotos e vídeos enviados por você. Imagens podem conter informações de outras pessoas ou metadados do aparelho.',
      'Localização: no acionamento do SOS, a latitude, a longitude e a precisão do GPS do seu aparelho.',
      'Dados de uso: data e hora do último acesso, usados para saber quem está conectado e enviar alertas de segurança em tempo real.',
      'Notificações: avisos enviados a você pelo sistema e a indicação de leitura.',
    ],
  },
  {
    titulo: '3. Para que usamos e com qual base legal',
    itens: [
      'Identificar você e controlar o acesso de acordo com o seu perfil — legítimo interesse da instituição na segurança e na gestão do campus (art. 7º, IX).',
      'Receber, encaminhar e acompanhar chamados de manutenção — legítimo interesse (art. 7º, IX).',
      'Atender um SOS e alertar pessoas próximas sobre uma situação de risco — proteção da vida e da integridade física (art. 7º, VII).',
      'Apurar denúncias e preservar registros para eventuais processos — exercício regular de direitos (art. 7º, VI).',
      'Enviar e-mails de acesso, redefinição de senha e avisos de segurança da conta — legítimo interesse (art. 7º, IX).',
      '[A DEFINIR: validar as bases legais acima com o encarregado de dados.]',
    ],
  },
  {
    titulo: '4. Quem pode ver seus dados',
    itens: [
      'Equipe de Segurança: ocorrências de SOS e denúncias encaminhadas a ela.',
      'Técnicos: chamados de manutenção encaminhados a eles.',
      'Administradores do sistema: todas as ocorrências, para triagem e encaminhamento.',
      'Usuários conectados ao campus recebem um alerta genérico de "zona vermelha" quando um SOS é acionado, sem a identificação de quem acionou.',
      'Fornecedores que operam a infraestrutura em nome da UNIFOR (hospedagem do sistema, banco de dados e envio de e-mails). Alguns desses serviços podem armazenar dados fora do Brasil, com as garantias exigidas pela LGPD (art. 33). [A DEFINIR: listar os fornecedores e países.]',
      'Não vendemos nem compartilhamos seus dados para fins de publicidade.',
    ],
  },
  {
    titulo: '5. Denúncias anônimas',
    paragrafos: [
      'Ao marcar uma denúncia como anônima, seu nome não aparece para a equipe que a atende nem para os administradores no sistema. Para evitar abusos e permitir a apuração, o sistema mantém internamente o vínculo entre a denúncia e a sua conta, com acesso restrito e só usado quando exigido por lei ou por ordem de autoridade competente.',
    ],
  },
  {
    titulo: '6. Por quanto tempo guardamos',
    paragrafos: [
      'Os dados da conta são mantidos enquanto você tiver vínculo com a UNIFOR. Quando uma conta é excluída, ela é desativada e o histórico das ocorrências é preservado para fins de segurança e auditoria.',
      'Prazos de guarda de ocorrências, anexos e localização: [A DEFINIR: prazo de retenção de cada tipo de dado e forma de descarte ou anonimização].',
    ],
  },
  {
    titulo: '7. Como protegemos seus dados',
    itens: [
      'Comunicação cifrada (HTTPS) entre o aplicativo e o servidor.',
      'Senhas guardadas com algoritmo de hash Argon2; links de redefinição de senha de uso único e com prazo de validade.',
      'Acesso aos dados limitado pelo perfil de cada pessoa; anexos só podem ser baixados por quem tem acesso à ocorrência.',
      'Sua sessão fica salva no navegador por até 60 minutos. Ao usar um computador compartilhado, toque em "Sair" ao terminar.',
    ],
  },
  {
    titulo: '8. Seus direitos',
    paragrafos: ['Conforme o art. 18 da LGPD, você pode, a qualquer momento:'],
    itens: [
      'confirmar se tratamos seus dados e ter acesso a eles;',
      'corrigir dados incompletos, inexatos ou desatualizados;',
      'pedir a anonimização, o bloqueio ou a eliminação de dados desnecessários ou excessivos;',
      'pedir a portabilidade dos seus dados;',
      'saber com quem seus dados foram compartilhados;',
      'opor-se a um tratamento que descumpra a LGPD;',
      'apresentar reclamação à Autoridade Nacional de Proteção de Dados (ANPD).',
    ],
  },
  {
    titulo: '9. Como exercer seus direitos',
    paragrafos: [
      'Envie sua solicitação ao encarregado de dados da UNIFOR pelo contato informado no item 1. Responderemos no prazo previsto na LGPD.',
    ],
  },
  {
    titulo: '10. Atualizações desta política',
    paragrafos: [
      'Esta política pode ser atualizada. Quando isso acontecer, avisaremos no próximo acesso ao sistema e você precisará confirmar a leitura da nova versão para continuar.',
    ],
  },
]
