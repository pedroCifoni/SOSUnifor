"""Popula o banco de teste de carga (unisos_carga) com dados realistas em volume.

Uso, a partir da pasta backend (com a API já tendo subido uma vez nesse banco,
para criar as tabelas e as contas iniciais):
    .\\.venv\\Scripts\\python.exe testes\\carga\\popular_banco.py postgresql+psycopg://unisos:uni12345@localhost:5433/unisos_carga
ou, com a URL na variável DATABASE_URL:
    $env:DATABASE_URL='postgresql+psycopg://unisos:uni12345@localhost:5433/unisos_carga'
    .\\.venv\\Scripts\\python.exe testes\\carga\\popular_banco.py

O que é criado (somente o que ainda faltar; rodar de novo não duplica nada):
- 300 usuários comuns, 10 da segurança e 5 técnicos (e-mails carga.<perfil>.<n>@unifor.br, senha 123456);
- 6000 ocorrências nos últimos 365 dias, com 1 a 3 eventos cada;
- 20000 notificações, ~3000 delas para admin@unifor.br.

Por segurança, o script se recusa a rodar se o banco não se chamar unisos_carga.
"""

import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Permite importar o pacote `app` rodando o arquivo direto da pasta backend.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

URL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATABASE_URL", "")
if not URL:
    sys.exit("Informe a URL do banco por argumento ou pela variável DATABASE_URL.")
os.environ["DATABASE_URL"] = URL  # o app lê a URL ao ser importado

from sqlalchemy import create_engine, func, insert, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.seguranca import gerar_hash_senha  # noqa: E402
from app.entities import EventoOcorrencia, Notificacao, Ocorrencia, Usuario  # noqa: E402

BANCO_PERMITIDO = "unisos_carga"
TOTAL_POR_PERFIL = {"usuario": 300, "seguranca": 10, "tecnico": 5}
TOTAL_OCORRENCIAS = 6000
TOTAL_NOTIFICACOES = 20000
NOTIFICACOES_DO_ADMIN = 3000
EMAIL_ADMIN = "admin@unifor.br"
LOTE = 2000

LOCAIS = [
    "Bloco A - Sala 12", "Bloco B - Laboratório 3", "Bloco C - Corredor", "Bloco D - Auditório",
    "Biblioteca Central", "Estacionamento E1", "Estacionamento E3", "Praça de Alimentação",
    "Ginásio Poliesportivo", "Centro de Convivência", "Reitoria", "Bloco J - Banheiro masculino",
    "Bloco M - Sala 204", "Parque Tecnológico", "Entrada principal",
]
TITULOS = {
    "sos": ["SOS acionado", "Pedido de socorro", "Mal-estar súbito", "Situação de risco"],
    "manutencao": ["Ar-condicionado quebrado", "Lâmpada queimada", "Projetor sem sinal", "Vazamento no banheiro", "Tomada sem energia"],
    "denuncia": ["Comportamento suspeito", "Vandalismo", "Assédio relatado", "Furto de objeto"],
}
PESOS_TIPO = {"sos": 2, "manutencao": 5, "denuncia": 3}
PESOS_STATUS = {"pendente": 2, "aguardando_aceite": 1, "em_atendimento": 2, "concluido": 5, "cancelado": 1}


def em_lotes(linhas: list[dict], tamanho: int = LOTE):
    for inicio in range(0, len(linhas), tamanho):
        yield linhas[inicio : inicio + tamanho]


def inserir(sessao: Session, entidade, linhas: list[dict]) -> None:
    for lote in em_lotes(linhas):
        sessao.execute(insert(entidade), lote)


def popular_usuarios(sessao: Session) -> None:
    existentes = set(sessao.scalars(select(Usuario.email).where(Usuario.email.like("carga.%"))))
    senha_hash = None
    agora = datetime.now(timezone.utc)
    novos = []
    for perfil, total in TOTAL_POR_PERFIL.items():
        for numero in range(1, total + 1):
            email = f"carga.{perfil}.{numero:03d}@unifor.br"
            if email in existentes:
                continue
            senha_hash = senha_hash or gerar_hash_senha("123456")  # hash gerado uma vez só
            novos.append(
                {
                    "id": uuid4(),
                    "nome": f"{perfil.capitalize()} de Carga {numero:03d}",
                    "email": email,
                    "matricula": f"CG{perfil[:3].upper()}{numero:04d}",
                    "senha_hash": senha_hash,
                    "tipo_usuario": perfil,
                    "ativo": True,
                    "email_verificado_em": agora,  # contas de carga já entram confirmadas
                }
            )
    inserir(sessao, Usuario, novos)
    print(f"Usuários: {len(novos)} criados.")


