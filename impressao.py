"""
impressao.py - Envia as notas para a impressora do Windows.

Há dois MODOS de impressão (escolhidos em Configurar notinhas › Impressora):

  1. "Pelo driver do Windows" (o modo de sempre). O programa escolhe sozinho:
     - impressora GRÁFICA (driver normal): a nota é desenhada como imagem
       (com logo, tamanho de fonte e negrito) e enviada ao Windows;
     - impressora SÓ DE TEXTO (driver "Generic / Text Only"): o texto puro vai
       direto para ela (logo e tamanho de fonte não funcionam).

  2. "ESC/POS direto (RAW)": o programa monta os comandos ESC/POS (a "língua" das
     impressoras térmicas: Tomate, Elgin, Bematech, Epson, Knup, "POS-58/POS-80"...)
     e manda crus para a fila da impressora, sem o driver mexer. Assim funcionam
     negrito, letra grande, corte do papel, gaveta de dinheiro e a logo em preto e
     branco, qualquer que seja o driver instalado.

Usa a biblioteca pywin32 (win32print e win32ui), que só existe no Windows.
Se ela faltar, o detalhe técnico vai para o arquivo logs\\impressao.log (na pasta
de dados) e a tela mostra uma mensagem simples.
"""

import importlib
import os
import sys
import time
import traceback
import unicodedata
from datetime import datetime

MODO_WINDOWS = "windows"
MODO_ESCPOS = "escpos"
MODOS = {MODO_WINDOWS: "Pelo driver do Windows", MODO_ESCPOS: "ESC/POS direto (RAW)"}

# Páginas de código (tabela de letras) das impressoras ESC/POS:
# chave -> (nome na tela, codificação do Python, número do comando "ESC t n").
PAGINAS_CODIGO = {
    "cp850": ("PC850 - Multilíngue (o mais comum)", "cp850", 2),
    "cp860": ("PC860 - Português", "cp860", 3),
    "cp1252": ("WPC1252 - Windows", "cp1252", 16),
    "cp437": ("PC437 - EUA (sem ã e õ)", "cp437", 0),
}

# Largura de impressão em pontos (203 dpi = 8 pontos por mm): 48 mm e 72 mm úteis.
PONTOS_POR_LINHA = {"58mm": 384, "80mm": 576, "A4": 576}

# Bibliotecas que o módulo de impressão usa (o autoteste confere uma por uma).
BIBLIOTECAS = ["pywintypes", "win32print", "win32con", "win32ui", "PIL.Image", "PIL.ImageWin"]

ESC, GS = b"\x1b", b"\x1d"


class ErroImpressao(Exception):
    """Erro com mensagem amigável para mostrar na tela."""


# ----------------------------------------------------------------------
# Registro de erros e bibliotecas
# ----------------------------------------------------------------------

def arquivo_log():
    """logs\\impressao.log dentro da pasta de dados (ou na pasta temporária, se não der)."""
    try:
        import config  # (só aqui: este módulo funciona sozinho, sem o resto do programa)
        pasta = os.path.join(config.pasta_base(), "logs")
    except Exception:
        pasta = os.path.join(os.environ.get("TEMP", "."), "EasyServ")
    return os.path.join(pasta, "impressao.log")


def registrar_erro(contexto, erro):
    """Anota o erro (com o detalhe técnico) no impressao.log. Devolve o caminho do arquivo."""
    caminho = arquivo_log()
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        detalhe = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"[{datetime.now():%d/%m/%Y %H:%M:%S}] {contexto}\n"
                          f"  programa instalado: {'sim' if getattr(sys, 'frozen', False) else 'não'}"
                          f"  ·  Python {sys.version.split()[0]}\n{detalhe}\n")
    except OSError:
        pass  # sem lugar para gravar: segue só com a mensagem na tela
    return caminho


def mensagem_modulo(caminho_log):
    """A mensagem de quando falta uma biblioteca. No programa instalado, nunca fala em pip."""
    texto = ("Erro no módulo de impressão.\n"
             "Reinstale o EasyServ ou fale com o suporte.\n\n"
             f"(Detalhe técnico gravado em: {caminho_log})")
    if not getattr(sys, "frozen", False):
        texto += "\n\nRodando pelo código: python -m pip install pywin32 pillow"
    return texto


