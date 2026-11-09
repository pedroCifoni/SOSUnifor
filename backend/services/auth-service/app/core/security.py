from pwdlib import PasswordHash


gerador_de_hash = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    # Aqui a senha vira hash. Salvar senha pura é pedir para o caos entrar pela porta.
    return gerador_de_hash.hash(senha)


def conferir_senha(senha: str, senha_hash: str) -> bool:
    # Compara sem precisar ressuscitar a senha original. Tecnologia, meu consagrado.
    return gerador_de_hash.verify(senha, senha_hash)
