"""
backup.py - Backup completo dos dados (menu Arquivo › Backup).

Um backup é um arquivo .zip com data e hora no nome, por exemplo
    EasyServ_backup_2026-11-01_18-30-05.zip
com dentro:
    o banco (todos os atendimentos), config.json (serviços, preços e dados da loja),
    preferencias.json (aparência e atalhos), layout_notas.json (as notinhas),
    a pasta imagens/ (a logo) e backup_easyserv.json (data, versão e quantos
    atendimentos tem, para mostrar antes de restaurar).

A pasta dos backups é a escolhida em Arquivo › Backup › Escolher pasta (ex.: um
pendrive ou uma pasta do Google Drive); se não tiver escolhido, é backups/ na pasta
de dados. O banco do treinamento nunca entra: só os dados de verdade.

Restaurar: antes de trocar qualquer coisa, faz um backup do estado atual (nada se perde).
"""

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime

import banco
import config
import layout_notas
import versao

PREFIXO = "EasyServ_backup_"
ARQUIVO_INFO = "backup_easyserv.json"
ARQUIVOS_JSON = ("config.json", "preferencias.json", "layout_notas.json")
PASTA_IMAGENS = "imagens"


class ErroBackup(Exception):
    """Problema ao fazer ou ler um backup (a mensagem já vem pronta para mostrar)."""


def pasta_padrao():
    return banco.PASTA_BACKUPS


def pasta_escolhida(cfg=None):
    """A pasta configurada (vazio = a padrão, backups/ na pasta de dados)."""
    try:
        cfg = cfg or config.carregar_config()
        return cfg.backup.get("pasta", "") or pasta_padrao()
    except config.ErroConfig:
        return pasta_padrao()


def _destino_sem_repetir(pasta, nome):
    """pasta/nome.zip; se já existir (dois backups no mesmo segundo), nome(2).zip..."""
    destino = os.path.join(pasta, nome + ".zip")
    numero = 2
    while os.path.exists(destino):
        destino = os.path.join(pasta, f"{nome}({numero}).zip")
        numero += 1
    return destino


def _contar(arquivo_db):
    conexao = sqlite3.connect(arquivo_db)
    try:
        return conexao.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
    except sqlite3.Error:
        return 0
    finally:
        conexao.close()


def fazer_backup(pasta=None, sufixo=""):
    """
    Cria o .zip na pasta (None = a escolhida) e devolve o caminho dele.
    sufixo vai no fim do nome (ex.: "_antes_de_restaurar").
    """
    pasta = pasta or pasta_escolhida()
    try:
        os.makedirs(pasta, exist_ok=True)
    except OSError as erro:
        raise ErroBackup(f"Não foi possível usar a pasta do backup:\n{pasta}\n\n{erro}\n\n"
                         "Se for um pendrive, confira se ele está conectado.") from erro
    agora = datetime.now()
    destino = _destino_sem_repetir(pasta, PREFIXO + agora.strftime("%Y-%m-%d_%H-%M-%S") + sufixo)
    base = config.pasta_base()
    with tempfile.TemporaryDirectory() as temporaria:
        # O banco é copiado pelo próprio SQLite: a cópia sai certa mesmo com o banco aberto.
        nome_banco = os.path.basename(banco.ARQUIVO_BANCO)
        copia_banco = os.path.join(temporaria, nome_banco)
        atendimentos = 0
        if os.path.exists(banco.ARQUIVO_BANCO):
            origem, copia = sqlite3.connect(banco.ARQUIVO_BANCO), sqlite3.connect(copia_banco)
            try:
                origem.backup(copia)
            finally:
                copia.close()
                origem.close()
            atendimentos = _contar(copia_banco)
        info = {"programa": versao.NOME_PROGRAMA, "versao": versao.VERSAO,
                "data_hora": agora.strftime("%Y-%m-%d %H:%M:%S"), "atendimentos": atendimentos,
                "banco": nome_banco}
        try:
            with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
                arquivo_zip.writestr(ARQUIVO_INFO, json.dumps(info, ensure_ascii=False, indent=2))
                if os.path.exists(copia_banco):
                    arquivo_zip.write(copia_banco, nome_banco)
                for nome in ARQUIVOS_JSON:
                    caminho = os.path.join(base, nome)
                    if os.path.exists(caminho):
                        arquivo_zip.write(caminho, nome)
                imagens = os.path.join(base, PASTA_IMAGENS)
                if os.path.isdir(imagens):
                    for nome in sorted(os.listdir(imagens)):
                        caminho = os.path.join(imagens, nome)
                        if os.path.isfile(caminho):
                            arquivo_zip.write(caminho, f"{PASTA_IMAGENS}/{nome}")
        except OSError as erro:
            try:
                os.remove(destino)  # não deixa um .zip pela metade
            except OSError:
                pass
            raise ErroBackup(f"Não foi possível gravar o backup em:\n{destino}\n\n{erro}") from erro
    return destino


