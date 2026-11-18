from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.excecoes import AcessoNegadoErro, NaoAutenticadoErro
from app.core.seguranca import conferir_senha, criar_token, ler_id_do_token
from app.dtos.auth_dto import LoginEntrada, TokenResposta
from app.entities.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository


# Intervalo mínimo entre duas gravações de `ultimo_acesso`, para não escrever no banco a cada requisição.
INTERVALO_REGISTRO_ACESSO = timedelta(seconds=20)


class AuthService:
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao
        self.usuarios = UsuarioRepository(sessao)

    def entrar(self, dados: LoginEntrada) -> TokenResposta:
        usuario = self.usuarios.buscar_por_email(dados.email)
        if usuario is None or not usuario.ativo or not conferir_senha(dados.senha, usuario.senha_hash):
            raise NaoAutenticadoErro("E-mail ou senha inválidos.")
        return TokenResposta(token=criar_token(usuario))

    def usuario_do_token(self, token: str | None) -> Usuario:
        """Identifica o usuário do token e registra o último acesso (usado para saber quem está online)."""
        if token is None:
            raise NaoAutenticadoErro("Autenticação obrigatória.")
        usuario = self.usuarios.buscar_por_id(ler_id_do_token(token))
        if usuario is None or not usuario.ativo:
            raise NaoAutenticadoErro("Usuário sem acesso.")
        agora = datetime.now(timezone.utc)
        if usuario.ultimo_acesso is None or agora - usuario.ultimo_acesso >= INTERVALO_REGISTRO_ACESSO:
            usuario.ultimo_acesso = agora
            self.sessao.commit()
        return usuario

    @staticmethod
    def exigir_perfil(usuario: Usuario, perfis: tuple[str, ...]) -> Usuario:
        if usuario.tipo_usuario not in perfis:
            raise AcessoNegadoErro("Você não tem permissão para esta ação.")
        return usuario
