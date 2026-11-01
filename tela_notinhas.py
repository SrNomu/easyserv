"""
tela_notinhas.py - Tela "Configurar notinhas" (editor do layout das notas), em PySide6.

  ┌ Editando: (•) Nota da loja  ( ) Nota do cliente ─────────────────────────┐
  │ Cabeçalho          │ Mostrar na nota     │ Pré-visualização           │
  │ Logo               │ Formato             │ (redesenhada a cada        │
  │ Rodapé             │ Impressora          │  mudança nas opções)       │
  └ [Restaurar padrão] [Imprimir teste]                [Salvar] [Fechar] ┘

As mudanças ficam só na memória até clicar em "Salvar".
"""

import json
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
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

import impressao
import layout_notas
import notas
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

        # --- Cabeçalho ---
        caixa = QGroupBox("Cabeçalho")
        formulario = QFormLayout(caixa)
        self.campo_nome = QLineEdit()
        self.campo_endereco = QLineEdit()
        self.campo_telefone = QLineEdit()
        self.campo_cnpj = QLineEdit()
        formulario.addRow("Nome da loja", self.campo_nome)
        formulario.addRow("Endereço", self.campo_endereco)
        formulario.addRow("Telefone", self.campo_telefone)
        formulario.addRow("CNPJ", self.campo_cnpj)
        dica = QLabel("Deixe vazio o que não quiser na nota.")
        dica.setObjectName("rotulo")
        formulario.addRow(dica)
        coluna.addWidget(caixa)

        # --- Logo ---
        caixa = QGroupBox("Logo")
        layout_logo = QVBoxLayout(caixa)
        self.check_logo = QCheckBox("Mostrar logo na nota")
        layout_logo.addWidget(self.check_logo)
        linha = QHBoxLayout()
        self.campo_logo = QLineEdit()
        self.campo_logo.setReadOnly(True)
        linha.addWidget(self.campo_logo, 1)
        botao = QPushButton("Escolher...")
        botao.clicked.connect(self.escolher_logo)
        linha.addWidget(botao)
        botao = QPushButton("Remover")
        botao.clicked.connect(self.remover_logo)
        linha.addWidget(botao)
        layout_logo.addLayout(linha)
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
        self.lbl_impressora = QLabel()
        self.lbl_impressora.setObjectName("rotulo")
        self.lbl_impressora.setWordWrap(True)
        self.lbl_impressora.setMinimumWidth(280)
        layout_impressora.addWidget(self.lbl_impressora)
        self.check_acentos = QCheckBox("Tirar acentos (se a impressora de texto\nimprimir letras estranhas)")
        layout_impressora.addWidget(self.check_acentos)
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
        for campo in (self.campo_nome, self.campo_endereco, self.campo_telefone, self.campo_cnpj, self.campo_logo):
            campo.textChanged.connect(self._alterou)
        self.campo_rodape.textChanged.connect(self._alterou)
        self.check_logo.toggled.connect(self._alterou)
        self.slider_logo.valueChanged.connect(self._alterou)
        for check in self.checks_mostrar.values():
            check.toggled.connect(self._alterou)
        self.grupo_papel.buttonToggled.connect(self._alterou)
        self.spin_fonte.valueChanged.connect(self._alterou)
        self.grupo_alinhamento.buttonToggled.connect(self._alterou)
        self.check_acentos.toggled.connect(self._alterou)
        self.combo_impressora.currentTextChanged.connect(self._trocar_impressora)
        self.grupo_modelo.buttonToggled.connect(self._trocar_modelo)
        self.grupo_exemplo.buttonToggled.connect(lambda *_: self._agendar_previa())

    # ------------------------------------------------------------------
    # Passar dados do layout para a tela e da tela para o layout
    # ------------------------------------------------------------------

    def _carregar_modelo(self):
        """Preenche os campos com o modelo atual (loja ou cliente)."""
        modelo = self.dados[self.chave_modelo]
        self._carregando = True
        self.campo_nome.setText(modelo["nome_loja"])
        self.campo_endereco.setText(modelo["endereco"])
        self.campo_telefone.setText(modelo["telefone"])
        self.campo_cnpj.setText(modelo["cnpj"])
        self.check_logo.setChecked(modelo["mostrar_logo"])
        self.campo_logo.setText(modelo["logo"])
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
        self._agendar_previa()

    def _carregar_impressao(self):
        opcoes = self.dados["impressao"]
        self._carregando = True
        nome = opcoes["impressora"] or TEXTO_IMPRESSORA_PADRAO
        if self.combo_impressora.findText(nome) < 0:
            self.combo_impressora.addItem(nome)  # impressora salva que não está mais instalada
        self.combo_impressora.setCurrentText(nome)
        self.check_acentos.setChecked(opcoes["tirar_acentos"])
        self._carregando = False
        self._verificar_impressora()

    def _ler_tela(self):
        """Copia o que está na tela para o layout (na memória)."""
        modelo = self.dados[self.chave_modelo]
        modelo["nome_loja"] = self.campo_nome.text()
        modelo["endereco"] = self.campo_endereco.text()
        modelo["telefone"] = self.campo_telefone.text()
        modelo["cnpj"] = self.campo_cnpj.text()
        modelo["rodape"] = self.campo_rodape.toPlainText()
        modelo["mostrar_logo"] = self.check_logo.isChecked()
        modelo["logo"] = self.campo_logo.text()
        modelo["tamanho_logo"] = self.slider_logo.value()
        modelo["mostrar"] = {chave: check.isChecked() for chave, check in self.checks_mostrar.items()}
        modelo["tamanho_fonte"] = self.spin_fonte.value()
        modelo["alinhamento"] = "centro" if self.radio_centro.isChecked() else "esquerda"
        modelo["papel"] = next(papel for papel, radio in self.radios_papel.items() if radio.isChecked())

        impressora = self.combo_impressora.currentText()
        self.dados["impressao"]["impressora"] = "" if impressora == TEXTO_IMPRESSORA_PADRAO else impressora
        self.dados["impressao"]["tirar_acentos"] = self.check_acentos.isChecked()

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

    def _verificar_impressora(self):
        """Descobre se a impressora escolhida só imprime texto e explica isso na tela."""
        try:
            self._nome_impressora = impressao.escolher_impressora(self.dados["impressao"]["impressora"])
            self._modo_texto = impressao.eh_impressora_texto(self._nome_impressora)
        except impressao.ErroImpressao as erro:
            self._nome_impressora = ""
            self._modo_texto = False
            self.lbl_impressora.setText(str(erro))
            return
        if self._modo_texto:
            texto = (f"'{self._nome_impressora}' só imprime TEXTO: logo, tamanho da fonte e negrito "
                     "não saem nela. A pré-visualização já mostra como fica.")
        else:
            texto = f"'{self._nome_impressora}': impressora gráfica (logo e fonte funcionam)."
        if not self.dados["impressao"]["impressora"]:
            # O Windows pode trocar a impressora padrão sozinho (vira a última usada).
            texto += "\nDica: escolha a impressora pelo nome na lista, para a nota não ir parar em outra."
        self.lbl_impressora.setText(texto)

    def _como_texto(self):
        return json.dumps(self.dados, sort_keys=True, ensure_ascii=False)

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
        linhas = notas.montar_linhas(modelo, numero, atendimento, itens, self.chave_modelo, self._modo_texto)
        imagem = notas.renderizar_imagem(modelo, linhas, self._modo_texto)

        # Diminui a imagem se ela for mais larga que a área de pré-visualização.
        largura_area = max(self.area_previa.viewport().width() - 40, 100)
        if imagem.width > largura_area:
            escala = largura_area / imagem.width
            imagem = imagem.resize((largura_area, round(imagem.height * escala)), Image.LANCZOS)
        self.lbl_imagem.setPixmap(_pil_para_pixmap(imagem))

        _, _, colunas = notas.medidas(modelo, self._modo_texto)
        info = f"Papel {modelo['papel']}  ·  {colunas} caracteres por linha"
        if modelo["mostrar_logo"] and not self._modo_texto and not layout_notas.caminho_logo(modelo):
            info += "  ·  Logo não encontrada: escolha a imagem de novo."
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

    def escolher_logo(self):
        caminho, _filtro = QFileDialog.getOpenFileName(
            self, "Escolher logo", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.gif);;Todos os arquivos (*.*)")
        if not caminho:
            return  # a pessoa cancelou
        try:
            with Image.open(caminho) as imagem:
                imagem.verify()  # confere se é mesmo uma imagem válida
            relativo = layout_notas.guardar_logo(caminho, self.chave_modelo)
        except OSError as erro:
            QMessageBox.critical(self, "Logo", f"Não foi possível usar esta imagem:\n{erro}")
            return
        self.campo_logo.setText(relativo)
        self.check_logo.setChecked(True)

    def remover_logo(self):
        self.campo_logo.setText("")
        self.check_logo.setChecked(False)

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
