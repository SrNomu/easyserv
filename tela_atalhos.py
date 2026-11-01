"""
tela_atalhos.py - Tela "Atalhos do teclado" (menu Ajuda › Atalhos do teclado...).

Mostra todas as ações do programa com a tecla de cada uma. Para trocar:
clique na tecla (ou selecione com Tab e aperte Enter) e aperte a tecla nova.
Serve qualquer tecla que o Windows reconheça, inclusive as teclas
programáveis de teclado de PDV (F13 a F24, combinações com Ctrl/Alt...).

Se a tecla nova já for de outra ação, aparece um aviso em vermelho na linha:
apertando a mesma tecla de novo ela passa para cá e a outra ação fica sem
atalho. Nada é gravado até clicar em Salvar.

Esta tela não usa janelas de mensagem do Windows (que fazem barulho): todos os
avisos aparecem escritos na própria tela.
"""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import atalhos
from estilo import repintar

# Como as ações aparecem separadas na tela: (título da caixa, ações, coluna 0 ou 1).
# ("Serviços" é montado na hora: uma linha por serviço cadastrado.)
GRUPOS = [
    ("Serviços", None, 0),
    ("Tela", ["teclado", "relatorio"], 0),
    ("Atendimento", ["nome", "telefone", "recebido", "finalizar", "remover", "cancelar"], 1),
    ("Pagamento", ["dinheiro", "pix", "debito", "credito"], 1),
]

TEXTO_CAPTURANDO = "Aperte a tecla..."


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


