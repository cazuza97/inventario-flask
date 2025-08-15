from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from werkzeug.utils import secure_filename
from functools import wraps



# ----------------------------
# Configuração do Flask
# ----------------------------
app = Flask(__name__)
app.secret_key = "inventario"  # Troque para algo seguro
DB_PATH = "inventario.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



USUARIO = "admin"
SENHA = "1234"

# ----------------------------
# Criar tabelas se não existirem
# ----------------------------
def criar_tabelas():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabela de produtos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            localizacao TEXT
        )
    """)

    # Tabela de documentos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            nome_arquivo TEXT NOT NULL,
            caminho_arquivo TEXT NOT NULL,
            FOREIGN KEY(produto_id) REFERENCES produtos(id) ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()

criar_tabelas()

# ----------------------------
# Função para conectar ao banco
# ----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------
# ROTAS
# ----------------------------
# Middleware para proteger rotas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logado"):  # verifica se o usuário está logado
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]
        if usuario == USUARIO and senha == SENHA:
            session["logado"] = True
            return redirect(url_for("index"))
        else:
            return "Usuário ou senha inválidos!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



# Página inicial / listagem
@app.route("/", methods=["GET"])
@login_required
def index():
    filtro = request.args.get("filtro", "")
    conn = get_conn()
    cursor = conn.cursor()
    if filtro:
        filtro = f"%{filtro}%"
        cursor.execute("""
            SELECT * FROM produtos
            WHERE codigo LIKE ? OR descricao LIKE ? OR localizacao LIKE ?
        """, (filtro, filtro, filtro))
    else:
        cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()
    conn.close()
    return render_template("index.html", produtos=produtos, filtro=filtro)

# Adicionar produto
@app.route("/adicionar", methods=["GET", "POST"])
@login_required
def adicionar():
    if request.method == "POST":
        codigo = request.form["codigo"].upper()
        descricao = request.form["descricao"].upper()
        quantidade = request.form["quantidade"]
        localizacao = request.form["localizacao"].upper()
        if codigo and descricao and quantidade.isdigit():
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO produtos (codigo, descricao, quantidade, localizacao) VALUES (?, ?, ?, ?)",
                           (codigo, descricao, int(quantidade), localizacao))
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
    return render_template("adicionar.html")

# Editar produto
@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produtos WHERE id=?", (id,))
    produto = cursor.fetchone()

    cursor.execute("SELECT * FROM documentos WHERE produto_id=?", (id,))
    documentos = cursor.fetchall()

    if request.method == "POST":
        codigo = request.form["codigo"].upper()
        descricao = request.form["descricao"].upper()
        quantidade = request.form["quantidade"]
        localizacao = request.form["localizacao"].upper()
        if codigo and descricao and quantidade.isdigit():
            cursor.execute("UPDATE produtos SET codigo=?, descricao=?, quantidade=?, localizacao=? WHERE id=?",
                           (codigo, descricao, int(quantidade), localizacao, id))
            conn.commit()
            conn.close()
            return redirect(url_for("index"))
    conn.close()
    return render_template("editar.html", produto=produto, documentos=documentos)

# Excluir produto
@app.route("/excluir/<int:id>")
@login_required
def excluir(id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM produtos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

# Upload de documentos
@app.route("/upload/<int:produto_id>", methods=["GET", "POST"])
@login_required
def upload(produto_id):
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if arquivo and arquivo.filename != "":
            filename = secure_filename(arquivo.filename)
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            arquivo.save(caminho)

            # Salvar apenas o nome do arquivo no banco
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documentos (produto_id, nome_arquivo, caminho_arquivo) VALUES (?, ?, ?)",
                (produto_id, filename, filename)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("editar", id=produto_id))
    return render_template("upload.html", produto_id=produto_id)

#excluir arquivo
@app.route("/excluir_documento/<int:id>")
@login_required
def excluir_documento(id):
    conn = get_conn()
    cursor = conn.cursor()

    # Pega o arquivo para deletar fisicamente
    cursor.execute("SELECT caminho_arquivo FROM documentos WHERE id=?", (id,))
    doc = cursor.fetchone()
    if doc:
        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], doc['caminho_arquivo'])
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)

        # Deleta do banco
        cursor.execute("DELETE FROM documentos WHERE id=?", (id,))
        conn.commit()

    conn.close()
    # Redireciona para a mesma página do produto
    return redirect(request.referrer or url_for("index"))


# ----------------------------
# Rota para servir arquivos enviados
# ----------------------------
from flask import send_from_directory

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ----------------------------
# RODAR APP
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)