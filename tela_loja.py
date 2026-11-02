"""
tela_loja.py - Os dados da loja: nome, endereço, telefone, CNPJ e logo.

  FormularioLoja      -> os campos (usado na aba "Loja" das Preferências e nas boas-vindas);
  DialogoBoasVindas   -> a janela "Dados da sua loja" da primeira vez que o programa abre.
  DialogoDadosLoja    -> a mesma coisa como janela avulsa (link do Configurar notinhas).

Esses dados ficam num lugar só (config.json, chave "loja") e valem para o programa
inteiro: título da janela, notinhas, relatórios (tela, A4, PDF, Excel e resumo) e
páginas de teste de impressão.
"""

import os

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import config
import layout_notas
from config import pasta_base, recurso
from utils import formatar_telefone

TAMANHO_PREVIA_LOGO = 72


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    rotulo.setWordWrap(True)
    return rotulo


class FormularioLoja(QWidget):
    """Os campos dos dados da loja. valores() devolve o dicionário para o config.json."""

    def __init__(self, loja, pai=None):
        super().__init__(pai)
        self._logo = loja.get("logo", "")
        formulario = QFormLayout(self)
        formulario.setContentsMargins(0, 0, 0, 0)
        formulario.setVerticalSpacing(8)
        self.campo_nome = QLineEdit(loja.get("nome", ""))
        self.campo_nome.setMaxLength(60)
        self.campo_nome.setPlaceholderText("Ex.: Papelaria Central")
        self.campo_endereco = QLineEdit(loja.get("endereco", ""))
        self.campo_endereco.setPlaceholderText("Rua, número, bairro (opcional)")
        self.campo_telefone = QLineEdit(loja.get("telefone", ""))
        self.campo_telefone.setPlaceholderText("(21) 99999-9999 (opcional)")
        self.campo_telefone.textEdited.connect(self._mascara_telefone)
        self.campo_cnpj = QLineEdit(loja.get("cnpj", ""))
        self.campo_cnpj.setPlaceholderText("Opcional")
        formulario.addRow("Nome da loja", self.campo_nome)
        formulario.addRow("Endereço", self.campo_endereco)
        formulario.addRow("Telefone", self.campo_telefone)
        formulario.addRow("CNPJ", self.campo_cnpj)

        linha = QHBoxLayout()
        self.previa_logo = QLabel()
        self.previa_logo.setFixedSize(TAMANHO_PREVIA_LOGO, TAMANHO_PREVIA_LOGO)
        self.previa_logo.setAlignment(Qt.AlignCenter)
        self.previa_logo.setObjectName("rotulo")
        linha.addWidget(self.previa_logo)
        self.btn_escolher_logo = QPushButton("Escolher imagem...")
        self.btn_escolher_logo.clicked.connect(self.escolher_logo)
        linha.addWidget(self.btn_escolher_logo)
        self.btn_remover_logo = QPushButton("Remover")
        self.btn_remover_logo.clicked.connect(self.remover_logo)
        linha.addWidget(self.btn_remover_logo)
        linha.addStretch(1)
        formulario.addRow("Logo", linha)
        formulario.addRow(_rotulo("A logo é opcional. Em Arquivo › Configurar notinhas você escolhe se ela e cada "
                                  "um destes dados aparecem em cada nota.", "rotulo"))
        for botao in (self.btn_escolher_logo, self.btn_remover_logo):
            botao.setAutoDefault(False)
        self._mostrar_logo()

    def _mascara_telefone(self, texto):
        formatado = formatar_telefone(texto)
        if formatado != texto:
            self.campo_telefone.setText(formatado)

    def _mostrar_logo(self):
        caminho = os.path.join(pasta_base(), self._logo) if self._logo else ""
        imagem = QPixmap(caminho) if caminho and os.path.exists(caminho) else QPixmap()
        if imagem.isNull():
            self.previa_logo.setPixmap(QPixmap())
            self.previa_logo.setText("sem logo")
        else:
            self.previa_logo.setText("")
            self.previa_logo.setPixmap(imagem.scaled(TAMANHO_PREVIA_LOGO, TAMANHO_PREVIA_LOGO,
                                                     Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.btn_remover_logo.setEnabled(bool(self._logo))

    def escolher_logo(self, caminho=None):
        if not caminho:
            caminho, _filtro = QFileDialog.getOpenFileName(
                self, "Escolher logo", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.gif);;Todos os arquivos (*.*)")
        if not caminho:
            return  # a pessoa cancelou
        try:
            with Image.open(caminho) as imagem:
                imagem.verify()  # confere se é mesmo uma imagem válida
            self._logo = layout_notas.guardar_logo(caminho, "loja")
        except OSError as erro:
            QMessageBox.critical(self, "Logo", f"Não foi possível usar esta imagem:\n{erro}")
            return
        self._mostrar_logo()

    def remover_logo(self):
        self._logo = ""
        self._mostrar_logo()

    def valores(self):
        return {"nome": self.campo_nome.text().strip(), "endereco": self.campo_endereco.text().strip(),
                "telefone": self.campo_telefone.text().strip(), "cnpj": self.campo_cnpj.text().strip(),
                "logo": self._logo}

    def erro(self):
        """Texto do problema (ou "" se estiver tudo certo)."""
        return "" if self.valores()["nome"] else "Digite o nome da loja."


class DialogoBoasVindas(QDialog):
    """
    "Dados da sua loja": aparece uma vez só, na primeira vez que o programa abre.
    Numa instalação que já existia, vem preenchida com o que já estava configurado.
    Fechar pelo X também conta (grava o que estiver nos campos, se o nome for válido).
    """

    def __init__(self, pai, loja):
        super().__init__(pai)
        self.setWindowTitle("Bem-vindo ao EasyServ")
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(22, 18, 22, 16)
        coluna.setSpacing(10)
        topo = QHBoxLayout()
        topo.setSpacing(14)
        logo = QLabel()
        imagem = QPixmap(recurso("easyserv.png"))
        if not imagem.isNull():
            logo.setPixmap(imagem.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        topo.addWidget(logo, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(_rotulo("Dados da sua loja", "servicoAtual"))
        ja_tinha = loja.get("nome") and loja.get("nome") != config.LOJA_PADRAO["nome"]
        textos.addWidget(_rotulo(
            "Confira os dados que já estavam configurados e clique em Confirmar." if ja_tinha else
            "Eles aparecem no título da janela, nas notinhas e nos relatórios.", "rotulo"))
        topo.addLayout(textos, 1)
        coluna.addLayout(topo)

        self.formulario = FormularioLoja(loja, self)
        coluna.addWidget(self.formulario)
        coluna.addWidget(_rotulo("Dá para mudar depois em Arquivo › Preferências › Loja.", "rotulo"))

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        self.btn_confirmar = QPushButton("Confirmar")
        self.btn_confirmar.setObjectName("finalizar")
        self.btn_confirmar.setAutoDefault(False)
        self.btn_confirmar.clicked.connect(self.confirmar)
        botoes.addWidget(self.btn_confirmar)
        coluna.addLayout(botoes)
        self.setMinimumWidth(560)
        self.salvou = False
        self.formulario.campo_nome.setFocus()
        if not ja_tinha:
            self.formulario.campo_nome.selectAll()  # ("Minha Loja": é só digitar por cima)

    def confirmar(self):
        erro = self.formulario.erro()
        if erro:
            QMessageBox.warning(self, "Dados da loja", erro)
            self.formulario.campo_nome.setFocus()
            return
        try:
            config.salvar_loja(self.formulario.valores())
        except (OSError, ValueError) as erro_ao_salvar:
            QMessageBox.critical(self, "Dados da loja", f"Não foi possível gravar o config.json:\n{erro_ao_salvar}")
            return
        self.salvou = True
        self.accept()

    def reject(self):
        """Fechou pelo X ou Esc: guarda o que está nos campos (a janela não volta a aparecer)."""
        if not self.formulario.erro():
            self.confirmar()
            return
        try:  # sem nome: confirma o que já estava configurado
            config.salvar_loja(config.carregar_config().loja)
        except Exception:
            pass
        super().reject()


class DialogoDadosLoja(QDialog):
    """Janela "Dados da loja" com Salvar e Cancelar. Accepted = gravou no config.json."""

    def __init__(self, pai):
        super().__init__(pai)
        self.setWindowTitle("Dados da loja")
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(18, 14, 18, 14)
        self.formulario = FormularioLoja(config.carregar_config().loja, self)
        coluna.addWidget(self.formulario)
        coluna.addWidget(_rotulo("Valem para o programa inteiro: título da janela, notinhas e relatórios.", "rotulo"))
        botoes = QHBoxLayout()
        botoes.addStretch(1)
        botao = QPushButton("Salvar")
        botao.setAutoDefault(False)
        botao.clicked.connect(self.salvar)
        botoes.addWidget(botao)
        botao = QPushButton("Cancelar")
        botao.setAutoDefault(False)
        botao.clicked.connect(self.reject)
        botoes.addWidget(botao)
        coluna.addLayout(botoes)
        self.setMinimumWidth(520)

    def salvar(self):
        erro = self.formulario.erro()
        if erro:
            QMessageBox.warning(self, "Dados da loja", erro)
            return
        try:
            config.salvar_loja(self.formulario.valores())
        except (OSError, ValueError) as erro_ao_salvar:
            QMessageBox.critical(self, "Dados da loja", f"Não foi possível gravar o config.json:\n{erro_ao_salvar}")
            return
        self.accept()