def _bibliotecas(*nomes):
    """Importa as bibliotecas só quando for usar (o resto do programa funciona sem elas)."""
    modulos = []
    for nome in nomes:
        try:
            modulos.append(importlib.import_module(nome))
        except Exception as erro:  # ImportError ou "DLL load failed" (OSError)
            raise ErroImpressao(mensagem_modulo(registrar_erro(f"Não foi possível carregar {nome}", erro))) from erro
    return modulos[0] if len(modulos) == 1 else modulos


def _win32print():
    return _bibliotecas("win32print")


# ----------------------------------------------------------------------
# Impressoras do Windows
# ----------------------------------------------------------------------

def listar_impressoras():
    """Nomes das impressoras instaladas no Windows."""
    win32print = _win32print()
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [impressora[2] for impressora in win32print.EnumPrinters(flags)]


def impressora_padrao():
    try:
        return _win32print().GetDefaultPrinter()
    except ErroImpressao:
        raise
    except Exception:
        raise ErroImpressao("Não há impressora padrão configurada no Windows.")


def escolher_impressora(nome_configurado):
    """Usa a impressora escolhida nas configurações; se estiver vazio, usa a padrão do Windows."""
    return nome_configurado or impressora_padrao()


def _dados_impressora(nome):
    """As informações do Windows sobre a impressora (driver, situação...)."""
    win32print = _win32print()
    try:
        alca = win32print.OpenPrinter(nome)
    except Exception:
        raise ErroImpressao(f"A impressora '{nome}' não foi encontrada.\n"
                            "Confira se ela está ligada e instalada no Windows.")
    try:
        return win32print.GetPrinter(alca, 2)
    finally:
        win32print.ClosePrinter(alca)


def eh_impressora_texto(nome):
    """True se a impressora usa o driver 'Generic / Text Only' (só imprime texto)."""
    return "text only" in _dados_impressora(nome)["pDriverName"].lower()


# Situações da impressora que impedem imprimir (valores do Windows).
_PROBLEMAS = [(0x00000080, "está desligada ou desconectada (offline)"),
              (0x00000010, "está sem papel"),
              (0x00000008, "está com o papel enroscado"),
              (0x00400000, "está com a tampa aberta"),
              (0x00001000, "não está disponível"),
              (0x00000002, "está com erro")]


def problema_na_impressora(nome):
    """Texto explicando o problema ('está sem papel'...) ou "" se o Windows não vê nenhum."""
    try:
        dados = _dados_impressora(nome)
    except ErroImpressao as erro:
        return str(erro)
    if dados.get("Attributes", 0) & 0x400:  # "Usar impressora offline" marcado no Windows
        return f"A impressora '{nome}' está marcada como \"Usar impressora offline\" no Windows."
    for bit, texto in _PROBLEMAS:
        if dados.get("Status", 0) & bit:
            return f"A impressora '{nome}' {texto}."
    return ""


def _conferir_trabalho(alca, trabalho, espera=2.0):
    """Olha a fila por alguns instantes: se o trabalho der erro, devolve o motivo."""
    win32print = _win32print()
    fim = time.monotonic() + espera
    while time.monotonic() < fim:
        try:
            situacao = win32print.GetJob(alca, trabalho, 1)["Status"]
        except Exception:
            return ""  # saiu da fila: foi impresso (ou o Windows não deixa olhar)
        if situacao & (0x2 | 0x20 | 0x40 | 0x200):  # erro, offline, sem papel, bloqueado
            return "a impressora recusou o trabalho (está ligada, com papel e com a tampa fechada?)"
        time.sleep(0.2)
    return ""


