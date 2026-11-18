"""Entidades persistidas (modelos SQLAlchemy).

Importar este pacote registra todas as tabelas em `Base.metadata`.
"""

from app.entities.area_campus import AreaCampus
from app.entities.evento_ocorrencia import EventoOcorrencia
from app.entities.notificacao import Notificacao
from app.entities.ocorrencia import Ocorrencia
from app.entities.usuario import Usuario

__all__ = ["AreaCampus", "EventoOcorrencia", "Notificacao", "Ocorrencia", "Usuario"]