def popular_ocorrencias(sessao: Session) -> None:
    existentes = sessao.scalar(select(func.count()).select_from(Ocorrencia)) or 0
    faltam = TOTAL_OCORRENCIAS - existentes
    if faltam <= 0:
        print("Ocorrências: já populadas.")
        return

    autores = list(sessao.scalars(select(Usuario.id).where(Usuario.tipo_usuario == "usuario")))
    atendentes = list(sessao.scalars(select(Usuario.id).where(Usuario.tipo_usuario.in_(["seguranca", "tecnico"]))))
    id_admin = sessao.scalar(select(Usuario.id).where(Usuario.email == EMAIL_ADMIN))

    agora = datetime.now(timezone.utc)
    datas = sorted(agora - timedelta(seconds=random.randint(60, 365 * 24 * 3600)) for _ in range(faltam))
    ocorrencias, eventos = [], []
    for posicao, criado_em in enumerate(datas, start=existentes + 1):
        tipo = random.choices(list(PESOS_TIPO), weights=list(PESOS_TIPO.values()))[0]
        status = random.choices(list(PESOS_STATUS), weights=list(PESOS_STATUS.values()))[0]
        responsavel = random.choice(atendentes) if status != "pendente" and random.random() < 0.6 else None
        autor = random.choice(autores)
        id_ocorrencia = uuid4()
        ocorrencias.append(
            {
                "id": id_ocorrencia,
                "protocolo": f"#{criado_em.year}-{posicao:04d}",
                "titulo": random.choice(TITULOS[tipo]),
                "descricao": "Registro gerado para teste de carga.",
                "local": random.choice(LOCAIS),
                "tipo": tipo,
                "status": status,
                "autor_id": autor,
                "responsavel_id": responsavel,
                "anonima": tipo == "denuncia" and random.random() < 0.3,
                "anexos": [],
                "latitude": -3.7697 + random.uniform(-0.004, 0.004),
                "longitude": -38.4812 + random.uniform(-0.004, 0.004),
                "precisao_metros": round(random.uniform(5, 60), 1),
                "criado_em": criado_em,
            }
        )
        eventos.append(
            {"id": uuid4(), "ocorrencia_id": id_ocorrencia, "autor_id": autor, "tipo": "criada",
             "descricao": "Ocorrência registrada pelo usuário.", "criado_em": criado_em}
        )
        extras = random.randint(0, 2)
        if extras >= 1:
            eventos.append(
                {"id": uuid4(), "ocorrencia_id": id_ocorrencia, "autor_id": id_admin, "tipo": "encaminhada",
                 "descricao": "Encaminhada para a equipe; aguardando aceite do atendimento.",
                 "criado_em": criado_em + timedelta(minutes=random.randint(1, 120))}
            )
        if extras == 2:
            eventos.append(
                {"id": uuid4(), "ocorrencia_id": id_ocorrencia, "autor_id": responsavel or id_admin,
                 "tipo": status, "descricao": f"Status alterado para {status}.",
                 "criado_em": criado_em + timedelta(hours=random.randint(3, 72))}
            )

    inserir(sessao, Ocorrencia, ocorrencias)
    inserir(sessao, EventoOcorrencia, eventos)
    print(f"Ocorrências: {len(ocorrencias)} criadas, com {len(eventos)} eventos.")


def popular_notificacoes(sessao: Session) -> None:
    existentes = sessao.scalar(select(func.count()).select_from(Notificacao)) or 0
    faltam = TOTAL_NOTIFICACOES - existentes
    if faltam <= 0:
        print("Notificações: já populadas.")
        return

    id_admin = sessao.scalar(select(Usuario.id).where(Usuario.email == EMAIL_ADMIN))
    usuarios = list(sessao.scalars(select(Usuario.id).where(Usuario.email.like("carga.%"))))
    ocorrencias = list(sessao.execute(select(Ocorrencia.id, Ocorrencia.protocolo, Ocorrencia.titulo, Ocorrencia.criado_em)))
    proporcao_admin = NOTIFICACOES_DO_ADMIN / TOTAL_NOTIFICACOES
    agora = datetime.now(timezone.utc)

    notificacoes = []
    for _ in range(faltam):
        id_ocorrencia, protocolo, titulo, criado_em = random.choice(ocorrencias)
        tipo = random.choice(["criada", "encaminhada", "concluida"])
        criada_em = min(criado_em + timedelta(minutes=random.randint(0, 600)), agora)
        notificacoes.append(
            {
                "id": uuid4(),
                "destinatario_id": id_admin if random.random() < proporcao_admin else random.choice(usuarios),
                "tipo": tipo,
                "titulo": {"criada": "Nova ocorrência", "encaminhada": "Ocorrência encaminhada", "concluida": "Chamado resolvido"}[tipo],
                "mensagem": f"{titulo} · {protocolo}",
                "ocorrencia_id": id_ocorrencia,
                "criada_em": criada_em,
                # As antigas quase sempre já foram lidas; as recentes, nem sempre.
                "lida": random.random() < (0.9 if agora - criada_em > timedelta(days=7) else 0.3),
            }
        )
    inserir(sessao, Notificacao, notificacoes)
    print(f"Notificações: {len(notificacoes)} criadas.")


def main() -> None:
    nome_banco = make_url(URL).database
    if nome_banco != BANCO_PERMITIDO:
        sys.exit(f"Recusado: este script só roda no banco '{BANCO_PERMITIDO}' (recebido: '{nome_banco}').")

    engine = create_engine(URL)
    with Session(engine) as sessao:
        if sessao.scalar(select(Usuario.id).where(Usuario.email == EMAIL_ADMIN)) is None:
            sys.exit("Conta admin@unifor.br não encontrada. Suba a API uma vez neste banco antes de popular.")
        popular_usuarios(sessao)
        popular_ocorrencias(sessao)
        popular_notificacoes(sessao)
        sessao.commit()
    engine.dispose()
    print("Banco de carga pronto.")


if __name__ == "__main__":
    main()
