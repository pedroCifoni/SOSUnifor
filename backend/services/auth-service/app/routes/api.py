from collections.abc import Iterable
from math import cos, radians, sqrt
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.autenticacao import criar_token, exigir_perfil, obter_usuario_atual
from app.core.database import obter_banco
from app.core.notificacoes_tempo_real import gerenciador_notificacoes
from app.core.security import conferir_senha, gerar_hash_senha
from app.models.credential import Usuario
from app.models.sistema import AreaCampus, EventoOcorrencia, Notificacao, Ocorrencia
from app.schemas.sistema import (
    AreaCampusEntrada,
    CoordenadasEntrada,
    CredenciaisLogin,
    EncaminhamentoEntrada,
    OcorrenciaEntrada,
    StatusEntrada,
    UsuarioAtualizacao,
    UsuarioAtualizacaoLote,
    UsuarioEntrada,
    UsuarioLoteEntrada,
)


rotas_api = APIRouter()
PASTA_ARQUIVOS = Path(__file__).resolve().parents[2] / "uploads"
PERFIS_VALIDOS = {"usuario", "seguranca", "tecnico", "admin"}
JANELA_USUARIO_ONLINE = timedelta(seconds=30)
TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024
TIPOS_ARQUIVO_PERMITIDOS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "video/mp4": {".mp4"},
}


def usuario_para_resposta(usuario: Usuario) -> dict[str, str]:
    return {
        "id": str(usuario.id),
        "nome": usuario.nome,
        "email": usuario.email,
        "perfil": usuario.tipo_usuario,
    }


def ocorrencia_para_resposta(
    ocorrencia: Ocorrencia, solicitante: str, eventos: list[EventoOcorrencia] | None = None
) -> dict[str, object]:
    resposta: dict[str, object] = {
        "id": str(ocorrencia.id),
        "protocolo": ocorrencia.protocolo,
        "titulo": ocorrencia.titulo,
        "descricao": ocorrencia.descricao,
        "local": ocorrencia.local,
        "tipo": ocorrencia.tipo,
        "status": ocorrencia.status,
        "solicitante": solicitante,
        "autorId": None if ocorrencia.anonima else str(ocorrencia.autor_id),
        "anonima": ocorrencia.anonima,
        "anexos": ocorrencia.anexos,
        "responsavelId": str(ocorrencia.responsavel_id) if ocorrencia.responsavel_id else None,
        "latitude": ocorrencia.latitude,
        "longitude": ocorrencia.longitude,
        "precisaoMetros": ocorrencia.precisao_metros,
        "criadoEm": ocorrencia.criado_em.isoformat(),
    }
    if eventos is not None:
        resposta["eventos"] = [
            {"tipo": evento.tipo, "descricao": evento.descricao, "criadoEm": evento.criado_em.isoformat()}
            for evento in eventos
        ]
    return resposta


def notificacao_para_resposta(notificacao: Notificacao) -> dict[str, object]:
    return {
        "id": str(notificacao.id),
        "destinatarioId": str(notificacao.destinatario_id),
        "tipo": notificacao.tipo,
        "titulo": notificacao.titulo,
        "mensagem": notificacao.mensagem,
        "ocorrenciaId": str(notificacao.ocorrencia_id),
        "criadaEm": notificacao.criada_em.isoformat(),
        "lida": notificacao.lida,
    }


def buscar_usuario_por_email(banco: Session, email: str) -> Usuario | None:
    return banco.scalar(select(Usuario).where(Usuario.email == email.lower().strip()))


def garantir_email_disponivel(banco: Session, email: str, usuario_id: UUID | None = None) -> str:
    email_normalizado = email.lower().strip()
    existente = buscar_usuario_por_email(banco, email_normalizado)
    if existente is not None and existente.id != usuario_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um usuário com este e-mail.")
    return email_normalizado


def garantir_ao_menos_um_admin(banco: Session, usuario: Usuario | None = None, novo_perfil: str | None = None) -> None:
    if usuario is None or usuario.tipo_usuario != "admin" or novo_perfil == "admin":
        return
    total = banco.scalar(select(func.count()).select_from(Usuario).where(Usuario.tipo_usuario == "admin", Usuario.ativo))
    if total is not None and total <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deve existir ao menos um administrador.")


