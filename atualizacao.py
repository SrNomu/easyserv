"""
atualizacao.py - Atualização automática pelo GitHub Releases.

Como funciona:
  1. consultar(): pergunta ao GitHub qual é a última versão publicada no repositório
     público (versao.REPOSITORIO_GITHUB). É só uma leitura pública: sem senha, sem token.
     Sem internet, repositório vazio ou qualquer erro -> None (o programa segue normal).
  2. Se a versão de lá for maior, o programa mostra as notas e PERGUNTA (tela_atualizacao.py).
  3. baixar() salva o instalador em %APPDATA%\\EasyServ\\atualizacoes.
  4. sha256_arquivo() confere o arquivo baixado com o SHA-256 publicado junto
     (arquivo "EasyServ_Setup_X.exe.sha256" na mesma versão, ou o "digest" do GitHub).
     Se não bater, o arquivo é apagado e nada é instalado.
  5. fazer_backups(): cópia do banco (backups/) e da pasta do programa atual (zip).
  6. iniciar_atualizador(): copia o EasyServAtualizador.exe para fora da pasta do
     programa, abre ele e o EasyServ fecha. O atualizador espera o EasyServ fechar,
     confere o SHA-256 de novo, roda o instalador em modo silencioso e abre o
     EasyServ atualizado. O instalador só troca os arquivos do programa: banco,
     configurações, layouts, temas e notas ficam em %APPDATA%\\EasyServ e não são tocados.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime

import versao
from config import pasta_base, pasta_programa

URL_API = "https://api.github.com/repos/{repositorio}/releases/latest"
PADRAO_INSTALADOR = re.compile(r"^EasyServ_Setup_[\w.\-]+\.exe$", re.IGNORECASE)
NOME_ATUALIZADOR = "EasyServAtualizador.exe"
BACKUPS_DO_PROGRAMA = 2  # quantos zips da versão anterior guardar

# Trocado nos testes por uma função falsa (nenhum teste acessa a internet).
abrir_url = urllib.request.urlopen


@dataclass
class Lancamento:
    versao: str            # ex.: "1.3"
    titulo: str
    notas: str             # texto da versão no GitHub (Markdown)
    url_instalador: str
    nome_instalador: str
    tamanho: int
    sha256: str = ""       # se o GitHub já informar ("digest")
    url_sha256: str = ""   # arquivo .sha256 publicado junto
    pagina: str = ""       # página da versão no GitHub


def pasta_atualizacoes():
    pasta = os.path.join(pasta_base(), "atualizacoes")
    os.makedirs(pasta, exist_ok=True)
    return pasta


def _pedido(url):
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{versao.NOME_PROGRAMA}/{versao.VERSAO}",  # o GitHub exige um User-Agent
    })


def _ler_json(url, tempo_limite):
    with abrir_url(_pedido(url), timeout=tempo_limite) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def eh_mais_nova(remota, atual=versao.VERSAO):
    return versao.numero(remota) > versao.numero(atual)


def ler_lancamento(dados):
    """Transforma a resposta do GitHub num Lancamento (ou None se não tiver instalador)."""
    arquivos = {a.get("name", ""): a for a in dados.get("assets", []) if isinstance(a, dict)}
    instalador = next((a for nome, a in arquivos.items() if PADRAO_INSTALADOR.match(nome)), None)
    if instalador is None:
        return None
    digest = str(instalador.get("digest") or "")
    arquivo_sha = arquivos.get(instalador["name"] + ".sha256") or arquivos.get("SHA256SUMS.txt")
    return Lancamento(
        versao=str(dados.get("tag_name", "")).lstrip("vV"),
        titulo=str(dados.get("name") or dados.get("tag_name") or ""),
        notas=str(dados.get("body") or ""),
        url_instalador=instalador["browser_download_url"],
        nome_instalador=instalador["name"],
        tamanho=int(instalador.get("size") or 0),
        sha256=digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else "",
        url_sha256=arquivo_sha["browser_download_url"] if arquivo_sha else "",
        pagina=str(dados.get("html_url") or ""),
    )


# Resultado de verificar(): o que mostrar para a pessoa.
NOVA = "nova"            # tem versão mais nova (vem junto o lançamento)
ATUAL = "atual"          # consultou e esta já é a mais nova
SEM_RESPOSTA = "erro"    # não deu para consultar (sem internet, GitHub fora do ar, resposta estranha)


def verificar(repositorio=None, tempo_limite=5):
    """
    (situacao, lancamento): situacao é NOVA, ATUAL ou SEM_RESPOSTA; lancamento só vem com NOVA.
    Nunca dá erro. Sem repositório configurado conta como SEM_RESPOSTA.
    """
    repositorio = versao.REPOSITORIO_GITHUB if repositorio is None else repositorio
    if not repositorio or versao.numero(versao.VERSAO) == ():
        return SEM_RESPOSTA, None
    try:
        dados = _ler_json(URL_API.format(repositorio=repositorio), tempo_limite)
        if not isinstance(dados, dict):
            return SEM_RESPOSTA, None
        if dados.get("draft") or dados.get("prerelease"):
            return ATUAL, None  # (o último publicado ainda é rascunho: para quem usa, nada novo)
        lancamento = ler_lancamento(dados)
    except Exception:
        return SEM_RESPOSTA, None
    if lancamento is None:
        return SEM_RESPOSTA, None
    if not eh_mais_nova(lancamento.versao):
        return ATUAL, None
    return NOVA, lancamento


def consultar(repositorio=None, tempo_limite=5):
    """
    A última versão publicada, se for MAIS NOVA que esta; senão None.
    Nunca dá erro: sem internet, sem repositório ou resposta estranha -> None.
    (Para saber se foi "já é a mais nova" ou "não deu para consultar", use verificar().)
    """
    return verificar(repositorio, tempo_limite)[1]


def sha256_publicado(lancamento, tempo_limite=15):
    """O SHA-256 que o autor publicou para o instalador (64 letras/números) ou ''."""
    if lancamento.url_sha256:
        try:
            with abrir_url(_pedido(lancamento.url_sha256), timeout=tempo_limite) as resposta:
                texto = resposta.read().decode("utf-8", "replace")
            for linha in texto.splitlines():
                achado = re.search(r"\b([0-9a-fA-F]{64})\b", linha)
                # (SHA256SUMS.txt tem uma linha por arquivo: pega a do instalador)
                if achado and (lancamento.nome_instalador in linha or len(texto.splitlines()) == 1):
                    return achado.group(1).lower()
        except Exception:
            pass
    return lancamento.sha256


def sha256_arquivo(caminho):
    soma = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(1024 * 1024), b""):
            soma.update(pedaco)
    return soma.hexdigest()


class Cancelado(Exception):
    pass


def baixar(lancamento, progresso=None, cancelado=lambda: False, tempo_limite=30):
    """
    Baixa o instalador para a pasta atualizacoes/. progresso(baixados, total) é chamado
    durante o download. Devolve o caminho do arquivo. Lança Cancelado ou OSError.
    """
    destino = os.path.join(pasta_atualizacoes(), lancamento.nome_instalador)
    parcial = destino + ".parcial"
    baixados = 0
    with abrir_url(_pedido(lancamento.url_instalador), timeout=tempo_limite) as resposta:
        total = int(resposta.headers.get("Content-Length") or lancamento.tamanho or 0)
        with open(parcial, "wb") as arquivo:
            while True:
                if cancelado():
                    raise Cancelado()
                pedaco = resposta.read(256 * 1024)
                if not pedaco:
                    break
                arquivo.write(pedaco)
                baixados += len(pedaco)
                if progresso:
                    progresso(baixados, total)
    if total and baixados != total:
        os.remove(parcial)
        raise OSError(f"O download veio incompleto ({baixados} de {total} bytes).")
    os.replace(parcial, destino)
    return destino


def conferir(caminho, sha_esperado):
    """True se o SHA-256 do arquivo bate. Se não bater, apaga o arquivo baixado."""
    if sha_esperado and sha256_arquivo(caminho) == sha_esperado.lower():
        return True
    try:
        os.remove(caminho)
    except OSError:
        pass
    return False


def fazer_backups():
    """
    Antes de atualizar: backup do banco e da versão atual do programa (zip).
    Devolve a lista de arquivos criados. Os dados em si não são alterados.
    """
    import banco
    import treino

    criados = []
    # O backup é do banco do caixa, mesmo se o modo treinamento estiver ligado.
    estava_no_treino = treino.ativo()
    if estava_no_treino:
        treino.ligar(False)
    try:
        if os.path.exists(banco.ARQUIVO_BANCO):
            criados.append(banco.fazer_backup())
    finally:
        if estava_no_treino:
            treino.ligar(True)
    if getattr(sys, "frozen", False):  # (rodando pelo Python não existe "versão instalada")
        pasta = os.path.join(pasta_base(), "backups", "programa")
        os.makedirs(pasta, exist_ok=True)
        nome = os.path.join(pasta, f"EasyServ_{versao.VERSAO}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
        criados.append(shutil.make_archive(nome, "zip", pasta_programa()))
        antigos = sorted((os.path.join(pasta, n) for n in os.listdir(pasta) if n.endswith(".zip")),
                         key=os.path.getmtime)
        for velho in antigos[:-BACKUPS_DO_PROGRAMA]:
            os.remove(velho)
    return criados


def iniciar_atualizador(instalador, sha):
    """
    Abre o atualizador (separado do programa) e devolve True. Depois disso o EasyServ
    precisa fechar: o atualizador espera ele sair para rodar o instalador.
    """
    original = os.path.join(pasta_programa(), NOME_ATUALIZADOR)
    if not os.path.exists(original):
        raise OSError(f"Não achei o {NOME_ATUALIZADOR} na pasta do programa.")
    # Roda uma cópia de fora da pasta do programa (o instalador vai trocar o original).
    copia = os.path.join(pasta_atualizacoes(), NOME_ATUALIZADOR)
    shutil.copy2(original, copia)
    argumentos = [copia, "--instalador", instalador, "--sha256", sha, "--pid", str(os.getpid()),
                  "--programa", sys.executable, "--log", os.path.join(pasta_atualizacoes(), "atualizacao.log")]
    sem_janela = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(argumentos, creationflags=sem_janela, close_fds=True)
    return True
