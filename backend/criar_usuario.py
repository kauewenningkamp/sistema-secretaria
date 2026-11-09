
from getpass import getpass
from werkzeug.security import generate_password_hash
from conexao import conectar


def criar_usuario():
    print("=== Cadastro do usuário do SIGE ===")

    nome = input("Nome do responsável da Secretaria: ").strip()
    email = input("E-mail para acessar o SIGE: ").strip().lower()
    senha = getpass("Crie uma senha: ")
    confirmar_senha = getpass("Confirme a senha: ")

    if not nome or not email or not senha:
        print("Erro: preencha todos os campos.")
        return

    if senha != confirmar_senha:
        print("Erro: as senhas não coincidem.")
        return

    if len(senha) < 8:
        print("Erro: a senha deve ter pelo menos 8 caracteres.")
        return

    senha_hash = generate_password_hash(senha)
    banco = conectar()

    if banco is None:
        print("Erro: não foi possível conectar ao banco.")
        return

    cursor = None

    try:
        cursor = banco.cursor()

        cursor.execute(
            """
            INSERT INTO usuarios
                (nome, email, senha_hash, perfil, ativo)
            VALUES (%s, %s, %s, 'secretaria', 1)
            """,
            (nome, email, senha_hash)
        )

        banco.commit()
        print("Usuário da Secretaria cadastrado com sucesso!")

    except Exception as erro:
        banco.rollback()
        print(f"Não foi possível cadastrar o usuário: {erro}")

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


if __name__ == "__main__":
    criar_usuario()
