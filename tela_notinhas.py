"""
tela_notinhas.py - Tela "Configurar notinhas" (editor do layout das notas), em PySide6.

  ┌ Editando: (•) Nota da loja  ( ) Nota do cliente ─────────────────────────┐
  │ Cabeçalho          │ Mostrar na nota     │ Pré-visualização           │
  │ Logo               │ Formato             │ (redesenhada a cada        │
  │ Rodapé             │ Impressora          │  mudança nas opções)       │
  └ [Restaurar padrão] [Imprimir teste]                [Salvar] [Fechar] ┘

As mudanças ficam só na memória até clicar em "Salvar".

Os dados da loja (nome, endereço, telefone, CNPJ e logo) NÃO são editados aqui: aqui só
se escolhe se cada um aparece na nota. Eles ficam em Preferências › Loja (o link
"Alterar dados da loja" abre a mesma janela).
"""

import json
import os
from datetime import datetime
from decimal import Decimal

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import config
import impressao
import layout_notas
import notas
import tela_loja
from utils import arredondar, base_da_taxa

TEXTO_IMPRESSORA_PADRAO = "(impressora padrão do Windows)"


def _pil_para_pixmap(imagem):
    """Converte uma imagem do Pillow (tons de cinza) para o formato que o Qt mostra na tela."""
    imagem = imagem.convert("L")
    dados = imagem.tobytes()
    qimagem = QImage(dados, imagem.width, imagem.height, imagem.width, QImage.Format_Grayscale8)
    return QPixmap.fromImage(qimagem.copy())  # copy(): o Qt passa a ter os próprios bytes


def _rolavel(conteudo):
    """Põe o conteúdo numa área com barra de rolagem (para nada ser cortado em telas pequenas)."""
    area = QScrollArea()
    area.setWidget(conteudo)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.setMinimumWidth(conteudo.minimumSizeHint().width() + area.verticalScrollBar().sizeHint().width())
    return area


