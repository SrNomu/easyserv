"""
tela_sobre.py - Janela "Sobre" (menu Ajuda › Sobre): logo, nome, versão, direitos
autorais, notas da versão, créditos das bibliotecas e termos de uso.

Os textos ficam em versao.py; os termos em LICENCA.txt e LICENCAS_TERCEIROS.txt.
"""

import html

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

import versao
from config import recurso


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


def html_notas():
    """As notas da versão em HTML (uma seção por versão, a mais nova em cima)."""
    partes = []
    for numero, data, mudancas in versao.NOTAS_DA_VERSAO:
        itens = "".join(f"<li>{html.escape(texto)}</li>" for texto in mudancas)
        partes.append(f"<h3>Versão {html.escape(numero)} <small>· {html.escape(data)}</small></h3>"
                      f"<ul>{itens}</ul>")
    return "".join(partes)


def html_creditos():
    """Tabela com as bibliotecas usadas e as licenças delas."""
    linhas = "".join(
        f"<tr><td><b>{html.escape(nome)}</b> {html.escape(numero)}</td><td>{html.escape(licenca)}</td>"
        f"<td><a href='{html.escape(site)}'>{html.escape(site)}</a></td></tr>"
        for nome, numero, licenca, site in versao.BIBLIOTECAS)
    return ("<p>O EasyServ foi feito com estas bibliotecas de código aberto. Obrigado aos autores!</p>"
            f"<table cellspacing='0' cellpadding='4'><tr><th align='left'>Biblioteca</th>"
            f"<th align='left'>Licença</th><th align='left'>Site</th></tr>{linhas}</table>"
            "<p>O Qt e o PySide6 são usados sem modificações, como bibliotecas separadas (LGPL v3). "
            "Detalhes em LICENCAS_TERCEIROS.txt, na pasta do programa.</p>")


def ler_texto(nome):
    """Lê um .txt que vem com o programa (LICENCA.txt...). Se não achar, avisa no lugar."""
    try:
        with open(recurso(nome), encoding="utf-8") as arquivo:
            return arquivo.read()
    except OSError:
        return f"(Arquivo {nome} não encontrado na pasta do programa.)"


class TelaSobre(QDialog):
    def __init__(self, pai):
        super().__init__(pai)
        self.setWindowTitle(f"Sobre o {versao.NOME_PROGRAMA}")
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(20, 16, 20, 16)
        coluna.setSpacing(6)

        topo = QHBoxLayout()
        topo.setSpacing(16)
        logo = QLabel()
        imagem = QPixmap(recurso("easyserv.png"))
        if not imagem.isNull():
            logo.setPixmap(imagem.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        topo.addWidget(logo, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.lbl_nome = _rotulo(versao.NOME_PROGRAMA, "total")
        textos.addWidget(self.lbl_nome)
        textos.addWidget(_rotulo(f"Versão {versao.VERSAO}", "valorGrande"))
        textos.addWidget(_rotulo(versao.COPYRIGHT))
        textos.addWidget(_rotulo(f"Feito por {versao.AUTOR}.", "rotulo"))
        textos.addStretch(1)
        topo.addLayout(textos, 1)
        coluna.addLayout(topo)
        coluna.addSpacing(8)

        self.abas = QTabWidget()
        self.notas = QTextBrowser()
        self.notas.setHtml(html_notas())
        self.abas.addTab(self.notas, "Notas da versão")
        self.creditos = QTextBrowser()
        self.creditos.setOpenExternalLinks(True)
        self.creditos.setHtml(html_creditos())
        self.abas.addTab(self.creditos, "Créditos e licenças")
        self.termos = QTextBrowser()
        self.termos.setPlainText(ler_texto("LICENCA.txt"))
        self.abas.addTab(self.termos, "Termos de uso")
        coluna.addWidget(self.abas, 1)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        botoes.addWidget(fechar)
        coluna.addLayout(botoes)
        self.resize(680, 600)

    def texto_completo(self):
        """Todo o texto da janela (usado nos testes)."""
        rotulos = " ".join(r.text() for r in self.findChildren(QLabel))
        return " ".join([rotulos, self.notas.toPlainText(), self.creditos.toPlainText(), self.termos.toPlainText()])
