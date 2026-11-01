"""
barra_titulo.py - Pinta a barra de título das janelas com as cores do tema.

Usamos a barra de título do próprio Windows (e não uma feita por nós), só
trocando a cor dela. Assim continua tudo funcionando exatamente como no Windows:
arrastar, dois cliques para maximizar, encaixar nos cantos (Snap do Windows 11),
redimensionar pelas bordas, o menu do Alt+Espaço...

A cor é trocada pela função DwmSetWindowAttribute do Windows 11. No Windows 10
ela não existe para a cor da barra: a barra fica na cor normal (clara ou escura),
sem nenhum erro.

Toda janela do programa que aparece (a principal, as telas de configuração, os
painéis flutuando) é pintada sozinha: um "vigia" escuta o evento de aparecer.
"""

import ctypes
import sys

from PySide6.QtCore import QEvent, QObject, Qt

# Números das opções do Windows (documentação da Microsoft: DWMWINDOWATTRIBUTE).
DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # botões da barra (minimizar, fechar) claros ou escuros
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35            # fundo da barra
DWMWA_TEXT_COLOR = 36               # cor do título

# Tipos de janela que têm barra de título (menus e dicas não têm).
TIPOS_COM_BARRA = (Qt.Window, Qt.Dialog, Qt.Tool)

_cores = None   # {"fundo": "#rrggbb", "texto": "#rrggbb", "escura": bool}
_vigia = None


def _colorref(cor):
    """'#8c2f57' -> número no formato do Windows (0x00BBGGRR)."""
    vermelho, verde, azul = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)
    return (azul << 16) | (verde << 8) | vermelho


def colorir(janela):
    """Pinta a barra de título de uma janela. Devolve True se o Windows aceitou a cor."""
    if sys.platform != "win32" or _cores is None:
        return False
    if not janela.isWindow() or janela.windowType() not in TIPOS_COM_BARRA:
        return False
    try:
        dwm = ctypes.windll.dwmapi
        alca = ctypes.c_void_p(int(janela.winId()))
        aceitou = True
        for atributo, valor in ((DWMWA_USE_IMMERSIVE_DARK_MODE, int(_cores["escura"])),
                                (DWMWA_CAPTION_COLOR, _colorref(_cores["fundo"])),
                                (DWMWA_TEXT_COLOR, _colorref(_cores["texto"])),
                                (DWMWA_BORDER_COLOR, _colorref(_cores["fundo"]))):
            numero = ctypes.c_uint32(valor)
            resultado = dwm.DwmSetWindowAttribute(alca, ctypes.c_uint32(atributo),
                                                  ctypes.byref(numero), ctypes.sizeof(numero))
            aceitou = aceitou and resultado == 0  # 0 = deu certo
        return aceitou
    except (AttributeError, OSError):  # Windows antigo, sem a biblioteca dwmapi
        return False


class _Vigia(QObject):
    """Pinta cada janela do programa no momento em que ela aparece."""

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Show and objeto.isWidgetType() and objeto.isWindow():
            colorir(objeto)
        return False  # não "come" o evento: só olha


def definir_cores(app, fundo, texto, escura):
    """Troca as cores da barra (chamada sempre que o tema muda) e repinta as janelas abertas."""
    global _cores, _vigia
    _cores = {"fundo": fundo, "texto": texto, "escura": escura}
    if _vigia is None:
        _vigia = _Vigia(app)
        app.installEventFilter(_vigia)
    for janela in app.topLevelWidgets():
        if janela.isVisible():
            colorir(janela)
