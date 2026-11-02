"""
teste_exe.py - Testa o PROGRAMA GERADO (EasyServ.exe), e não o código.

    python testes\\teste_exe.py                          (o dist\\EasyServ\\EasyServ.exe)
    python testes\\teste_exe.py "C:\\pasta\\EasyServ.exe"  (ex.: o programa instalado)

Por que existe: até a 1.4.1 todos os testes rodavam pelo código (python main.py). Lá as
bibliotecas de impressão sempre existem, mas no .exe do PyInstaller elas podem faltar:
foi assim que o "Imprimir teste" do programa instalado quebrou.

O que faz: roda "EasyServ.exe --autoteste-impressao" (sem janela e SEM imprimir nada),
com os dados numa pasta temporária (EASYSERV_DADOS), e confere o resultado: pywin32
(win32print, win32ui, win32con, pywintypes), o mfc140u.dll que o win32ui usa, o Pillow
e a montagem de uma nota ESC/POS. Também confere se os arquivos estão na pasta do programa.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_PADRAO = os.path.join(RAIZ, "dist", "EasyServ", "EasyServ.exe")
# Arquivos que têm que estar dentro da pasta _internal do programa (* = qualquer versão do Python).
ARQUIVOS = [os.path.join("win32", "win32print.pyd"), os.path.join("pythonwin", "win32ui.pyd"),
            os.path.join("pythonwin", "mfc140u.dll"), os.path.join("pywin32_system32", "pywintypes3*.dll"),
            os.path.join("PIL", "_imaging.*.pyd")]


def testar_exe(exe):
    """Devolve (deu certo?, [linhas do relatório])."""
    linhas = [f"Programa: {exe}"]
    if not os.path.exists(exe):
        return False, linhas + ["FALHA o EasyServ.exe não existe"]
    certo = True
    interna = os.path.join(os.path.dirname(exe), "_internal")
    for arquivo in ARQUIVOS:
        existe = bool(glob.glob(os.path.join(interna, arquivo)))
        certo &= existe
        linhas.append(f"{'OK   ' if existe else 'FALHA'} arquivo _internal\\{arquivo}")
    pasta = tempfile.mkdtemp(prefix="easyserv_teste_exe_")
    try:
        relatorio = os.path.join(pasta, "autoteste.txt")
        ambiente = dict(os.environ, EASYSERV_DADOS=os.path.join(pasta, "dados"))
        try:
            codigo = subprocess.run([exe, "--autoteste-impressao", relatorio], env=ambiente, timeout=120).returncode
        except subprocess.TimeoutExpired:
            return False, linhas + ["FALHA o autoteste não terminou em 2 minutos"]
        if not os.path.exists(relatorio):
            return False, linhas + [f"FALHA o .exe não gravou o relatório (código {codigo})"]
        texto = open(relatorio, encoding="utf-8").read().splitlines()
        linhas += texto
        certo &= codigo == 0 and "RESULTADO: OK" in texto
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    return certo, linhas


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    exe = sys.argv[1] if len(sys.argv) > 1 else EXE_PADRAO
    certo, linhas = testar_exe(exe)
    print("\n".join(linhas))
    print("\nTESTE DO .EXE:", "OK" if certo else "FALHOU")
    return 0 if certo else 1


if __name__ == "__main__":
    sys.exit(main())