def enviar_raw(nome_impressora, dados, nome_documento="Nota", conferir=False):
    """Manda bytes crus para a fila da impressora (o driver não mexe neles)."""
    win32print = _win32print()
    try:
        alca = win32print.OpenPrinter(nome_impressora)
    except Exception:
        raise ErroImpressao(f"A impressora '{nome_impressora}' não foi encontrada.\n"
                            "Confira se ela está ligada e instalada no Windows.")
    try:
        trabalho = win32print.StartDocPrinter(alca, 1, (nome_documento, None, "RAW"))
        try:
            win32print.StartPagePrinter(alca)
            escritos = win32print.WritePrinter(alca, dados)
            win32print.EndPagePrinter(alca)
        finally:
            win32print.EndDocPrinter(alca)
        if isinstance(escritos, int) and escritos < len(dados):
            raise ErroImpressao(f"A impressora '{nome_impressora}' recebeu só parte da nota.")
        motivo = _conferir_trabalho(alca, trabalho) if conferir else ""
        if motivo:
            raise ErroImpressao(f"Erro ao imprimir em '{nome_impressora}': {motivo}")
    except ErroImpressao:
        raise
    except Exception as erro:
        registrar_erro(f"Impressão direta (RAW) em '{nome_impressora}'", erro)
        raise ErroImpressao(f"Erro ao imprimir em '{nome_impressora}':\n{erro}")
    finally:
        win32print.ClosePrinter(alca)


