"""
ferramentas/gerar_icones.py - Gera, a partir da logo (recursos/easyserv.svg):

  recursos/easyserv.ico          ícone do .exe, da barra de tarefas, da barra de título
                                 e do instalador (16 a 256 px, tudo num arquivo só);
  recursos/easyserv.png          a logo em 512 px (tela de abertura e janela Sobre);
  recursos/instalador_*.png      imagens das telas do instalador (Inno Setup), no visual da
                                 tela de abertura: fundo escuro em degradê, logo e rosa.

Rode de novo só se mudar a logo:   python ferramentas\\gerar_icones.py
(O ferramentas\\gerar_instalador.py já chama este script.)
"""

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer

PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recursos")
SVG = os.path.join(PASTA, "easyserv.svg")
TAMANHOS_ICO = (16, 20, 24, 32, 40, 48, 64, 128, 256)
# As cores da tela de abertura (tela_abertura.py), para o instalador ficar igual a ela.
FUNDO, FUNDO_2 = "#1b1719", "#2a1520"


def desenhar(renderizador, largura, altura=None, fundo=Qt.transparent):
    """A logo desenhada direto no tamanho final (fica nítida, sem esticar uma imagem grande)."""
    imagem = QImage(largura, altura or largura, QImage.Format_ARGB32)
    imagem.fill(fundo)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setRenderHint(QPainter.SmoothPixmapTransform)
    renderizador.render(pintor, QRectF(0, 0, largura, altura or largura))
    pintor.end()
    return imagem


def png_bytes(imagem):
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    imagem.save(buffer, "PNG")
    return bytes(dados)


def salvar_ico(renderizador, caminho):
    """Arquivo .ico com várias imagens PNG (formato aceito pelo Windows Vista em diante)."""
    imagens = [png_bytes(desenhar(renderizador, t)) for t in TAMANHOS_ICO]
    cabecalho = struct.pack("<HHH", 0, 1, len(imagens))
    deslocamento = 6 + 16 * len(imagens)
    entradas, dados = b"", b""
    for tamanho, png in zip(TAMANHOS_ICO, imagens):
        lado = 0 if tamanho >= 256 else tamanho  # 0 quer dizer 256 no formato .ico
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), deslocamento + len(dados))
        dados += png
    with open(caminho, "wb") as arquivo:
        arquivo.write(cabecalho + entradas + dados)


def imagem_fundo(largura, altura):
    """Fundo de todas as telas do instalador: o mesmo degradê da tela de abertura."""
    imagem = QImage(largura, altura, QImage.Format_RGB32)
    pintor = QPainter(imagem)
    degrade = QLinearGradient(0, 0, largura, altura)
    degrade.setColorAt(0, QColor(FUNDO_2))
    degrade.setColorAt(0.55, QColor(FUNDO))
    pintor.fillRect(0, 0, largura, altura, degrade)
    pintor.end()
    return imagem


def imagem_lateral(renderizador, largura, altura):
    """
    Faixa da esquerda das telas de boas-vindas e final: só a logo, grande, sobre fundo
    transparente (o degradê do fundo aparece por trás), na altura do nome "EasyServ".
    """
    imagem = QImage(largura, altura, QImage.Format_ARGB32)
    imagem.fill(Qt.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setRenderHint(QPainter.SmoothPixmapTransform)
    lado = largura * 0.64
    renderizador.render(pintor, QRectF((largura - lado) / 2, altura * 0.075, lado, lado))
    pintor.end()
    return imagem


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderizador = QSvgRenderer(SVG)
    if not renderizador.isValid():
        raise SystemExit(f"Não consegui ler {SVG}")
    salvar_ico(renderizador, os.path.join(PASTA, "easyserv.ico"))
    desenhar(renderizador, 512).save(os.path.join(PASTA, "easyserv.png"))
    # Inno Setup 6.7: tamanhos das áreas com zoom do Windows em 100% e 200%.
    for escala, fundo, lateral, pequena in ((1, (596, 432), (202, 386), 58), (2, (1272, 922), (430, 824), 124)):
        imagem_fundo(*fundo).save(os.path.join(PASTA, f"instalador_fundo_{escala}x.png"))
        imagem_lateral(renderizador, *lateral).save(os.path.join(PASTA, f"instalador_lateral_{escala}x.png"))
        desenhar(renderizador, pequena).save(os.path.join(PASTA, f"instalador_pequena_{escala}x.png"))
    print("Ícones gerados em", PASTA)
    del app


if __name__ == "__main__":
    main()
