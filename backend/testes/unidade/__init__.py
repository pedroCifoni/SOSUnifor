"""Execute a suíte a partir de ``backend`` com ``.\\.venv\\Scripts\\python.exe -m pytest -q``.

Ela usa exclusivamente o banco PostgreSQL ``unisos_testes`` e intercepta todos os
e-mails antes do SMTP, para que credenciais locais nunca sejam usadas.
"""