class TelaAtalhos(QDialog):
    """
    pai             = a janela principal;
    teclas          = {"acao": "tecla"} atuais;
    servicos        = [(id, nome), ...] dos serviços ativos, na ordem da tela;
    ao_salvar       = função chamada com o dicionário novo {"acao": "tecla"}.
    """

    def __init__(self, pai, teclas, servicos, ao_salvar):
        super().__init__(pai)
        self.setWindowTitle("Atalhos do teclado")
        self.ao_salvar = ao_salvar
        self.originais = dict(teclas)
        self.ids_servicos = [id_servico for id_servico, _nome in servicos]
        nomes = {atalhos.acao_do_servico(id_servico): f"{posicao}. {nome}"
                 for posicao, (id_servico, nome) in enumerate(servicos, start=1)}
        # Teclas de fábrica (para a dica e para o "Restaurar atalhos padrão").
        self.padrao = atalhos.completar({}, self.ids_servicos)
        self.teclas = dict(teclas)
        self.capturando = None     # ação que está esperando a tecla nova
        self.pendente = None       # tecla já usada por outra ação, esperando confirmação
        self._pode_descartar = False
        # Cada linha da tela: acao -> {"botao", "limpar", "aviso", "descricao"}
        self.linhas = {}

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(10)
        explicacao = _rotulo(
            "Para trocar um atalho, clique na tecla dele e aperte a tecla nova (vale também tecla "
            "programável de teclado de PDV e combinações com Ctrl ou Alt). Números, letras e Delete "
            "não funcionam como atalho enquanto o cursor está num campo de texto; F1 a F24, Esc e "
            "combinações com Ctrl/Alt funcionam sempre.", "rotulo")
        explicacao.setWordWrap(True)
        coluna.addWidget(explicacao)

        # --- Ações, em duas colunas (com rolagem, se a tela for pequena) ---
        conteudo = QWidget()
        colunas = QHBoxLayout(conteudo)
        colunas.setContentsMargins(0, 0, 0, 0)
        colunas.setSpacing(12)
        esquerda, direita = QVBoxLayout(), QVBoxLayout()
        for titulo, acoes, lado in GRUPOS:
            if acoes is None:
                acoes = list(nomes)
            caixa = QGroupBox(titulo)
            grade = QGridLayout(caixa)
            grade.setHorizontalSpacing(10)
            grade.setVerticalSpacing(2)
            grade.setColumnStretch(0, 1)
            for acao in acoes:
                self._adicionar_linha(grade, acao, nomes.get(acao) or atalhos.DESCRICOES[acao])
            (esquerda if lado == 0 else direita).addWidget(caixa)
        esquerda.addStretch(1)
        direita.addStretch(1)
        colunas.addLayout(esquerda, 1)
        colunas.addLayout(direita, 1)
        self.conteudo = conteudo
        self.rolagem = rolagem = QScrollArea()
        rolagem.setWidget(conteudo)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.setMinimumWidth(conteudo.sizeHint().width() + rolagem.verticalScrollBar().sizeHint().width())
        coluna.addWidget(rolagem, 1)

        fixas = _rotulo("Fixas (não mudam): Enter adiciona o item e aperta o botão selecionado · "
                        "Tab passa para o próximo campo.", "rotulo")
        fixas.setWordWrap(True)
        coluna.addWidget(fixas)
        # Recado geral embaixo (ex.: "teclas de fábrica de volta", "aperte Esc de novo...").
        # (o espaço dele fica sempre reservado, para a tela não "pular" quando ele aparece)
        self.lbl_recado = _rotulo("", "aviso")
        self.lbl_recado.setWordWrap(True)
        self.lbl_recado.ensurePolished()
        self.lbl_recado.setMinimumHeight(self.lbl_recado.fontMetrics().height() + 2)
        coluna.addWidget(self.lbl_recado)

        # --- Botões de baixo ---
        botoes = QHBoxLayout()
        btn_padrao = QPushButton("Restaurar atalhos padrão")
        btn_padrao.clicked.connect(self.restaurar_padrao)
        botoes.addWidget(btn_padrao)
        botoes.addStretch(1)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        botoes.addWidget(btn_cancelar)
        self.btn_salvar = QPushButton("Salvar")
        self.btn_salvar.setObjectName("finalizar")
        self.btn_salvar.clicked.connect(self.salvar)
        botoes.addWidget(self.btn_salvar)
        coluna.addLayout(botoes)
        for botao in self.findChildren(QPushButton):
            botao.setAutoDefault(False)  # Enter não aperta o "Salvar" sozinho

        self.resize(max(self.sizeHint().width(), 820), self.sizeHint().height())
        self._tamanho_acertado = False

        # Escuta as teclas do programa todo enquanto espera a tecla nova
        # (senão Esc fecharia a tela e Tab mudaria de campo).
        QApplication.instance().installEventFilter(self)
        QApplication.instance().focusChanged.connect(self._foco_mudou)
        self._atualizar_todas()
        next(iter(self.linhas.values()))["botao"].setFocus()

    def showEvent(self, evento):
        """Ao aparecer, fica alta o bastante para mostrar tudo sem rolar (sem passar da tela)."""
        super().showEvent(evento)
        if self._tamanho_acertado:
            return
        self._tamanho_acertado = True
        # (só agora as medidas valem: o estilo, com as bordas e espaços, já foi aplicado)
        self.layout().activate()
        falta = self.conteudo.sizeHint().height() - self.rolagem.viewport().height()
        tela = self.screen().availableGeometry()
        if falta > 0:
            self.resize(self.width(), min(self.height() + falta + 4, tela.height() - 60))
            # centraliza de novo na tela, já com o tamanho final
            self.move(self.x(), max(tela.top() + 20, tela.center().y() - self.height() // 2))

    def _adicionar_linha(self, grade, acao, descricao):
        """Uma linha: o que faz | [tecla] [sem atalho]; aviso embaixo (escondido)."""
        linha = grade.rowCount()
        grade.addWidget(QLabel(descricao), linha, 0)
        botao = QPushButton()
        botao.setProperty("papel", "atalho")
        botao.setToolTip(f"Clique e aperte a tecla nova. De fábrica: "
                         f"{atalhos.texto_para_mostrar(self.padrao[acao])}")
        botao.clicked.connect(lambda _marcado=False, acao=acao: self.iniciar_captura(acao))
        grade.addWidget(botao, linha, 1)
        limpar = QPushButton("Sem atalho")
        limpar.setToolTip("Deixa esta ação sem tecla de atalho")
        limpar.clicked.connect(lambda _marcado=False, acao=acao: self.definir_tecla(acao, ""))
        grade.addWidget(limpar, linha, 2)
        aviso = _rotulo("", "aviso")
        aviso.setWordWrap(True)
        aviso.hide()
        grade.addWidget(aviso, linha + 1, 0, 1, 3)
        self.linhas[acao] = {"botao": botao, "limpar": limpar, "aviso": aviso, "descricao": descricao}

    # ------------------------------------------------------------------
    # Mostrar
    # ------------------------------------------------------------------

    def _atualizar_botao(self, acao):
        botao = self.linhas[acao]["botao"]
        capturando = acao == self.capturando
        botao.setText(TEXTO_CAPTURANDO if capturando else atalhos.texto_para_mostrar(self.teclas[acao]))
        botao.setProperty("capturando", capturando)
        botao.setProperty("vazio", not self.teclas[acao] and not capturando)
        repintar(botao)

    def _atualizar_todas(self):
        for acao in self.linhas:
            self._atualizar_botao(acao)

    def _avisar(self, acao, texto, erro=True):
        """Escreve um aviso embaixo da linha (vermelho = erro; cinza = informação). "" esconde."""
        aviso = self.linhas[acao]["aviso"]
        aviso.setText(texto)
        aviso.setObjectName("aviso" if erro else "rotulo")
        repintar(aviso)
        aviso.setVisible(bool(texto))

    def _marcar_conflito(self, acao, ligado):
        botao = self.linhas[acao]["botao"]
        botao.setProperty("erro", ligado)
        repintar(botao)

    def _recado(self, texto, erro=True):
        """Recado geral embaixo da lista (vermelho = atenção; cinza = informação)."""
        self.lbl_recado.setText(texto)
        self.lbl_recado.setObjectName("aviso" if erro else "rotulo")
        repintar(self.lbl_recado)

    def _limpar_avisos(self):
        for acao in self.linhas:
            self._avisar(acao, "")
            self._marcar_conflito(acao, False)

    def _dono_da_tecla(self, tecla, menos=None):
        """Qual outra ação já usa esta tecla (ou None)."""
        for acao, atual in self.teclas.items():
            if acao != menos and tecla and atual == tecla:
                return acao
        return None

    # ------------------------------------------------------------------
    # Capturar a tecla nova
    # ------------------------------------------------------------------

    def iniciar_captura(self, acao):
        """Clique na tecla: começa a esperar a tecla nova. Clicar de novo desiste."""
        anterior = self.capturando
        self.parar_captura()
        if anterior == acao:
            return
        self._limpar_avisos()
        self._recado("")
        self._pode_descartar = False
        self.capturando = acao
        self._atualizar_botao(acao)
        self._avisar(acao, "Aperte a tecla nova (Esc também vale). Para desistir, clique de novo na tecla.",
                     erro=False)

    def parar_captura(self):
        acao = self.capturando
        if acao is None:
            return
        self.capturando = None
        self.pendente = None
        self._atualizar_botao(acao)
        self._avisar(acao, "")
        for outra in self.linhas:
            self._marcar_conflito(outra, False)

    def _foco_mudou(self, _antigo, novo):
        # Clicou em outro lugar (outra tecla, Salvar...): para de esperar a tecla.
        if self.capturando is not None and novo is not self.linhas[self.capturando]["botao"]:
            self.parar_captura()

    def eventFilter(self, objeto, evento):
        if self.capturando is None:
            return super().eventFilter(objeto, evento)
        tipo = evento.type()
        if tipo == QEvent.ShortcutOverride:
            evento.accept()  # nenhuma tecla vira atalho do Qt enquanto esperamos a tecla nova
            return True
        if tipo == QEvent.KeyRelease:
            return True
        if tipo != QEvent.KeyPress:
            return super().eventFilter(objeto, evento)

        acao = self.capturando
        if evento.key() in atalhos.MODIFICADORAS or evento.isAutoRepeat():
            return True  # Ctrl/Alt/Shift sozinhos: espera a tecla que vem junto
        tecla = atalhos.tecla_do_evento(evento)
        if not tecla:
            self._avisar(acao, "Essa tecla não pode ser atalho (Enter, Tab, espaço e Backspace são usados "
                               "para digitar e andar pela tela). Aperte outra tecla.")
            return True
        dono = self._dono_da_tecla(tecla, menos=acao)
        if dono is not None and self.pendente != tecla:
            # Primeira vez: só avisa. Apertando a mesma tecla de novo, ela passa para cá.
            self.pendente = tecla
            for outra in self.linhas:
                self._marcar_conflito(outra, outra == dono)
            self._avisar(acao, f"{tecla} já é usada em \"{self._texto_da_acao(dono)}\". Aperte {tecla} de "
                               f"novo para passar para cá (lá fica sem atalho), ou aperte outra tecla.")
            return True
        self.parar_captura()
        if dono is not None:
            self.definir_tecla(dono, "", recado=False)
            self._avisar(dono, f"Ficou sem atalho: {tecla} passou para \"{self._texto_da_acao(acao)}\".")
        self.definir_tecla(acao, tecla, recado=False)
        return True

    def _texto_da_acao(self, acao):
        return self.linhas[acao]["descricao"]

    def definir_tecla(self, acao, tecla, recado=True):
        if acao == self.capturando:
            self.parar_captura()
        if recado:
            self._limpar_avisos()
            self._recado("")
        self.teclas[acao] = tecla
        self._pode_descartar = False
        self._atualizar_botao(acao)

    # ------------------------------------------------------------------
    # Botões e teclado
    # ------------------------------------------------------------------

    def keyPressEvent(self, evento):
        # Enter num botão aperta o botão (igual à tela principal); Enter em outro lugar não fecha a tela.
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter):
            foco = QApplication.focusWidget()
            if isinstance(foco, QPushButton):
                foco.animateClick()
            return
        super().keyPressEvent(evento)

    def restaurar_padrao(self):
        self.parar_captura()
        self._limpar_avisos()
        self.teclas = dict(self.padrao)
        self._pode_descartar = False
        self._atualizar_todas()
        self._recado("Teclas de fábrica de volta na tela. Clique em Salvar para passar a valer.", erro=False)

    def salvar(self):
        self.parar_captura()
        self.ao_salvar(dict(self.teclas))
        self.accept()

    def reject(self):
        """Cancelar / Esc / X: com mudanças não salvas, pede para confirmar (escrito, sem barulho)."""
        self.parar_captura()
        if self.teclas != self.originais and not self._pode_descartar:
            self._pode_descartar = True
            self._recado("Há mudanças que não foram salvas. Aperte Cancelar (ou Esc) de novo para "
                         "descartar, ou clique em Salvar.")
            return
        super().reject()

    def done(self, resultado):
        QApplication.instance().removeEventFilter(self)
        QApplication.instance().focusChanged.disconnect(self._foco_mudou)
        super().done(resultado)


class BotaoTecla(QPushButton):
    """
    Botão que mostra uma tecla de atalho. Clicando, ele espera a próxima tecla
    apertada e avisa quem usa (sinal tecla_apertada) - quem decide se aceita é
    a tela (ex.: tecla já usada por outro serviço). Usado em "Serviços e preços".
    Enquanto espera, nenhuma tecla faz outra coisa (nem o Esc fecha a tela).
    """

    tecla_apertada = Signal(str)  # a tecla, ou "" se for uma que não pode virar atalho
    captura_mudou = Signal(bool)  # começou (True) ou parou (False) de esperar a tecla

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tecla = ""
        self.capturando = False
        self.setProperty("papel", "atalho")
        self.setAutoDefault(False)
        self.clicked.connect(lambda: self.parar() if self.capturando else self.comecar())
        self._mostrar()

    def definir(self, tecla):
        self.tecla = tecla
        self.parar()

    def comecar(self):
        self.capturando = True
        self._mostrar()
        self.captura_mudou.emit(True)

    def parar(self):
        if self.capturando:
            self.capturando = False
            self.captura_mudou.emit(False)
        self._mostrar()

    def _mostrar(self):
        self.setText(TEXTO_CAPTURANDO if self.capturando else atalhos.texto_para_mostrar(self.tecla))
        self.setProperty("capturando", self.capturando)
        self.setProperty("vazio", not self.tecla and not self.capturando)
        repintar(self)

    def event(self, evento):
        if self.capturando:
            tipo = evento.type()
            if tipo == QEvent.ShortcutOverride:
                evento.accept()
                return True
            if tipo == QEvent.KeyRelease:
                return True
            if tipo == QEvent.KeyPress:
                if evento.key() not in atalhos.MODIFICADORAS and not evento.isAutoRepeat():
                    self.tecla_apertada.emit(atalhos.tecla_do_evento(evento))
                return True
        return super().event(evento)

    def focusOutEvent(self, evento):
        self.parar()  # clicou em outro lugar: desiste de esperar a tecla
        super().focusOutEvent(evento)