def criar_notificacoes(
    banco: Session,
    destinatarios: Iterable[UUID],
    tipo: str,
    titulo: str,
    mensagem: str,
    ocorrencia_id: UUID,
    ignorar_usuario_id: UUID | None = None,
) -> None:
    for destinatario in set(destinatarios):
        if destinatario == ignorar_usuario_id:
            continue
        banco.add(
            Notificacao(
                destinatario_id=destinatario,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
                ocorrencia_id=ocorrencia_id,
            )
        )


def registrar_evento(
    banco: Session, ocorrencia_id: UUID, tipo: str, descricao: str, autor_id: UUID | None
) -> None:
    banco.add(EventoOcorrencia(ocorrencia_id=ocorrencia_id, tipo=tipo, descricao=descricao, autor_id=autor_id))


def listar_usuarios_online(banco: Session) -> list[UUID]:
    limite = datetime.now(timezone.utc) - JANELA_USUARIO_ONLINE
    return list(
        banco.scalars(
            select(Usuario.id).where(
                Usuario.ativo,
                Usuario.tipo_usuario == "usuario",
                Usuario.ultimo_acesso.is_not(None),
                Usuario.ultimo_acesso >= limite,
            )
        )
    )


def area_para_resposta(area: AreaCampus) -> dict[str, object]:
    return {
        "id": str(area.id),
        "nome": area.nome,
        "tipo": area.tipo,
        "coordenadas": area.coordenadas,
        "limiteCampus": area.limite_campus,
        "prioridade": area.prioridade,
    }


def ponto_esta_dentro_da_area(latitude: float, longitude: float, coordenadas: list[dict[str, float]]) -> bool:
    dentro = False
    quantidade_pontos = len(coordenadas)
    for indice_atual in range(quantidade_pontos):
        indice_anterior = (indice_atual - 1) % quantidade_pontos
        ponto_atual = coordenadas[indice_atual]
        ponto_anterior = coordenadas[indice_anterior]
        latitude_atual, longitude_atual = ponto_atual["latitude"], ponto_atual["longitude"]
        latitude_anterior, longitude_anterior = ponto_anterior["latitude"], ponto_anterior["longitude"]
        produto_vetorial = (longitude - longitude_anterior) * (latitude_atual - latitude_anterior) - (latitude - latitude_anterior) * (longitude_atual - longitude_anterior)
        esta_na_linha = abs(produto_vetorial) < 0.0000000001
        dentro_dos_extremos = (
            min(latitude_anterior, latitude_atual) <= latitude <= max(latitude_anterior, latitude_atual)
            and min(longitude_anterior, longitude_atual) <= longitude <= max(longitude_anterior, longitude_atual)
        )
        if esta_na_linha and dentro_dos_extremos:
            return True
        cruza_linha_horizontal = (latitude_atual > latitude) != (latitude_anterior > latitude)
        if not cruza_linha_horizontal:
            continue
        longitude_no_cruzamento = (longitude_anterior - longitude_atual) * (latitude - latitude_atual) / (latitude_anterior - latitude_atual) + longitude_atual
        if longitude < longitude_no_cruzamento:
            dentro = not dentro
    return dentro


def calcular_distancia_ate_segmento(
    latitude: float,
    longitude: float,
    inicio: dict[str, float],
    fim: dict[str, float],
) -> float:
    """Mede a menor distância entre um ponto e uma lateral do polígono, em metros."""
    metros_por_grau_latitude = 111_320
    metros_por_grau_longitude = 111_320 * cos(radians(latitude))
    inicio_x = (inicio["longitude"] - longitude) * metros_por_grau_longitude
    inicio_y = (inicio["latitude"] - latitude) * metros_por_grau_latitude
    fim_x = (fim["longitude"] - longitude) * metros_por_grau_longitude
    fim_y = (fim["latitude"] - latitude) * metros_por_grau_latitude
    vetor_x, vetor_y = fim_x - inicio_x, fim_y - inicio_y
    tamanho_quadrado = vetor_x**2 + vetor_y**2
    if tamanho_quadrado == 0:
        return sqrt(inicio_x**2 + inicio_y**2)
    proporcao = max(0, min(1, -(inicio_x * vetor_x + inicio_y * vetor_y) / tamanho_quadrado))
    ponto_mais_proximo_x = inicio_x + proporcao * vetor_x
    ponto_mais_proximo_y = inicio_y + proporcao * vetor_y
    return sqrt(ponto_mais_proximo_x**2 + ponto_mais_proximo_y**2)