def ler_backup(caminho):
    """
    Confere o .zip e devolve {"data_hora": datetime, "atendimentos": int, "versao": str,
    "banco": nome do .db dentro do zip}. ErroBackup se não for um backup do EasyServ.
    """
    try:
        with zipfile.ZipFile(caminho) as arquivo_zip:
            nomes = arquivo_zip.namelist()
            bancos = [nome for nome in nomes if nome in (banco.NOME_BANCO, banco.NOME_BANCO_ANTIGO)]
            if not bancos and "config.json" not in nomes:
                raise ErroBackup("Este arquivo não é um backup do EasyServ.")
            info = {}
            if ARQUIVO_INFO in nomes:
                try:
                    info = json.loads(arquivo_zip.read(ARQUIVO_INFO).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    info = {}
            if not isinstance(info, dict):
                info = {}
            atendimentos = info.get("atendimentos")
            if not isinstance(atendimentos, int):
                atendimentos = 0
                if bancos:  # sem a ficha: conta direto no banco do backup
                    with tempfile.TemporaryDirectory() as temporaria:
                        atendimentos = _contar(arquivo_zip.extract(bancos[0], temporaria))
    except (zipfile.BadZipFile, OSError) as erro:
        raise ErroBackup(f"Não foi possível abrir o backup:\n{erro}") from erro
    try:
        data_hora = datetime.strptime(info.get("data_hora", ""), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        data_hora = datetime.fromtimestamp(os.path.getmtime(caminho))
    return {"data_hora": data_hora, "atendimentos": atendimentos, "versao": str(info.get("versao", "")),
            "banco": bancos[0] if bancos else ""}


def restaurar_backup(caminho):
    """
    Troca os dados atuais pelos do backup. ANTES faz um backup do estado atual e
    devolve o caminho dele. Só arquivos conhecidos saem do .zip (nada fora da pasta de dados).
    Depois disso o programa precisa abrir de novo (a janela fecha sozinha).
    """
    info = ler_backup(caminho)  # (confere antes de mexer em qualquer coisa)
    try:
        seguranca = fazer_backup(sufixo="_antes_de_restaurar")
    except ErroBackup:
        seguranca = fazer_backup(pasta_padrao(), sufixo="_antes_de_restaurar")  # pendrive saiu? usa a padrão
    base = config.pasta_base()
    try:
        with zipfile.ZipFile(caminho) as arquivo_zip, tempfile.TemporaryDirectory() as temporaria:
            if info["banco"]:
                # O banco do backup vai para o arquivo de banco em uso (mesmo que o nome seja o antigo).
                extraido = arquivo_zip.extract(info["banco"], temporaria)
                origem, destino = sqlite3.connect(extraido), sqlite3.connect(banco.ARQUIVO_BANCO)
                try:
                    origem.backup(destino)
                finally:
                    destino.close()
                    origem.close()
            nomes = arquivo_zip.namelist()
            for nome in ARQUIVOS_JSON:
                if nome in nomes:
                    with arquivo_zip.open(nome) as entrada, open(os.path.join(base, nome), "wb") as saida:
                        shutil.copyfileobj(entrada, saida)
            for nome in nomes:
                partes = nome.split("/")
                # só imagens/arquivo (sem subpastas, sem "..")
                if len(partes) == 2 and partes[0] == PASTA_IMAGENS and partes[1] not in ("", ".", ".."):
                    os.makedirs(layout_notas.PASTA_IMAGENS, exist_ok=True)
                    with arquivo_zip.open(nome) as entrada, \
                            open(os.path.join(layout_notas.PASTA_IMAGENS, partes[1]), "wb") as saida:
                        shutil.copyfileobj(entrada, saida)
    except (zipfile.BadZipFile, OSError, sqlite3.Error) as erro:
        raise ErroBackup(f"Não foi possível restaurar o backup:\n{erro}\n\n"
                         f"Os dados de antes estão guardados em:\n{seguranca}") from erro
    banco.criar_tabelas()  # (backup de uma versão antiga: ganha as colunas novas)
    return seguranca


def descrever(info):
    """Texto curto para mostrar ao escolher um backup."""
    texto = (f"Backup de {info['data_hora'].strftime('%d/%m/%Y às %H:%M')}\n"
             f"{info['atendimentos']} atendimento(s)")
    if info["versao"]:
        texto += f"  ·  feito na versão {info['versao']}"
    return texto
