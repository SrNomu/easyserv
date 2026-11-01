"""
banco.py - Tudo o que mexe com o banco de dados SQLite.

O SQLite guarda os dados num único arquivo (easyserv.db), na pasta de dados.
Não precisa instalar nada: o Python já vem com o módulo sqlite3.

Temos duas tabelas:
  - atendimentos: um registro por atendimento (cliente, pagamento, totais...)
  - itens: os serviços de cada atendimento (ligados pelo atendimento_id)

Os valores em dinheiro são guardados em CENTAVOS (números inteiros).
Ex.: R$ 1,50 é guardado como 150. Assim as somas nunca têm erro de arredondamento.

No modo treinamento (treino.py) tudo isto usa outro arquivo, o treino.db.

Boletos e recargas (opção "Pedir o valor do boleto/recarga"): o valor que é de
terceiros fica em colunas separadas (itens.valor_terceiros_centavos e
atendimentos.repasse_centavos). Os totais do atendimento (subtotal, taxa, total)
continuam sendo SÓ da loja; o valor recebido e o troco são do valor cobrado de
verdade (total + repasse).
"""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

import treino
from config import pasta_base
from utils import de_centavos, para_centavos

NOME_BANCO = "easyserv.db"
# Nome do arquivo nas versões até a 1.3. Se ele existir (e o novo não), continua sendo
# usado: assim quem atualiza não perde nada e o arquivo nunca precisa ser renomeado.
NOME_BANCO_ANTIGO = "maisbella.db"


def _escolher_arquivo_banco(pasta):
    novo, antigo = os.path.join(pasta, NOME_BANCO), os.path.join(pasta, NOME_BANCO_ANTIGO)
    return antigo if os.path.exists(antigo) and not os.path.exists(novo) else novo


ARQUIVO_BANCO = _escolher_arquivo_banco(pasta_base())
PASTA_BACKUPS = os.path.join(pasta_base(), "backups")


def arquivo_banco():
    """O arquivo do banco em uso: o de verdade ou o do treinamento."""
    return treino.ARQUIVO_BANCO_TREINO if treino.ativo() else ARQUIVO_BANCO


def conectar():
    """Abre uma conexão com o banco (o de verdade ou o do treino, conforme o modo)."""
    conexao = sqlite3.connect(arquivo_banco())
    conexao.execute("PRAGMA foreign_keys = ON")  # faz o SQLite respeitar o vínculo item -> atendimento
    return conexao


def criar_tabelas():
    """Cria as tabelas, caso ainda não existam. É chamada toda vez que o programa abre."""
    conexao = conectar()
    try:
        with conexao:  # o "with" salva (commit) no final, ou desfaz tudo se der erro
            conexao.execute("""
                CREATE TABLE IF NOT EXISTS atendimentos (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora             TEXT    NOT NULL,   -- formato AAAA-MM-DD HH:MM:SS
                    cliente_nome          TEXT,
                    cliente_telefone      TEXT,
                    forma_pagamento       TEXT    NOT NULL,
                    subtotal_centavos     INTEGER NOT NULL,
                    taxa_percentual       TEXT    NOT NULL,   -- ex.: '5' (texto para não perder casas decimais)
                    taxa_centavos         INTEGER NOT NULL,   -- taxa da maquininha em centavos
                    total_centavos        INTEGER NOT NULL,
                    recebido_centavos     INTEGER,            -- só para dinheiro
                    troco_centavos        INTEGER             -- só para dinheiro
                )
            """)
            conexao.execute("""
                CREATE TABLE IF NOT EXISTS itens (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    atendimento_id          INTEGER NOT NULL REFERENCES atendimentos(id),
                    servico                 TEXT    NOT NULL,
                    tipo                    TEXT    NOT NULL,   -- 'unidade' ou 'valor'
                    quantidade              INTEGER NOT NULL,
                    valor_unitario_centavos INTEGER NOT NULL,   -- preço unitário (tipo 'unidade')
                    valor_digitado_centavos INTEGER NOT NULL,   -- valor da recarga/boleto (tipo 'valor')
                    taxa_servico_centavos   INTEGER NOT NULL,   -- taxa do serviço (tipo 'valor')
                    total_centavos          INTEGER NOT NULL
                )
            """)
            # Colunas da versão 1.3 (bancos antigos ganham as colunas com 0).
            _adicionar_coluna(conexao, "atendimentos", "repasse_centavos", "INTEGER NOT NULL DEFAULT 0")
            _adicionar_coluna(conexao, "itens", "valor_terceiros_centavos", "INTEGER NOT NULL DEFAULT 0")
            # Índice para deixar rápida a busca por data (usada no relatório do dia).
            conexao.execute("CREATE INDEX IF NOT EXISTS idx_atendimentos_data ON atendimentos(data_hora)")
    finally:
        conexao.close()


