"""
ferramentas/gerar_instalador.py - Gera o EasyServ inteiro, pronto para publicar:

    python ferramentas\\gerar_instalador.py

O que ele faz (na ordem):
  1. gera os ícones a partir da logo (recursos/easyserv.svg);
  2. gera o programa (PyInstaller, pasta dist\\EasyServ com EasyServ.exe);
  3. gera o atualizador separado (EasyServAtualizador.exe) e põe junto do programa,
     e roda o autoteste do módulo de impressão no EasyServ.exe gerado;
  4. anota o tamanho de cada arquivo (manifesto.json, usado na tela de abertura);
  5. gera o instalador com o Inno Setup: dist\\EasyServ_Setup_<versão>.exe;
  6. calcula o SHA-256 do instalador: dist\\EasyServ_Setup_<versão>.exe.sha256.

Os arquivos para publicar no GitHub são os dois do passo 5 e 6.
Passo a passo da publicação: ferramentas\\COMO_PUBLICAR.txt.
"""

import hashlib
import os
import shutil
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import integridade  # noqa: E402  (precisa do sys.path acima)
import versao  # noqa: E402

DIST, BUILD = os.path.join(RAIZ, "dist"), os.path.join(RAIZ, "build")
PASTA_PROGRAMA = os.path.join(DIST, "EasyServ")
ICONE = os.path.join(RAIZ, "recursos", "easyserv.ico")
# Bibliotecas de impressão que o impressao.py carrega "na hora" (o PyInstaller não as
# enxerga sozinho): sem elas, o "Imprimir teste" do programa instalado não funciona.
IMPORTS_ESCONDIDOS = ["pywintypes", "win32print", "win32ui", "win32con", "win32api",
                      "PIL.Image", "PIL.ImageWin", "PIL.ImageDraw", "PIL.ImageFont"]
# O win32ui precisa do mfc140u.dll (Visual C++). O PyInstaller não o leva, porque ele está
# em System32 neste computador; mas nem todo Windows tem: por isso ele vai junto do win32ui.
MFC = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "mfc140u.dll")
LUGARES_ISCC = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def passo(texto):
    print(f"\n=== {texto}", flush=True)


def rodar(comando):
    print(" ".join(f'"{c}"' if " " in c else c for c in comando), flush=True)
    subprocess.run(comando, check=True)