def tirar_acentos(texto):
    """'Serviços à vista' -> 'Servicos a vista'."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


# ----------------------------------------------------------------------
# Modo "Pelo driver do Windows"
# ----------------------------------------------------------------------

def imprimir_texto(nome_impressora, texto, sem_acentos=False, nome_documento="Nota"):
    """Manda texto puro para uma impressora 'Generic / Text Only' (modo RAW)."""
    if sem_acentos:
        texto = tirar_acentos(texto)
    # Linhas em branco no final para o papel sair da impressora e poder ser cortado.
    texto = texto.rstrip("\n") + "\n" * 5
    # A maioria das impressoras térmicas usa a tabela de caracteres cp850 (tem ç, ã, é...).
    enviar_raw(nome_impressora, texto.replace("\n", "\r\n").encode("cp850", errors="replace"), nome_documento)


def imprimir_imagem(nome_impressora, imagem, largura_mm, nome_documento="Nota", arquivo_saida=None):
    """
    Imprime uma imagem (PIL) com a largura indicada em milímetros.
    Se a nota for mais comprida que a folha, ela é dividida em várias páginas.
    'arquivo_saida' serve para imprimir em arquivo (ex.: na "Microsoft Print to PDF").
    """
    win32con, win32ui, ImageWin = _bibliotecas("win32con", "win32ui", "PIL.ImageWin")

    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(nome_impressora)
    except Exception as erro:
        registrar_erro(f"Abrir a impressora '{nome_impressora}' (driver do Windows)", erro)
        raise ErroImpressao(f"Não foi possível usar a impressora '{nome_impressora}'.")

    try:
        # "Pontos por polegada" da impressora e área que ela consegue imprimir (em pontos).
        dpi_x = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        dpi_y = dc.GetDeviceCaps(win32con.LOGPIXELSY)
        area_largura = dc.GetDeviceCaps(win32con.HORZRES)
        area_altura = dc.GetDeviceCaps(win32con.VERTRES)

        # Largura final na impressora (sem passar da área imprimível).
        largura = min(round(largura_mm / 25.4 * dpi_x), area_largura)
        escala_x = largura / imagem.width
        escala_y = escala_x * dpi_y / dpi_x  # mantém a proporção mesmo se dpi_x != dpi_y

        # Quantas linhas de pixels da imagem cabem em uma página.
        pixels_por_pagina = max(1, int(area_altura / escala_y))

        imagem = imagem.convert("RGB")
        if arquivo_saida:
            dc.StartDoc(nome_documento, arquivo_saida)
        else:
            dc.StartDoc(nome_documento)
        for topo in range(0, imagem.height, pixels_por_pagina):
            pedaco = imagem.crop((0, topo, imagem.width, min(topo + pixels_por_pagina, imagem.height)))
            altura = round(pedaco.height * escala_y)
            dc.StartPage()
            ImageWin.Dib(pedaco).draw(dc.GetHandleOutput(), (0, 0, largura, altura))
            dc.EndPage()
        dc.EndDoc()
    except ErroImpressao:
        raise
    except Exception as erro:
        registrar_erro(f"Impressão pelo driver em '{nome_impressora}'", erro)
        raise ErroImpressao(f"Erro ao imprimir em '{nome_impressora}':\n{erro}")
    finally:
        dc.DeleteDC()


# ----------------------------------------------------------------------
# Modo "ESC/POS direto (RAW)"
# ----------------------------------------------------------------------

def imagem_raster(imagem, largura_max):
    """
    A logo como imagem preto e branco no comando ESC/POS "GS v 0" (imagem raster).
    Tons de cinza viram pontinhos (pontilhado), como num jornal. A imagem vai em
    faixas de até 128 linhas, porque as impressoras baratas têm pouca memória.
    """
    from PIL import Image

    cinza = imagem.convert("L")
    if cinza.width > largura_max:
        cinza = cinza.resize((largura_max, max(1, round(cinza.height * largura_max / cinza.width))),
                             Image.LANCZOS)
    largura_bytes = (cinza.width + 7) // 8
    pb = Image.new("1", (largura_bytes * 8, cinza.height), 1)  # (1 = branco)
    pb.paste(cinza.convert("1"), (0, 0))  # convert("1") faz o pontilhado
    bits = bytes(b ^ 0xFF for b in pb.tobytes())  # no ESC/POS, 1 = ponto preto
    comandos = bytearray()
    for topo in range(0, pb.height, 128):
        linhas = min(128, pb.height - topo)
        comandos += GS + b"v0\x00" + bytes([largura_bytes % 256, largura_bytes // 256, linhas % 256, linhas // 256])
        comandos += bits[topo * largura_bytes:(topo + linhas) * largura_bytes]
    return bytes(comandos)


def comandos_escpos(linhas, pagina_codigo="cp850", sem_acentos=False, logo=None, largura_logo=384,
                    logo_no_centro=True, letra_grande=True, cortar=True, gaveta=False):
    """
    Monta a nota inteira em comandos ESC/POS. 'linhas' = [(texto, negrito), ...] (de notas.py).
    Com letra_grande, o nome da loja (as linhas em negrito antes do primeiro separador)
    e o TOTAL saem com o dobro da altura (a largura não muda, então cabem iguais).
    """
    _, codificacao, numero = PAGINAS_CODIGO.get(pagina_codigo, PAGINAS_CODIGO["cp850"])
    dados = bytearray(ESC + b"@")                 # ESC @   = reinicia a impressora
    dados += ESC + b"t" + bytes([numero])         # ESC t n = página de código (acentos)
    if logo is not None:
        dados += ESC + b"a" + (b"\x01" if logo_no_centro else b"\x00")  # ESC a = alinhamento
        dados += imagem_raster(logo, largura_logo)
        dados += ESC + b"a\x00"
    no_cabecalho = True
    for conteudo, negrito in linhas:
        if conteudo and set(conteudo) <= set("=-"):
            no_cabecalho = False  # passou do cabeçalho
        grande = letra_grande and negrito and (no_cabecalho or conteudo.startswith("TOTAL"))
        modo = (0x08 if negrito else 0) | (0x10 if grande else 0)  # ESC ! n: negrito e altura dupla
        if sem_acentos:
            conteudo = tirar_acentos(conteudo)
        dados += ESC + b"!" + bytes([modo]) + conteudo.encode(codificacao, errors="replace") + b"\n"
    dados += ESC + b"!\x00"
    dados += ESC + b"d\x04"                       # ESC d 4 = avança 4 linhas (o papel sai)
    if cortar:
        dados += GS + b"V\x42\x00"                # GS V 66 0 = corta (quem não tem guilhotina ignora)
    if gaveta:
        dados += ESC + b"p\x00\x19\xfa"           # ESC p 0 = pulso que abre a gaveta de dinheiro
    return bytes(dados)


def comando_gaveta():
    """Só abrir a gaveta de dinheiro (sem imprimir nada)."""
    return ESC + b"@" + ESC + b"p\x00\x19\xfa"


def imprimir_escpos(nome_impressora, dados, nome_documento="Nota", conferir=False):
    enviar_raw(nome_impressora, dados, nome_documento, conferir)


def abrir_gaveta(nome_impressora):
    enviar_raw(nome_impressora, comando_gaveta(), "Abrir gaveta")


def sugestao_outro_modo(modo):
    """O que dizer quando o modo escolhido falha: tentar o outro."""
    outro = MODO_WINDOWS if modo == MODO_ESCPOS else MODO_ESCPOS
    return (f"Dica: em Configurar notinhas › Impressora, troque o modo para \"{MODOS[outro]}\" "
            "ou clique em \"Detectar\" para o programa testar os dois.")


# ----------------------------------------------------------------------
# Autoteste (EasyServ.exe --autoteste-impressao): o módulo carrega no programa?
# ----------------------------------------------------------------------

def verificar_modulos():
    """
    Confere, SEM imprimir nada, se tudo o que a impressão usa está dentro do programa:
    importa cada biblioteca, lista as impressoras (só lê), desenha uma imagem pelo
    win32ui numa memória (não na impressora) e monta uma nota ESC/POS.
    Devolve [(o que foi testado, deu certo?, detalhe), ...].
    """
    resultado = []

    def testar(nome, funcao):
        try:
            detalhe = funcao()
            resultado.append((nome, True, detalhe or ""))
        except Exception as erro:
            resultado.append((nome, False, f"{type(erro).__name__}: {erro}"))

    for nome in BIBLIOTECAS:
        testar(f"importar {nome}", lambda nome=nome: getattr(importlib.import_module(nome), "__file__", "") or "")

    def impressoras():
        return f"{len(listar_impressoras())} impressora(s) no Windows"

    def desenhar_na_memoria():
        win32ui, ImageWin = _bibliotecas("win32ui", "PIL.ImageWin")
        from PIL import Image
        memoria = win32ui.CreateDC().CreateCompatibleDC(None)  # um "papel" na memória
        try:
            figura = win32ui.CreateBitmap()
            figura.CreateCompatibleBitmap(memoria, 16, 16)
            memoria.SelectObject(figura)
            ImageWin.Dib(Image.new("RGB", (16, 16), "white")).draw(memoria.GetHandleOutput(), (0, 0, 16, 16))
        finally:
            memoria.DeleteDC()
        return "win32ui + ImageWin.Dib"

    def montar_escpos():
        from PIL import Image
        dados = comandos_escpos([("MINHA LOJA", True), ("=" * 32, False), ("Ação é ç", False)],
                                logo=Image.new("L", (100, 40), 0))
        return f"{len(dados)} bytes"

    def dll_mfc():
        """
        O win32ui precisa do mfc140u.dll. Nem todo Windows tem essa DLL, por isso ela vai
        DENTRO do programa: no .exe, ela tem que ter sido carregada da pasta do programa.
        """
        import ctypes
        _bibliotecas("win32ui")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p  # (em 64 bits o número não cabe num int)
        kernel32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
        alca = kernel32.GetModuleHandleW("mfc140u.dll")
        if not alca:
            raise RuntimeError("mfc140u.dll não foi carregada")
        caminho = ctypes.create_unicode_buffer(1024)
        kernel32.GetModuleFileNameW(alca, caminho, 1024)
        pasta = getattr(sys, "_MEIPASS", "")
        if pasta and not os.path.normcase(caminho.value).startswith(os.path.normcase(pasta)):
            raise RuntimeError(f"veio do Windows ({caminho.value}), não do programa: em outro PC pode faltar")
        return caminho.value

    testar("mfc140u.dll (usada pelo win32ui)", dll_mfc)
    testar("listar impressoras (só leitura)", impressoras)
    testar("desenhar imagem na memória", desenhar_na_memoria)
    testar("montar nota ESC/POS", montar_escpos)
    return resultado
