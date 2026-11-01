"""
tela_abertura.py - Tela de abertura (splash), no estilo dos programas de edição:
fundo escuro, logo, nome, versão, direitos e uma barra de progresso dizendo o que
está sendo feito ("Verificando arquivos...", "Carregando banco de dados...").

    abertura = TelaAbertura()
    abertura.show()
    abertura.etapa("Verificando arquivos...", 10)
    ...
    abertura.close()

Quem decide as etapas é o main.py; esta tela só mostra.
"""

import threading
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

import versao
from config import recurso

LARGURA, ALTURA = 640, 360
FUNDO, FUNDO_2 = QColor("#1b1719"), QColor("#2a1520")
TEXTO, TEXTO_FRACO = QColor("#f1ecee"), QColor("#a99ba2")
DESTAQUE, TRILHO = QColor("#e891b6"), QColor("#3a2a31")


class TelaAbertura(QWidget):
    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)  # cantos arredondados
        self.setFixedSize(LARGURA, ALTURA)
        self.setWindowTitle(versao.NOME_PROGRAMA)
        self.logo = QSvgRenderer(recurso("easyserv.svg"))
        self.texto = "Iniciando..."
        self.progresso = 0
        tela = QApplication.primaryScreen().availableGeometry()
        self.move(tela.center().x() - LARGURA // 2, tela.center().y() - ALTURA // 2)

    def etapa(self, texto, progresso):
        """Muda o texto e a barra e redesenha já (o programa ainda está carregando)."""
        self.texto, self.progresso = texto, max(0, min(100, progresso))
        self.repaint()
        QApplication.processEvents()

    def esperar(self, funcao, limite_segundos):
        """
        Roda 'funcao' em segundo plano sem congelar a tela e devolve o resultado.
        Se passar do limite, desiste e devolve None (ex.: internet muito lenta).
        """
        resultado = {}
        fio = threading.Thread(target=lambda: resultado.setdefault("valor", funcao()), daemon=True)
        fio.start()
        fim = time.monotonic() + limite_segundos
        while fio.is_alive() and time.monotonic() < fim:
            QApplication.processEvents()
            fio.join(0.03)
        return resultado.get("valor")

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        caixa = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        contorno = QPainterPath()
        contorno.addRoundedRect(caixa, 14, 14)
        degrade = QLinearGradient(0, 0, LARGURA, ALTURA)
        degrade.setColorAt(0, FUNDO_2)
        degrade.setColorAt(0.55, FUNDO)
        p.fillPath(contorno, degrade)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.drawPath(contorno)

        # Logo e nome
        self.logo.render(p, QRectF(48, 72, 112, 112))
        p.setPen(TEXTO)
        p.setFont(self._fonte(46, QFont.DemiBold))
        p.drawText(QRectF(188, 70, 420, 64), Qt.AlignLeft | Qt.AlignVCenter, versao.NOME_PROGRAMA)
        p.setPen(DESTAQUE)
        p.setFont(self._fonte(17))
        p.drawText(QRectF(190, 134, 420, 28), Qt.AlignLeft | Qt.AlignVCenter, f"Versão {versao.VERSAO}")
        p.setPen(TEXTO_FRACO)
        p.setFont(self._fonte(13))
        p.drawText(QRectF(190, 162, 420, 24), Qt.AlignLeft | Qt.AlignVCenter, "Atendimento e caixa para serviços")

        # Progresso
        p.setPen(TEXTO)
        p.setFont(self._fonte(13))
        p.drawText(QRectF(48, 252, LARGURA - 96, 22), Qt.AlignLeft | Qt.AlignVCenter, self.texto)
        trilho = QRectF(48, 282, LARGURA - 96, 4)
        p.setPen(Qt.NoPen)
        p.setBrush(TRILHO)
        p.drawRoundedRect(trilho, 2, 2)
        p.setBrush(DESTAQUE)
        p.drawRoundedRect(QRectF(trilho.x(), trilho.y(), trilho.width() * self.progresso / 100, 4), 2, 2)

        p.setPen(TEXTO_FRACO)
        p.setFont(self._fonte(11))
        p.drawText(QRectF(48, ALTURA - 50, LARGURA - 96, 20), Qt.AlignLeft | Qt.AlignVCenter, versao.COPYRIGHT)
        p.end()

    @staticmethod
    def _fonte(pixels, peso=QFont.Normal):
        fonte = QFont("Segoe UI")
        fonte.setPixelSize(pixels)
        fonte.setWeight(peso)
        return fonte