def _adicionar_coluna(conexao, tabela, coluna, definicao):
    """Cria a coluna se ela ainda não existir (banco de uma versão antiga)."""
    existentes = [linha[1] for linha in conexao.execute(f"PRAGMA table_info({tabela})")]
    if coluna not in existentes:
        conexao.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def salvar_atendimento(atendimento, itens):
    """
    Salva um atendimento e seus itens. Devolve o número (id) do atendimento.

    'atendimento' é um dicionário com os dados gerais e 'itens' é a lista do carrinho.
    Os valores chegam como Decimal e são convertidos para centavos aqui.
    """
    def centavos_ou_nulo(valor):
        return None if valor is None else para_centavos(valor)

    conexao = conectar()
    try:
        with conexao:
            cursor = conexao.execute(
                """
                INSERT INTO atendimentos (
                    data_hora, cliente_nome, cliente_telefone, forma_pagamento,
                    subtotal_centavos, taxa_percentual, taxa_centavos, total_centavos,
                    recebido_centavos, troco_centavos, repasse_centavos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    atendimento["data_hora"].strftime("%Y-%m-%d %H:%M:%S"),
                    atendimento["cliente_nome"] or None,
                    atendimento["cliente_telefone"] or None,
                    atendimento["forma_pagamento"],
                    para_centavos(atendimento["subtotal"]),
                    str(atendimento["taxa_percentual"]),
                    para_centavos(atendimento["taxa_valor"]),
                    para_centavos(atendimento["total"]),
                    centavos_ou_nulo(atendimento["valor_recebido"]),
                    centavos_ou_nulo(atendimento["troco"]),
                    para_centavos(atendimento.get("repasse", 0)),
                ),
            )
            # lastrowid é o id que o SQLite acabou de gerar: o número do atendimento.
            atendimento_id = cursor.lastrowid

            for item in itens:
                conexao.execute(
                    """
                    INSERT INTO itens (
                        atendimento_id, servico, tipo, quantidade, valor_unitario_centavos,
                        valor_digitado_centavos, taxa_servico_centavos, total_centavos,
                        valor_terceiros_centavos
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        atendimento_id,
                        item["servico"],
                        item["tipo"],
                        item["quantidade"],
                        para_centavos(item["valor_unitario"]),
                        para_centavos(item["valor_digitado"]),
                        para_centavos(item["taxa_servico"]),
                        para_centavos(item["total"]),
                        para_centavos(item.get("valor_terceiros", 0)),
                    ),
                )
        return atendimento_id
    finally:
        conexao.close()


def atendimentos_do_dia(dia):
    """
    Devolve os atendimentos de um dia (dia = datetime.date), do primeiro ao último.
    Cada atendimento vem no mesmo formato usado para montar a nota (valores em Decimal,
    data_hora como datetime), com a chave "numero" e a lista "itens".
    """
    inicio = dia.strftime("%Y-%m-%d 00:00:00")
    fim = dia.strftime("%Y-%m-%d 23:59:59")

    def reais_ou_nulo(centavos):
        return None if centavos is None else de_centavos(centavos)

    conexao = conectar()
    conexao.row_factory = sqlite3.Row  # permite ler as colunas pelo nome: linha["total_centavos"]
    try:
        atendimentos = []
        linhas = conexao.execute(
            "SELECT * FROM atendimentos WHERE data_hora BETWEEN ? AND ? ORDER BY data_hora, id",
            (inicio, fim),
        ).fetchall()
        for linha in linhas:
            itens = conexao.execute(
                "SELECT * FROM itens WHERE atendimento_id = ? ORDER BY id", (linha["id"],)
            ).fetchall()
            atendimentos.append({
                "numero": linha["id"],
                "data_hora": datetime.strptime(linha["data_hora"], "%Y-%m-%d %H:%M:%S"),
                "cliente_nome": linha["cliente_nome"] or "",
                "cliente_telefone": linha["cliente_telefone"] or "",
                "forma_pagamento": linha["forma_pagamento"],
                "subtotal": de_centavos(linha["subtotal_centavos"]),
                "taxa_percentual": Decimal(linha["taxa_percentual"]),
                "taxa_valor": de_centavos(linha["taxa_centavos"]),
                "total": de_centavos(linha["total_centavos"]),
                "valor_recebido": reais_ou_nulo(linha["recebido_centavos"]),
                "troco": reais_ou_nulo(linha["troco_centavos"]),
                "repasse": de_centavos(linha["repasse_centavos"]),
                "itens": [{
                    "servico": item["servico"],
                    "tipo": item["tipo"],
                    "quantidade": item["quantidade"],
                    "valor_unitario": de_centavos(item["valor_unitario_centavos"]),
                    "valor_digitado": de_centavos(item["valor_digitado_centavos"]),
                    "taxa_servico": de_centavos(item["taxa_servico_centavos"]),
                    "total": de_centavos(item["total_centavos"]),
                    "valor_terceiros": de_centavos(item["valor_terceiros_centavos"]),
                } for item in itens],
            })
        return atendimentos
    finally:
        conexao.close()


