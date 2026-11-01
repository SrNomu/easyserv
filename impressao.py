"""
impressao.py - Envia as notas para a impressora do Windows.

Há dois jeitos de imprimir, e o programa escolhe sozinho:

  1. Impressora GRÁFICA (driver normal): a nota é desenhada como imagem
     (com logo, tamanho de fonte e negrito) e enviada ao Windows.

  2. Impressora SÓ DE TEXTO (driver "Generic / Text Only", muito usado com
     impressoras térmicas): ela não sabe imprimir imagens, então mandamos o
     texto puro direto para ela. Logo e tamanho de fonte não funcionam nesse modo.

Usa a biblioteca pywin32 (módulos win32print e win32ui), que só existe no Windows.
"""

import unicodedata


class ErroImpressao(Exception):
    """Erro com mensagem amigável para mostrar na tela."""


def _win32print():
    """Importa o win32print só quando for usar (assim o resto do programa funciona sem ele)."""
    try:
        import win32print
    except ImportError:
        raise ErroImpressao("A biblioteca de impressão não está instalada.\n"
                            "Rode no terminal: python -m pip install pywin32")
    return win32print


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


def eh_impressora_texto(nome):
    """True se a impressora usa o driver 'Generic / Text Only' (só imprime texto)."""
    win32print = _win32print()
    try:
        alca = win32print.OpenPrinter(nome)
    except Exception:
        raise ErroImpressao(f"A impressora '{nome}' não foi encontrada.\n"
                            "Confira se ela está ligada e instalada no Windows.")
    try:
        driver = win32print.GetPrinter(alca, 2)["pDriverName"]
    finally:
        win32print.ClosePrinter(alca)
    return "text only" in driver.lower()


def tirar_acentos(texto):
    """'Serviços à vista' -> 'Servicos a vista'."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def imprimir_texto(nome_impressora, texto, sem_acentos=False, nome_documento="Nota"):
    """Manda texto puro direto para a impressora (modo RAW)."""
    win32print = _win32print()
    if sem_acentos:
        texto = tirar_acentos(texto)
    # Linhas em branco no final para o papel sair da impressora e poder ser cortado.
    texto = texto.rstrip("\n") + "\n" * 5
    # A maioria das impressoras térmicas usa a tabela de caracteres cp850 (tem ç, ã, é...).
    dados = texto.replace("\n", "\r\n").encode("cp850", errors="replace")

    try:
        alca = win32print.OpenPrinter(nome_impressora)
    except Exception:
        raise ErroImpressao(f"A impressora '{nome_impressora}' não foi encontrada.")
    try:
        win32print.StartDocPrinter(alca, 1, (nome_documento, None, "RAW"))
        try:
            win32print.StartPagePrinter(alca)
            win32print.WritePrinter(alca, dados)
            win32print.EndPagePrinter(alca)
        finally:
            win32print.EndDocPrinter(alca)
    except Exception as erro:
        raise ErroImpressao(f"Erro ao imprimir em '{nome_impressora}':\n{erro}")
    finally:
        win32print.ClosePrinter(alca)


def imprimir_imagem(nome_impressora, imagem, largura_mm, nome_documento="Nota", arquivo_saida=None):
    """
    Imprime uma imagem (PIL) com a largura indicada em milímetros.
    Se a nota for mais comprida que a folha, ela é dividida em várias páginas.
    'arquivo_saida' serve para imprimir em arquivo (ex.: na "Microsoft Print to PDF").
    """
    try:
        import win32con
        import win32ui
        from PIL import ImageWin
    except ImportError:
        raise ErroImpressao("Faltam bibliotecas de impressão.\n"
                            "Rode no terminal: python -m pip install pywin32 pillow")

    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(nome_impressora)
    except Exception:
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
        raise ErroImpressao(f"Erro ao imprimir em '{nome_impressora}':\n{erro}")
    finally:
        dc.DeleteDC()
