import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { CONTATO_DPO, CONTATO_DPO_PROVISORIO, DATA_TERMOS, VERSAO_TERMOS } from '@/models/privacidade'

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-bold text-brand-900">{titulo}</h2>
      <div className="space-y-2 text-sm leading-relaxed text-ink">{children}</div>
    </section>
  )
}

function Item({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <li>
      <strong className="text-brand-900">{titulo}:</strong> {children}
    </li>
  )
}

/** Política de Privacidade (LGPD, Lei 13.709/2018). Página pública: abre com ou sem login. */
export function PrivacidadePage() {
  const { usuario } = useAuth()

  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 to-surface px-4 py-8">
      <article className="mx-auto w-full max-w-2xl space-y-6 rounded-3xl border border-line bg-white p-6 shadow-sm sm:p-8">
        <Link
          to={usuario ? '/perfil' : '/login'}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-500 hover:text-brand-900"
        >
          <ArrowLeft size={14} /> {usuario ? 'Voltar ao perfil' : 'Voltar ao login'}
        </Link>

        <header className="space-y-1">
          <img src="/unifor-logo-horizontal.svg" alt="UNIFOR" className="mb-3 h-9" />
          <h1 className="text-2xl font-bold text-brand-900">Política de Privacidade do Uni SOS</h1>
          <p className="text-xs text-muted">
            Versão {VERSAO_TERMOS} · atualizada em {DATA_TERMOS}
          </p>
        </header>

        <p className="text-sm leading-relaxed text-ink">
          Este texto explica, em linguagem simples, quais dados pessoais o Uni SOS usa, para quê, com quem eles são
          compartilhados, por quanto tempo ficam guardados e como você pode exercer os seus direitos previstos na Lei
          Geral de Proteção de Dados Pessoais (LGPD, Lei 13.709/2018).
        </p>

        <Secao titulo="1. Quem é o responsável pelos seus dados">
          <p>
            O <strong>controlador</strong> é a <strong>Universidade de Fortaleza (UNIFOR)</strong>, que decide como os
            dados do Uni SOS são usados. O sistema é usado pela comunidade universitária para pedir socorro (SOS), abrir
            chamados de manutenção e fazer denúncias.
          </p>
        </Secao>

        <Secao titulo="2. Quais dados usamos">
          <ul className="list-disc space-y-1.5 pl-5">
            <Item titulo="Dados da conta">nome, e-mail institucional, perfil de acesso (usuário, segurança, técnico ou administrador) e senha, guardada apenas de forma cifrada (hash Argon2), nunca em texto.</Item>
            <Item titulo="Localização (GPS)">usada <strong>somente quando você aciona o SOS</strong>, para a equipe de segurança saber onde você está. O sistema não acompanha a sua localização em nenhum outro momento.</Item>
            <Item titulo="Ocorrências">o que você escreve nos chamados, SOS e denúncias (título, descrição, local) e as fotos ou vídeos anexados, além do histórico de atendimento.</Item>
            <Item titulo="Registros de acesso">data do último acesso, registros técnicos de uso da API, notificações recebidas e a data em que você declarou ciência desta política.</Item>
          </ul>
          <p>
            Em uma <strong>denúncia anônima</strong>, o seu nome não aparece para ninguém que atende a denúncia. O
            sistema guarda internamente quem a enviou apenas para que você possa acompanhá-la.
          </p>
        </Secao>

        <Secao titulo="3. Para que usamos e com qual base legal">
          <ul className="list-disc space-y-1.5 pl-5">
            <Item titulo="Atender pedidos de socorro (SOS)">proteção da vida e da incolumidade física (art. 7º, VII da LGPD).</Item>
            <Item titulo="Chamados de manutenção e denúncias">execução da política institucional de segurança e manutenção do campus e legítimo interesse da UNIFOR em manter o campus seguro (art. 7º, IX).</Item>
            <Item titulo="Conta, login e segurança do sistema">legítimo interesse e prevenção a fraudes e acessos indevidos (art. 7º, IX).</Item>
            <Item titulo="Guarda de registros de ocorrências e de acesso">cumprimento de obrigação legal ou regulatória e exercício regular de direitos (art. 7º, II e VI).</Item>
          </ul>
          <p>Não usamos os seus dados para publicidade nem os vendemos a ninguém.</p>
        </Secao>

        <Secao titulo="4. Com quem compartilhamos">
          <ul className="list-disc space-y-1.5 pl-5">
            <Item titulo="Dentro da UNIFOR">a equipe de segurança e os técnicos veem apenas as ocorrências encaminhadas a eles; os administradores do sistema veem todas, para fazer a triagem.</Item>
            <Item titulo="Prestadores de serviço (operadores)">empresas que hospedam e operam o sistema em nome da UNIFOR: Render (servidor da API), Neon (banco de dados), Vercel (site), Brevo (envio de e-mails) e CloudAMQP (mensagens em tempo real). Alguns desses serviços ficam fora do Brasil.</Item>
            <Item titulo="Autoridades">quando houver obrigação legal ou ordem judicial.</Item>
          </ul>
        </Secao>

        <Secao titulo="5. Por quanto tempo guardamos">
          <ul className="list-disc space-y-1.5 pl-5">
            <Item titulo="Conta">enquanto você tiver vínculo com a UNIFOR ou até a eliminação a seu pedido.</Item>
            <Item titulo="Ocorrências e histórico de atendimento">são mantidos como registro de segurança da instituição. Se você pedir a eliminação, eles continuam guardados, mas sem identificar você.</Item>
            <Item titulo="Notificações">as já lidas são apagadas automaticamente depois de 180 dias.</Item>
            <Item titulo="Links de redefinição de senha">valem 30 minutos e são apagados automaticamente pouco depois de vencerem.</Item>
          </ul>
        </Secao>

        <Secao titulo="6. Seus direitos (art. 18 da LGPD)">
          <p>Você pode, a qualquer momento:</p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>confirmar que tratamos os seus dados e <strong>acessá-los</strong>: use “Baixar meus dados” em <em>Meu Perfil</em> (arquivo .json, que também serve para portabilidade);</li>
            <li>pedir a <strong>correção</strong> de dados incompletos ou errados, falando com a administração do sistema;</li>
            <li>pedir a <strong>eliminação</strong> dos seus dados: use “Solicitar exclusão dos meus dados” em <em>Meu Perfil</em>. A conta é desativada e o seu nome e e-mail são apagados de forma irreversível;</li>
            <li>saber com quem os seus dados são compartilhados (seção 4) e pedir informações sobre o tratamento;</li>
            <li>apresentar reclamação à Autoridade Nacional de Proteção de Dados (ANPD).</li>
          </ul>
        </Secao>

        <Secao titulo="7. Como protegemos os seus dados">
          <p>
            Senhas cifradas, acesso por login com prazo de validade, permissões por perfil (cada pessoa vê só o que
            precisa), conexões protegidas (HTTPS) e anexos liberados apenas para quem pode ver a ocorrência.
          </p>
        </Secao>

        <Secao titulo="8. Fale com o encarregado (DPO)">
          <p>
            Para dúvidas ou pedidos sobre os seus dados pessoais, escreva para{' '}
            <a href={`mailto:${CONTATO_DPO}`} className="font-semibold text-brand-500 underline">
              {CONTATO_DPO}
            </a>
            .
          </p>
          {CONTATO_DPO_PROVISORIO && (
            <p className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
              Endereço provisório: a UNIFOR ainda precisa indicar o canal oficial do encarregado (variável
              VITE_CONTATO_DPO).
            </p>
          )}
        </Secao>

        <p className="border-t border-line pt-4 text-[11px] text-muted">
          Esta política pode ser atualizada. Quando a mudança for relevante, o sistema pedirá que você leia a nova versão
          no próximo acesso.
        </p>
      </article>
    </div>
  )
}