def calcular_distancia_ate_area(latitude: float, longitude: float, area: AreaCampus) -> float:
    """Retorna zero dentro do polígono ou a distância até sua borda mais próxima."""
    if ponto_esta_dentro_da_area(latitude, longitude, area.coordenadas):
        return 0
    return min(
        calcular_distancia_ate_segmento(latitude, longitude, area.coordenadas[indice - 1], area.coordenadas[indice])
        for indice in range(len(area.coordenadas))
    )


def buscar_bloco_mais_proximo(areas: list[AreaCampus], latitude: float, longitude: float) -> AreaCampus | None:
    blocos = [area for area in areas if not area.limite_campus and area.tipo == "bloco"]
    if not blocos:
        return None
    return min(blocos, key=lambda bloco: calcular_distancia_ate_area(latitude, longitude, bloco))


def descrever_local(area: AreaCampus | None, bloco_mais_proximo: AreaCampus | None) -> str:
    if area is None:
        return f"Próximo ao {bloco_mais_proximo.nome}" if bloco_mais_proximo else "Área do campus não mapeada"
    if area.tipo in {"area_verde", "area_externa"} and bloco_mais_proximo:
        return f"{area.nome} · próximo ao {bloco_mais_proximo.nome}"
    return area.nome


def identificar_area_por_coordenadas(
    banco: Session, latitude: float, longitude: float
) -> tuple[AreaCampus | None, AreaCampus | None, bool]:
    areas = banco.scalars(
        select(AreaCampus).where(AreaCampus.ativo).order_by(AreaCampus.prioridade.desc(), AreaCampus.nome)
    ).all()
    limites_campus = [area for area in areas if area.limite_campus]
    dentro_do_campus = bool(limites_campus) and any(
        ponto_esta_dentro_da_area(latitude, longitude, area.coordenadas) for area in limites_campus
    )
    if not dentro_do_campus:
        return None, None, False
    for area in areas:
        if not area.limite_campus and ponto_esta_dentro_da_area(latitude, longitude, area.coordenadas):
            return area, buscar_bloco_mais_proximo(areas, latitude, longitude), True
    return None, buscar_bloco_mais_proximo(areas, latitude, longitude), True


def obter_ocorrencia_acessivel(banco: Session, ocorrencia_id: UUID, usuario: Usuario) -> Ocorrencia:
    ocorrencia = banco.get(Ocorrencia, ocorrencia_id)
    if ocorrencia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada.")
    if usuario.tipo_usuario != "admin" and usuario.id not in {ocorrencia.autor_id, ocorrencia.responsavel_id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pode acessar esta ocorrência.")
    return ocorrencia


def usuario_pode_acessar_anexo(banco: Session, nome_armazenado: str, usuario: Usuario) -> bool:
    ocorrencias = banco.scalars(select(Ocorrencia).where(Ocorrencia.anexos.is_not(None))).all()
    for ocorrencia in ocorrencias:
        possui_anexo = any(
            isinstance(anexo, dict) and str(anexo.get("url", "")).endswith(f"/arquivos/{nome_armazenado}")
            for anexo in ocorrencia.anexos
        )
        if not possui_anexo:
            continue
        try:
            obter_ocorrencia_acessivel(banco, ocorrencia.id, usuario)
            return True
        except HTTPException:
            continue
    return False


@rotas_api.post("/auth/login")
def entrar(dados: CredenciaisLogin, banco: Session = Depends(obter_banco)) -> dict[str, str]:
    usuario = buscar_usuario_por_email(banco, dados.email)
    if usuario is None or not usuario.ativo or not conferir_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")
    return {"token": criar_token(usuario)}


@rotas_api.get("/usuarios")
def listar_usuarios(
    _: Usuario = Depends(exigir_perfil("admin")), banco: Session = Depends(obter_banco)
) -> list[dict[str, str]]:
    usuarios = banco.scalars(select(Usuario).where(Usuario.ativo).order_by(Usuario.nome)).all()
    return [usuario_para_resposta(usuario) for usuario in usuarios]


@rotas_api.get("/usuarios/segurancas")
def listar_segurancas(
    _: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, str]]:
    usuarios = banco.scalars(
        select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == "seguranca").order_by(Usuario.nome)
    ).all()
    return [usuario_para_resposta(usuario) for usuario in usuarios]