class TelaNotinhas(QDialog):
    """Janela do editor. 'ao_salvar' é uma função chamada com o layout novo depois de salvar."""

    def __init__(self, pai, ao_salvar=None):
        super().__init__(pai)
        self.setWindowTitle("Configurar notinhas")
        self.resize(1320, 820)
        self.setModal(True)  # bloqueia a janela principal enquanto esta estiver aberta
        self.ao_salvar = ao_salvar

        self.dados = layout_notas.carregar_layout()
        self._dados_salvos = self._como_texto()  # para saber, ao fechar, se algo mudou
        self.chave_modelo = "loja"
        self._carregando = False   # True enquanto preenchemos a tela (não conta como alteração)
        self._modo_texto = False   # a impressora escolhida só imprime texto?
        self._nome_impressora = ""

        # Espera um instante antes de redesenhar: se várias mudanças chegarem juntas
        # (ex.: arrastando a barra do tamanho da logo), desenha uma vez só.
        self._timer_previa = QTimer(self)
        self._timer_previa.setSingleShot(True)
        self._timer_previa.setInterval(120)
        self._timer_previa.timeout.connect(self._atualizar_previa)

        self._criar_tela()
        self._carregar_impressao()
        self._carregar_modelo()
        self._ligar_sinais()

        atalho_salvar = QShortcut(QKeySequence.Save, self)  # Ctrl+S
        atalho_salvar.activated.connect(self.salvar)

    # ------------------------------------------------------------------
    # Montagem da tela
    # ------------------------------------------------------------------

    def _criar_tela(self):
        principal = QVBoxLayout(self)
        principal.setContentsMargins(16, 12, 16, 12)
        principal.setSpacing(10)

        # --- Topo: qual modelo está sendo editado ---
        topo = QHBoxLayout()
        titulo = QLabel("Editando:")
        titulo.setStyleSheet("font-weight: 600;")
        topo.addWidget(titulo)
        self.grupo_modelo = QButtonGroup(self)
        self.radios_modelo = {}
        for chave, nome in layout_notas.MODELOS.items():
            radio = QRadioButton(nome)
            self.grupo_modelo.addButton(radio)
            self.radios_modelo[chave] = radio
            topo.addWidget(radio)
        self.radios_modelo["loja"].setChecked(True)
        topo.addStretch(1)
        self.btn_copiar = QPushButton()
        self.btn_copiar.clicked.connect(self.copiar_para_outro)
        topo.addWidget(self.btn_copiar)
        principal.addLayout(topo)

        # --- As três colunas ---
        colunas = QHBoxLayout()
        colunas.setSpacing(12)
        colunas.addWidget(_rolavel(self._criar_coluna_textos()))
        colunas.addWidget(_rolavel(self._criar_coluna_opcoes()))
        colunas.addWidget(self._criar_coluna_previa(), 1)
        principal.addLayout(colunas, 1)

        # --- Botões de baixo ---
        rodape = QHBoxLayout()
        botao = QPushButton("Restaurar padrão")
        botao.clicked.connect(self.restaurar_padrao)
        rodape.addWidget(botao)
        botao = QPushButton("Imprimir teste")
        botao.clicked.connect(self.imprimir_teste)
        rodape.addWidget(botao)
        rodape.addStretch(1)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #247b50;")
        rodape.addWidget(self.lbl_status)
        botao = QPushButton("Salvar  Ctrl+S")
        botao.clicked.connect(self.salvar)
        rodape.addWidget(botao)
        botao = QPushButton("Fechar")
        botao.clicked.connect(self.reject)  # reject() = fechar (ver mais abaixo)
        rodape.addWidget(botao)
        principal.addLayout(rodape)

    def _criar_coluna_textos(self):
        coluna_widget = QWidget()
        coluna = QVBoxLayout(coluna_widget)
        coluna.setContentsMargins(0, 0, 4, 0)

        # --- Cabeçalho: só mostrar ou esconder (os dados vêm de Preferências › Loja) ---
        caixa = QGroupBox("Cabeçalho (dados da loja)")
        layout_cabecalho = QVBoxLayout(caixa)
        self.checks_cabecalho = {}
        for chave, rotulo in layout_notas.CAMPOS_CABECALHO:
            check = QCheckBox(rotulo)
            self.checks_cabecalho[chave] = check
            layout_cabecalho.addWidget(check)
        self.lbl_link_loja = QLabel('<a href="#">Alterar dados da loja</a>')
        self.lbl_link_loja.setTextFormat(Qt.RichText)
        self.lbl_link_loja.setCursor(Qt.PointingHandCursor)
        self.lbl_link_loja.linkActivated.connect(lambda _link: self.alterar_dados_da_loja())
        layout_cabecalho.addWidget(self.lbl_link_loja)
        coluna.addWidget(caixa)

        # --- Logo (a imagem também é dos dados da loja; aqui só se aparece e o tamanho) ---
        caixa = QGroupBox("Logo")
        layout_logo = QVBoxLayout(caixa)
        self.check_logo = QCheckBox("Mostrar logo na nota")
        layout_logo.addWidget(self.check_logo)
        self.lbl_logo = QLabel()
        self.lbl_logo.setObjectName("rotulo")
        self.lbl_logo.setWordWrap(True)
        layout_logo.addWidget(self.lbl_logo)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Tamanho"))
        self.slider_logo = QSlider(Qt.Horizontal)
        self.slider_logo.setRange(layout_notas.LOGO_MIN, layout_notas.LOGO_MAX)
        linha.addWidget(self.slider_logo, 1)
        self.lbl_tamanho_logo = QLabel()
        self.lbl_tamanho_logo.setMinimumWidth(44)
        linha.addWidget(self.lbl_tamanho_logo)
        layout_logo.addLayout(linha)
        coluna.addWidget(caixa)

        # --- Rodapé ---
        caixa = QGroupBox("Mensagem do rodapé")
        layout_rodape = QVBoxLayout(caixa)
        self.campo_rodape = QPlainTextEdit()
        self.campo_rodape.setFixedHeight(84)
        layout_rodape.addWidget(self.campo_rodape)
        coluna.addWidget(caixa)
        coluna.addStretch(1)
        return coluna_widget

    def _criar_coluna_opcoes(self):
        coluna_widget = QWidget()
        coluna = QVBoxLayout(coluna_widget)
        coluna.setContentsMargins(0, 0, 4, 0)

        # --- O que mostrar ---
        caixa = QGroupBox("Mostrar na nota")
        layout_mostrar = QVBoxLayout(caixa)
        self.checks_mostrar = {}
        for chave, rotulo in layout_notas.CAMPOS:
            check = QCheckBox(rotulo)
            self.checks_mostrar[chave] = check
            layout_mostrar.addWidget(check)
        coluna.addWidget(caixa)

        # --- Formato ---
        caixa = QGroupBox("Formato")
        formulario = QFormLayout(caixa)
        linha = QHBoxLayout()
        self.grupo_papel = QButtonGroup(self)
        self.radios_papel = {}
        for papel in layout_notas.PAPEIS:
            radio = QRadioButton(papel)
            self.grupo_papel.addButton(radio)
            self.radios_papel[papel] = radio
            linha.addWidget(radio)
        formulario.addRow("Papel", linha)
        self.spin_fonte = QSpinBox()
        self.spin_fonte.setRange(layout_notas.FONTE_MIN, layout_notas.FONTE_MAX)
        self.spin_fonte.setSuffix(" pt")
        formulario.addRow("Fonte", self.spin_fonte)
        linha = QHBoxLayout()
        self.grupo_alinhamento = QButtonGroup(self)
        self.radio_esquerda = QRadioButton("Esquerda")
        self.radio_centro = QRadioButton("Centro")
        for radio in (self.radio_esquerda, self.radio_centro):
            self.grupo_alinhamento.addButton(radio)
            linha.addWidget(radio)
        formulario.addRow("Alinhar", linha)
        dica = QLabel("Alinhamento do cabeçalho, logo e rodapé.")
        dica.setObjectName("rotulo")
        formulario.addRow(dica)
        coluna.addWidget(caixa)

        # --- Impressora (vale para as duas notas) ---
        caixa = QGroupBox("Impressora (vale para as duas notas)")
        layout_impressora = QVBoxLayout(caixa)
        self.combo_impressora = QComboBox()
        try:
            impressoras = impressao.listar_impressoras()
        except impressao.ErroImpressao:
            impressoras = []
        self.combo_impressora.addItems([TEXTO_IMPRESSORA_PADRAO, *impressoras])
        layout_impressora.addWidget(self.combo_impressora)
        linha = QHBoxLayout()
        linha.addWidget(QLabel("Modo"))
        self.combo_modo = QComboBox()
        for chave, nome in impressao.MODOS.items():
            self.combo_modo.addItem(nome, chave)
        linha.addWidget(self.combo_modo, 1)
        self.btn_detectar = QPushButton("Detectar")
        self.btn_detectar.setToolTip("Imprime uma página de teste em cada modo e diz qual funcionou.")
        self.btn_detectar.clicked.connect(self.detectar)
        linha.addWidget(self.btn_detectar)
        layout_impressora.addLayout(linha)
        self.lbl_impressora = QLabel()
        self.lbl_impressora.setObjectName("rotulo")
        self.lbl_impressora.setWordWrap(True)
        self.lbl_impressora.setMinimumWidth(280)
        layout_impressora.addWidget(self.lbl_impressora)
        self.widget_colunas = QWidget()
        linha = QHBoxLayout(self.widget_colunas)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.addWidget(QLabel("Letras por linha"))
        self.spin_colunas = QSpinBox()
        # (o menor valor aparece como "Automático": 32 no papel de 58mm, 48 no de 80mm)
        self.spin_colunas.setRange(layout_notas.COLUNAS_MIN - 1, layout_notas.COLUNAS_MAX)
        self.spin_colunas.setSpecialValueText("Automático (pelo papel)")
        linha.addWidget(self.spin_colunas, 1)
        layout_impressora.addWidget(self.widget_colunas)
        self.check_acentos = QCheckBox("Tirar acentos (se saírem letras estranhas)")
        layout_impressora.addWidget(self.check_acentos)

        # Opções que só existem no modo ESC/POS direto.
        self.widget_escpos = QWidget()
        layout_escpos = QFormLayout(self.widget_escpos)
        layout_escpos.setContentsMargins(0, 0, 0, 0)
        self.combo_pagina = QComboBox()
        for chave, (nome, _, _) in impressao.PAGINAS_CODIGO.items():
            self.combo_pagina.addItem(nome, chave)
        layout_escpos.addRow("Acentos", self.combo_pagina)
        self.check_cortar = QCheckBox("Cortar o papel no fim (se tiver guilhotina)")
        self.check_gaveta = QCheckBox("Abrir a gaveta de dinheiro ao finalizar")
        self.check_logo_escpos = QCheckBox("Imprimir a logo (em preto e branco)")
        self.check_letra_grande = QCheckBox("Nome da loja e TOTAL em letra grande")
        for check in (self.check_cortar, self.check_gaveta, self.check_logo_escpos, self.check_letra_grande):
            layout_escpos.addRow(check)
        layout_impressora.addWidget(self.widget_escpos)
        coluna.addWidget(caixa)
        coluna.addStretch(1)
        return coluna_widget

    def _criar_coluna_previa(self):
        caixa = QGroupBox("Pré-visualização")
        layout_previa = QVBoxLayout(caixa)

        linha = QHBoxLayout()
        linha.addWidget(QLabel("Exemplo pago em:"))
        self.grupo_exemplo = QButtonGroup(self)
        self.radio_exemplo_dinheiro = QRadioButton("Dinheiro (troco)")
        self.radio_exemplo_credito = QRadioButton("Crédito (taxa)")
        for radio in (self.radio_exemplo_dinheiro, self.radio_exemplo_credito):
            self.grupo_exemplo.addButton(radio)
            linha.addWidget(radio)
        self.radio_exemplo_dinheiro.setChecked(True)
        linha.addStretch(1)
        layout_previa.addLayout(linha)

        # A nota aparece como imagem dentro de uma área com rolagem, sobre um fundo cinza.
        self.lbl_imagem = QLabel()
        self.lbl_imagem.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.lbl_imagem.setStyleSheet("background: #9e979b; padding: 14px;")
        self.area_previa = QScrollArea()
        self.area_previa.setWidget(self.lbl_imagem)
        self.area_previa.setWidgetResizable(True)
        self.area_previa.setMinimumWidth(360)
        layout_previa.addWidget(self.area_previa, 1)

        self.lbl_info_previa = QLabel()
        self.lbl_info_previa.setObjectName("rotulo")
        self.lbl_info_previa.setWordWrap(True)
        layout_previa.addWidget(self.lbl_info_previa)
        return caixa

    def _ligar_sinais(self):
        """Qualquer mudança nas opções -> guarda no layout e atualiza a pré-visualização."""
        for check in self.checks_cabecalho.values():
            check.toggled.connect(self._alterou)
        self.campo_rodape.textChanged.connect(self._alterou)
        self.check_logo.toggled.connect(self._alterou)
        self.slider_logo.valueChanged.connect(self._alterou)
        for check in self.checks_mostrar.values():
            check.toggled.connect(self._alterou)
        self.grupo_papel.buttonToggled.connect(self._alterou)
        self.spin_fonte.valueChanged.connect(self._alterou)
        self.grupo_alinhamento.buttonToggled.connect(self._alterou)
        self.check_acentos.toggled.connect(self._alterou)
        self.spin_colunas.valueChanged.connect(self._alterou)
        self.combo_pagina.currentIndexChanged.connect(self._alterou)
        for check in (self.check_cortar, self.check_gaveta, self.check_logo_escpos, self.check_letra_grande):
            check.toggled.connect(self._alterou)
        self.combo_impressora.currentTextChanged.connect(self._trocar_impressora)
        self.combo_modo.currentIndexChanged.connect(self._trocar_impressora)
        self.grupo_modelo.buttonToggled.connect(self._trocar_modelo)
        self.grupo_exemplo.buttonToggled.connect(lambda *_: self._agendar_previa())

    # ------------------------------------------------------------------
    # Passar dados do layout para a tela e da tela para o layout
    # ------------------------------------------------------------------

    def _carregar_modelo(self):
        """Preenche os campos com o modelo atual (loja ou cliente)."""
        modelo = self.dados[self.chave_modelo]
        self._carregando = True
        for chave, check in self.checks_cabecalho.items():
            check.setChecked(modelo["mostrar"].get(chave, True))
        self.check_logo.setChecked(modelo["mostrar_logo"])
        self.slider_logo.setValue(modelo["tamanho_logo"])
        for chave, check in self.checks_mostrar.items():
            check.setChecked(modelo["mostrar"][chave])
        self.radios_papel[modelo["papel"]].setChecked(True)
        self.spin_fonte.setValue(modelo["tamanho_fonte"])
        (self.radio_centro if modelo["alinhamento"] == "centro" else self.radio_esquerda).setChecked(True)
        self.campo_rodape.setPlainText(modelo["rodape"])
        self._carregando = False

        outro = "cliente" if self.chave_modelo == "loja" else "loja"
        self.btn_copiar.setText(f"Copiar estas opções para a {layout_notas.MODELOS[outro]}")
        self.lbl_tamanho_logo.setText(f"{modelo['tamanho_logo']}%")
        self._mostrar_dados_da_loja()
        self._agendar_previa()

    def _mostrar_dados_da_loja(self):
        """Ao lado de cada caixa, o que a loja tem (vazio = não aparece mesmo marcado)."""
        modelo = self.dados[self.chave_modelo]
        for chave, rotulo in layout_notas.CAMPOS_CABECALHO:
            chave_modelo = next(c for c, caixa in layout_notas.MOSTRAR_CABECALHO.items() if caixa == chave)
            valor = modelo.get(chave_modelo, "").strip()
            self.checks_cabecalho[chave].setText(f"{rotulo}: {valor}" if valor else f"{rotulo} (não preenchido)")
        logo = modelo.get("logo", "")
        self.lbl_logo.setText(f"Imagem: {os.path.basename(logo)}" if logo else
                              "Nenhuma imagem: escolha em Alterar dados da loja.")

    def _carregar_impressao(self):
        opcoes = self.dados["impressao"]
        self._carregando = True
        nome = opcoes["impressora"] or TEXTO_IMPRESSORA_PADRAO
        if self.combo_impressora.findText(nome) < 0:
            self.combo_impressora.addItem(nome)  # impressora salva que não está mais instalada
        self.combo_impressora.setCurrentText(nome)
        self.check_acentos.setChecked(opcoes["tirar_acentos"])
        self.combo_modo.setCurrentIndex(max(self.combo_modo.findData(opcoes["modo"]), 0))
        self.spin_colunas.setValue(opcoes["colunas"] or self.spin_colunas.minimum())
        self.combo_pagina.setCurrentIndex(max(self.combo_pagina.findData(opcoes["pagina_codigo"]), 0))
        self.check_cortar.setChecked(opcoes["cortar_papel"])
        self.check_gaveta.setChecked(opcoes["abrir_gaveta"])
        self.check_logo_escpos.setChecked(opcoes["logo_escpos"])
        self.check_letra_grande.setChecked(opcoes["letra_grande"])
        self._carregando = False
        self._verificar_impressora()

    def _ler_tela(self):
        """Copia o que está na tela para o layout (na memória)."""
        modelo = self.dados[self.chave_modelo]
        modelo["rodape"] = self.campo_rodape.toPlainText()
        modelo["mostrar_logo"] = self.check_logo.isChecked()
        modelo["tamanho_logo"] = self.slider_logo.value()
        modelo["mostrar"] = {chave: check.isChecked()
                             for chave, check in {**self.checks_mostrar, **self.checks_cabecalho}.items()}
        modelo["tamanho_fonte"] = self.spin_fonte.value()
        modelo["alinhamento"] = "centro" if self.radio_centro.isChecked() else "esquerda"
        modelo["papel"] = next(papel for papel, radio in self.radios_papel.items() if radio.isChecked())

        impressora = self.combo_impressora.currentText()
        opcoes = self.dados["impressao"]
        opcoes["impressora"] = "" if impressora == TEXTO_IMPRESSORA_PADRAO else impressora
        opcoes["tirar_acentos"] = self.check_acentos.isChecked()
        opcoes["modo"] = self.combo_modo.currentData()
        colunas = self.spin_colunas.value()
        opcoes["colunas"] = 0 if colunas == self.spin_colunas.minimum() else colunas
        opcoes["pagina_codigo"] = self.combo_pagina.currentData()
        opcoes["cortar_papel"] = self.check_cortar.isChecked()
        opcoes["abrir_gaveta"] = self.check_gaveta.isChecked()
        opcoes["logo_escpos"] = self.check_logo_escpos.isChecked()
        opcoes["letra_grande"] = self.check_letra_grande.isChecked()

    def _alterou(self, *_):
        if self._carregando:
            return
        # O grupo de botões avisa duas vezes (um desmarca, outro marca); só seguimos com um marcado.
        if not any(radio.isChecked() for radio in self.radios_papel.values()):
            return
        self._ler_tela()
        self.lbl_tamanho_logo.setText(f"{self.dados[self.chave_modelo]['tamanho_logo']}%")
        self.lbl_status.setText("")
        self._agendar_previa()

    def _trocar_modelo(self, botao, marcado):
        if not marcado:
            return  # ignora o aviso do botão que foi desmarcado
        self.chave_modelo = next(chave for chave, radio in self.radios_modelo.items() if radio is botao)
        self._carregar_modelo()

    def _trocar_impressora(self, *_):
        if self._carregando:
            return
        self._ler_tela()
        self._verificar_impressora()
        self._agendar_previa()

    def _escpos(self):
        return self.dados["impressao"]["modo"] == impressao.MODO_ESCPOS

    def _verificar_impressora(self):
        """Descobre se a impressora escolhida só imprime texto e explica isso na tela."""
        escpos = self._escpos()
        self.widget_escpos.setVisible(escpos)
        try:
            self._nome_impressora = impressao.escolher_impressora(self.dados["impressao"]["impressora"])
            self._modo_texto = escpos or impressao.eh_impressora_texto(self._nome_impressora)
        except impressao.ErroImpressao as erro:
            self._nome_impressora = ""
            self._modo_texto = escpos
            self.widget_colunas.setVisible(escpos)
            self.lbl_impressora.setText(str(erro))
            return
        self.widget_colunas.setVisible(self._modo_texto)  # (letras por linha só valem nos modos de texto)
        if escpos:
            texto = (f"'{self._nome_impressora}': ESC/POS direto. Negrito, letra grande, corte do papel, "
                     "gaveta e logo em preto e branco pelos comandos da impressora térmica.")
        elif self._modo_texto:
            texto = (f"'{self._nome_impressora}' só imprime TEXTO: logo, tamanho da fonte e negrito "
                     "não saem nela. A pré-visualização já mostra como fica.")
        else:
            texto = f"'{self._nome_impressora}': impressora gráfica (logo e fonte funcionam)."
        if not self.dados["impressao"]["impressora"]:
            # O Windows pode trocar a impressora padrão sozinho (vira a última usada).
            texto += "\nDica: escolha a impressora pelo nome na lista, para a nota não ir parar em outra."
        self.lbl_impressora.setText(texto)

    def _como_texto(self):
        """O layout como texto, sem os dados da loja (eles se salvam sozinhos, em outro lugar)."""
        dados = layout_notas.copiar(self.dados)
        for chave in layout_notas.MODELOS:
            for chave_modelo in layout_notas.DADOS_DA_LOJA:
                dados[chave].pop(chave_modelo, None)
        return json.dumps(dados, sort_keys=True, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Pré-visualização
    # ------------------------------------------------------------------

    def _agendar_previa(self):
        self._timer_previa.start()  # se já estava contando, recomeça

    def resizeEvent(self, evento):
        # A janela mudou de tamanho: redesenha a nota para caber na área.
        super().resizeEvent(evento)
        self._agendar_previa()

    def _atualizar_previa(self):
        modelo = self.dados[self.chave_modelo]
        numero, atendimento, itens = self._dados_exemplo()
        colunas = notas.colunas_texto(self.dados, modelo) if self._modo_texto else None
        escpos = self.dados["impressao"] if self._escpos() else None
        linhas = notas.montar_linhas(modelo, numero, atendimento, itens, self.chave_modelo, self._modo_texto,
                                     colunas)
        imagem = notas.renderizar_imagem(modelo, linhas, self._modo_texto, colunas, escpos)

        # Diminui a imagem se ela for mais larga que a área de pré-visualização.
        largura_area = max(self.area_previa.viewport().width() - 40, 100)
        if imagem.width > largura_area:
            escala = largura_area / imagem.width
            imagem = imagem.resize((largura_area, round(imagem.height * escala)), Image.LANCZOS)
        self.lbl_imagem.setPixmap(_pil_para_pixmap(imagem))

        _, _, colunas = notas.medidas(modelo, self._modo_texto, colunas)
        info = f"Papel {modelo['papel']}  ·  {colunas} caracteres por linha"
        com_logo = escpos["logo_escpos"] if escpos else not self._modo_texto
        if modelo["mostrar_logo"] and com_logo and not layout_notas.caminho_logo(modelo):
            info += "  ·  Sem imagem da logo: escolha em Alterar dados da loja."
        self.lbl_info_previa.setText(info)

    def _dados_exemplo(self):
        """Um atendimento de mentira, só para a pré-visualização e o teste de impressão."""
        def item_unidade(nome, quantidade, preco, cobra_taxa=True):
            preco = Decimal(preco)
            return {"servico": nome, "tipo": "unidade", "quantidade": quantidade, "valor_unitario": preco,
                    "valor_digitado": Decimal("0"), "taxa_servico": Decimal("0"),
                    "total": arredondar(preco * quantidade), "cobra_taxa_maquininha": cobra_taxa}

        itens = [
            item_unidade("Xerox", 3, "0.50"),
            item_unidade("Impressão colorida", 2, "2.50"),
            # boleto: preço fixo e sem a taxa da maquininha (o valor do boleto é pago à parte)
            item_unidade("Pagamento de boletos", 2, "2.00", cobra_taxa=False),
        ]
        subtotal = sum(item["total"] for item in itens)
        base = base_da_taxa(itens)
        forma = "Crédito" if self.radio_exemplo_credito.isChecked() else "Dinheiro"
        if forma == "Crédito":
            percentual = Decimal("5")
            taxa = arredondar(base * percentual / 100)
            recebido = troco = None
        else:
            percentual = taxa = Decimal("0")
            recebido = Decimal("50")
            troco = recebido - subtotal
        atendimento = {
            "data_hora": datetime.now(),
            "cliente_nome": "Maria da Silva",
            "cliente_telefone": "(21) 99999-9999",
            "forma_pagamento": forma,
            "subtotal": subtotal,
            "taxa_percentual": percentual,
            "taxa_valor": taxa,
            "taxa_base": base,
            "total": subtotal + taxa,
            "valor_recebido": recebido,
            "troco": troco,
        }
        return 123, atendimento, itens

    # ------------------------------------------------------------------
    # Botões
    # ------------------------------------------------------------------

    def alterar_dados_da_loja(self):
        """O link "Alterar dados da loja": a mesma janela de Preferências › Loja."""
        dialogo = tela_loja.DialogoDadosLoja(self)
        if dialogo.exec() != QDialog.Accepted:
            return
        layout_notas.aplicar_loja(self.dados, config.carregar_config().loja)
        if dialogo.formulario.valores()["logo"] and not self.dados[self.chave_modelo]["mostrar_logo"]:
            self.check_logo.setChecked(True)  # acabou de escolher uma logo: já mostra
        self._mostrar_dados_da_loja()
        self._agendar_previa()
        pai = self.parent()
        if hasattr(pai, "loja_alterada"):
            pai.loja_alterada()  # título da janela principal e notas já com os dados novos

    def copiar_para_outro(self):
        outro = "cliente" if self.chave_modelo == "loja" else "loja"
        nome_atual = layout_notas.MODELOS[self.chave_modelo]
        nome_outro = layout_notas.MODELOS[outro]
        resposta = QMessageBox.question(self, "Copiar opções",
                                        f"Substituir todas as opções da {nome_outro} pelas da {nome_atual}?")
        if resposta == QMessageBox.Yes:
            self.dados[outro] = layout_notas.copiar(self.dados[self.chave_modelo])
            self.lbl_status.setText(f"Copiado para a {nome_outro} (falta salvar).")

    def restaurar_padrao(self):
        nome = layout_notas.MODELOS[self.chave_modelo]
        resposta = QMessageBox.question(self, "Restaurar padrão", f"Voltar a {nome} para as opções de fábrica?")
        if resposta == QMessageBox.Yes:
            self.dados[self.chave_modelo] = layout_notas.modelo_padrao(self.chave_modelo)
            layout_notas.aplicar_loja(self.dados, layout_notas.dados_da_loja())
            self._carregar_modelo()
            self.lbl_status.setText("Padrão restaurado (falta salvar).")

    def imprimir_teste(self):
        if not self._nome_impressora:
            QMessageBox.critical(self, "Imprimir teste", "Nenhuma impressora disponível.")
            return
        nome = layout_notas.MODELOS[self.chave_modelo]
        resposta = QMessageBox.question(self, "Imprimir teste",
                                        f"Imprimir um teste da {nome} em '{self._nome_impressora}'?")
        if resposta != QMessageBox.Yes:
            return
        numero, atendimento, itens = self._dados_exemplo()
        try:
            notas.imprimir_nota(self.dados, numero, atendimento, itens, self.chave_modelo)
        except impressao.ErroImpressao as erro:
            QMessageBox.critical(self, "Imprimir teste", str(erro))
            return
        self.lbl_status.setText("Teste enviado para a impressora.")

    def detectar(self):
        """
        Botão "Detectar": imprime uma página de teste em cada modo (ESC/POS e driver do
        Windows), pergunta se o papel saiu e escolhe o modo que funcionou (falta salvar).
        """
        if not self._nome_impressora:
            QMessageBox.critical(self, "Detectar", "Nenhuma impressora disponível.")
            return
        escpos, windows = impressao.MODOS[impressao.MODO_ESCPOS], impressao.MODOS[impressao.MODO_WINDOWS]
        resposta = QMessageBox.question(
            self, "Detectar", f"Imprimir duas páginas de teste em '{self._nome_impressora}', uma em cada "
            f"modo (\"{escpos}\" e \"{windows}\")?")
        if resposta != QMessageBox.Yes:
            return
        self._ler_tela()
        resultado = notas.detectar_modos(self.dados, self.chave_modelo)
        funcionou, relatorio = [], []
        for modo, erro in resultado.items():
            nome = impressao.MODOS[modo]
            if erro:
                relatorio.append(f"• {nome}: não deu certo.\n  {erro}")
                continue
            saiu = QMessageBox.question(
                self, "Detectar", f"Saiu o papel \"TESTE DE IMPRESSÃO\" com \"Modo: {nome}\", legível e "
                "com a régua numa linha só?")
            if saiu == QMessageBox.Yes:
                funcionou.append(modo)
                relatorio.append(f"• {nome}: funcionou.")
            else:
                relatorio.append(f"• {nome}: enviado, mas o papel não saiu certo.")
        if funcionou:
            # Os dois funcionaram: fica o ESC/POS (é o primeiro: tem corte, gaveta e letra grande).
            escolhido = funcionou[0]
            self.combo_modo.setCurrentIndex(self.combo_modo.findData(escolhido))
            relatorio.append(f"\nModo escolhido: \"{impressao.MODOS[escolhido]}\". "
                             "Clique em Salvar para manter.")
            self.lbl_status.setText(f"Detectado: {impressao.MODOS[escolhido]} (falta salvar).")
        else:
            relatorio.append("\nNenhum modo funcionou. Confira se a impressora está ligada, com papel, "
                             "instalada no Windows e se é a certa na lista.")
        QMessageBox.information(self, "Detectar", "\n".join(relatorio))

    def salvar(self):
        try:
            layout_notas.salvar_layout(self.dados)
        except OSError as erro:
            QMessageBox.critical(self, "Salvar", f"Não foi possível salvar:\n{erro}")
            return False
        self._dados_salvos = self._como_texto()
        self.lbl_status.setText("Configurações salvas!")
        if self.ao_salvar:
            self.ao_salvar(layout_notas.copiar(self.dados))
        return True

    def reject(self):
        """Chamada ao fechar (botão Fechar, Esc ou o X da janela)."""
        if self._como_texto() != self._dados_salvos:
            resposta = QMessageBox.question(
                self, "Configurar notinhas", "Salvar as alterações antes de fechar?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if resposta == QMessageBox.Cancel:
                return  # continua na tela
            if resposta == QMessageBox.Yes and not self.salvar():
                return
        super().reject()
