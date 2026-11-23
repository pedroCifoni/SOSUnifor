"""Teste de carga da API do Uni SOS com Locust.

Simula pessoas usando o sistema ao mesmo tempo: entram, consultam ocorrências,
notificações e áreas do campus, e identificam a própria localização (como no SOS).

Rodar (com a API no ar), a partir da pasta backend:
    .\\.venv\\Scripts\\locust -f testes\\carga\\locustfile.py --host http://127.0.0.1:8001
e abrir http://localhost:8089

Variáveis opcionais:
    CARGA_EMAIL / CARGA_SENHA  conta usada pelos usuários simulados (padrão: admin de desenvolvimento)

ATENÇÃO
- Rode só contra o ambiente local. Nunca contra a API publicada sem combinar antes.
- Este roteiro NÃO chama rotas que enviam e-mail (criar usuário, esqueci a senha):
  com o Gmail configurado, isso mandaria e-mails de verdade e pode bloquear a conta.
- Também não cria ocorrências, para não encher o banco nem disparar notificações.
"""

import os
import random

from locust import HttpUser, between, task


EMAIL = os.getenv("CARGA_EMAIL", "admin@unifor.br")
SENHA = os.getenv("CARGA_SENHA", "123456")

# Pontos dentro e em volta da UNIFOR, para o "identificar local" variar como no uso real.
PONTOS = [(-3.7697 + random.uniform(-0.004, 0.004), -38.4812 + random.uniform(-0.004, 0.004)) for _ in range(50)]


class PessoaUsandoOSistema(HttpUser):
    """Uso típico: entra uma vez e navega. É o cenário principal."""

    weight = 9
    wait_time = between(1, 3)  # cada pessoa espera de 1 a 3 s entre uma ação e outra

    def on_start(self) -> None:
        resposta = self.client.post("/auth/login", json={"email": EMAIL, "senha": SENHA}, name="/auth/login")
        token = resposta.json().get("token") if resposta.ok else None
        if not token:
            raise RuntimeError(f"Login falhou ({resposta.status_code}). Confira CARGA_EMAIL e CARGA_SENHA.")
        self.client.headers["Authorization"] = f"Bearer {token}"

    @task(5)
    def ver_notificacoes(self) -> None:
        # O front consulta isto com frequência: é a rota mais chamada.
        self.client.get("/notificacoes")

    @task(3)
    def ver_ocorrencias(self) -> None:
        self.client.get("/ocorrencias")

    @task(2)
    def identificar_local(self) -> None:
        latitude, longitude = random.choice(PONTOS)
        self.client.post("/areas-campus/identificar", json={"latitude": latitude, "longitude": longitude})

    @task(1)
    def ver_areas_do_campus(self) -> None:
        self.client.get("/areas-campus")


class PessoaEntrando(HttpUser):
    """Login repetido. O hash de senha (Argon2) é propositalmente pesado, então esta é a rota mais cara."""

    weight = 1
    wait_time = between(2, 5)

    @task
    def entrar(self) -> None:
        self.client.post("/auth/login", json={"email": EMAIL, "senha": SENHA}, name="/auth/login (repetido)")
