"""
tela_cores.py - Tela "Cores do programa" (menu Exibir › Cores do programa...).

A pessoa escolhe 5 cores (principal, destaque, fundo, texto e botão Finalizar)
para o modo claro e para o modo escuro, ou usa um tema. Ao lado, uma
pré-visualização mostra pedaços de verdade da tela (botões de serviço,
pagamento, total, Finalizar, teclado) já com as cores novas.

Temas: os prontos (Padrão, Azul, Verde, Escuro) e os que a pessoa salvou com
"Salvar como tema...". Os salvos podem ser excluídos; os prontos não.

As cores do programa só mudam ao apertar "Salvar". "Cancelar" desiste delas
(um tema salvo ou excluído com os botões de tema já fica gravado na hora).
"""

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
)

import estilo

# Quantos botões de tema cabem numa linha (os temas salvos continuam na linha de baixo).
TEMAS_POR_LINHA = 4
TAMANHO_MAXIMO_NOME = 30


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


def _icone_tema(cores):
    """Um ícone com 3 bolinhas (fundo, destaque e principal) para o botão do tema."""
    pixmap = QPixmap(54, 18)
    pixmap.fill(Qt.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.Antialiasing)
    for i, chave in enumerate(("fundo", "destaque", "principal")):
        pintor.setPen(QColor(estilo.misturar(cores[chave], cores["texto"], 0.25)))
        pintor.setBrush(QColor(cores[chave]))
        pintor.drawEllipse(1 + i * 18, 1, 16, 16)
    pintor.end()
    return QIcon(pixmap)