def arquivo_de_versao():
    """Informações que aparecem em Propriedades › Detalhes do EasyServ.exe."""
    numeros = (list(versao.numero(versao.VERSAO)) + [0, 0, 0, 0])[:4]
    caminho = os.path.join(BUILD, "versao_exe.txt")
    os.makedirs(BUILD, exist_ok=True)
    texto = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tuple(numeros)}, prodvers={tuple(numeros)}),
  kids=[StringFileInfo([StringTable('041604B0', [
    StringStruct('CompanyName', '{versao.AUTOR}'),
    StringStruct('FileDescription', '{versao.NOME_PROGRAMA}'),
    StringStruct('FileVersion', '{versao.VERSAO}'),
    StringStruct('InternalName', 'EasyServ'),
    StringStruct('LegalCopyright', '{versao.COPYRIGHT}'),
    StringStruct('OriginalFilename', 'EasyServ.exe'),
    StringStruct('ProductName', '{versao.NOME_PROGRAMA}'),
    StringStruct('ProductVersion', '{versao.VERSAO}')])]),
  VarFileInfo([VarStruct('Translation', [0x0416, 1200])])]
)"""
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto)
    return caminho


def autoteste_no_exe(exe):
    """
    Roda o teste do EasyServ.exe GERADO (testes/teste_exe.py: --autoteste-impressao, sem
    janela, sem imprimir nada) e para tudo se o módulo de impressão não carregar nele.
    """
    sys.path.insert(0, os.path.join(RAIZ, "testes"))
    import teste_exe
    certo, linhas = teste_exe.testar_exe(exe)
    print("\n".join(linhas))
    if not certo:
        raise SystemExit("O módulo de impressão NÃO carrega no .exe gerado. Instalador não foi gerado.")


def main():
    print(f"Gerando {versao.titulo()}")

    passo("1/6 Ícones")
    rodar([sys.executable, os.path.join("ferramentas", "gerar_icones.py")])

    passo("2/6 Programa (PyInstaller)")
    if not os.path.exists(MFC):
        raise SystemExit(f"Não achei {MFC}. Instale o \"Visual C++ Redistributable\" (x64) da Microsoft.")
    shutil.rmtree(PASTA_PROGRAMA, ignore_errors=True)
    escondidos = [opcao for nome in IMPORTS_ESCONDIDOS for opcao in ("--hidden-import", nome)]
    rodar([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "EasyServ",
           "--icon", ICONE, "--version-file", arquivo_de_versao(),
           # (com --specpath, caminhos relativos seriam lidos a partir da pasta build: por isso absolutos)
           "--add-data", f"{os.path.join(RAIZ, 'recursos')}{os.pathsep}recursos",
           "--add-data", f"{os.path.join(RAIZ, 'LICENCA.txt')}{os.pathsep}.",
           "--add-data", f"{os.path.join(RAIZ, 'LICENCAS_TERCEIROS.txt')}{os.pathsep}.",
           *escondidos, "--add-binary", f"{MFC}{os.pathsep}pythonwin",
           # (numpy vem junto à toa por causa do Pillow: são uns 27 MB que o programa não usa)
           "--exclude-module", "tkinter", "--exclude-module", "versao_tkinter", "--exclude-module", "numpy",
           "--distpath", DIST, "--workpath", BUILD, "--specpath", BUILD,
           os.path.join(RAIZ, "main.py")])

    passo("3/6 Atualizador separado")
    rodar([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--noconsole",
           "--name", "EasyServAtualizador", "--icon", ICONE,
           "--exclude-module", "tkinter", "--exclude-module", "PySide6",
           "--distpath", os.path.join(BUILD, "atualizador"), "--workpath", BUILD, "--specpath", BUILD,
           os.path.join(RAIZ, "atualizador", "atualizador.py")])
    shutil.copy2(os.path.join(BUILD, "atualizador", "EasyServAtualizador.exe"), PASTA_PROGRAMA)

    passo("Autoteste do módulo de impressão no .exe gerado")
    autoteste_no_exe(os.path.join(PASTA_PROGRAMA, "EasyServ.exe"))

    passo("4/6 Manifesto (lista de arquivos)")
    # (LICENCA.txt e LICENCAS_TERCEIROS.txt também vão para a pasta do programa)
    for nome in ("LICENCA.txt", "LICENCAS_TERCEIROS.txt"):
        shutil.copy2(nome, PASTA_PROGRAMA)
    print(integridade.gerar_manifesto(PASTA_PROGRAMA, versao.VERSAO), "arquivos anotados")

    passo("5/6 Instalador (Inno Setup)")
    iscc = next((c for c in LUGARES_ISCC if os.path.exists(c)), None)
    if iscc is None:
        raise SystemExit("Inno Setup 6 não encontrado. Instale em https://jrsoftware.org/isdl.php")
    rodar([iscc, "/Q", f"/DVersao={versao.VERSAO}", os.path.join("instalador", "EasyServ.iss")])

    passo("6/6 SHA-256")
    nome = f"EasyServ_Setup_{versao.VERSAO}.exe"
    instalador = os.path.join(DIST, nome)
    soma = hashlib.sha256(open(instalador, "rb").read()).hexdigest()
    with open(instalador + ".sha256", "w", encoding="ascii") as arquivo:
        arquivo.write(f"{soma}  {nome}\n")
    tamanho = os.path.getsize(instalador) / 1048576
    print(f"\nPronto!\n  {instalador}  ({tamanho:.1f} MB)\n  {instalador}.sha256\n  SHA-256: {soma}")


if __name__ == "__main__":
    main()
