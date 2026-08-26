from flask import Flask, render_template, request, redirect, url_for
from database import get_connection, init_db

app = Flask(__name__)


@app.route("/")
def inicio():
    return redirect(url_for("listar_produtos"))


@app.route("/produtos")
def listar_produtos():
    conn = get_connection()

    produtos = conn.execute(
        "SELECT * FROM produtos WHERE ativo = 1 ORDER BY nome"
    ).fetchall()

    conn.close()

    return render_template("produtos.html", produtos=produtos)


@app.route("/produtos/novo", methods=["GET", "POST"])
def novo_produto():

    if request.method == "POST":

        conn = get_connection()

        conn.execute("""
            INSERT INTO produtos (
                nome,
                categoria,
                tamanho,
                cor,
                preco_custo,
                preco_venda,
                quantidade_estoque
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form["nome"],
            request.form["categoria"],
            request.form["tamanho"],
            request.form["cor"],
            request.form.get("preco_custo") or 0,
            request.form["preco_venda"],
            request.form.get("quantidade_estoque") or 0
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("listar_produtos"))

    return render_template("produtos.html", novo=True)


@app.route("/produtos/<int:id>/editar", methods=["GET", "POST"])
def editar_produto(id):

    conn = get_connection()

    if request.method == "POST":

        conn.execute("""
            UPDATE produtos SET
                nome=?,
                categoria=?,
                tamanho=?,
                cor=?,
                preco_custo=?,
                preco_venda=?,
                quantidade_estoque=?
            WHERE id=?
        """, (
            request.form["nome"],
            request.form["categoria"],
            request.form["tamanho"],
            request.form["cor"],
            request.form.get("preco_custo") or 0,
            request.form["preco_venda"],
            request.form.get("quantidade_estoque") or 0,
            id
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("listar_produtos"))

    produto = conn.execute(
        "SELECT * FROM produtos WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        "produtos.html",
        produto=produto,
        editar=True
    )


@app.route("/produtos/<int:id>/excluir", methods=["POST"])
def excluir_produto(id):

    conn = get_connection()

    conn.execute(
        "UPDATE produtos SET ativo = 0 WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("listar_produtos"))


@app.route("/vendas/nova", methods=["GET", "POST"])
def nova_venda():
    conn = get_connection()

    if request.method == "POST":
        produto_ids = request.form.getlist("produto_id")
        quantidades = request.form.getlist("quantidade")
        forma_pagamento = request.form["forma_pagamento"]

        try:
            total = 0
            itens = []

            # 1. Valida estoque ANTES de mexer em qualquer coisa
            for pid in produto_ids:
                qtd = int(request.form.get(f"quantidade_{pid}", 0))
                produto = conn.execute(
                    "SELECT * FROM produtos WHERE id = ?", (pid,)
                ).fetchone()

                if produto["quantidade_estoque"] < qtd:
                    raise ValueError(
                        f"Estoque insuficiente para {produto['nome']}")

                subtotal = produto["preco_venda"] * qtd
                total += subtotal
                itens.append((pid, qtd, produto["preco_venda"]))

            # 2. Só chega aqui se TODOS os produtos passaram na validação
            cursor = conn.execute(
                "INSERT INTO vendas (forma_pagamento, total) VALUES (?, ?)",
                (forma_pagamento, total)
            )
            venda_id = cursor.lastrowid

            for pid, qtd, preco in itens:
                conn.execute("""
                    INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario)
                    VALUES (?, ?, ?, ?)
                """, (venda_id, pid, qtd, preco))

                conn.execute("""
                    UPDATE produtos SET quantidade_estoque = quantidade_estoque - ?
                    WHERE id = ?
                """, (qtd, pid))

            conn.commit()  # só salva se tudo deu certo
            conn.close()
            return redirect(url_for("listar_produtos"))

        except Exception as e:
            conn.rollback()  # desfaz tudo se algo falhou
            conn.close()
            return f"Erro ao processar venda: {e}", 400

    # GET: mostra formulário com produtos disponíveis
    produtos = conn.execute(
        "SELECT * FROM produtos WHERE ativo = 1 AND quantidade_estoque > 0 ORDER BY nome"
    ).fetchall()
    conn.close()
    return render_template("nova_venda.html", produtos=produtos)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
