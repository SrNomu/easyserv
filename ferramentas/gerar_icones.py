"""
ferramentas/gerar_icones.py - Gera, a partir da logo (recursos/easyserv.svg):

  recursos/easyserv.ico          ícone do .exe, da barra de tarefas, da barra de título
                                 e do instalador (16 a 256 px, tudo num arquivo só);
  recursos/easyserv.png          a logo em 512 px (tela de abertura e janela Sobre);
  recursos/instalador_*.bmp      imagens das telas do instalador (Inno Setup).

Rode de novo só se mudar a logo:   python ferramentas\\gerar_icones.py
(O ferramentas\\gerar_instalador.py já chama este script.)
"""

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recursos")
SVG = os.path.join(PASTA, "easyserv.svg")
TAMANHOS_ICO = (16, 20, 24, 32, 40, 48, 64, 128, 256)
VINHO = "#8c2f57"


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


def imagem_lateral(renderizador, largura, altura):
    """Faixa da esquerda da tela de boas-vindas do instalador: vinho com a logo e o nome."""
    imagem = QImage(largura, altura, QImage.Format_RGB32)
    imagem.fill(QColor(VINHO))
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.Antialiasing)
    lado = int(largura * 0.62)
    renderizador.render(pintor, QRectF((largura - lado) / 2, altura * 0.22, lado, lado))
    fonte = QFont("Segoe UI", 1, QFont.Bold)
    fonte.setPixelSize(int(largura * 0.15))
    pintor.setFont(fonte)
    pintor.setPen(QColor("white"))
    pintor.drawText(QRectF(0, altura * 0.22 + lado + largura * 0.08, largura, largura * 0.25), Qt.AlignHCenter,
                    "EasyServ")
    pintor.end()
    return imagem


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderizador = QSvgRenderer(SVG)
    if not renderizador.isValid():
        raise SystemExit(f"Não consegui ler {SVG}")
    salvar_ico(renderizador, os.path.join(PASTA, "easyserv.ico"))
    desenhar(renderizador, 512).save(os.path.join(PASTA, "easyserv.png"))
    # Inno Setup: tamanhos para 100% e 200% de zoom do Windows.
    for escala in (1, 2):
        imagem_lateral(renderizador, 164 * escala, 314 * escala).save(
            os.path.join(PASTA, f"instalador_lateral_{escala}x.bmp"))
        desenhar(renderizador, 55 * escala, fundo=QColor("white")).convertToFormat(QImage.Format_RGB32).save(
            os.path.join(PASTA, f"instalador_pequena_{escala}x.bmp"))
    print("Ícones gerados em", PASTA)
    del app


if __name__ == "__main__":
    main()