class TelaCores(QDialog):
    """
    pai       = a janela principal;
    cores     = as cores atuais {"claro": {...}, "escuro": {...}};
    modo      = o modo que está aparecendo agora ("claro" ou "escuro");
    ao_salvar = função chamada com as cores novas quando a pessoa aperta Salvar;
    temas_salvos   = {"nome": cores} salvos pela pessoa;
    ao_mudar_temas = função chamada com o dicionário novo de temas salvos
                     (depois de "Salvar como tema..." ou "Excluir").
    """

    def __init__(self, pai, cores, modo, ao_salvar, temas_salvos=None, ao_mudar_temas=None):
        super().__init__(pai)
        self.setWindowTitle("Cores do programa")
        self.cores = copy.deepcopy(cores)   # trabalhamos numa cópia até salvar
        self.modo = modo                    # modo cujas cores estão sendo editadas
        self.ao_salvar = ao_salvar
        self.temas_salvos = copy.deepcopy(temas_salvos or {})
        self.ao_mudar_temas = ao_mudar_temas
        self.botoes_cor = {}                # chave -> botão com a amostra da cor
        self.campos_cor = {}                # chave -> campo com o código (#8c2f57)
        self.botoes_tema = {}               # nome do tema -> botão

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(12)

        # --- Temas (prontos e salvos) ---
        caixa_temas = QGroupBox("Temas")
        coluna_temas = QVBoxLayout(caixa_temas)
        coluna_temas.setSpacing(8)
        self.grade_temas = QGridLayout()
        self.grade_temas.setSpacing(8)
        coluna_temas.addLayout(self.grade_temas)
        linha_botoes_tema = QHBoxLayout()
        self.btn_salvar_tema = QPushButton("Salvar como tema...")
        self.btn_salvar_tema.setToolTip("Guarda as cores atuais (dos dois modos) com um nome")
        self.btn_salvar_tema.clicked.connect(self.salvar_como_tema)
        linha_botoes_tema.addWidget(self.btn_salvar_tema)
        self.btn_excluir_tema = QPushButton("Excluir tema")
        self.btn_excluir_tema.clicked.connect(self.excluir_tema)
        linha_botoes_tema.addWidget(self.btn_excluir_tema)
        self.lbl_temas = _rotulo("", "rotulo")
        linha_botoes_tema.addWidget(self.lbl_temas, 1)
        coluna_temas.addLayout(linha_botoes_tema)
        coluna.addWidget(caixa_temas)
        self._montar_temas()

        meio = QHBoxLayout()
        meio.setSpacing(12)
        coluna.addLayout(meio, 1)

        # --- As 5 cores ---
        caixa_cores = QGroupBox("Cores")
        grade = QGridLayout(caixa_cores)
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(10)

        linha_modo = QHBoxLayout()
        linha_modo.setSpacing(16)
        linha_modo.addWidget(_rotulo("Editar as cores do modo:"))
        self.grupo_modo = QButtonGroup(self)
        for valor, texto in (("claro", "Claro"), ("escuro", "Escuro")):
            radio = QRadioButton(texto)
            radio.setChecked(valor == modo)
            radio.toggled.connect(lambda marcado, valor=valor: marcado and self._trocar_modo(valor))
            self.grupo_modo.addButton(radio)
            linha_modo.addWidget(radio)
        linha_modo.addStretch(1)
        grade.addLayout(linha_modo, 0, 0, 1, 3)

        for i, (chave, nome, dica) in enumerate(estilo.CAMPOS_CORES, start=1):
            amostra = QPushButton()
            amostra.setFixedSize(44, 32)
            amostra.setToolTip("Clique para escolher a cor")
            amostra.clicked.connect(lambda _marcado=False, chave=chave: self.escolher_cor(chave))
            grade.addWidget(amostra, i, 0)
            textos = QVBoxLayout()
            textos.setSpacing(0)
            textos.addWidget(_rotulo(nome))
            textos.addWidget(_rotulo(dica, "rotulo"))
            grade.addLayout(textos, i, 1)
            campo = QLineEdit()
            campo.setMaxLength(7)
            campo.setFixedWidth(100)
            campo.setToolTip("Código da cor, ex.: #8c2f57")
            campo.editingFinished.connect(lambda chave=chave: self._codigo_digitado(chave))
            grade.addWidget(campo, i, 2)
            self.botoes_cor[chave] = amostra
            self.campos_cor[chave] = campo
        grade.setColumnStretch(1, 1)

        self.lbl_aviso = _rotulo("", "aviso")
        self.lbl_aviso.setWordWrap(True)
        grade.addWidget(self.lbl_aviso, len(estilo.CAMPOS_CORES) + 1, 0, 1, 3)
        grade.addWidget(_rotulo("O modo que aparece na tela (Claro, Escuro ou Seguir o\n"
                                "Windows) é escolhido no menu Exibir › Modo de cor.", "rotulo"),
                        len(estilo.CAMPOS_CORES) + 2, 0, 1, 3)
        grade.setRowStretch(len(estilo.CAMPOS_CORES) + 3, 1)
        meio.addWidget(caixa_cores)

        # --- Pré-visualização ---
        caixa_previa = QGroupBox("Pré-visualização")
        coluna_previa = QVBoxLayout(caixa_previa)
        self.previa = self._criar_previa()
        coluna_previa.addWidget(self.previa)
        meio.addWidget(caixa_previa, 1)

        # --- Botões de baixo ---
        botoes = QHBoxLayout()
        btn_padrao = QPushButton("Restaurar padrão")
        btn_padrao.setToolTip("Volta para o tema Padrão (nos dois modos)")
        btn_padrao.clicked.connect(lambda: self.usar_tema(estilo.TEMA_PADRAO))
        botoes.addWidget(btn_padrao)
        botoes.addStretch(1)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        botoes.addWidget(btn_cancelar)
        btn_salvar = QPushButton("Salvar  Ctrl+S")
        btn_salvar.setObjectName("finalizar")
        btn_salvar.clicked.connect(self.salvar)
        botoes.addWidget(btn_salvar)
        coluna.addLayout(botoes)
        atalho = QShortcut(QKeySequence("Ctrl+S"), self)
        atalho.activated.connect(self.salvar)

        self._atualizar()

    # ------------------------------------------------------------------
    # Pré-visualização
    # ------------------------------------------------------------------

    def _criar_previa(self):
        """Pedaços da tela principal, feitos com os mesmos tipos de botão e rótulo."""
        fundo = QFrame()
        fundo.setObjectName("previaFundo")
        coluna = QVBoxLayout(fundo)
        coluna.setContentsMargins(12, 12, 12, 12)
        coluna.setSpacing(10)

        # Cartão 1: serviços e item
        cartao = QFrame()
        cartao.setObjectName("painel")
        c1 = QVBoxLayout(cartao)
        c1.setContentsMargins(12, 8, 12, 12)
        c1.setSpacing(6)
        c1.addWidget(_rotulo("Consulta", "grupo"))
        c1.addWidget(self._botao_servico("7", "Consulta RioCard", "R$ 3,00", selecionado=True))
        c1.addWidget(_rotulo("RecargaPay", "grupo"))
        c1.addWidget(self._botao_servico("8", "Recarga RioCard", "valor + R$ 1,00"))
        c1.addSpacing(4)
        c1.addWidget(_rotulo("Consulta RioCard", "servicoAtual"))
        linha = QHBoxLayout()
        campo = QLineEdit("2")
        campo.setFocusPolicy(Qt.NoFocus)
        linha.addWidget(campo, 1)
        linha.addWidget(_rotulo("= R$ 6,00", "previa"))
        c1.addLayout(linha)
        coluna.addWidget(cartao)

        # Cartão 2: pagamento, total, finalizar e teclado
        cartao2 = QFrame()
        cartao2.setObjectName("painel")
        c2 = QGridLayout(cartao2)
        c2.setContentsMargins(12, 10, 12, 12)
        c2.setHorizontalSpacing(8)
        c2.setVerticalSpacing(8)
        for i, (texto, marcado) in enumerate((("Dinheiro · F5", True), ("Pix · F6", False))):
            botao = QPushButton(texto)
            botao.setProperty("papel", "forma")
            botao.setCheckable(True)
            botao.setChecked(marcado)
            botao.setFocusPolicy(Qt.NoFocus)
            c2.addWidget(botao, 0, i)
        c2.addWidget(_rotulo("Total", "rotuloTotal"), 1, 0, Qt.AlignBottom)
        c2.addWidget(_rotulo("R$ 6,00", "total"), 1, 1, Qt.AlignRight)
        troco = _rotulo("Troco: R$ 4,00", "troco")
        troco.setProperty("estado", "positivo")
        c2.addWidget(troco, 2, 0, 1, 2)
        check = QCheckBox("Imprimir nota do cliente")
        check.setChecked(True)
        check.setFocusPolicy(Qt.NoFocus)
        c2.addWidget(check, 3, 0, 1, 2)
        finalizar = QPushButton("Finalizar  F12")
        finalizar.setObjectName("finalizar")
        finalizar.setFocusPolicy(Qt.NoFocus)
        c2.addWidget(finalizar, 4, 0, 1, 2)
        teclas = QHBoxLayout()
        teclas.setSpacing(6)
        for texto, papel in (("7", "tecla"), ("8", "tecla"), ("⌫", "tecla-acao"), ("↵", "tecla-enter")):
            tecla = QPushButton(texto)
            tecla.setProperty("papel", papel)
            tecla.setFocusPolicy(Qt.NoFocus)
            tecla.setMinimumSize(48, 48)
            teclas.addWidget(tecla)
        c2.addLayout(teclas, 5, 0, 1, 2)
        coluna.addWidget(cartao2)
        coluna.addStretch(1)
        return fundo

    @staticmethod
    def _botao_servico(tecla, nome, preco, selecionado=False):
        """Igual ao botão de serviço da tela principal (tecla, nome e preço)."""
        botao = QPushButton()
        botao.setProperty("papel", "servico")
        botao.setProperty("selecionado", selecionado)
        botao.setFocusPolicy(Qt.NoFocus)
        linha = QHBoxLayout(botao)
        linha.setContentsMargins(12, 10, 12, 10)
        linha.setSpacing(10)
        linha.addWidget(_rotulo(tecla, "teclaServico"))
        linha.addWidget(_rotulo(nome, "nomeServico"))
        linha.addStretch(1)
        linha.addWidget(_rotulo(preco, "precoServico"))
        botao.setMinimumHeight(linha.sizeHint().height())
        return botao

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _trocar_modo(self, modo):
        self.modo = modo
        self._atualizar()

    def _todos_os_temas(self):
        """Os prontos primeiro, depois os salvos (em ordem alfabética)."""
        temas = dict(estilo.TEMAS)
        for nome in sorted(self.temas_salvos, key=str.casefold):
            temas[nome] = self.temas_salvos[nome]
        return temas

    def _montar_temas(self):
        """(Re)cria os botões de tema: usado ao abrir e depois de salvar/excluir um tema."""
        for botao in self.botoes_tema.values():
            self.grade_temas.removeWidget(botao)
            botao.deleteLater()
        self.botoes_tema = {}
        for i, nome in enumerate(self._todos_os_temas()):
            botao = QPushButton(nome)
            botao.setProperty("papel", "forma")  # mesmo visual das formas de pagamento
            botao.setCheckable(True)
            botao.setAutoDefault(False)
            botao.setIconSize(QSize(54, 18))  # o ícone com as 3 bolinhas de cor
            botao.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            if nome in self.temas_salvos:
                botao.setToolTip("Tema salvo por você")
            botao.clicked.connect(lambda _marcado=False, nome=nome: self.usar_tema(nome))
            self.grade_temas.addWidget(botao, i // TEMAS_POR_LINHA, i % TEMAS_POR_LINHA)
            self.botoes_tema[nome] = botao
        for coluna in range(TEMAS_POR_LINHA):
            self.grade_temas.setColumnStretch(coluna, 1)  # todos os botões da mesma largura

    def usar_tema(self, nome):
        """Usa as cores de um tema (nos dois modos)."""
        self.cores = copy.deepcopy(self._todos_os_temas()[nome])
        self._atualizar()

    def salvar_como_tema(self):
        """Guarda as cores atuais (claro e escuro) com um nome, junto dos temas prontos."""
        atual = estilo.nome_do_tema(self.cores, self.temas_salvos)
        sugestao = atual if atual in self.temas_salvos else ""
        nome, ok = QInputDialog.getText(self, "Salvar como tema",
                                        "Nome do tema (guarda as cores do modo claro e do escuro):",
                                        text=sugestao)
        nome = " ".join(nome.split())  # tira espaços sobrando
        if not ok or not nome:
            return
        if len(nome) > TAMANHO_MAXIMO_NOME:
            QMessageBox.warning(self, "Salvar como tema",
                                f"Use um nome com até {TAMANHO_MAXIMO_NOME} letras.")
            return
        if any(nome.casefold() == pronto.casefold() for pronto in estilo.TEMAS):
            QMessageBox.warning(self, "Salvar como tema",
                                f"\"{nome}\" é o nome de um tema pronto. Escolha outro nome.")
            return
        # Mesmo nome com maiúsculas diferentes conta como o mesmo tema.
        existente = next((n for n in self.temas_salvos if n.casefold() == nome.casefold()), None)
        if existente is not None:
            resposta = QMessageBox.question(self, "Salvar como tema",
                                            f"Já existe um tema \"{existente}\". Substituir pelas cores atuais?")
            if resposta != QMessageBox.Yes:
                return
            del self.temas_salvos[existente]
        self.temas_salvos[nome] = copy.deepcopy(self.cores)
        self._temas_mudaram()
        self.lbl_temas.setText(f"Tema \"{nome}\" salvo.")

    def excluir_tema(self):
        """Exclui o tema salvo que está marcado (os prontos não podem ser excluídos)."""
        nome = estilo.nome_do_tema(self.cores, self.temas_salvos)
        if nome not in self.temas_salvos:
            return
        resposta = QMessageBox.question(self, "Excluir tema",
                                        f"Excluir o tema \"{nome}\"? As cores que estão na tela continuam "
                                        "as mesmas até você escolher outras.")
        if resposta != QMessageBox.Yes:
            return
        del self.temas_salvos[nome]
        self._temas_mudaram()
        self.lbl_temas.setText(f"Tema \"{nome}\" excluído.")

    def _temas_mudaram(self):
        if self.ao_mudar_temas:
            self.ao_mudar_temas(copy.deepcopy(self.temas_salvos))
        self._montar_temas()
        self._atualizar()

    def escolher_cor(self, chave):
        """Abre o seletor de cor do Qt."""
        nome = dict((c, n) for c, n, _d in estilo.CAMPOS_CORES)[chave]
        cor = QColorDialog.getColor(QColor(self.cores[self.modo][chave]), self, f"Escolher: {nome}")
        if cor.isValid():  # inválida = a pessoa cancelou
            self.cores[self.modo][chave] = cor.name()
            self._atualizar()

    def _codigo_digitado(self, chave):
        """A pessoa digitou o código da cor (ex.: #8c2f57). Se não for válido, volta o anterior."""
        texto = self.campos_cor[chave].text().strip()
        if texto and not texto.startswith("#"):
            texto = "#" + texto
        if len(texto) == 7 and QColor.isValidColorName(texto):
            self.cores[self.modo][chave] = QColor(texto).name()
        self._atualizar()

    def _atualizar(self):
        """Redesenha amostras, códigos, temas marcados, avisos e a pré-visualização."""
        jogo = self.cores[self.modo]
        borda = estilo.misturar(jogo["fundo"], jogo["texto"], 0.35)
        for chave, botao in self.botoes_cor.items():
            botao.setStyleSheet(f"QPushButton {{ background: {jogo[chave]}; border: 1px solid {borda};"
                                " border-radius: 6px; }")
            self.campos_cor[chave].setText(jogo[chave])

        tema_atual = estilo.nome_do_tema(self.cores, self.temas_salvos)
        temas = self._todos_os_temas()
        for nome, botao in self.botoes_tema.items():
            botao.setChecked(nome == tema_atual)
            botao.setIcon(_icone_tema(temas[nome][self.modo]))
        # Só dá para excluir um tema salvo (e só o que está marcado).
        salvo = tema_atual in self.temas_salvos
        self.btn_excluir_tema.setEnabled(salvo)
        self.btn_excluir_tema.setText(f"Excluir \"{tema_atual}\"" if salvo else "Excluir tema")
        self.btn_excluir_tema.setToolTip("" if salvo else
                                         "Escolha um tema salvo por você para excluir (os prontos não saem)")

        self.lbl_aviso.setText(self._avisos(jogo))
        k = estilo.cores_derivadas(jogo)
        self.previa.setPalette(estilo.paleta(jogo))
        self.previa.setStyleSheet(
            estilo.folha_de_estilo(jogo)
            + f"QFrame#previaFundo {{ background: {k.fundo}; border-radius: 8px; }}"
        )

    @staticmethod
    def _avisos(jogo):
        """Avisa quando alguma combinação fica difícil de ler."""
        k = estilo.cores_derivadas(jogo)
        avisos = []
        if estilo.contraste(k.texto, k.superficie) < 4.5 or estilo.contraste(k.texto, k.fundo) < 4.5:
            avisos.append("o texto está com pouco contraste com o fundo")
        # (o TOTAL é grande e em negrito; para letra grande, 3 já é suficiente)
        if estilo.contraste(k.principal, k.superficie) < 3:
            avisos.append("a cor principal está difícil de ler sobre os painéis")
        if estilo.contraste(k.destaque, k.superficie) < 1.08:
            avisos.append("a cor de destaque quase não aparece sobre os painéis")
        if not avisos:
            return ""
        return "Atenção: " + "; ".join(avisos) + "."

    def salvar(self):
        self.ao_salvar(copy.deepcopy(self.cores))
        self.accept()
