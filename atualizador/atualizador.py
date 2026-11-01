"""
atualizador.py - O atualizador separado do EasyServ (vira EasyServAtualizador.exe).

Por que separado: um programa não consegue trocar os próprios arquivos enquanto
está aberto. Então o EasyServ abre este atualizador e fecha. O atualizador:
  1. espera o EasyServ fechar (até 2 minutos);
  2. confere o SHA-256 do instalador baixado DE NOVO (se não bater, não instala);
  3. roda o instalador em modo silencioso (/SILENT): ele só troca os arquivos do
     programa; os dados em %APPDATA%\\EasyServ não são tocados;
  4. abre o EasyServ atualizado.
Tudo fica anotado no arquivo de log (atualizacoes\\atualizacao.log).

Uso (o EasyServ monta essa linha sozinho):
  EasyServAtualizador.exe --instalador X.exe --sha256 ABC... --pid 1234 --programa EasyServ.exe --log arq.log

Não usa Qt (fica pequeno) nem internet.
"""

import argparse
import ctypes
import hashlib
import os
import subprocess
import sys
from datetime import datetime

SYNCHRONIZE = 0x00100000
ESPERA_MAXIMA_MS = 120_000
MB_OK, MB_ICONERROR, MB_ICONINFO = 0x0, 0x10, 0x40


def avisar(texto, erro=True):
    ctypes.windll.user32.MessageBoxW(None, texto, "Atualização do EasyServ",
                                     MB_OK | (MB_ICONERROR if erro else MB_ICONINFO))


def anotar(log, texto):
    linha = f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] {texto}"
    try:
        with open(log, "a", encoding="utf-8") as arquivo:
            arquivo.write(linha + "\n")
    except OSError:
        pass


def esperar_fechar(pid):
    """Espera o processo do EasyServ terminar. True se terminou (ou já não existia)."""
    alca = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not alca:
        return True
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(alca, ESPERA_MAXIMA_MS) == 0
    finally:
        ctypes.windll.kernel32.CloseHandle(alca)


def sha256_arquivo(caminho):
    soma = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for pedaco in iter(lambda: arquivo.read(1024 * 1024), b""):
            soma.update(pedaco)
    return soma.hexdigest()


def main(argv=None, executar=subprocess.run, abrir=subprocess.Popen):
    partes = argparse.ArgumentParser()
    for nome in ("--instalador", "--sha256", "--programa", "--log"):
        partes.add_argument(nome, required=True)
    partes.add_argument("--pid", type=int, required=True)
    args = partes.parse_args(argv)
    log = args.log
    anotar(log, f"Atualizador iniciado. Instalador: {args.instalador}")

    if not esperar_fechar(args.pid):
        anotar(log, "O EasyServ não fechou a tempo. Atualização cancelada.")
        avisar("O EasyServ não fechou a tempo, então a atualização foi cancelada.\n"
               "Feche o programa e tente de novo.")
        return 2

    if not os.path.exists(args.instalador) or sha256_arquivo(args.instalador) != args.sha256.lower():
        anotar(log, "SHA-256 não confere. Instalador apagado, nada foi instalado.")
        try:
            os.remove(args.instalador)
        except OSError:
            pass
        avisar("O arquivo da atualização não passou na conferência de segurança (SHA-256).\n"
               "Nada foi instalado. O EasyServ continua na versão de antes.")
        abrir([args.programa])
        return 3

    log_instalador = os.path.join(os.path.dirname(log), "instalador.log")
    comando = [args.instalador, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
               f"/LOG={log_instalador}"]
    anotar(log, "Rodando o instalador: " + " ".join(comando))
    resultado = executar(comando)
    anotar(log, f"Instalador terminou com código {resultado.returncode}.")
    if resultado.returncode != 0:
        avisar("A instalação da atualização não terminou.\nO EasyServ continua na versão de antes.\n"
               f"Detalhes em: {log_instalador}")
    abrir([args.programa])  # abre o EasyServ (atualizado, se deu certo)
    anotar(log, "EasyServ aberto. Fim.")
    return 0 if resultado.returncode == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
