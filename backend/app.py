
from flask import Flask, jsonify, render_template, redirect, url_for, request, session
from werkzeug.security import check_password_hash
from conexao import conectar
from datetime import datetime
import os

PASTA_FRONTEND = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend")
)

app = Flask(
    __name__,
    template_folder=PASTA_FRONTEND,
    static_folder=PASTA_FRONTEND,
    static_url_path=""
)

# Chave temporária para a sessão durante o desenvolvimento.
# Antes de publicar o sistema, use uma chave secreta protegida.
app.secret_key = os.environ.get(
    "SIGE_SECRET_KEY",
    "chave-temporaria-apenas-para-desenvolvimento"
)


@app.route("/")
def inicio():
    if session.get("usuario_id"):
        return "Login realizado! A próxima etapa será criar o painel do SIGE."
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    dados = request.get_json(silent=True) or {}
    email = dados.get("email", "").strip().lower()
    senha = dados.get("senha", "")

    if not email or not senha:
        return jsonify({
            "erro": "Informe o e-mail e a senha."
        }), 400

    banco = conectar()

    if banco is None:
        return jsonify({
            "erro": "Não foi possível conectar ao banco de dados."
        }), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id_usuario, nome, email, senha_hash, perfil, ativo
            FROM usuarios
            WHERE email = %s
            LIMIT 1
            """,
            (email,)
        )

        usuario = cursor.fetchone()

        if (
            usuario is None
            or not usuario["ativo"]
            or usuario["perfil"] != "secretaria"
            or not check_password_hash(usuario["senha_hash"], senha)
        ):
            return jsonify({
                "erro": "E-mail ou senha inválidos."
            }), 401

        session.clear()
        session["usuario_id"] = usuario["id_usuario"]
        session["usuario_nome"] = usuario["nome"]

        return jsonify({
            "mensagem": f"Login realizado com sucesso! Bem-vindo(a), {usuario['nome']}."
        })

    except Exception:
        app.logger.exception("Erro ao processar o login")
        return jsonify({
            "erro": "Ocorreu um erro ao verificar o acesso."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()

   
@app.route("/api/equipamentos/<int:id_equipamento>/status", methods=["PATCH"])
def atualizar_status_equipamento(id_equipamento):
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}
    novo_status = dados.get("status", "").strip().upper()

    status_permitidos = {
        "DISPONIVEL",
        "DANIFICADO",
        "MANUTENCAO",
        "INATIVO"
    }

    if novo_status not in status_permitidos:
        return jsonify({"erro": "Selecione uma situação válida."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_equipamento, status
            FROM equipamentos
            WHERE id_equipamento = %s
            FOR UPDATE
        """, (id_equipamento,))

        equipamento = cursor.fetchone()

        if equipamento is None:
            banco.rollback()
            return jsonify({"erro": "Equipamento não encontrado."}), 404

        if equipamento["status"] == "EMPRESTADO":
            banco.rollback()
            return jsonify({
                "erro": "Não é possível alterar a situação de um equipamento emprestado."
            }), 409

        cursor.execute("""
            UPDATE equipamentos
            SET status = %s
            WHERE id_equipamento = %s
        """, (novo_status, id_equipamento))

        banco.commit()

        return jsonify({
            "mensagem": "Situação do equipamento atualizada com sucesso.",
            "status": novo_status
        })

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao atualizar situação do equipamento")
        return jsonify({
            "erro": "Não foi possível atualizar a situação do equipamento."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()
     

@app.route("/teste-banco")
def teste_banco():
    banco = conectar()

    if banco:
        banco.close()
        return jsonify({
            "mensagem": "Conexão com o MySQL funcionando!"
        })

    return jsonify({
        "erro": "Não foi possível conectar ao banco de dados."
    }), 500



@app.route("/api/professores", methods=["GET"])
def listar_professores():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_professor, nome, ativo
            FROM professores
            ORDER BY nome
        """)
        professores = cursor.fetchall()

        return jsonify(professores)

    except Exception:
        app.logger.exception("Erro ao listar professores")
        return jsonify({"erro": "Não foi possível listar os professores."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/professores", methods=["POST"])
def cadastrar_professor():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}
    nome = dados.get("nome", "").strip()

    if not nome:
        return jsonify({"erro": "Informe o nome do professor."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor()
        cursor.execute(
            "INSERT INTO professores (nome) VALUES (%s)",
            (nome,)
        )
        banco.commit()

        return jsonify({
            "mensagem": "Professor cadastrado com sucesso.",
            "id_professor": cursor.lastrowid,
            "nome": nome
        }), 201

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao cadastrar professor")
        return jsonify({"erro": "Não foi possível cadastrar o professor."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/professores/<int:id_professor>/status", methods=["PATCH"])
def atualizar_status_professor(id_professor):
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}
    novo_status = dados.get("ativo")

    if not isinstance(novo_status, bool):
        return jsonify({"erro": "Informe uma situação válida."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_professor
            FROM professores
            WHERE id_professor = %s
            FOR UPDATE
        """, (id_professor,))

        professor = cursor.fetchone()

        if professor is None:
            banco.rollback()
            return jsonify({"erro": "Professor não encontrado."}), 404

        cursor.execute("""
            UPDATE professores
            SET ativo = %s
            WHERE id_professor = %s
        """, (novo_status, id_professor))

        banco.commit()

        return jsonify({
            "mensagem": "Situação do professor atualizada com sucesso.",
            "ativo": novo_status
        })

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao atualizar situação do professor")
        return jsonify({
            "erro": "Não foi possível atualizar a situação do professor."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/professores")
def pagina_professores():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("professores.html")


@app.route("/painel")
def pagina_painel():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("painel.html")


@app.route("/api/painel")
def resumo_painel():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM equipamentos
        """)
        total_equipamentos = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM emprestimos
            WHERE status = 'ATIVO'
              AND data_devolucao IS NULL
        """)
        emprestimos_ativos = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM emprestimos
            WHERE data_prevista_devolucao < NOW()
              AND data_devolucao IS NULL
        """)
        emprestimos_atrasados = cursor.fetchone()["total"]

        return jsonify({
            "total_equipamentos": total_equipamentos,
            "emprestimos_ativos": emprestimos_ativos,
            "emprestimos_atrasados": emprestimos_atrasados
        })

    except Exception:
        app.logger.exception("Erro ao carregar o resumo do painel")
        return jsonify({
            "erro": "Não foi possível carregar os indicadores."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/equipamentos", methods=["GET"])
def listar_equipamentos():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                e.id_equipamento,
                e.id_tipo,
                t.nome AS tipo,
                e.numero_patrimonio,
                e.descricao,
                e.status,
                e.observacao,
                e.criado_em
            FROM equipamentos e
            INNER JOIN tipos_equipamento t
                ON t.id_tipo = e.id_tipo
            ORDER BY t.nome, e.numero_patrimonio
        """)
        equipamentos = cursor.fetchall()

        for equipamento in equipamentos:
            if equipamento["criado_em"] is not None:
                equipamento["criado_em"] = equipamento["criado_em"].isoformat(
                    sep=" ", timespec="seconds"
                )

        return jsonify(equipamentos)

    except Exception:
        app.logger.exception("Erro ao listar equipamentos")
        return jsonify({"erro": "Não foi possível listar os equipamentos."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/equipamentos", methods=["POST"])
def cadastrar_equipamento():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}

    try:
        id_tipo = int(dados.get("id_tipo", 0))
    except (TypeError, ValueError):
        return jsonify({"erro": "Selecione um tipo válido."}), 400

    patrimonio = dados.get("numero_patrimonio", "").strip()
    descricao = dados.get("descricao", "").strip() or None
    observacao = dados.get("observacao", "").strip() or None

    if not patrimonio:
        return jsonify({"erro": "Informe o número de patrimônio."}), 400

    if len(patrimonio) > 80:
        return jsonify({"erro": "O patrimônio deve ter no máximo 80 caracteres."}), 400

    if descricao and len(descricao) > 255:
        return jsonify({"erro": "A descrição deve ter no máximo 255 caracteres."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute(
            "SELECT id_tipo FROM tipos_equipamento WHERE id_tipo = %s",
            (id_tipo,)
        )
        if cursor.fetchone() is None:
            return jsonify({"erro": "O tipo de equipamento selecionado não existe."}), 400

        cursor.execute(
            "SELECT id_equipamento FROM equipamentos WHERE numero_patrimonio = %s",
            (patrimonio,)
        )
        if cursor.fetchone() is not None:
            return jsonify({"erro": "Já existe um equipamento com esse patrimônio."}), 409

        cursor.execute("""
            INSERT INTO equipamentos
                (id_tipo, numero_patrimonio, descricao, observacao)
            VALUES (%s, %s, %s, %s)
        """, (id_tipo, patrimonio, descricao, observacao))

        id_novo = cursor.lastrowid
        banco.commit()

        return jsonify({
            "mensagem": "Equipamento cadastrado com sucesso.",
            "id_equipamento": id_novo
        }), 201

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao cadastrar equipamento")
        return jsonify({"erro": "Não foi possível cadastrar o equipamento."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/tipos-equipamento", methods=["GET"])
def listar_tipos_equipamento():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_tipo, nome, descricao
            FROM tipos_equipamento
            ORDER BY nome
        """)
        return jsonify(cursor.fetchall())

    except Exception:
        app.logger.exception("Erro ao listar tipos de equipamento")
        return jsonify({"erro": "Não foi possível carregar os tipos."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()



@app.route("/equipamentos")
def pagina_equipamentos():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("equipamentos.html")


@app.route("/api/turmas", methods=["GET"])
def listar_turmas():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_turma, nome, curso, periodo, ativa
            FROM turmas
            ORDER BY nome
        """)
        return jsonify(cursor.fetchall())

    except Exception:
        app.logger.exception("Erro ao listar turmas")
        return jsonify({"erro": "Não foi possível listar as turmas."}), 500

    finally:
     if cursor is not None:
        cursor.close()
     banco.close()


@app.route("/api/turmas", methods=["POST"])
def cadastrar_turma():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}

    nome = dados.get("nome", "").strip()
    curso = dados.get("curso", "").strip() or None
    periodo = dados.get("periodo", "").strip() or None

    if not nome:
        return jsonify({"erro": "Informe o nome da turma."}), 400

    if len(nome) > 80:
        return jsonify({"erro": "O nome deve ter no máximo 80 caracteres."}), 400

    if curso and len(curso) > 100:
        return jsonify({"erro": "O curso deve ter no máximo 100 caracteres."}), 400

    if periodo and len(periodo) > 40:
        return jsonify({"erro": "O período deve ter no máximo 40 caracteres."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None
    try:
        cursor = banco.cursor()
        cursor.execute(
            """
            INSERT INTO turmas (nome, curso, periodo)
            VALUES (%s, %s, %s)
            """,
            (nome, curso, periodo)
        )
        banco.commit()

        return jsonify({
            "mensagem": "Turma cadastrada com sucesso.",
            "id_turma": cursor.lastrowid
        }), 201

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao cadastrar turma")
        return jsonify({"erro": "Não foi possível cadastrar a turma."}), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/turmas/<int:id_turma>/status", methods=["PATCH"])
def atualizar_status_turma(id_turma):
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}
    novo_status = dados.get("ativa")

    if not isinstance(novo_status, bool):
        return jsonify({"erro": "Informe uma situação válida."}), 400

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_turma
            FROM turmas
            WHERE id_turma = %s
            FOR UPDATE
        """, (id_turma,))

        turma = cursor.fetchone()

        if turma is None:
            banco.rollback()
            return jsonify({"erro": "Turma não encontrada."}), 404

        cursor.execute("""
            UPDATE turmas
            SET ativa = %s
            WHERE id_turma = %s
        """, (novo_status, id_turma))

        banco.commit()

        return jsonify({
            "mensagem": "Situação da turma atualizada com sucesso.",
            "ativa": novo_status
        })

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao atualizar situação da turma")
        return jsonify({
            "erro": "Não foi possível atualizar a situação da turma."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/turmas")
def pagina_turmas():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("turmas.html")

@app.route("/emprestimos")
def pagina_emprestimos():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("emprestimos.html")


@app.route("/api/emprestimos", methods=["GET"])
def listar_emprestimos():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()

    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            UPDATE emprestimos
            SET status = 'ATRASADO'
            WHERE status = 'ATIVO'
              AND data_prevista_devolucao < NOW()
              AND data_devolucao IS NULL
        """)

        banco.commit()

        cursor.execute("""
            SELECT
                e.id_emprestimo,
                p.nome AS professor,
                t.nome AS turma,
                e.data_emprestimo,
                e.data_prevista_devolucao,
                e.data_devolucao,
                e.status,
                e.observacao,
                u.nome AS responsavel,
                COUNT(ie.id_item) AS quantidade_equipamentos,
                GROUP_CONCAT(
                    eq.numero_patrimonio
                    ORDER BY eq.numero_patrimonio
                    SEPARATOR ', '
                ) AS equipamentos
            FROM emprestimos e
            INNER JOIN professores p
                ON p.id_professor = e.id_professor
            INNER JOIN turmas t
                ON t.id_turma = e.id_turma
            INNER JOIN usuarios u
                ON u.id_usuario = e.id_responsavel_registro
            LEFT JOIN itens_emprestimo ie
                ON ie.id_emprestimo = e.id_emprestimo
            LEFT JOIN equipamentos eq
                ON eq.id_equipamento = ie.id_equipamento
            GROUP BY
                e.id_emprestimo,
                p.nome,
                t.nome,
                e.data_emprestimo,
                e.data_prevista_devolucao,
                e.data_devolucao,
                e.status,
                e.observacao,
                u.nome
            ORDER BY e.id_emprestimo DESC
        """)

        emprestimos = cursor.fetchall()

        for item in emprestimos:
            for campo in (
                "data_emprestimo",
                "data_prevista_devolucao",
                "data_devolucao"
            ):
                if item[campo] is not None:
                    item[campo] = item[campo].strftime("%d/%m/%Y %H:%M")

        return jsonify(emprestimos)

    except Exception:
        app.logger.exception("Erro ao listar empréstimos")
        return jsonify({
            "erro": "Não foi possível consultar os empréstimos."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()
@app.route("/api/emprestimos", methods=["POST"])
def cadastrar_emprestimo():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    dados = request.get_json(silent=True) or {}

    try:
        id_professor = int(dados.get("id_professor", 0))
        id_turma = int(dados.get("id_turma", 0))
        ids_equipamentos = dados.get("ids_equipamentos", [])

        if not isinstance(ids_equipamentos, list) or not ids_equipamentos:
            return jsonify({"erro": "Adicione pelo menos um equipamento."}), 400

        ids_equipamentos = [int(valor) for valor in ids_equipamentos]

        if any(valor <= 0 for valor in ids_equipamentos):
            return jsonify({"erro": "Há um equipamento inválido na seleção."}), 400

        if len(ids_equipamentos) != len(set(ids_equipamentos)):
            return jsonify({"erro": "Há equipamentos repetidos na seleção."}), 400

        data_emprestimo = datetime.strptime(
            dados.get("data_emprestimo", ""),
            "%Y-%m-%dT%H:%M"
        )
        data_prevista = datetime.strptime(
            dados.get("data_prevista_devolucao", ""),
            "%Y-%m-%dT%H:%M"
        )

    except (TypeError, ValueError):
        return jsonify({"erro": "Confira o professor, a turma, os equipamentos e as datas."}), 400

    if data_prevista <= data_emprestimo:
        return jsonify({
            "erro": "A devolução prevista deve ser posterior à retirada."
        }), 400

    observacao = (dados.get("observacao") or "").strip() or None

    banco = conectar()
    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_professor
            FROM professores
            WHERE id_professor = %s AND ativo = TRUE
        """, (id_professor,))

        if cursor.fetchone() is None:
            return jsonify({"erro": "Selecione um professor ativo."}), 400

        cursor.execute("""
            SELECT id_turma
            FROM turmas
            WHERE id_turma = %s AND ativa = TRUE
        """, (id_turma,))

        if cursor.fetchone() is None:
            return jsonify({"erro": "Selecione uma turma ativa."}), 400

        # Bloqueia os equipamentos durante a validação da transação.
        placeholders = ", ".join(["%s"] * len(ids_equipamentos))

        cursor.execute(f"""
            SELECT id_equipamento, status
            FROM equipamentos
            WHERE id_equipamento IN ({placeholders})
            ORDER BY id_equipamento
            FOR UPDATE
        """, tuple(sorted(ids_equipamentos)))

        equipamentos = cursor.fetchall()

        if len(equipamentos) != len(ids_equipamentos):
            banco.rollback()
            return jsonify({"erro": "Um ou mais equipamentos não existem."}), 400

        if any(item["status"] != "DISPONIVEL" for item in equipamentos):
            banco.rollback()
            return jsonify({
                "erro": "Um ou mais equipamentos não estão mais disponíveis. Atualize a página."
            }), 409

        cursor.execute("""
            INSERT INTO emprestimos (
                id_professor,
                id_turma,
                id_responsavel_registro,
                data_emprestimo,
                data_prevista_devolucao,
                status,
                observacao
            )
            VALUES (%s, %s, %s, %s, %s, 'ATIVO', %s)
        """, (
            id_professor,
            id_turma,
            session["usuario_id"],
            data_emprestimo,
            data_prevista,
            observacao
        ))

        id_emprestimo = cursor.lastrowid

        for id_equipamento in ids_equipamentos:
            cursor.execute("""
                INSERT INTO itens_emprestimo (
                    id_emprestimo,
                    id_equipamento,
                    status_item
                )
                VALUES (%s, %s, 'EMPRESTADO')
            """, (id_emprestimo, id_equipamento))

            cursor.execute("""
                UPDATE equipamentos
                SET status = 'EMPRESTADO'
                WHERE id_equipamento = %s
                  AND status = 'DISPONIVEL'
            """, (id_equipamento,))

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Um equipamento deixou de estar disponível."
                )

        banco.commit()

        return jsonify({
            "mensagem": "Empréstimo registrado com sucesso.",
            "id_emprestimo": id_emprestimo,
            "quantidade_equipamentos": len(ids_equipamentos)
        }), 201

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao cadastrar empréstimo")
        return jsonify({
            "erro": "Não foi possível registrar o empréstimo."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()


@app.route("/api/devolucoes/<int:id_emprestimo>", methods=["POST"])
def registrar_devolucao(id_emprestimo):
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()

    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        # Bloqueia o empréstimo durante a devolução.
        cursor.execute("""
            SELECT id_emprestimo, status, data_devolucao
            FROM emprestimos
            WHERE id_emprestimo = %s
            FOR UPDATE
        """, (id_emprestimo,))

        emprestimo = cursor.fetchone()

        if emprestimo is None:
            banco.rollback()
            return jsonify({"erro": "Empréstimo não encontrado."}), 404

        if emprestimo["status"] not in ("ATIVO", "ATRASADO") or emprestimo["data_devolucao"] is not None:
            banco.rollback()
            return jsonify({"erro": "Este empréstimo já foi devolvido ou não está disponível."}), 409

        # Busca e bloqueia todos os equipamentos do empréstimo.
        cursor.execute("""
            SELECT ie.id_equipamento, ie.status_item, eq.status AS status_equipamento
            FROM itens_emprestimo ie
            INNER JOIN equipamentos eq
                ON eq.id_equipamento = ie.id_equipamento
            WHERE ie.id_emprestimo = %s
            FOR UPDATE
        """, (id_emprestimo,))

        itens = cursor.fetchall()

        if not itens:
            banco.rollback()
            return jsonify({"erro": "Este empréstimo não possui equipamentos."}), 400

        if any(
            item["status_item"] != "EMPRESTADO"
            or item["status_equipamento"] != "EMPRESTADO"
            for item in itens
        ):
            banco.rollback()
            return jsonify({
                "erro": "Há equipamentos com situação diferente de emprestado. Verifique o empréstimo."
            }), 409

        # Registra a devolução de todos os itens juntos.
        cursor.execute("""
            UPDATE itens_emprestimo
            SET status_item = 'DEVOLVIDO',
                data_devolucao_item = NOW()
            WHERE id_emprestimo = %s
        """, (id_emprestimo,))

        cursor.execute("""
            UPDATE equipamentos eq
            INNER JOIN itens_emprestimo ie
                ON ie.id_equipamento = eq.id_equipamento
            SET eq.status = 'DISPONIVEL'
            WHERE ie.id_emprestimo = %s
        """, (id_emprestimo,))

        cursor.execute("""
            UPDATE emprestimos
            SET status = 'DEVOLVIDO',
                data_devolucao = NOW()
            WHERE id_emprestimo = %s
        """, (id_emprestimo,))

        banco.commit()

        return jsonify({
            "mensagem": "Devolução registrada com sucesso.",
            "id_emprestimo": id_emprestimo,
            "quantidade_equipamentos": len(itens)
        })

    except Exception:
        banco.rollback()
        app.logger.exception("Erro ao registrar devolução")
        return jsonify({
            "erro": "Não foi possível registrar a devolução."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()
@app.route("/api/devolucoes", methods=["GET"])
def listar_devolucoes():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()

    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            UPDATE emprestimos
            SET status = 'ATRASADO'
            WHERE status = 'ATIVO'
              AND data_prevista_devolucao < NOW()
              AND data_devolucao IS NULL
        """)

        banco.commit()

        cursor.execute("""
            SELECT
                e.id_emprestimo,
                p.nome AS professor,
                t.nome AS turma,
                e.data_emprestimo,
                e.data_prevista_devolucao,
                e.status,
                COUNT(ie.id_item) AS quantidade_equipamentos,
                GROUP_CONCAT(
                    eq.numero_patrimonio
                    ORDER BY eq.numero_patrimonio
                    SEPARATOR ', '
                ) AS equipamentos
            FROM emprestimos e
            INNER JOIN professores p
                ON p.id_professor = e.id_professor
            INNER JOIN turmas t
                ON t.id_turma = e.id_turma
            INNER JOIN itens_emprestimo ie
                ON ie.id_emprestimo = e.id_emprestimo
            INNER JOIN equipamentos eq
                ON eq.id_equipamento = ie.id_equipamento
            WHERE e.status IN ('ATIVO', 'ATRASADO')
              AND e.data_devolucao IS NULL
            GROUP BY
                e.id_emprestimo,
                p.nome,
                t.nome,
                e.data_emprestimo,
                e.data_prevista_devolucao,
                e.status
            ORDER BY e.data_prevista_devolucao ASC
        """)

        devolucoes = cursor.fetchall()

        for item in devolucoes:
            item["data_emprestimo"] = item["data_emprestimo"].strftime("%d/%m/%Y %H:%M")
            item["data_prevista_devolucao"] = item["data_prevista_devolucao"].strftime("%d/%m/%Y %H:%M")

        return jsonify(devolucoes)

    except Exception:
        app.logger.exception("Erro ao listar devoluções")
        return jsonify({
            "erro": "Não foi possível consultar as devoluções."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()

@app.route("/api/historico", methods=["GET"])
def listar_historico():
    if not session.get("usuario_id"):
        return jsonify({"erro": "Faça login para continuar."}), 401

    banco = conectar()

    if banco is None:
        return jsonify({"erro": "Falha na conexão com o banco."}), 500

    cursor = None

    try:
        cursor = banco.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                e.id_emprestimo,
                p.nome AS professor,
                t.nome AS turma,
                e.data_emprestimo,
                e.data_devolucao,
                e.status,
                COUNT(ie.id_item) AS quantidade_equipamentos,
                GROUP_CONCAT(
                    eq.numero_patrimonio
                    ORDER BY eq.numero_patrimonio
                    SEPARATOR ', '
                ) AS equipamentos
            FROM emprestimos e
            INNER JOIN professores p
                ON p.id_professor = e.id_professor
            INNER JOIN turmas t
                ON t.id_turma = e.id_turma
            INNER JOIN itens_emprestimo ie
                ON ie.id_emprestimo = e.id_emprestimo
            INNER JOIN equipamentos eq
                ON eq.id_equipamento = ie.id_equipamento
            WHERE e.status = 'DEVOLVIDO'
              AND e.data_devolucao IS NOT NULL
            GROUP BY
                e.id_emprestimo,
                p.nome,
                t.nome,
                e.data_emprestimo,
                e.data_devolucao,
                e.status
            ORDER BY e.data_devolucao DESC
        """)

        historico = cursor.fetchall()

        for item in historico:
            item["data_emprestimo"] = item["data_emprestimo"].strftime(
                "%d/%m/%Y %H:%M"
            )
            item["data_devolucao"] = item["data_devolucao"].strftime(
                "%d/%m/%Y %H:%M"
            )

        return jsonify(historico)

    except Exception:
        app.logger.exception("Erro ao consultar histórico")
        return jsonify({
            "erro": "Não foi possível consultar o histórico."
        }), 500

    finally:
        if cursor is not None:
            cursor.close()
        banco.close()
@app.route("/historico")
def pagina_historico():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("historico.html")
@app.route("/devolucoes")
def pagina_devolucoes():
    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return render_template("devolucoes.html")

if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)
