"""
integridade.py - Confere, na tela de abertura, se o programa e os dados estão inteiros.

  verificar_programa(): os arquivos do programa instalado batem com o manifesto.json
      (lista com o tamanho de cada arquivo, gerada junto com o instalador). Conferir o
      tamanho é rápido e pega arquivo apagado ou cortado pela metade. Rodando pelo
      Python, confere só os recursos (logo, ícone, licença).
  verificar_dados(): os .json abrem e os bancos SQLite passam no "quick_check".

As duas devolvem uma lista de problemas (textos); lista vazia = tudo certo.
Nenhuma das duas muda nada: só olham.
"""

import json
import os
import sqlite3
import sys

from config import pasta_base, pasta_programa, recurso

MANIFESTO = "manifesto.json"
RECURSOS = ("easyserv.ico", "easyserv.png", "LICENCA.txt")
ARQUIVOS_JSON = ("config.json", "preferencias.json", "layout_notas.json")
BANCOS = ("easyserv.db", "maisbella.db", "treino.db")  # (maisbella.db: nome antigo)


def verificar_programa(pasta=None):
    problemas = [f"Falta o arquivo do programa: {nome}" for nome in RECURSOS if not os.path.exists(recurso(nome))]
    pasta = pasta or pasta_programa()
    caminho = os.path.join(pasta, MANIFESTO)
    if not getattr(sys, "frozen", False) and not os.path.exists(caminho):
        return problemas  # desenvolvimento: não tem manifesto
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            arquivos = json.load(arquivo)["arquivos"]
    except (OSError, ValueError, KeyError, TypeError):
        return problemas + ["A lista de arquivos do programa (manifesto.json) está faltando ou estragada."]
    faltando, alterados = [], []
    for relativo, tamanho in arquivos.items():
        completo = os.path.join(pasta, relativo)
        if not os.path.isfile(completo):
            faltando.append(relativo)
        elif os.path.getsize(completo) != tamanho:
            alterados.append(relativo)
    if faltando:
        problemas.append(f"{len(faltando)} arquivo(s) do programa faltando, ex.: {', '.join(faltando[:3])}")
    if alterados:
        problemas.append(f"{len(alterados)} arquivo(s) do programa corrompido(s), ex.: {', '.join(alterados[:3])}")
    return problemas


def verificar_banco(caminho):
    """None se o banco está bom (ou ainda não existe); senão, o texto do problema."""
    if not os.path.exists(caminho):
        return None
    nome = os.path.basename(caminho)
    try:
        with open(caminho, "rb") as arquivo:
            cabecalho = arquivo.read(16)
        if cabecalho and cabecalho != b"SQLite format 3\x00":
            return f"O banco de dados {nome} está corrompido (não é um arquivo de banco válido)."
        conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)  # só leitura: não mexe em nada
        try:
            resultado = conexao.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            conexao.close()
    except (OSError, sqlite3.Error) as erro:
        return f"O banco de dados {nome} não pôde ser aberto: {erro}"
    if resultado != "ok":
        return f"O banco de dados {nome} está corrompido: {resultado}"
    return None


def verificar_dados(pasta=None):
    pasta = pasta or pasta_base()
    problemas = []
    for nome in ARQUIVOS_JSON:
        caminho = os.path.join(pasta, nome)
        if not os.path.exists(caminho):
            continue  # o programa cria com os valores de fábrica
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                json.load(arquivo)
        except (OSError, ValueError) as erro:
            problemas.append(f"O arquivo {nome} está corrompido ({erro}).")
    for nome in BANCOS:
        problema = verificar_banco(os.path.join(pasta, nome))
        if problema:
            problemas.append(problema)
    return problemas


def gerar_manifesto(pasta, versao):
    """Usado pelo gerador do instalador: anota o tamanho de cada arquivo do programa."""
    arquivos = {}
    for raiz, _pastas, nomes in os.walk(pasta):
        for nome in nomes:
            completo = os.path.join(raiz, nome)
            relativo = os.path.relpath(completo, pasta).replace("\\", "/")
            if relativo != MANIFESTO:
                arquivos[relativo] = os.path.getsize(completo)
    with open(os.path.join(pasta, MANIFESTO), "w", encoding="utf-8") as arquivo:
        json.dump({"versao": versao, "arquivos": arquivos}, arquivo, ensure_ascii=False, indent=0)
    return len(arquivos)