@rotas_api.get("/usuarios/tecnicos")
def listar_tecnicos(
    _: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, str]]:
    usuarios = banco.scalars(
        select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == "tecnico").order_by(Usuario.nome)
    ).all()
    return [usuario_para_resposta(usuario) for usuario in usuarios]


@rotas_api.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioEntrada, _: Usuario = Depends(exigir_perfil("admin")), banco: Session = Depends(obter_banco)
) -> dict[str, str]:
    email = garantir_email_disponivel(banco, dados.email)
    usuario = Usuario(nome=dados.nome.strip(), email=email, senha_hash=gerar_hash_senha(dados.senha), tipo_usuario=dados.perfil)
    banco.add(usuario)
    banco.commit()
    banco.refresh(usuario)
    return usuario_para_resposta(usuario)


@rotas_api.put("/usuarios/{usuario_id}")
def atualizar_usuario(
    usuario_id: UUID,
    dados: UsuarioAtualizacao,
    atual: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> dict[str, str]:
    usuario = banco.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    novos_dados = dados.model_dump(exclude_unset=True)
    if not novos_dados:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie ao menos um campo para atualizar.")
    if usuario.id == atual.id and "perfil" in novos_dados:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode alterar o próprio perfil.")
    if "email" in novos_dados:
        usuario.email = garantir_email_disponivel(banco, novos_dados["email"], usuario.id)
    if "nome" in novos_dados:
        usuario.nome = novos_dados["nome"].strip()
    if "perfil" in novos_dados:
        garantir_ao_menos_um_admin(banco, usuario, novos_dados["perfil"])
        usuario.tipo_usuario = novos_dados["perfil"]
    if "senha" in novos_dados:
        usuario.senha_hash = gerar_hash_senha(novos_dados["senha"])
    banco.commit()
    banco.refresh(usuario)
    return usuario_para_resposta(usuario)


@rotas_api.post("/usuarios/lote")
def salvar_usuarios_em_lote(
    dados: UsuarioLoteEntrada,
    atual: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> dict[str, int]:
    """Aplica o rascunho administrativo em uma única transação atômica."""
    try:
        for criacao in dados.criacoes:
            email = garantir_email_disponivel(banco, criacao.email)
            banco.add(Usuario(nome=criacao.nome.strip(), email=email, senha_hash=gerar_hash_senha(criacao.senha), tipo_usuario=criacao.perfil))
        banco.flush()
        for atualizacao in dados.atualizacoes:
            usuario = banco.get(Usuario, UUID(atualizacao.id))
            if usuario is None or not usuario.ativo:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
            novos_dados = atualizacao.model_dump(exclude={"id"}, exclude_unset=True)
            if usuario.id == atual.id and "perfil" in novos_dados:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode alterar o próprio perfil.")
            if "email" in novos_dados:
                usuario.email = garantir_email_disponivel(banco, novos_dados["email"], usuario.id)
            if "nome" in novos_dados:
                usuario.nome = novos_dados["nome"].strip()
            if "perfil" in novos_dados:
                garantir_ao_menos_um_admin(banco, usuario, novos_dados["perfil"])
                usuario.tipo_usuario = novos_dados["perfil"]
            if "senha" in novos_dados and novos_dados["senha"]:
                usuario.senha_hash = gerar_hash_senha(novos_dados["senha"])
        for usuario_id in dados.exclusoes:
            usuario = banco.get(Usuario, UUID(usuario_id))
            if usuario is None or not usuario.ativo:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
            if usuario.id == atual.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode excluir a si mesmo.")
            garantir_ao_menos_um_admin(banco, usuario)
            usuario.ativo = False
        banco.commit()
    except Exception:
        banco.rollback()
        raise
    return {"criadas": len(dados.criacoes), "atualizadas": len(dados.atualizacoes), "excluidas": len(dados.exclusoes)}


@rotas_api.delete("/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario(
    usuario_id: UUID,
    atual: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> None:
    usuario = banco.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    if usuario.id == atual.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Você não pode excluir a si mesmo.")
    garantir_ao_menos_um_admin(banco, usuario)
    usuario.ativo = False
    banco.commit()


@rotas_api.get("/areas-campus")
def listar_areas_campus(
    _: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, object]]:
    areas = banco.scalars(
        select(AreaCampus).where(AreaCampus.ativo).order_by(AreaCampus.limite_campus.desc(), AreaCampus.prioridade.desc(), AreaCampus.nome)
    ).all()
    return [area_para_resposta(area) for area in areas]


@rotas_api.post("/areas-campus", status_code=status.HTTP_201_CREATED)
def criar_area_campus(
    dados: AreaCampusEntrada,
    _: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    area = AreaCampus(
        nome=dados.nome.strip(),
        tipo=dados.tipo.strip(),
        coordenadas=[ponto.model_dump() for ponto in dados.coordenadas],
        limite_campus=dados.limite_campus,
        prioridade=dados.prioridade,
    )
    banco.add(area)
    banco.commit()
    banco.refresh(area)
    return area_para_resposta(area)


@rotas_api.post("/areas-campus/identificar")
def identificar_area_campus(
    dados: CoordenadasEntrada,
    _: Usuario = Depends(obter_usuario_atual),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    area, bloco_mais_proximo, dentro_do_campus = identificar_area_por_coordenadas(banco, dados.latitude, dados.longitude)
    return {
        "dentroCampus": dentro_do_campus,
        "area": area_para_resposta(area) if area else None,
        "blocoMaisProximo": area_para_resposta(bloco_mais_proximo) if bloco_mais_proximo else None,
        "local": descrever_local(area, bloco_mais_proximo) if dentro_do_campus else "Área externa do campus",
    }


@rotas_api.put("/areas-campus/{area_id}")
def atualizar_area_campus(
    area_id: UUID,
    dados: AreaCampusEntrada,
    _: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    area = banco.get(AreaCampus, area_id)
    if area is None or not area.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")
    area.nome = dados.nome.strip()
    area.tipo = dados.tipo.strip()
    area.coordenadas = [ponto.model_dump() for ponto in dados.coordenadas]
    area.limite_campus = dados.limite_campus
    area.prioridade = dados.prioridade
    banco.commit()
    banco.refresh(area)
    return area_para_resposta(area)


@rotas_api.delete("/areas-campus/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_area_campus(
    area_id: UUID,
    _: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> None:
    area = banco.get(AreaCampus, area_id)
    if area is None or not area.ativo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Área não encontrada.")
    area.ativo = False
    banco.commit()


@rotas_api.get("/ocorrencias")
def listar_ocorrencias(
    usuario: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, object]]:
    consulta = select(Ocorrencia).order_by(Ocorrencia.criado_em.desc())
    if usuario.tipo_usuario == "usuario":
        consulta = consulta.where(Ocorrencia.autor_id == usuario.id)
    elif usuario.tipo_usuario in {"seguranca", "tecnico"}:
        consulta = consulta.where(Ocorrencia.responsavel_id == usuario.id)
    ocorrencias = banco.scalars(consulta).all()
    autores = {autor.id: autor.nome for autor in banco.scalars(select(Usuario)).all()}
    return [ocorrencia_para_resposta(ocorrencia, "Anônimo" if ocorrencia.anonima else autores.get(ocorrencia.autor_id, "Usuário")) for ocorrencia in ocorrencias]


@rotas_api.get("/ocorrencias/{ocorrencia_id}")
def buscar_ocorrencia(
    ocorrencia_id: UUID, usuario: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> dict[str, object]:
    ocorrencia = obter_ocorrencia_acessivel(banco, ocorrencia_id, usuario)
    autor = banco.get(Usuario, ocorrencia.autor_id)
    solicitante = "Anônimo" if ocorrencia.anonima else (autor.nome if autor else "Usuário")
    eventos = banco.scalars(
        select(EventoOcorrencia).where(EventoOcorrencia.ocorrencia_id == ocorrencia.id).order_by(EventoOcorrencia.criado_em)
    ).all()
    return ocorrencia_para_resposta(ocorrencia, solicitante, eventos)


@rotas_api.post("/ocorrencias", status_code=status.HTTP_201_CREATED)
def criar_ocorrencia(
    dados: OcorrenciaEntrada,
    tarefas: BackgroundTasks,
    usuario: Usuario = Depends(exigir_perfil("usuario")),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    if (dados.latitude is None) != (dados.longitude is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie latitude e longitude juntas.")

    local_identificado = dados.local.strip()
    if dados.tipo == "sos":
        if dados.latitude is None or dados.longitude is None:
            local_identificado = "Localização não obtida"
        else:
            area, bloco_mais_proximo, dentro_do_campus = identificar_area_por_coordenadas(banco, dados.latitude, dados.longitude)
            if not dentro_do_campus:
                detalhe = "O limite do campus ainda não foi configurado." if not banco.scalar(
                    select(AreaCampus.id).where(AreaCampus.ativo, AreaCampus.limite_campus).limit(1)
                ) else "Você está muito longe do campus para ativar o SOS. Em emergência, ligue para 190."
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=detalhe,
                )
            local_identificado = descrever_local(area, bloco_mais_proximo)

    proximo_numero = (banco.scalar(select(func.count()).select_from(Ocorrencia)) or 0) + 1
    ocorrencia = Ocorrencia(
        protocolo=f"#{datetime.now(timezone.utc).year}-{proximo_numero:04d}",
        titulo=dados.titulo.strip(),
        descricao=dados.descricao.strip() if dados.descricao else None,
        local=local_identificado,
        tipo=dados.tipo,
        autor_id=usuario.id,
        anonima=dados.anonima,
        anexos=[anexo.model_dump() for anexo in dados.anexos],
        latitude=dados.latitude,
        longitude=dados.longitude,
        precisao_metros=dados.precisao_metros,
    )
    banco.add(ocorrencia)
    banco.flush()
    registrar_evento(banco, ocorrencia.id, "criada", "Ocorrência registrada pelo usuário.", usuario.id)
    destinatarios = [admin.id for admin in banco.scalars(select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == "admin"))]
    titulo = {"sos": "SOS acionado", "manutencao": "Novo chamado de manutenção", "denuncia": "Nova denúncia"}[dados.tipo]
    criar_notificacoes(banco, destinatarios, "criada", titulo, ocorrencia.local if dados.tipo == "sos" else f"{ocorrencia.titulo} · {ocorrencia.protocolo}", ocorrencia.id, usuario.id)
    if dados.tipo == "sos":
        usuarios_alertados = listar_usuarios_online(banco)
        criar_notificacoes(
            banco,
            usuarios_alertados,
            "alerta",
            "Atenção: zona vermelha",
            "Um SOS foi acionado no campus. Mantenha-se atento e evite a área, se possível.",
            ocorrencia.id,
            usuario.id,
        )
        destinatarios.extend(usuarios_alertados)
    banco.commit()
    tarefas.add_task(gerenciador_notificacoes.avisar, destinatarios)
    banco.refresh(ocorrencia)
    return ocorrencia_para_resposta(ocorrencia, "Anônimo" if ocorrencia.anonima else usuario.nome)


@rotas_api.patch("/ocorrencias/{ocorrencia_id}/encaminhar")
def encaminhar_ocorrencia(
    ocorrencia_id: UUID,
    dados: EncaminhamentoEntrada,
    tarefas: BackgroundTasks,
    _: Usuario = Depends(exigir_perfil("admin")),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    ocorrencia = banco.get(Ocorrencia, ocorrencia_id)
    responsavel_id = UUID(dados.responsavel_id)
    responsavel = banco.get(Usuario, responsavel_id)
    if ocorrencia is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ocorrência não encontrada.")
    perfil_responsavel_necessario = "tecnico" if ocorrencia.tipo == "manutencao" else "seguranca"
    nome_responsavel_necessario = "técnico" if perfil_responsavel_necessario == "tecnico" else "segurança"
    if responsavel is None or not responsavel.ativo or responsavel.tipo_usuario != perfil_responsavel_necessario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Responsável {nome_responsavel_necessario} inválido.",
        )
    ocorrencia.responsavel_id = responsavel.id
    ocorrencia.status = "aguardando_aceite"
    registrar_evento(
        banco,
        ocorrencia.id,
        "encaminhada",
        f"Encaminhada para {responsavel.nome}; aguardando aceite do atendimento.",
        _.id,
    )
    titulo_encaminhamento = "Chamado técnico encaminhado para você" if ocorrencia.tipo == "manutencao" else "Ocorrência encaminhada para você"
    criar_notificacoes(banco, [responsavel.id], "encaminhada", titulo_encaminhamento, f"{ocorrencia.titulo} · {ocorrencia.local}", ocorrencia.id)
    criar_notificacoes(banco, [ocorrencia.autor_id], "encaminhada", "Seu chamado foi encaminhado", f"{ocorrencia.protocolo} · aguardando aceite da equipe", ocorrencia.id)
    banco.commit()
    tarefas.add_task(gerenciador_notificacoes.avisar, [responsavel.id, ocorrencia.autor_id])
    banco.refresh(ocorrencia)
    autor = banco.get(Usuario, ocorrencia.autor_id)
    return ocorrencia_para_resposta(ocorrencia, "Anônimo" if ocorrencia.anonima else (autor.nome if autor else "Usuário"))


@rotas_api.patch("/ocorrencias/{ocorrencia_id}/status")
def atualizar_status_ocorrencia(
    ocorrencia_id: UUID,
    dados: StatusEntrada,
    tarefas: BackgroundTasks,
    usuario: Usuario = Depends(obter_usuario_atual),
    banco: Session = Depends(obter_banco),
) -> dict[str, object]:
    ocorrencia = obter_ocorrencia_acessivel(banco, ocorrencia_id, usuario)
    pode_cancelar_sos_proprio = usuario.id == ocorrencia.autor_id and ocorrencia.tipo == "sos" and dados.status == "cancelado"
    responsavel_pode_atualizar = usuario.id == ocorrencia.responsavel_id and dados.status in {"em_atendimento", "concluido"}
    if usuario.tipo_usuario != "admin" and not responsavel_pode_atualizar and not pode_cancelar_sos_proprio:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não pode alterar esta ocorrência.")
    ocorrencia.status = dados.status
    descricao_evento = {
        "em_atendimento": "Atendimento aceito pela equipe responsável.",
        "concluido": "Atendimento concluído.",
        "cancelado": "SOS cancelado pelo solicitante.",
        "aguardando_aceite": "Ocorrência aguardando aceite da equipe.",
        "pendente": "Ocorrência retornou para a fila de triagem.",
    }[dados.status]
    registrar_evento(banco, ocorrencia.id, dados.status, descricao_evento, usuario.id)
    destinatarios_notificacao: list[UUID] = []
    if dados.status in {"concluido", "cancelado"}:
        administradores = banco.scalars(select(Usuario.id).where(Usuario.ativo, Usuario.tipo_usuario == "admin")).all()
        titulo_notificacao = "SOS cancelado" if dados.status == "cancelado" else ("SOS encerrado" if ocorrencia.tipo == "sos" else "Chamado resolvido")
        criar_notificacoes(banco, [ocorrencia.autor_id, *administradores], "concluida", titulo_notificacao, f"{ocorrencia.protocolo} · {ocorrencia.titulo}", ocorrencia.id, usuario.id)
        destinatarios_notificacao = [ocorrencia.autor_id, *administradores]
    banco.commit()
    if destinatarios_notificacao:
        tarefas.add_task(gerenciador_notificacoes.avisar, destinatarios_notificacao)
    banco.refresh(ocorrencia)
    autor = banco.get(Usuario, ocorrencia.autor_id)
    return ocorrencia_para_resposta(ocorrencia, "Anônimo" if ocorrencia.anonima else (autor.nome if autor else "Usuário"))


@rotas_api.get("/notificacoes")
def listar_notificacoes(
    usuario: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, object]]:
    notificacoes = banco.scalars(
        select(Notificacao).where(Notificacao.destinatario_id == usuario.id).order_by(Notificacao.criada_em.desc())
    ).all()
    return [notificacao_para_resposta(notificacao) for notificacao in notificacoes]


@rotas_api.patch("/notificacoes/lidas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_notificacoes_lidas(usuario: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)) -> None:
    notificacoes = banco.scalars(
        select(Notificacao).where(Notificacao.destinatario_id == usuario.id, Notificacao.lida.is_(False))
    ).all()
    for notificacao in notificacoes:
        notificacao.lida = True
    banco.commit()


@rotas_api.get("/segurancas/notificadas")
def listar_segurancas_notificadas(
    _: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> list[dict[str, object]]:
    segurancas = banco.scalars(
        select(Usuario).where(Usuario.ativo, Usuario.tipo_usuario == "seguranca").order_by(Usuario.nome)
    ).all()
    return [
        {"id": str(seguranca.id), "nome": seguranca.nome, "viatura": f"Patrulha {indice:02d}", "distanciaM": indice * 150, "status": "notificado"}
        for indice, seguranca in enumerate(segurancas, start=1)
    ]


@rotas_api.post("/arquivos", status_code=status.HTTP_201_CREATED)
async def enviar_arquivo(
    requisicao: Request, arquivo: UploadFile = File(...), _: Usuario = Depends(obter_usuario_atual)
) -> dict[str, str | None]:
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecione um arquivo válido.")
    extensao = Path(arquivo.filename).suffix.lower()
    extensoes_permitidas = TIPOS_ARQUIVO_PERMITIDOS.get(arquivo.content_type or "")
    if extensoes_permitidas is None or extensao not in extensoes_permitidas:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Envie apenas imagens JPG, PNG, WEBP ou vídeo MP4.")
    if arquivo.size is not None and arquivo.size > TAMANHO_MAXIMO_ARQUIVO:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="O arquivo deve ter no máximo 5 MB.")
    PASTA_ARQUIVOS.mkdir(parents=True, exist_ok=True)
    nome_armazenado = f"{uuid4()}{extensao}"
    destino = PASTA_ARQUIVOS / nome_armazenado
    conteudo = await arquivo.read()
    if len(conteudo) > TAMANHO_MAXIMO_ARQUIVO:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="O arquivo deve ter no máximo 5 MB.")
    destino.write_bytes(conteudo)
    return {"nome": arquivo.filename, "url": f"{str(requisicao.base_url).rstrip('/')}/arquivos/{nome_armazenado}", "tipo": arquivo.content_type}


@rotas_api.get("/arquivos/{nome_armazenado}")
def baixar_arquivo(
    nome_armazenado: str, usuario: Usuario = Depends(obter_usuario_atual), banco: Session = Depends(obter_banco)
) -> FileResponse:
    if Path(nome_armazenado).name != nome_armazenado or not usuario_pode_acessar_anexo(banco, nome_armazenado, usuario):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado.")
    arquivo = PASTA_ARQUIVOS / nome_armazenado
    if not arquivo.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado.")
    return FileResponse(arquivo, filename=arquivo.name, content_disposition_type="inline")