# ----------------------------------------------------------------------
# Limpar dados e treinamento
# ----------------------------------------------------------------------

def _filtro_periodo(inicio, fim):
    """Parte do SQL que escolhe os atendimentos de um período (datas incluídas). Sem datas = todos."""
    if inicio is None or fim is None:
        return "", ()
    return " WHERE data_hora BETWEEN ? AND ?", (inicio.strftime("%Y-%m-%d 00:00:00"),
                                                 fim.strftime("%Y-%m-%d 23:59:59"))


def contar_atendimentos(inicio=None, fim=None):
    """Quantos atendimentos existem no período (inicio e fim = datetime.date; sem datas = todos)."""
    filtro, valores = _filtro_periodo(inicio, fim)
    conexao = conectar()
    try:
        return conexao.execute("SELECT COUNT(*) FROM atendimentos" + filtro, valores).fetchone()[0]
    finally:
        conexao.close()


def fazer_backup():
    """
    Copia o banco em uso para backups/, com data e hora no nome
    (ex.: backups/easyserv_2026-11-01_18-30-05.db). Devolve o caminho da cópia.
    Usa a cópia do próprio SQLite, que é segura mesmo com o banco aberto.
    """
    os.makedirs(PASTA_BACKUPS, exist_ok=True)
    nome = os.path.splitext(os.path.basename(arquivo_banco()))[0]
    destino = os.path.join(PASTA_BACKUPS, f"{nome}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db")
    numero = 2
    while os.path.exists(destino):  # (dois backups no mesmo segundo)
        destino = destino.removesuffix(".db").rsplit("(", 1)[0] + f"({numero}).db"
        numero += 1
    origem = conectar()
    copia = sqlite3.connect(destino)
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    return destino


def apagar_atendimentos(inicio=None, fim=None):
    """
    Apaga os atendimentos do período (e os itens deles). Sem datas = apaga todos.
    Devolve quantos foram apagados. A numeração continua de onde parou (o próximo
    atendimento não repete um número antigo, então as notas antigas nunca se confundem).
    """
    filtro, valores = _filtro_periodo(inicio, fim)
    conexao = conectar()
    try:
        with conexao:
            conexao.execute("DELETE FROM itens WHERE atendimento_id IN (SELECT id FROM atendimentos"
                            + filtro + ")", valores)
            return conexao.execute("DELETE FROM atendimentos" + filtro, valores).rowcount
    finally:
        conexao.close()


def zerar_treino():
    """
    Apaga TODO o treino: o treino.db (recomeça do atendimento nº 1), as notas de
    notas_treino/ e os relatórios de relatorios_treino/. O banco de verdade não é tocado.
    """
    if os.path.exists(treino.ARQUIVO_BANCO_TREINO):
        os.remove(treino.ARQUIVO_BANCO_TREINO)
    for pasta in (treino.PASTA_NOTAS_TREINO, treino.PASTA_RELATORIOS_TREINO):
        shutil.rmtree(pasta, ignore_errors=True)
    if treino.ativo():
        criar_tabelas()  # o programa continua no treino: já deixa o banco novo pronto


# ----------------------------------------------------------------------
# Privacidade: dados do cliente
# ----------------------------------------------------------------------

def apagar_dados_clientes(dias=None, arquivo=None):
    """
    Apaga SÓ o nome e o telefone dos clientes, mantendo o atendimento, os itens e
    os valores. dias = apaga dos atendimentos com mais de tantos dias (None = de todos).
    arquivo = qual banco (None = o que está em uso). Devolve quantos atendimentos mudaram.
    """
    arquivo = arquivo or arquivo_banco()
    if not os.path.exists(arquivo):
        return 0
    filtro, valores = "", ()
    if dias is not None:
        limite = datetime.now() - timedelta(days=dias)
        filtro, valores = " AND data_hora < ?", (limite.strftime("%Y-%m-%d %H:%M:%S"),)
    conexao = sqlite3.connect(arquivo)
    try:
        with conexao:
            return conexao.execute(
                "UPDATE atendimentos SET cliente_nome = NULL, cliente_telefone = NULL"
                " WHERE (cliente_nome IS NOT NULL OR cliente_telefone IS NOT NULL)" + filtro, valores
            ).rowcount
    finally:
        conexao.close()
