"""
rodar_testes.py - Roda todas as baterias de testes automáticos do EasyServ.

    python testes\\rodar_testes.py            (todas)
    python testes\\rodar_testes.py relatorio  (só as que têm "relatorio" no nome)

Cada bateria roda numa CÓPIA do programa, numa pasta temporária, com a variável
EASYSERV_DADOS apontando para essa cópia. Assim os testes nunca mexem nos dados
de verdade (banco, configurações, notas) nem em %APPDATA%\\EasyServ.
Os testes também nunca imprimem de verdade, nunca acessam a internet e nunca
abrem o teclado do Windows: essas funções são trocadas por funções falsas.

Cada verificação imprime "OK" ou "FALHA"; no fim aparece o total.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile

PASTA_TESTES = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(PASTA_TESTES)
ORDEM = ["teste_interface", "teste_regras_de_negocio", "teste_relatorio", "teste_funcoes_gerais",
         "teste_v1_0", "teste_v1_1", "teste_v1_2", "teste_v1_3", "teste_v1_3_1", "teste_v1_4", "teste_v1_4_2"]


def copiar_programa(destino):
    """Copia só o programa (código, textos e recursos), sem nenhum dado."""
    os.makedirs(destino)
    for caminho in glob.glob(os.path.join(RAIZ, "*.py")) + glob.glob(os.path.join(RAIZ, "*.txt")):
        shutil.copy(caminho, destino)
    for pasta in ("recursos", "atualizador"):
        shutil.copytree(os.path.join(RAIZ, pasta), os.path.join(destino, pasta))


def rodar(nome, base):
    copia, saida = os.path.join(base, nome), os.path.join(base, nome + "_saida")
    copiar_programa(copia)
    os.makedirs(saida)
    ambiente = dict(os.environ, EASYSERV_DADOS=copia, PYTHONIOENCODING="utf-8")
    resultado = subprocess.run([sys.executable, os.path.join(PASTA_TESTES, nome + ".py"), copia, saida],
                               env=ambiente, capture_output=True, text=True, encoding="utf-8", timeout=600)
    linhas = (resultado.stdout + resultado.stderr).splitlines()
    oks = sum(l.startswith("OK") for l in linhas)
    falhas = [l for l in linhas if l.startswith("FALHA ")]  # ("FALHAS: 0" é o resumo do teste)
    if resultado.returncode != 0:  # o teste parou no meio (erro no Python)
        falhas.append("ERRO: " + " | ".join(linhas[-6:]))
    return oks, falhas


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    nomes = [n for n in ORDEM if filtro in n]
    total_ok, total_falhas = 0, 0
    base = tempfile.mkdtemp(prefix="easyserv_testes_")
    try:
        for nome in nomes:
            oks, falhas = rodar(nome, base)
            total_ok += oks
            total_falhas += len(falhas)
            print(f"{nome:28} {oks:4} OK  {len(falhas)} falha(s)")
            for falha in falhas:
                print("    " + falha)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n{len(nomes)} bateria(s), {total_ok + total_falhas} verificações: {total_ok} OK, {total_falhas} falha(s)")
    return 1 if total_falhas else 0


if __name__ == "__main__":
    sys.exit(main())
