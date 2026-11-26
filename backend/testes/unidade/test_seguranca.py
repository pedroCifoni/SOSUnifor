from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from app.core.config import configuracoes
from app.core.excecoes import NaoAutenticadoErro
from app.core.seguranca import conferir_senha, criar_token, gerar_hash_senha, ler_id_do_token
from app.entities.usuario import Usuario


def test_hash_de_senha_confere_apenas_a_senha_original() -> None:
    senha_hash = gerar_hash_senha("senha-segura")
    assert conferir_senha("senha-segura", senha_hash)
    assert not conferir_senha("outra-senha", senha_hash)


def test_jwt_valido_adulterado_e_expirado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(configuracoes, "jwt_secret", "segredo-de-teste")
    usuario = Usuario(id=uuid4(), nome="Teste", email="teste@edu.unifor.br", senha_hash="x", tipo_usuario="usuario")
    token = criar_token(usuario)
    assert ler_id_do_token(token) == usuario.id

    cabecalho, carga, assinatura = token.split(".")
    adulterado = f"{cabecalho}.{carga}.{assinatura[:-1]}{'a' if assinatura[-1] != 'a' else 'b'}"
    with pytest.raises(NaoAutenticadoErro):
        ler_id_do_token(adulterado)

    expirado = jwt.encode(
        {"sub": str(usuario.id), "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        configuracoes.jwt_secret,
        algorithm=configuracoes.jwt_algorithm,
    )
    with pytest.raises(NaoAutenticadoErro):
        ler_id_do_token(expirado)
