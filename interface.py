"""
interface.py - A janela principal do programa, feita com PySide6 (Qt).

Cada parte da tela é um PAINEL (QDockWidget), como no OBS ou no Photoshop:
    Serviços · Adicionar item · Atendimento atual · Teclado · Cliente · Pagamento · Totais

Os painéis podem ser arrastados pela barra de título, desgrudados (viram janelas
flutuantes), encaixados em qualquer lado, redimensionados e empilhados em abas
(solte um painel em cima de outro). O menu Exibir mostra/esconde cada painel,
troca de layout (Padrão, Compacto, Touch ou um salvo com nome), trava o layout,
escolhe o modo claro/escuro e abre a tela de cores. Ao fechar, tudo é salvo
em preferencias.json e o programa abre do mesmo jeito.

Fluxo de uso pelo teclado:
  1. Aperte a tecla do serviço (1 a 9 e 0).
  2. Digite a quantidade ou o valor e aperte Enter.
  3. Repita para outros serviços.
  4. Escolha o pagamento (F5 a F8), digite o valor recebido (F4) se for dinheiro.
  5. Aperte F12 para finalizar.
(Essas são as teclas de fábrica; dá para trocar em Ajuda › Atalhos do teclado.)
"""

import os
import sqlite3
import subprocess
from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QFont, QFontMetrics, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import atalhos
import atualizacao
import backup
import banco
import config
import estilo
import impressao
import layout_notas
import migracao
import notas
import preferencias
import toque
import treino
import versao
from estilo import repintar
from tela_atalhos import TelaAtalhos
from tela_atualizacao import DialogoAtualizacao
from tela_cores import TelaCores
from tela_limpar import TelaLimpar
from tela_loja import DialogoBoasVindas
from tela_notinhas import TelaNotinhas
from tela_preferencias import TelaPreferencias
from tela_relatorio import TelaRelatorio
from tela_servicos import TelaServicos
from tela_sobre import TelaSobre
from teclado import TecladoNumerico, digitar_no_campo
from utils import (
    arredondar,
    base_da_taxa,
    converter_quantidade,
    converter_valor,
    formatar_percentual,
    formatar_reais,
    formatar_telefone,
    so_digitos,
)

ZERO = Decimal("0")

# Número da "versão" do layout dos painéis. Se um dia os painéis mudarem
# (um painel novo, por exemplo), aumente este número: o layout antigo salvo
# deixa de ser usado e o programa abre com o layout padrão.
VERSAO_LAYOUT = 1

# Painéis da tela: (nome interno, título). O nome interno é o que o Qt usa
# para salvar e restaurar a posição de cada um, por isso não deve mudar.
PAINEIS = [
    ("servicos", "Serviços"),
    ("item", "Adicionar item"),
    ("atendimento", "Atendimento atual"),
    ("teclado", "Teclado"),
    ("cliente", "Cliente"),
    ("pagamento", "Pagamento"),
    ("totais", "Totais"),
]

# Layouts prontos do menu Exibir › Layouts (os salvos pela pessoa aparecem depois deles).
LAYOUTS_PRONTOS = ["Padrão", "Compacto", "Touch"]
DICAS_LAYOUTS = {
    "Padrão": "Todos os painéis lado a lado",
    "Compacto": "Para tela pequena: Cliente fica em aba com o Pagamento e o teclado fica escondido",
    "Touch": "Teclado grande no meio da tela, bom para usar com o dedo",
}

def _rotulo(texto="", nome=None):
    """Cria um QLabel. 'nome' é o objectName, usado na folha de estilo (estilo.py)."""
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


class AreaRolavel(QScrollArea):
    """
    Envolve o conteúdo de um painel. Se o painel ficar mais baixo que o conteúdo,
    aparece uma barra de rolagem em vez de cortar os botões. Na largura, o painel
    nunca fica mais estreito que o conteúdo precisa (assim nenhum texto é cortado).
    """

    def __init__(self, conteudo):
        super().__init__()
        self.setWidget(conteudo)
        self.setWidgetResizable(True)  # o conteúdo estica para ocupar o painel todo
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Sem isto, clicar num botão do teclado (que não aceita o cursor) faria o Qt
        # dar o cursor para esta área, tirando-o do campo onde a pessoa estava digitando.
        self.setFocusPolicy(Qt.NoFocus)

    def minimumSizeHint(self):
        # Calculado na hora (e não uma vez só), porque o tamanho do texto muda
        # quando os serviços são recarregados ou o estilo é aplicado.
        largura = self.widget().minimumSizeHint().width() + self.verticalScrollBar().sizeHint().width()
        return QSize(largura, 90)


class LinhaDeBotoes(QWidget):
    """
    Botões lado a lado (o primeiro à esquerda, o último à direita). Se o painel ficar
    estreito demais para eles, ficam um embaixo do outro, em vez de alargar o painel
    (e a janela passar da tela).
    """

    def __init__(self, botoes):
        super().__init__()
        self.botoes = botoes
        self.caixa = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.caixa.setContentsMargins(0, 0, 0, 0)
        for numero, botao in enumerate(botoes):
            if numero:
                self.caixa.addStretch(1)
            self.caixa.addWidget(botao)

    def _largura_lado_a_lado(self):
        return sum(botao.sizeHint().width() for botao in self.botoes) + 24 * (len(self.botoes) - 1)

    def minimumSizeHint(self):
        # A largura mínima é a de um botão só (empilhados); a altura, a do jeito que está agora.
        largura = max(botao.minimumSizeHint().width() for botao in self.botoes)
        return QSize(largura, self.caixa.minimumSize().height())

    def empilhados(self):
        return self.caixa.direction() == QBoxLayout.TopToBottom

    def resizeEvent(self, evento):
        direcao = QBoxLayout.TopToBottom if self.width() < self._largura_lado_a_lado() else QBoxLayout.LeftToRight
        if self.caixa.direction() != direcao:
            self.caixa.setDirection(direcao)
            self.updateGeometry()  # (a altura mudou: o painel arruma o resto)
        super().resizeEvent(evento)


class BotaoServico(QPushButton):
    """Botão de um serviço: a tecla de atalho, o nome e o preço (encostado à direita)."""

    def __init__(self, tecla, nome, preco):
        super().__init__()
        self.setProperty("papel", "servico")
        self.setProperty("selecionado", False)
        linha = QHBoxLayout(self)
        linha.setContentsMargins(12, 10, 12, 10)
        linha.setSpacing(10)
        for texto, nome_objeto in ((tecla, "teclaServico"), (nome, "nomeServico"), (preco, "precoServico")):
            rotulo = _rotulo(texto, nome_objeto)
            # Os cliques passam direto para o botão (o texto não "rouba" o clique).
            rotulo.setAttribute(Qt.WA_TransparentForMouseEvents)
            linha.addWidget(rotulo)
            if nome_objeto == "teclaServico":
                self.lbl_tecla = rotulo
            if nome_objeto == "nomeServico":
                linha.addStretch(1)  # empurra o preço para a direita

    # O QPushButton calcula o tamanho só pelo próprio texto (que aqui é vazio).
    # Usamos o tamanho dos rótulos lá dentro, para nada ficar cortado.
    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def definir_selecionado(self, selecionado):
        self.setProperty("selecionado", selecionado)
        repintar(self)


class JanelaPrincipal(QMainWindow):
    """A janela do programa e o estado do atendimento atual."""

    def __init__(self):
        super().__init__()
        self.config = config.carregar_config()
        # (não chamamos de self.layout porque o QMainWindow já tem um método layout())
        self.layout_das_notas = layout_notas.carregar_layout()
        self._apagar_dados_clientes_antigos()
        self.preferencias = preferencias.carregar()
        self._conferir_preferencias()
        # Teclas de atalho: {"acao": "tecla"} (as que a pessoa trocou + as de fábrica).
        self._carregar_atalhos()
        self.modo_tablet = self.preferencias["modo_tablet"]
        estilo.definir_escala(estilo.ESCALA_TABLET if self.modo_tablet else 1.0)
        self._aplicando_tema = False
        self._aplicar_tema()

        # Estado do atendimento atual.
        self.carrinho = []           # lista de itens (cada item é um dicionário)
        self.servico_atual = None    # serviço escolhido para o próximo item
        self.botoes_servicos = []
        self._formatando_telefone = False  # evita loop infinito na máscara do telefone
        self._ultimo_campo = None    # último campo que teve o cursor (usado pelo teclado na tela)
        self._travado = False
        self.paineis = {}            # nome interno -> QDockWidget

        self._atualizar_titulo()
        # Permite painéis lado a lado dentro de um mesmo canto e empilhados em abas.
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AllowTabbedDocks
                            | QMainWindow.AnimatedDocks)
        # O Qt exige um "widget central"; aqui ele fica escondido e os painéis ocupam a janela toda.
        central = QWidget()
        central.hide()
        self.setCentralWidget(central)

        self._criar_paineis()
        self.teclado.definir_grande(self.preferencias["teclado_grande"])
        self._criar_menu()
        self._criar_faixa_treino()
        self._criar_barra_status()
        self._aplicar_textos_atalhos()
        self._organizar_layout_padrao()
        self._restaurado = self._restaurar_layout_salvo()
        self._aplicar_trava(self.preferencias["layout_travado"])
        self._rolagem_por_toque(self.modo_tablet)

        # Escuta TODAS as teclas do programa (atalhos e Enter nos botões).
        QApplication.instance().installEventFilter(self)
        # Avisa sempre que o cursor muda de campo (para o teclado na tela saber onde digitar).
        QApplication.instance().focusChanged.connect(self._foco_mudou)
        # Avisa quando o Windows troca entre claro e escuro (para o "Seguir o Windows").
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._windows_mudou_cor)

        self._limpar_selecao_servico()
        self._atualizar_carrinho()

    def mostrar(self):
        """Abre a janela: do jeito que estava da última vez, ou maximizada na primeira vez."""
        if self._restaurado:
            self.show()
        else:
            # Na primeira vez, abre no monitor principal (com dois monitores, o Windows
            # poderia escolher o outro).
            self.setGeometry(QApplication.primaryScreen().availableGeometry())
            # Os tamanhos padrão dos painéis dependem do tamanho final da janela, e o
            # Windows ainda muda esse tamanho algumas vezes enquanto maximiza. Então,
            # durante o primeiro segundo, cada mudança de tamanho refaz o ajuste.
            self._ajustando_abertura = True
            self.showMaximized()
            QTimer.singleShot(0, self._ajustar_tamanhos_padrao)
            QTimer.singleShot(1000, lambda: setattr(self, "_ajustando_abertura", False))

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if getattr(self, "_ajustando_abertura", False):
            QTimer.singleShot(0, self._ajustar_tamanhos_padrao)

    # ------------------------------------------------------------------
    # Montagem dos painéis
    # ------------------------------------------------------------------

    def _novo_cartao(self):
        """O "cartão" branco que fica dentro de cada painel."""
        cartao = QFrame()
        cartao.setObjectName("painel")
        return cartao

    def _criar_paineis(self):
        conteudos = {
            "servicos": self._criar_conteudo_servicos(),
            "item": self._criar_conteudo_item(),
            "atendimento": self._criar_conteudo_atendimento(),
            "teclado": self._criar_conteudo_teclado(),
            "cliente": self._criar_conteudo_cliente(),
            "pagamento": self._criar_conteudo_pagamento(),
            "totais": self._criar_conteudo_totais(),
        }
        for nome, titulo in PAINEIS:
            painel = QDockWidget(titulo, self)
            painel.setObjectName(f"painel_{nome}")  # obrigatório para salvar o layout
            painel.setWidget(AreaRolavel(conteudos[nome]))
            self.paineis[nome] = painel

    def _criar_conteudo_servicos(self):
        cartao = self._novo_cartao()
        self.lista_servicos = QVBoxLayout(cartao)
        self.lista_servicos.setContentsMargins(12, 8, 12, 12)
        self.lista_servicos.setSpacing(6)
        self._criar_botoes_servicos()
        return cartao

    def _criar_botoes_servicos(self):
        """Cria um botão para cada serviço do config, agrupados (Impressão / Consulta / RecargaPay)."""
        # Apaga o que existia (usado ao recarregar as configurações).
        while self.lista_servicos.count():
            item = self.lista_servicos.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.botoes_servicos = []

        grupo_anterior = None
        for indice, servico in enumerate(self.config.servicos):
            if servico.grupo != grupo_anterior:
                self.lista_servicos.addWidget(_rotulo(servico.grupo, "grupo"))
                grupo_anterior = servico.grupo
            botao = BotaoServico("", servico.nome, self._descricao_preco(servico, self.config.pede_valor(servico)))
            # "indice=indice" guarda o valor atual do laço (sem isso todos os botões
            # chamariam o último serviço).
            botao.clicked.connect(lambda _marcado=False, indice=indice: self.selecionar_servico(indice))
            self.lista_servicos.addWidget(botao)
            self.botoes_servicos.append(botao)
        self.lista_servicos.addStretch(1)
        self._textos_botoes_servicos()

    def _textos_botoes_servicos(self):
        """Escreve em cada botão de serviço a tecla de atalho dele (e a dica ao parar o mouse)."""
        for indice, (botao, servico) in enumerate(zip(self.botoes_servicos, self.config.servicos)):
            tecla = self._tecla_do_servico(indice)
            botao.lbl_tecla.setText(tecla)
            botao.lbl_tecla.setVisible(bool(tecla))
            dica = f"Tecla {tecla}" if tecla else servico.nome
            if self.config.pede_valor(servico):
                dica += (f" · pede o valor do {servico.nome_do_valor()} e soma o serviço "
                         "(sem taxa da maquininha)")
            elif not servico.cobra_taxa_maquininha:
                dica += " · sem taxa da maquininha (o valor da recarga/boleto é cobrado à parte)"
            botao.setToolTip(dica)

    def _criar_conteudo_item(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(16, 12, 16, 14)
        coluna.setSpacing(6)

        self.lbl_servico_atual = _rotulo("", "servicoAtual")
        self.lbl_servico_atual.setWordWrap(True)  # nome comprido quebra a linha em vez de cortar
        # Reserva a altura do título com serviço escolhido (18px, negrito: estilo.py), que é
        # mais alto que o "nenhum serviço"; assim o painel não precisa de rolagem ao escolher.
        fonte = QFont(self.lbl_servico_atual.font())
        fonte.setPixelSize(18)
        fonte.setWeight(QFont.DemiBold)
        self.lbl_servico_atual.setMinimumHeight(QFontMetrics(fonte).height())
        coluna.addWidget(self.lbl_servico_atual)

        # Em cima do campo: "Quantidade", "Valor do boleto (R$)" ou, digitando um boleto/recarga,
        # a conta inteira ("Valor do boleto: R$ 200,00 + Serviço: R$ 2,00 = Cobrar do cliente: R$ 202,00").
        # Não deixa o painel mais largo nem mais alto (assim nenhum layout ganha barra de rolagem).
        self.lbl_campo_item = _rotulo("Quantidade", "rotulo")
        self.lbl_campo_item.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        coluna.addWidget(self.lbl_campo_item)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        self.entry_item = QLineEdit()
        self.entry_item.setMinimumWidth(110)
        self.entry_item.textChanged.connect(self._atualizar_previa)
        self.entry_item.returnPressed.connect(self.adicionar_item)
        linha.addWidget(self.entry_item, 1)
        # Prévia do valor ("= R$ 21,00"), na mesma linha do campo.
        self.lbl_previa = _rotulo("", "previa")
        self.lbl_previa.setMinimumWidth(self.lbl_previa.fontMetrics().horizontalAdvance("= R$ 0.000,00") + 12)
        linha.addWidget(self.lbl_previa)
        self.btn_adicionar = QPushButton("Adicionar  ↵")
        self.btn_adicionar.clicked.connect(self.adicionar_item)
        linha.addWidget(self.btn_adicionar)
        coluna.addLayout(linha)
        coluna.addStretch(1)
        return cartao

    def _criar_conteudo_atendimento(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(8, 8, 8, 10)
        coluna.setSpacing(8)

        self.tabela = QTableWidget(0, 4)
        self.tabela.setHorizontalHeaderLabels(["Serviço", "Qtd", "Detalhe", "Total"])
        self.tabela.verticalHeader().hide()
        self.tabela.setShowGrid(False)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setWordWrap(True)                  # texto comprido quebra a linha
        self.tabela.setTextElideMode(Qt.ElideNone)     # ...em vez de virar "..."
        cabecalho = self.tabela.horizontalHeader()
        # Serviço e Detalhe dividem o espaço; Qtd e Total ficam do tamanho do conteúdo.
        cabecalho.setSectionResizeMode(0, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        cabecalho.setHighlightSections(False)
        # Títulos alinhados como o conteúdo: texto à esquerda, números à direita.
        for coluna_num in range(4):
            alinhamento = Qt.AlignRight if coluna_num in (1, 3) else Qt.AlignLeft
            self.tabela.horizontalHeaderItem(coluna_num).setTextAlignment(alinhamento | Qt.AlignVCenter)
        # A altura de cada linha acompanha o texto: se a coluna estreitar e o texto
        # quebrar em duas linhas, a linha cresce (em vez de esconder o final).
        self.tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # Quando não há itens, mostra uma frase no lugar da tabela vazia.
        self.lbl_aviso_vazio = _rotulo("", "vazio")
        self.lbl_aviso_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_aviso_vazio.setWordWrap(True)
        self.pilha_atendimento = QStackedWidget()
        self.pilha_atendimento.addWidget(self.lbl_aviso_vazio)
        self.pilha_atendimento.addWidget(self.tabela)
        coluna.addWidget(self.pilha_atendimento, 1)

        self.btn_remover = QPushButton()
        self.btn_remover.clicked.connect(lambda: self.remover_item())
        self.btn_cancelar = QPushButton()
        self.btn_cancelar.clicked.connect(lambda: self.cancelar_atendimento())
        # Lado a lado; se o painel ficar estreito (tela menor, letras grandes), um embaixo do outro.
        self.botoes_atendimento = LinhaDeBotoes([self.btn_remover, self.btn_cancelar])
        coluna.addWidget(self.botoes_atendimento)
        return cartao

    def _criar_conteudo_teclado(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(0, 0, 0, 0)
        self.teclado = TecladoNumerico()
        self.teclado.tecla_apertada.connect(self._tecla_na_tela)
        coluna.addWidget(self.teclado)
        return cartao

    def _criar_conteudo_cliente(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(16, 12, 16, 14)
        coluna.setSpacing(4)
        self.lbl_rotulo_nome = _rotulo("", "rotulo")
        coluna.addWidget(self.lbl_rotulo_nome)
        self.entry_nome = QLineEdit()
        self.entry_nome.returnPressed.connect(lambda: self._focar(self.entry_telefone))
        coluna.addWidget(self.entry_nome)
        coluna.addSpacing(6)
        self.lbl_rotulo_telefone = _rotulo("", "rotulo")
        coluna.addWidget(self.lbl_rotulo_telefone)
        self.entry_telefone = QLineEdit()
        self.entry_telefone.setPlaceholderText("(21) 99999-9999")
        self.entry_telefone.textChanged.connect(self._aplicar_mascara_telefone)
        self.entry_telefone.returnPressed.connect(lambda: self._focar(self.tabela))
        coluna.addWidget(self.entry_telefone)
        coluna.addStretch(1)
        return cartao

    def _criar_conteudo_pagamento(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(16, 12, 16, 14)
        coluna.setSpacing(6)

        # Formas de pagamento: botões grandes que ficam marcados (um de cada vez).
        grade = QGridLayout()
        grade.setSpacing(6)
        self.grupo_formas = QButtonGroup(self)
        self.grupo_formas.setExclusive(True)  # só um marcado por vez
        self.botoes_pagamento = {}
        for i, forma in enumerate(config.FORMAS_PAGAMENTO):
            botao = QPushButton()
            botao.setProperty("papel", "forma")
            botao.setCheckable(True)
            botao.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.grupo_formas.addButton(botao)
            grade.addWidget(botao, i // 2, i % 2)
            self.botoes_pagamento[forma] = botao
        self.botoes_pagamento["Dinheiro"].setChecked(True)
        self.grupo_formas.buttonToggled.connect(lambda *_: self.atualizar_totais())
        self._atualizar_textos_pagamento()
        coluna.addLayout(grade)

        coluna.addSpacing(8)
        self.lbl_rotulo_recebido = _rotulo("", "rotulo")
        self.lbl_rotulo_recebido.setWordWrap(True)  # (quebra a linha em vez de alargar o painel)
        coluna.addWidget(self.lbl_rotulo_recebido)
        self.entry_recebido = QLineEdit()
        self.entry_recebido.textChanged.connect(lambda *_: self.atualizar_totais())
        self.entry_recebido.returnPressed.connect(lambda: self._focar(self.btn_finalizar))
        coluna.addWidget(self.entry_recebido)
        self.lbl_troco = _rotulo("", "troco")
        # Reserva a altura do troco mesmo vazio, para o painel não "pular" quando ele aparece.
        self.lbl_troco.ensurePolished()  # aplica o estilo agora, para medir com a fonte certa
        self.lbl_troco.setMinimumHeight(self.lbl_troco.fontMetrics().height() + 4)
        coluna.addWidget(self.lbl_troco)
        coluna.addStretch(1)
        return cartao

    def _criar_conteudo_totais(self):
        cartao = self._novo_cartao()
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(6)

        grade = QGridLayout()
        grade.setHorizontalSpacing(16)
        grade.setVerticalSpacing(4)
        grade.addWidget(_rotulo("Subtotal", "rotulo"), 0, 0)
        self.lbl_subtotal = _rotulo("", "valor")
        grade.addWidget(self.lbl_subtotal, 0, 1, Qt.AlignRight)
        self.lbl_taxa_rotulo = _rotulo("Taxa maquininha", "rotulo")
        grade.addWidget(self.lbl_taxa_rotulo, 1, 0)
        self.lbl_taxa = _rotulo("", "valor")
        grade.addWidget(self.lbl_taxa, 1, 1, Qt.AlignRight)
        # Boletos e recargas (só aparece quando tem): o valor que é de terceiros.
        self.lbl_repasse_rotulo = _rotulo("Boletos e recargas", "rotulo")
        grade.addWidget(self.lbl_repasse_rotulo, 2, 0)
        self.lbl_repasse = _rotulo("", "valor")
        grade.addWidget(self.lbl_repasse, 2, 1, Qt.AlignRight)
        self.lbl_repasse_rotulo.hide()
        self.lbl_repasse.hide()
        self.lbl_total_rotulo = _rotulo("Total", "rotuloTotal")
        grade.addWidget(self.lbl_total_rotulo, 3, 0, Qt.AlignBottom)
        self.lbl_total = _rotulo("", "total")
        grade.addWidget(self.lbl_total, 3, 1, Qt.AlignRight)
        grade.setColumnStretch(1, 1)
        coluna.addLayout(grade)

        coluna.addSpacing(6)
        # (a nota da loja é sempre gerada; esta caixinha é só para a do cliente)
        self.check_nota_cliente = QCheckBox("Imprimir nota do cliente")
        coluna.addWidget(self.check_nota_cliente)
        coluna.addSpacing(4)
        self.btn_finalizar = QPushButton()
        self.btn_finalizar.setObjectName("finalizar")
        self.btn_finalizar.clicked.connect(self.finalizar_atendimento)
        coluna.addWidget(self.btn_finalizar)
        coluna.addStretch(1)
        return cartao

    def _atualizar_textos_pagamento(self):
        """Escreve nos botões de pagamento a tecla de atalho e a taxa. Ex.: 'Débito · F7  +5%'."""
        for acao, forma in atalhos.FORMA_DA_ACAO.items():
            botao = self.botoes_pagamento[forma]
            texto = forma + self._tecla(acao, " · ")
            taxa = self.config.taxas_maquininha.get(forma)
            if taxa:
                texto += f"\n+{formatar_percentual(taxa)} maquininha"
            botao.setText(texto)

    # ------------------------------------------------------------------
    # Menu, barra de status e atalhos
    # ------------------------------------------------------------------

    def _criar_menu(self):
        barra = self.menuBar()

        menu_arquivo = barra.addMenu("&Arquivo")
        self.acao_relatorio = menu_arquivo.addAction("Relatório do dia...", self.relatorio_do_dia)
        menu_arquivo.addSeparator()
        self.acao_treino = QAction("Modo treinamento", self, checkable=True)
        self.acao_treino.setToolTip("Usa um banco separado: nada vai para o caixa nem para o relatório real")
        self.acao_treino.triggered.connect(self.definir_modo_treino)
        menu_arquivo.addAction(self.acao_treino)
        menu_arquivo.addAction("Zerar banco de treino...", self.zerar_treino)
        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Serviços e preços...", self.configurar_servicos)
        menu_arquivo.addAction("Preferências...", self.configurar)
        menu_arquivo.addAction("Configurar notinhas...", self.configurar_notinhas)
        menu_arquivo.addAction("Abrir pasta de notas", self.abrir_pasta_notas)
        menu_arquivo.addAction("Abrir pasta de dados", self.abrir_pasta_dados)
        menu_arquivo.addAction("Importar dados de outra pasta...", self.importar_dados)
        menu_backup = menu_arquivo.addMenu("Backup")
        menu_backup.addAction("Fazer backup agora", self.fazer_backup_agora)
        menu_backup.addAction("Escolher pasta do backup...", self.escolher_pasta_backup)
        menu_backup.addAction("Abrir pasta do backup", self.abrir_pasta_backup)
        menu_backup.addSeparator()
        menu_backup.addAction("Restaurar backup...", self.restaurar_backup)
        menu_arquivo.addAction("Editar config.json (avançado)", self.editar_config)
        menu_arquivo.addAction("Recarregar configurações", lambda: self.recarregar_config())
        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Limpar dados...", self.limpar_dados)
        menu_arquivo.addSeparator()
        menu_arquivo.addAction("Sair", self.close)

        menu_exibir = barra.addMenu("&Exibir")
        for nome, _titulo in PAINEIS:
            # toggleViewAction: ação pronta do Qt que mostra/esconde o painel (com ✓ no menu).
            acao = self.paineis[nome].toggleViewAction()
            if nome == "teclado":
                self.acao_teclado = acao
            menu_exibir.addAction(acao)
        menu_exibir.addSeparator()
        # Layouts: a lista é montada na hora de abrir (muda quando a pessoa salva/exclui).
        self.menu_layouts = menu_exibir.addMenu("Layouts")
        self.menu_layouts.setToolTipsVisible(True)
        self.menu_layouts.aboutToShow.connect(self._montar_menu_layouts)
        self.acao_travar = QAction("Travar layout", self, checkable=True)
        self.acao_travar.toggled.connect(self._aplicar_trava)
        menu_exibir.addAction(self.acao_travar)
        menu_exibir.addAction("Restaurar layout padrão", self.restaurar_layout_padrao)
        menu_exibir.addSeparator()
        self.acao_tablet = QAction("Modo tablet", self, checkable=True)
        self.acao_tablet.setChecked(self.modo_tablet)
        self.acao_tablet.setToolTip("Tudo maior, para usar com o dedo")
        self.acao_tablet.triggered.connect(self.definir_modo_tablet)
        menu_exibir.addAction(self.acao_tablet)

        menu_exibir.addSeparator()
        menu_modo = menu_exibir.addMenu("Modo de cor")
        grupo_modo = QActionGroup(self)  # só um marcado por vez
        self.acoes_modo = {}
        for modo, texto in estilo.MODOS.items():
            acao = QAction(texto, self, checkable=True)
            acao.setChecked(modo == self.preferencias["modo_cor"])
            acao.triggered.connect(lambda _marcado=False, modo=modo: self.definir_modo_cor(modo))
            grupo_modo.addAction(acao)
            menu_modo.addAction(acao)
            self.acoes_modo[modo] = acao
        menu_exibir.addAction("Cores do programa...", self.configurar_cores)

        menu_ajuda = barra.addMenu("Aj&uda")
        menu_ajuda.addAction("Atalhos do teclado...", self.configurar_atalhos)
        menu_ajuda.addAction("Procurar atualizações...", self.procurar_atualizacoes)
        menu_ajuda.addSeparator()
        menu_ajuda.addAction(f"Sobre o {versao.NOME_PROGRAMA}", lambda: TelaSobre(self).exec())

    def _criar_faixa_treino(self):
        """A faixa amarela no topo que aparece no modo treinamento."""
        self.faixa_treino = QToolBar("Modo treinamento", self)
        self.faixa_treino.setObjectName("faixa_treino")  # (o Qt pede um nome para salvar o layout)
        self.faixa_treino.setMovable(False)
        self.faixa_treino.setFloatable(False)
        # Não aparece no menu do botão direito (onde dá para esconder painéis e barras).
        self.faixa_treino.toggleViewAction().setVisible(False)
        texto = QLabel("MODO TREINAMENTO - nada é salvo no caixa")
        texto.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.faixa_treino.addWidget(texto)
        for rotulo, funcao in (("Zerar treino", self.zerar_treino),
                               ("Sair do treinamento", lambda: self.definir_modo_treino(False))):
            botao = QPushButton(rotulo)
            botao.setFocusPolicy(Qt.NoFocus)
            botao.clicked.connect(funcao)
            self.faixa_treino.addWidget(botao)
        self.addToolBar(Qt.TopToolBarArea, self.faixa_treino)
        self.faixa_treino.hide()

    def _mostrar_faixa_treino(self, visivel):
        """
        Mostra/esconde a faixa sem bagunçar os painéis: a faixa ocupa (ou devolve)
        uns 50 pixels de altura e o Qt encolheria todos os painéis um pouco,
        fazendo aparecer barra de rolagem. Em vez disso, em cada coluna os painéis
        de cima ficam com a altura que tinham e só o de baixo cede (ou ganha) o espaço.
        """
        if self.faixa_treino.isVisibleTo(self) == visivel:
            return
        antes = {painel: painel.height() for painel in self.paineis.values()
                 if painel.isVisible() and not painel.isFloating()}
        self.faixa_treino.setVisible(visivel)
        if self.isVisible():
            self.layout().activate()  # o Qt reorganiza agora (e não só depois)
            self._manter_alturas(antes)

    def _manter_alturas(self, antes):
        # Junta numa "coluna" os painéis que ficam um embaixo do outro (que se cruzam
        # na horizontal). Ex.: "Adicionar item" em cima de "Atendimento" + "Teclado".
        colunas = []
        for painel in sorted(antes, key=lambda p: p.x()):
            if not painel.isVisible() or painel.isFloating():
                continue
            inicio, fim = painel.x(), painel.x() + painel.width()
            juntas = [c for c in colunas if any(o.x() < fim and inicio < o.x() + o.width() for o in c)]
            colunas = [c for c in colunas if all(c is not j for j in juntas)]
            colunas.append([painel] + [p for c in juntas for p in c])
        for coluna in colunas:
            # Um painel por "andar" (os que estão lado a lado no mesmo andar vão juntos).
            andares = {}
            for painel in sorted(coluna, key=lambda p: (p.y(), p.x())):
                andares.setdefault(painel.y(), painel)
            paineis = list(andares.values())  # de cima para baixo
            if len(paineis) < 2:
                continue
            total = sum(painel.height() + self._altura_abas(painel) for painel in paineis)
            alturas = [antes[painel] + self._altura_abas(painel) for painel in paineis[:-1]]
            alturas.append(max(total - sum(alturas), 100))
            self.resizeDocks(paineis, alturas, Qt.Vertical)

    def _atualizar_titulo(self):
        titulo = f"{versao.NOME_PROGRAMA} - {self.config.nome_loja}"
        self.setWindowTitle(f"[TREINAMENTO] {titulo}" if treino.ativo() else titulo)

    def _apagar_dados_clientes_antigos(self):
        """
        Opção "Apagar automaticamente depois de X dias": roda ao abrir o programa.
        Apaga só nome e telefone (no caixa e no treino); atendimentos e valores ficam.
        """
        opcao = self.config.dados_cliente
        if opcao["guardar"] != "apagar":
            return 0
        apagados = 0
        for arquivo in (banco.ARQUIVO_BANCO, treino.ARQUIVO_BANCO_TREINO):
            try:
                apagados += banco.apagar_dados_clientes(opcao["dias"], arquivo)
            except sqlite3.Error:
                pass  # banco ocupado ou estragado: tenta de novo na próxima vez que abrir
        return apagados

    def _tem_atendimento_aberto(self):
        return bool(self.carrinho or self.entry_nome.text().strip() or self.entry_telefone.text().strip())

    def definir_modo_treino(self, ligar):
        """Liga/desliga o modo treinamento (banco treino.db, notas em notas_treino/)."""
        ligar = bool(ligar)
        if ligar == treino.ativo():
            self.acao_treino.setChecked(ligar)
            return
        if self._tem_atendimento_aberto():
            onde = "o treinamento" if ligar else "o caixa de verdade"
            resposta = QMessageBox.question(
                self, "Modo treinamento",
                f"Há um atendimento em andamento. Para passar para {onde}, ele será cancelado. Continuar?")
            if resposta != QMessageBox.Yes:
                self.acao_treino.setChecked(treino.ativo())  # desfaz o ✓ do menu
                return
            self.cancelar_atendimento(perguntar=False)
        treino.ligar(ligar)
        try:
            banco.criar_tabelas()  # no treino: cria o treino.db na primeira vez
        except sqlite3.Error as erro:
            treino.ligar(not ligar)
            self.acao_treino.setChecked(treino.ativo())
            QMessageBox.critical(self, "Modo treinamento", f"Não foi possível abrir o banco:\n{erro}")
            return
        self.acao_treino.setChecked(ligar)
        self._mostrar_faixa_treino(ligar)
        self._atualizar_titulo()
        if ligar:
            self._status("Modo treinamento ligado: os atendimentos vão para o treino.db e as notas "
                         "para notas_treino/. O caixa de verdade não muda.")
        else:
            self._status("Modo treinamento desligado. De volta ao caixa de verdade.")

    def zerar_treino(self):
        resposta = QMessageBox.question(
            self, "Zerar banco de treino",
            "Apagar todos os atendimentos, notas e relatórios do TREINAMENTO?\n"
            "(O caixa de verdade não é tocado.)")
        if resposta != QMessageBox.Yes:
            return
        if treino.ativo() and self._tem_atendimento_aberto():
            self.cancelar_atendimento(perguntar=False)
        try:
            banco.zerar_treino()
        except (OSError, sqlite3.Error) as erro:
            QMessageBox.critical(self, "Zerar banco de treino", f"Não foi possível apagar o treino:\n{erro}")
            return
        self._status("Treino zerado: o próximo atendimento de treino começa do nº 1.")

    def limpar_dados(self):
        TelaLimpar(self, ao_limpar=lambda: self._status("Dados apagados (com cópia de segurança em backups/).")).exec()

    def _criar_barra_status(self):
        self.lbl_status = QLabel("Pronto.")
        self.statusBar().addWidget(self.lbl_status, 1)
        self.btn_teclado = QPushButton()
        self.btn_teclado.setFocusPolicy(Qt.NoFocus)
        acao_teclado = self.paineis["teclado"].toggleViewAction()
        self.btn_teclado.clicked.connect(acao_teclado.trigger)
        acao_teclado.toggled.connect(self._atualizar_botao_teclado)
        self.statusBar().addPermanentWidget(self.btn_teclado)
        self._atualizar_botao_teclado(True)

    def _atualizar_botao_teclado(self, visivel):
        texto = "Esconder teclado" if visivel else "Mostrar teclado"
        self.btn_teclado.setText(texto + self._tecla("teclado", "  "))

    def _tecla(self, acao, antes=""):
        """A tecla da ação para mostrar num texto (com 'antes' na frente), ou "" se não tiver."""
        tecla = self.atalhos.get(acao, "")
        return antes + tecla if tecla else ""

    def _tecla_do_servico(self, indice):
        return self.atalhos.get(atalhos.acao_do_servico(self.config.servicos[indice].id), "")

    def _carregar_atalhos(self):
        """
        Junta as teclas salvas com as dos serviços atuais. A tecla que um serviço
        recebeu sozinho (1 a 0) fica gravada, para ele não mudar de tecla se a
        ordem dos serviços mudar depois.
        """
        self.atalhos = atalhos.completar(self.preferencias["atalhos"], self._ids_servicos())
        if self.preferencias["atalhos"] != self.atalhos:
            self.preferencias["atalhos"] = dict(self.atalhos)
            self._salvar_preferencias()

    def _ids_servicos(self):
        return [servico.id for servico in self.config.servicos]

    def _texto_teclas_servicos(self):
        """Ex.: 'tecla 1 a 0' (de fábrica) ou 'tecla de atalho' (se a pessoa trocou)."""
        teclas = [self._tecla_do_servico(i) for i in range(len(self.config.servicos))]
        if teclas and teclas == list(atalhos.TECLAS_SERVICOS[:len(teclas)]):
            return f"tecla {teclas[0]} a {teclas[-1]}"
        return "tecla de atalho" if any(teclas) else ""

    def _aplicar_textos_atalhos(self):
        """Escreve as teclas de atalho atuais em todos os botões, rótulos e menus."""
        teclas = self._texto_teclas_servicos()
        self.lbl_aviso_vazio.setText("Nenhum item ainda.\nEscolha um serviço"
                                     + (f" ({teclas.replace('tecla', 'teclas', 1)})" if teclas else "")
                                     + " para começar.")
        self.btn_remover.setText("Remover item" + self._tecla("remover", "  "))
        self.btn_cancelar.setText("Cancelar atendimento" + self._tecla("cancelar", "  "))
        def entre_parenteses(acao):  # "Nome (F2)" ou só "Nome" se não tiver atalho
            tecla = self._tecla(acao)
            return f" ({tecla})" if tecla else ""
        self.lbl_rotulo_nome.setText(f"Nome{entre_parenteses('nome')} · opcional")
        self.lbl_rotulo_telefone.setText(f"Telefone{entre_parenteses('telefone')} · opcional")
        self.lbl_rotulo_recebido.setText(f"Valor recebido{entre_parenteses('recebido')} · vazio = valor exato")
        self.btn_finalizar.setText("Finalizar" + self._tecla("finalizar", "  "))
        # No menu, o que vem depois do \t aparece alinhado à direita (como atalho).
        self.acao_relatorio.setText("Relatório do dia..." + self._tecla("relatorio", "\t"))
        self.acao_teclado.setText("Teclado na tela" + self._tecla("teclado", "\t"))
        self._atualizar_botao_teclado(self.acao_teclado.isChecked())
        self._atualizar_textos_pagamento()
        self._textos_botoes_servicos()
        if self.servico_atual is None:
            self._limpar_selecao_servico()

    def configurar_atalhos(self):
        TelaAtalhos(self, self.atalhos, [(s.id, s.nome) for s in self.config.servicos],
                    ao_salvar=self._atalhos_salvos).exec()

    def _atalhos_salvos(self, novos):
        self.atalhos = atalhos.completar(novos, self._ids_servicos())
        self.preferencias["atalhos"] = dict(self.atalhos)
        self._salvar_preferencias()
        self._aplicar_textos_atalhos()
        self._status("Atalhos do teclado salvos.")

    def _executar_atalho(self, acao):
        """Faz o que o atalho manda. Devolve False se não havia nada para fazer."""
        id_servico = atalhos.id_do_servico(acao)
        if id_servico is not None:
            indice = self._ids_servicos().index(id_servico) if id_servico in self._ids_servicos() else None
            if indice is None:
                return False
            self.selecionar_servico(indice)
        elif acao in atalhos.FORMA_DA_ACAO:
            self.botoes_pagamento[atalhos.FORMA_DA_ACAO[acao]].setChecked(True)
        elif acao == "nome":
            self._focar(self.entry_nome)
        elif acao == "telefone":
            self._focar(self.entry_telefone)
        elif acao == "recebido":
            self._focar_recebido()
        elif acao == "teclado":
            self.acao_teclado.trigger()
        elif acao == "relatorio":
            self.relatorio_do_dia()
        elif acao == "finalizar":
            self.finalizar_atendimento()
        elif acao == "remover":
            self.remover_item(pelo_teclado=True)
        elif acao == "cancelar":
            self._tecla_esc()
        return True

    def _desta_janela(self, widget):
        """True se o widget está nesta janela ou num painel dela que está flutuando."""
        if not isinstance(widget, QWidget):
            return False
        janela = widget.window()
        return janela is self or (isinstance(janela, QDockWidget) and janela in self.paineis.values())

    def _acao_da_tecla(self, objeto, evento):
        """Qual atalho a tecla apertada dispara aqui (ou None)."""
        texto = atalhos.tecla_do_evento(evento)
        if not texto:
            return None
        # Num campo de texto, números, letras e Delete são para digitar.
        if isinstance(objeto, QLineEdit) and atalhos.eh_de_digitacao(texto):
            return None
        for acao, tecla in self.atalhos.items():
            if tecla == texto:
                return acao
        return None

    def eventFilter(self, objeto, evento):
        """
        Recebe todas as teclas do programa ANTES dos campos. Cuida de:
          - todos os atalhos (as teclas escolhidas em Ajuda › Atalhos do teclado),
            em qualquer painel, mesmo flutuando. Com uma janela de diálogo aberta
            (ex.: Configurar notinhas) eles não funcionam;
          - Enter aperta o botão que está selecionado (o Qt só usa a barra de espaço).
        """
        tipo = evento.type()
        if self.modo_tablet and tipo in (QEvent.MouseButtonPress, QEvent.TouchBegin) \
                and isinstance(objeto, QWidget) and objeto.toolTip() and self._desta_janela(objeto):
            # No tablet não existe "passar o mouse por cima": a dica aparece na barra de baixo.
            self._status(objeto.toolTip())
        if tipo in (QEvent.KeyPress, QEvent.ShortcutOverride) and self._desta_janela(objeto):
            if tipo == QEvent.KeyPress and evento.key() in (Qt.Key_Return, Qt.Key_Enter) \
                    and isinstance(objeto, QAbstractButton):
                if objeto.isEnabled():
                    objeto.animateClick()
                return True
            acao = self._acao_da_tecla(objeto, evento)
            if acao is not None:
                if tipo == QEvent.ShortcutOverride:
                    # "Essa tecla é nossa": assim o Qt não a usa para outra coisa
                    # (ex.: Alt+A abriria o menu Arquivo) e ela chega aqui como KeyPress.
                    evento.accept()
                    return True
                # Segurar a tecla apertada não repete a ação (ex.: finalizar duas vezes).
                if evento.isAutoRepeat() or self._executar_atalho(acao):
                    return True  # a tecla já foi usada; ninguém mais precisa dela
        return super().eventFilter(objeto, evento)

    def _tecla_esc(self):
        # Esc no campo do item: só desiste do item. Em qualquer outro lugar: cancela o atendimento.
        if QApplication.focusWidget() is self.entry_item:
            self._limpar_selecao_servico()
            self._focar(self.tabela if self.carrinho else None)
        else:
            self.cancelar_atendimento()

    def _atalho_servico(self, caractere):
        """Escolhe o serviço cujo atalho é essa tecla (usado pelo teclado na tela)."""
        for indice in range(len(self.config.servicos)):
            if caractere and self._tecla_do_servico(indice) == caractere:
                self.selecionar_servico(indice)
                return

    # ------------------------------------------------------------------
    # Foco e teclado na tela
    # ------------------------------------------------------------------

    def _foco_mudou(self, _antigo, novo):
        """Guarda o último campo desta janela que recebeu o cursor."""
        if novo is not None and self._desta_janela(novo):
            self._ultimo_campo = novo
        if self.modo_tablet and novo is self.entry_nome:
            toque.abrir_teclado_windows()  # o Nome precisa de letras: abre o teclado do Windows

    def _focar(self, widget):
        """
        Põe o cursor no widget (ou tira de tudo, se widget for None).
        Se o painel dele estiver escondido, mostra; se estiver em outra janela
        (painel flutuando), ativa essa janela.
        """
        if widget is None:
            atual = QApplication.focusWidget()
            if atual is not None and self._desta_janela(atual):
                atual.clearFocus()
            self._ultimo_campo = None
            return
        painel = widget.parent()
        while painel is not None and not isinstance(painel, QDockWidget):
            painel = painel.parent()
        if painel is not None and not painel.isVisible():
            painel.show()
        if painel is not None:
            painel.raise_()  # se estiver numa aba, traz a aba para a frente
        widget.window().activateWindow()
        widget.setFocus()
        self._ultimo_campo = widget

    def _tecla_na_tela(self, tecla):
        """Chamada quando um botão do teclado na tela é apertado."""
        campo = self._ultimo_campo

        if tecla == "enter":
            # Manda um Enter de verdade para o campo selecionado: assim ele faz exatamente
            # o mesmo que o Enter do teclado físico (adicionar item, ir para o próximo campo...).
            if campo is not None:
                self._focar(campo)
                QApplication.sendEvent(campo, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
            return

        campos_numericos = (self.entry_item, self.entry_recebido, self.entry_telefone)
        if campo in campos_numericos:
            if campo.isEnabled():
                self._focar(campo)  # devolve o cursor (caso o teclado esteja flutuando)
                digitar_no_campo(campo, tecla)
        elif campo is not self.entry_nome:
            # Nenhum campo numérico selecionado: os números escolhem o serviço,
            # igual ao teclado físico.
            self._atalho_servico(tecla)

    def _focar_recebido(self):
        self.botoes_pagamento["Dinheiro"].setChecked(True)
        self._focar(self.entry_recebido)
        self.entry_recebido.selectAll()

    def _aplicar_mascara_telefone(self, texto):
        """Formata o telefone enquanto a pessoa digita: (21) 99999-9999."""
        if self._formatando_telefone:
            return
        formatado = formatar_telefone(texto)
        if formatado != texto:
            self._formatando_telefone = True
            self.entry_telefone.setText(formatado)  # setText já põe o cursor no fim
            self._formatando_telefone = False

    # ------------------------------------------------------------------
    # Layout dos painéis
    # ------------------------------------------------------------------

    def _soltar_paineis(self):
        """Tira todos os painéis do lugar, para montar um layout do zero."""
        for painel in self.paineis.values():
            painel.setFloating(False)  # painel desgrudado volta para dentro da janela
            self.removeDockWidget(painel)

    def _mostrar_todos(self):
        for painel in self.paineis.values():
            painel.setFloating(False)
            painel.show()

    def _organizar_layout_padrao(self):
        """
        Layout "Padrão" (o de fábrica):
          ┌──────────┬────────────────────┬─────────┬───────────┐
          │          │ Adicionar item               │ Cliente   │
          │ Serviços ├────────────────────┬─────────┤ Pagamento │
          │          │ Atendimento atual  │ Teclado │ Totais    │
          └──────────┴────────────────────┴─────────┴───────────┘
        """
        p = self.paineis
        self._soltar_paineis()
        self.addDockWidget(Qt.LeftDockWidgetArea, p["servicos"])
        self.splitDockWidget(p["servicos"], p["item"], Qt.Horizontal)
        self.splitDockWidget(p["item"], p["atendimento"], Qt.Vertical)
        self.splitDockWidget(p["atendimento"], p["teclado"], Qt.Horizontal)
        self.addDockWidget(Qt.RightDockWidgetArea, p["cliente"])
        self.splitDockWidget(p["cliente"], p["pagamento"], Qt.Vertical)
        self.splitDockWidget(p["pagamento"], p["totais"], Qt.Vertical)
        self._mostrar_todos()

    def _organizar_layout_compacto(self):
        """
        Layout "Compacto" (tela pequena): três colunas, Cliente em aba junto do
        Pagamento e o teclado escondido (o atalho do teclado mostra, também como aba).
          ┌──────────┬────────────────────┬─────────────────────┐
          │          │ Adicionar item     │ [Pagamento|Cliente] │
          │ Serviços ├────────────────────┼─────────────────────┤
          │          │ Atendimento atual  │ Totais              │
          └──────────┴────────────────────┴─────────────────────┘
        """
        p = self.paineis
        self._soltar_paineis()
        self.addDockWidget(Qt.LeftDockWidgetArea, p["servicos"])
        self.splitDockWidget(p["servicos"], p["item"], Qt.Horizontal)
        self.splitDockWidget(p["item"], p["atendimento"], Qt.Vertical)
        self.addDockWidget(Qt.RightDockWidgetArea, p["pagamento"])
        self.splitDockWidget(p["pagamento"], p["totais"], Qt.Vertical)
        self.tabifyDockWidget(p["pagamento"], p["cliente"])
        self.tabifyDockWidget(p["cliente"], p["teclado"])
        self._mostrar_todos()
        p["teclado"].hide()
        p["pagamento"].raise_()  # a aba do Pagamento fica na frente

    # As colunas do layout Touch (para saber se as quatro cabem na tela).
    COLUNAS_TOUCH = (["servicos"], ["item", "atendimento"], ["teclado"], ["cliente", "pagamento", "totais"])
    # (as do Touch de três colunas, para conferir que elas cabem)
    COLUNAS_TOUCH_ESTREITO = (["servicos"], ["item", "teclado", "atendimento"], ["cliente", "pagamento", "totais"])

    def _largura_minima(self, nomes):
        """A largura que uma coluna de painéis precisa para nada ficar cortado."""
        return max(self.paineis[nome].widget().minimumSizeHint().width() for nome in nomes) + 12

    def _largura_disponivel(self):
        """A largura da janela (a de antes de ligar o tablet), sem passar da tela onde ela está."""
        largura = getattr(self, "_largura_alvo", None) or self.width()
        tela = self.screen().availableGeometry().width() if self.screen() else largura
        return min(largura, tela)

    def _voltar_para_largura_alvo(self):
        """
        Com as letras maiores, o Qt alarga a janela antes de o layout novo ficar pronto.
        Depois de pronto, ela volta para a largura de antes (se o layout novo couber nela).
        """
        alvo, self._largura_alvo = getattr(self, "_largura_alvo", None), None
        if alvo and not (self.isMaximized() or self.isFullScreen()) and self.width() > alvo:
            self.resize(max(alvo, self.minimumSizeHint().width()), self.height())

    def _touch_em_tres_colunas(self):
        """True se as quatro colunas do Touch não cabem (telas de 1440 px ou menos no modo tablet)."""
        return sum(self._largura_minima(coluna) for coluna in self.COLUNAS_TOUCH) > self._largura_disponivel()

    def _organizar_layout_touch(self):
        """
        Layout "Touch": o teclado (com teclas grandes) ganha uma coluna inteira.
          ┌──────────┬────────────────┬─────────────┬───────────┐
          │          │ Adicionar item │             │ Cliente   │
          │ Serviços ├────────────────┤   Teclado   │ Pagamento │
          │          │ Atendimento    │   grande    │ Totais    │
          └──────────┴────────────────┴─────────────┴───────────┘
        Se as quatro colunas não cabem na tela, o teclado vai para baixo do "Adicionar item"
        e o Cliente fica em aba junto do Pagamento (F2 traz a aba para a frente):
          ┌──────────┬────────────────┬─────────────────────┐
          │          │ Adicionar item │ [Pagamento|Cliente] │
          │ Serviços │ Teclado grande ├─────────────────────┤
          │          │ Atendimento    │ Totais              │
          └──────────┴────────────────┴─────────────────────┘
        """
        p = self.paineis
        self._soltar_paineis()
        self._touch_estreito = self._touch_em_tres_colunas()
        self.teclado.definir_grande(True, baixo=self._touch_estreito)
        self.addDockWidget(Qt.LeftDockWidgetArea, p["servicos"])
        self.splitDockWidget(p["servicos"], p["item"], Qt.Horizontal)
        if self._touch_estreito:
            self.splitDockWidget(p["item"], p["teclado"], Qt.Vertical)
            self.splitDockWidget(p["teclado"], p["atendimento"], Qt.Vertical)
            self.addDockWidget(Qt.RightDockWidgetArea, p["pagamento"])
            self.splitDockWidget(p["pagamento"], p["totais"], Qt.Vertical)
            self.tabifyDockWidget(p["pagamento"], p["cliente"])
            self._mostrar_todos()
            p["pagamento"].raise_()  # a aba do Pagamento fica na frente
            return
        self.splitDockWidget(p["item"], p["teclado"], Qt.Horizontal)
        self.splitDockWidget(p["item"], p["atendimento"], Qt.Vertical)
        self.addDockWidget(Qt.RightDockWidgetArea, p["cliente"])
        self.splitDockWidget(p["cliente"], p["pagamento"], Qt.Vertical)
        self.splitDockWidget(p["pagamento"], p["totais"], Qt.Vertical)
        self._mostrar_todos()

    def _ajustar_tamanhos(self, colunas, direita, meio=("item", "atendimento")):
        """
        Acerta os tamanhos depois de montar um layout.
        colunas = [(painel, fração da largura da janela), ...] da esquerda para a direita;
        direita = painéis da coluna da direita, de cima para baixo. Cada um fica com a
                  altura que o conteúdo pede e o último fica com o que sobrar;
        meio    = os painéis da coluna do meio, do mesmo jeito.
        """
        p = self.paineis
        largura = self.width()
        # Cada coluna ganha primeiro o mínimo que precisa (nada cortado) e o que sobrar
        # da janela é dividido conforme as frações. (Antes era só a fração, e numa
        # janela estreita o teclado grande ficava mais estreito que as teclas.)
        grupos = {"atendimento": list(meio), "pagamento": [*direita, "cliente"], "cliente": list(direita)}
        minimos = [self._largura_minima(grupos.get(nome, [nome])) for nome, _ in colunas]
        sobra = max(largura - sum(minimos), 0)
        soma_fracoes = sum(fracao for _, fracao in colunas) or 1
        self.resizeDocks([p[nome] for nome, _ in colunas],
                         [int(minimo + sobra * fracao / soma_fracoes) for minimo, (_, fracao) in zip(minimos, colunas)],
                         Qt.Horizontal)
        # Em cada coluna, os painéis de cima ficam com a altura certa e o de baixo
        # com o resto. O total é a altura que a coluna tem hoje (se passássemos mais
        # do que cabe, o Qt encolheria todos e apareceria barra de rolagem).
        for coluna in (list(meio), direita):
            paineis = [p[nome] for nome in coluna]
            total = sum(painel.height() + self._altura_abas(painel) for painel in paineis)
            alturas = [self._altura_necessaria(painel) for painel in paineis[:-1]]
            alturas.append(max(total - sum(alturas), 100))
            self.resizeDocks(paineis, alturas, Qt.Vertical)

    def _altura_necessaria(self, painel):
        """
        Altura para o painel mostrar todo o conteúdo sem barra de rolagem:
        a "moldura" (barra de título e bordas) mais a altura que o conteúdo pede.
        Se o painel estiver em abas, vale o conteúdo mais alto entre elas.
        """
        area = painel.widget()
        moldura = painel.height() - area.viewport().height()
        grupo = [painel, *self.tabifiedDockWidgets(painel)]
        conteudo = max(dock.widget().widget().sizeHint().height() for dock in grupo)
        return conteudo + moldura + self._altura_abas(painel) + 2

    def _altura_abas(self, painel):
        """Altura da barra de abas embaixo do painel (0 se ele não estiver em abas)."""
        for barra in self.findChildren(QTabBar):
            if barra.isVisible() and painel.windowTitle() in (barra.tabText(i) for i in range(barra.count())):
                return barra.height()
        return 0

    def _ajustar_tamanhos_padrao(self):
        self._ajustar_tamanhos([("servicos", 0.21), ("atendimento", 0.40), ("teclado", 0.17), ("cliente", 0.22)],
                               ["cliente", "pagamento", "totais"])

    def _ajustar_tamanhos_compacto(self):
        self._ajustar_tamanhos([("servicos", 0.27), ("atendimento", 0.45), ("pagamento", 0.28)],
                               ["pagamento", "totais"])

    def _ajustar_tamanhos_touch(self):
        if getattr(self, "_touch_estreito", False):  # (três colunas: o teclado está no meio)
            self._ajustar_tamanhos([("servicos", 0.30), ("atendimento", 0.40), ("pagamento", 0.30)],
                                   ["pagamento", "totais"], meio=("item", "teclado", "atendimento"))
            return
        self._ajustar_tamanhos([("servicos", 0.20), ("atendimento", 0.30), ("teclado", 0.27), ("cliente", 0.23)],
                               ["cliente", "pagamento", "totais"])

    def _layouts_prontos(self):
        """Nome -> (função que monta, função que acerta os tamanhos, teclado grande?)."""
        return {
            "Padrão": (self._organizar_layout_padrao, self._ajustar_tamanhos_padrao, False),
            "Compacto": (self._organizar_layout_compacto, self._ajustar_tamanhos_compacto, False),
            "Touch": (self._organizar_layout_touch, self._ajustar_tamanhos_touch, True),
        }

    def usar_layout(self, nome):
        """Troca a arrumação dos painéis por um layout pronto ou por um salvo com nome."""
        prontos = self._layouts_prontos()
        if nome in prontos:
            organizar, ajustar, teclado_grande = prontos[nome]
            self.teclado.definir_grande(teclado_grande)
            self._recalcular_larguras_minimas()
            organizar()
            # Os tamanhos só podem ser acertados depois que o Qt arrumar os painéis.
            QTimer.singleShot(0, lambda: (self._voltar_para_largura_alvo(), ajustar()))
        else:
            salvo = self.preferencias["layouts_salvos"].get(nome)
            if salvo is None:
                return
            self.teclado.definir_grande(salvo["teclado_grande"])
            if not self._restaurar_estado(salvo["estado"]):
                QMessageBox.warning(self, "Layout", f"Não foi possível abrir o layout “{nome}”.\n"
                                    "Ele foi salvo numa versão antiga do programa.")
                return
        self.preferencias["layout_atual"] = nome
        self._salvar_preferencias()
        self._status(f"Layout “{nome}” aplicado.")

    def _recalcular_larguras_minimas(self):
        """
        Faz cada painel medir de novo a largura mínima do conteúdo. Sem isto, depois de
        trocar o tamanho das letras (modo tablet) os painéis continuavam pedindo a largura
        de antes, e a janela ficava mais larga que a tela (cortada à direita).
        """
        for painel in self.paineis.values():
            conteudo = painel.widget().widget()
            for widget in (conteudo, *conteudo.findChildren(QWidget)):
                if widget.layout() is not None:
                    widget.layout().invalidate()
            if conteudo.layout() is not None:
                conteudo.layout().activate()
            painel.widget().updateGeometry()

    def _restaurar_estado(self, texto):
        """Põe os painéis como no estado salvo (texto base64). Devolve False se não deu."""
        ok = self.restoreState(QByteArray.fromBase64(texto.encode("ascii")), VERSAO_LAYOUT)
        # O estado salvo também lembra se a faixa do treino estava aparecendo: quem manda
        # nela é só o modo treinamento.
        self._mostrar_faixa_treino(treino.ativo())
        return ok

    def _estado_atual(self):
        """A arrumação atual dos painéis, como texto (para guardar no preferencias.json)."""
        return {
            "estado": bytes(self.saveState(VERSAO_LAYOUT).toBase64()).decode("ascii"),
            "teclado_grande": self.teclado.grande,
        }

    def restaurar_layout_padrao(self):
        """Volta para o layout definido como padrão (ou o Padrão de fábrica, se nenhum foi definido)."""
        padrao = self.preferencias["layout_padrao"]
        if not padrao:
            self.usar_layout("Padrão")
            return
        self.teclado.definir_grande(padrao["teclado_grande"])
        if not self._restaurar_estado(padrao["estado"]):
            # (salvo numa versão antiga do programa: usa o de fábrica e esquece o antigo)
            self.preferencias["layout_padrao"] = {}
            self.usar_layout("Padrão")
            return
        self.preferencias["layout_atual"] = padrao.get("nome", "")
        self._salvar_preferencias()
        self._status("Layout padrão aplicado.")

    def definir_layout_padrao(self):
        """O "Restaurar layout padrão" passa a voltar para a arrumação que está na tela agora."""
        self.preferencias["layout_padrao"] = {**self._estado_atual(), "nome": self.preferencias["layout_atual"]}
        self._salvar_preferencias()
        self._status("Pronto: o layout atual agora é o padrão (Exibir › Restaurar layout padrão volta para ele).")

    def voltar_layout_padrao_de_fabrica(self):
        self.preferencias["layout_padrao"] = {}
        self._salvar_preferencias()
        self.usar_layout("Padrão")
        self._status("O layout padrão voltou a ser o de fábrica.")

    def _montar_menu_layouts(self):
        """Monta o menu Exibir › Layouts (chamado toda vez que ele é aberto)."""
        menu = self.menu_layouts
        menu.clear()
        atual = self.preferencias["layout_atual"]
        salvos = self.preferencias["layouts_salvos"]
        for nome in LAYOUTS_PRONTOS + sorted(salvos, key=str.lower):
            acao = menu.addAction(nome, lambda nome=nome: self.usar_layout(nome))
            acao.setCheckable(True)
            acao.setChecked(nome == atual)
            acao.setToolTip(DICAS_LAYOUTS.get(nome, "Layout salvo"))
            if nome == LAYOUTS_PRONTOS[-1] and salvos:
                menu.addSeparator()  # separa os prontos dos salvos
        menu.addSeparator()
        menu.addAction("Salvar layout atual como...", self.salvar_layout_como)
        menu_excluir = menu.addMenu("Excluir layout salvo")
        menu_excluir.setEnabled(bool(salvos))
        for nome in sorted(salvos, key=str.lower):
            menu_excluir.addAction(nome, lambda nome=nome: self.excluir_layout(nome))
        menu.addSeparator()
        acao = menu.addAction("Definir layout atual como padrão", self.definir_layout_padrao)
        acao.setToolTip("O \"Restaurar layout padrão\" passa a voltar para esta arrumação")
        acao = menu.addAction("Voltar ao layout padrão de fábrica", self.voltar_layout_padrao_de_fabrica)
        acao.setEnabled(bool(self.preferencias["layout_padrao"]))

    def salvar_layout_como(self):
        """Guarda a arrumação atual dos painéis com um nome."""
        atual = self.preferencias["layout_atual"]
        sugestao = atual if atual in self.preferencias["layouts_salvos"] else ""
        nome, ok = QInputDialog.getText(self, "Salvar layout", "Nome do layout:", text=sugestao)
        nome = nome.strip()
        if not ok or not nome:
            return
        if nome.lower() in (pronto.lower() for pronto in LAYOUTS_PRONTOS):
            QMessageBox.warning(self, "Salvar layout",
                                f"“{nome}” é o nome de um layout pronto. Escolha outro nome.")
            return
        salvos = self.preferencias["layouts_salvos"]
        if nome in salvos:
            resposta = QMessageBox.question(self, "Salvar layout",
                                            f"Já existe um layout chamado “{nome}”. Substituir?")
            if resposta != QMessageBox.Yes:
                return
        salvos[nome] = self._estado_atual()
        self.preferencias["layout_atual"] = nome
        self._salvar_preferencias()
        self._status(f"Layout “{nome}” salvo. Ele aparece em Exibir › Layouts.")

    def excluir_layout(self, nome):
        resposta = QMessageBox.question(self, "Excluir layout", f"Excluir o layout “{nome}”?\n"
                                        "(A arrumação que está na tela agora não muda.)")
        if resposta != QMessageBox.Yes:
            return
        self.preferencias["layouts_salvos"].pop(nome, None)
        if self.preferencias["layout_atual"] == nome:
            self.preferencias["layout_atual"] = ""
        self._salvar_preferencias()
        self._status(f"Layout “{nome}” excluído.")

    def _restaurar_layout_salvo(self):
        """Abre a janela e os painéis como estavam ao fechar. Devolve True se conseguiu."""
        geometria = self.preferencias["geometria_janela"]
        estado = self.preferencias["estado_paineis"]
        if not geometria or not estado:
            return False
        # O Qt guarda o layout como bytes; no arquivo eles ficam como texto (base64).
        ok_janela = self.restoreGeometry(QByteArray.fromBase64(geometria.encode("ascii")))
        ok_paineis = self._restaurar_estado(estado)
        if not ok_paineis:
            self._organizar_layout_padrao()
        return ok_janela and ok_paineis

    def _aplicar_trava(self, travado):
        """Travado: os painéis não podem ser arrastados, desgrudados, fechados nem redimensionados."""
        self._travado = travado
        if travado:
            recursos = QDockWidget.NoDockWidgetFeatures
        else:
            recursos = (QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
                        | QDockWidget.DockWidgetClosable)
        for painel in self.paineis.values():
            painel.setFeatures(recursos)
        if self.acao_travar.isChecked() != travado:
            self.acao_travar.setChecked(travado)

    def event(self, evento):
        # Com o layout travado, ignora o clique nas divisórias entre os painéis
        # (é esse clique que começa a redimensionar).
        # (getattr: o Qt já chama event() enquanto a janela ainda está sendo criada)
        travado = getattr(self, "_travado", False)
        if travado and evento.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            return True
        return super().event(evento)

    def closeEvent(self, evento):
        """Ao fechar: salva o tamanho da janela e a posição dos painéis."""
        if getattr(self, "_sem_salvar_ao_fechar", False):
            QApplication.instance().removeEventFilter(self)
            super().closeEvent(evento)
            return
        self.preferencias["geometria_janela"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.preferencias["estado_paineis"] = bytes(self.saveState(VERSAO_LAYOUT).toBase64()).decode("ascii")
        self.preferencias["layout_travado"] = self._travado
        self.preferencias["teclado_grande"] = self.teclado.grande
        self._salvar_preferencias()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(evento)

    def _salvar_preferencias(self):
        preferencias.salvar(self.preferencias)

    def _conferir_preferencias(self):
        """Corrige o que vier estragado do preferencias.json (o programa sempre abre)."""
        prefs = self.preferencias
        if prefs["modo_cor"] not in estilo.MODOS:
            prefs["modo_cor"] = "sistema"
        prefs["cores"] = estilo.completar_cores(prefs["cores"])
        prefs["temas_salvos"] = estilo.conferir_temas_salvos(prefs["temas_salvos"])
        # Só ficam os layouts salvos que têm o formato certo.
        prefs["layouts_salvos"] = {
            nome: {"estado": dados["estado"], "teclado_grande": bool(dados.get("teclado_grande"))}
            for nome, dados in prefs["layouts_salvos"].items()
            if isinstance(dados, dict) and isinstance(dados.get("estado"), str)
        }
        padrao = prefs["layout_padrao"]
        if isinstance(padrao.get("estado"), str) and padrao["estado"]:
            prefs["layout_padrao"] = {"estado": padrao["estado"],
                                      "teclado_grande": bool(padrao.get("teclado_grande")),
                                      "nome": padrao.get("nome") if isinstance(padrao.get("nome"), str) else ""}
        else:
            prefs["layout_padrao"] = {}

    # ------------------------------------------------------------------
    # Modo claro/escuro e cores
    # ------------------------------------------------------------------

    def _aplicar_tema(self):
        # (a trava evita repetir: aplicar o tema pode fazer o Qt avisar "o esquema de cor mudou")
        if self._aplicando_tema:
            return
        self._aplicando_tema = True
        try:
            self._modo_efetivo = estilo.aplicar(QApplication.instance(), self.preferencias["modo_cor"],
                                                self.preferencias["cores"])
        finally:
            self._aplicando_tema = False

    def definir_modo_cor(self, modo):
        """Menu Exibir › Modo de cor: 'claro', 'escuro' ou 'sistema' (seguir o Windows)."""
        self.preferencias["modo_cor"] = modo
        self._aplicar_tema()
        self.acoes_modo[modo].setChecked(True)
        self._salvar_preferencias()
        self._status(f"Modo de cor: {estilo.MODOS[modo]}.")

    def _windows_mudou_cor(self, *_args):
        # Só interessa se a pessoa escolheu "Seguir o Windows".
        if self.preferencias["modo_cor"] == "sistema":
            self._aplicar_tema()

    def configurar_cores(self):
        TelaCores(self, self.preferencias["cores"], self._modo_efetivo, self._cores_salvas,
                  self.preferencias["temas_salvos"], self._temas_salvos).exec()

    def _temas_salvos(self, temas):
        self.preferencias["temas_salvos"] = temas
        self._salvar_preferencias()

    def _cores_salvas(self, cores):
        self.preferencias["cores"] = cores
        self._aplicar_tema()
        self._salvar_preferencias()
        nome = estilo.nome_do_tema(cores, self.preferencias["temas_salvos"])
        self._status(f"Cores salvas (tema {nome})." if nome else "Cores salvas.")

    # ------------------------------------------------------------------
    # Serviços e carrinho
    # ------------------------------------------------------------------

    @staticmethod
    def _descricao_preco(servico, pede_valor=False):
        if pede_valor:
            return f"valor + {formatar_reais(servico.preco_do_servico)}"
        if servico.tipo == "unidade":
            return f"{formatar_reais(servico.preco)} un."
        return f"valor + {formatar_reais(servico.taxa)}"

    def selecionar_servico(self, indice):
        """Escolhe o serviço e prepara o campo para digitar a quantidade ou o valor."""
        self.servico_atual = self.config.servicos[indice]
        for i, botao in enumerate(self.botoes_servicos):
            botao.definir_selecionado(i == indice)

        self.lbl_servico_atual.setText(
            f"{self.servico_atual.nome} · "
            f"{self._descricao_preco(self.servico_atual, self.config.pede_valor(self.servico_atual))}")
        self.lbl_servico_atual.setProperty("vazio", False)
        repintar(self.lbl_servico_atual)
        self.entry_item.setEnabled(True)
        self.btn_adicionar.setEnabled(True)
        if self.config.pede_valor(self.servico_atual):
            self._rotulo_do_campo(f"{self._nome_do_valor(self.servico_atual)} (R$)")
            self.entry_item.setText("")
        elif self.servico_atual.tipo == "unidade":
            self._rotulo_do_campo("Quantidade")
            self.entry_item.setText("1")  # já vem 1: é só apertar Enter
        else:
            self._rotulo_do_campo("Valor (R$)")
            self.entry_item.setText("")
        self._atualizar_previa()  # (o campo pode já estar vazio: aí o textChanged não avisa)
        self._focar(self.entry_item)
        self.entry_item.selectAll()  # seleciona o texto para a pessoa digitar por cima

    def _limpar_selecao_servico(self):
        self.servico_atual = None
        for botao in self.botoes_servicos:
            botao.definir_selecionado(False)
        teclas = self._texto_teclas_servicos()
        self.lbl_servico_atual.setText(f"Escolha um serviço: {teclas} ou clique" if teclas
                                       else "Escolha um serviço: clique nele")
        self.lbl_servico_atual.setProperty("vazio", True)
        repintar(self.lbl_servico_atual)
        self.entry_item.setText("")
        self._rotulo_do_campo("Quantidade")
        self.entry_item.setEnabled(False)
        self.btn_adicionar.setEnabled(False)

    def _montar_item(self, texto):
        """
        Cria o dicionário do item a partir do que foi digitado.
        Se o texto for inválido, as funções converter_* lançam ValueError.
        """
        servico = self.servico_atual
        if self.config.pede_valor(servico):
            # Boleto/recarga: o item vale só o serviço da loja; o valor do boleto vai à parte
            # ("valor_terceiros"), só para cobrar e dar o troco. Sem taxa da maquininha.
            valor = converter_valor(texto)
            return {
                "servico": servico.nome,
                "tipo": "unidade",
                "quantidade": 1,
                "valor_unitario": servico.preco_do_servico,
                "valor_digitado": ZERO,
                "taxa_servico": ZERO,
                "total": arredondar(servico.preco_do_servico),
                "cobra_taxa_maquininha": False,
                "valor_terceiros": valor,
                "nome_do_valor": servico.nome_do_valor(),
            }
        if servico.tipo == "unidade":
            quantidade = converter_quantidade(texto)
            return {
                "servico": servico.nome,
                "tipo": "unidade",
                "quantidade": quantidade,
                "valor_unitario": servico.preco,
                "valor_digitado": ZERO,
                "taxa_servico": ZERO,
                "total": arredondar(servico.preco * quantidade),
                "cobra_taxa_maquininha": servico.cobra_taxa_maquininha,
            }
        # Tipo "valor": recarga/boleto. Total = valor informado + taxa do serviço.
        valor = converter_valor(texto)
        total = arredondar(valor + servico.taxa)
        return {
            "servico": servico.nome,
            "tipo": "valor",
            "quantidade": 1,
            "valor_unitario": total,
            "valor_digitado": valor,
            "taxa_servico": servico.taxa,
            "total": total,
            "cobra_taxa_maquininha": servico.cobra_taxa_maquininha,
        }

    def _atualizar_previa(self):
        """Mostra embaixo do campo quanto o item vai custar, enquanto a pessoa digita."""
        if not self.servico_atual:
            self.lbl_previa.setText("")
            return
        pede_valor = self.config.pede_valor(self.servico_atual)
        try:
            item = self._montar_item(self.entry_item.text())
        except ValueError:
            self.lbl_previa.setText("")
            if pede_valor:
                self._rotulo_do_campo(f"{self._nome_do_valor(self.servico_atual)} (R$) · serviço "
                                      f"{formatar_reais(self.servico_atual.preco_do_servico)}")
            return
        self.lbl_previa.setText(f"= {formatar_reais(self._cobrar_do_item(item))}")
        if pede_valor:
            self._rotulo_do_campo(self._texto_da_conta(item), destaque=True)

    def _rotulo_do_campo(self, texto, destaque=False):
        """O texto em cima do campo do item (destaque = a conta do boleto/recarga, na cor do tema)."""
        self.lbl_campo_item.setText(texto)
        self.lbl_campo_item.setToolTip(texto if destaque else "")
        if self.lbl_campo_item.property("destaque") != destaque:
            self.lbl_campo_item.setProperty("destaque", destaque)
            repintar(self.lbl_campo_item)

    @staticmethod
    def _nome_do_valor(servico_ou_item):
        """'Valor do boleto', 'Valor da recarga' ou 'Valor do boleto/recarga'."""
        nome = (servico_ou_item.get("nome_do_valor", "boleto/recarga") if isinstance(servico_ou_item, dict)
                else servico_ou_item.nome_do_valor())
        return f"Valor da {nome}" if nome == "recarga" else f"Valor do {nome}"

    @staticmethod
    def _cobrar_do_item(item):
        """Quanto o cliente paga por este item (o serviço + o boleto/recarga, se tiver)."""
        return item["total"] + item.get("valor_terceiros", ZERO)

    def _texto_da_conta(self, item):
        return (f"{self._nome_do_valor(item)}: {formatar_reais(item['valor_terceiros'])} + Serviço: "
                f"{formatar_reais(item['total'])} = Cobrar do cliente: {formatar_reais(self._cobrar_do_item(item))}")

    def adicionar_item(self):
        if not self.servico_atual:
            QMessageBox.warning(self, "Atenção", "Escolha um serviço primeiro.")
            return
        try:
            item = self._montar_item(self.entry_item.text())
        except ValueError as erro:
            QMessageBox.warning(self, "Valor inválido", str(erro))
            self._focar(self.entry_item)
            self.entry_item.selectAll()
            return

        self.carrinho.append(item)
        self._limpar_selecao_servico()
        self._atualizar_carrinho()
        if item.get("valor_terceiros"):
            self._status(f"Adicionado: {item['servico']} - {self._texto_da_conta(item)}")
        else:
            self._status(f"Adicionado: {item['servico']} - {formatar_reais(item['total'])}")

    def _atualizar_carrinho(self):
        """Redesenha a tabela do carrinho e recalcula os totais."""
        self.tabela.setRowCount(len(self.carrinho))
        for linha, item in enumerate(self.carrinho):
            if item.get("valor_terceiros"):
                detalhe = (f"{item['nome_do_valor'].capitalize()} {formatar_reais(item['valor_terceiros'])}"
                           f" + serviço {formatar_reais(item['total'])}")
            elif item["tipo"] == "unidade":
                detalhe = f"{formatar_reais(item['valor_unitario'])} cada"
            else:
                detalhe = f"{formatar_reais(item['valor_digitado'])} + taxa {formatar_reais(item['taxa_servico'])}"
            valores = [item["servico"], str(item["quantidade"]), detalhe,
                       formatar_reais(self._cobrar_do_item(item))]
            for coluna, texto in enumerate(valores):
                celula = QTableWidgetItem(texto)
                if coluna in (1, 3):  # números à direita
                    celula.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabela.setItem(linha, coluna, celula)

        if self.carrinho:
            self.pilha_atendimento.setCurrentWidget(self.tabela)
            # Deixa o último item selecionado, para o Delete funcionar direto.
            self.tabela.selectRow(len(self.carrinho) - 1)
            self._focar(self.tabela)
        else:
            self.pilha_atendimento.setCurrentIndex(0)  # a frase "Nenhum item ainda"
            self._focar(None)
        self.atualizar_totais()

    def remover_item(self, pelo_teclado=False):
        linhas = self.tabela.selectionModel().selectedRows()
        if not self.carrinho or not linhas:
            if pelo_teclado:
                # Pelo atalho, só avisa embaixo (sem janela nem som).
                self._status("Para remover, selecione o item na lista do atendimento.")
            else:
                QMessageBox.information(self, "Remover item", "Selecione na lista o item que deseja remover.")
            return
        item = self.carrinho.pop(linhas[0].row())
        self._atualizar_carrinho()
        self._status(f"Removido: {item['servico']}")

    def cancelar_atendimento(self, perguntar=True):
        """Limpa tudo para começar um novo atendimento."""
        tem_dados = self.carrinho or self.entry_nome.text().strip() or self.entry_telefone.text().strip()
        if perguntar and tem_dados:
            resposta = QMessageBox.question(self, "Cancelar atendimento",
                                            "Deseja apagar todo o atendimento atual?")
            if resposta != QMessageBox.Yes:
                return
        self.carrinho = []
        self.entry_nome.clear()
        self.entry_telefone.clear()
        self.entry_recebido.clear()
        self.botoes_pagamento["Dinheiro"].setChecked(True)
        self._limpar_selecao_servico()
        self._atualizar_carrinho()
        if perguntar and tem_dados:
            self._status("Atendimento cancelado.")

    # ------------------------------------------------------------------
    # Totais e pagamento
    # ------------------------------------------------------------------

    def forma_escolhida(self):
        for forma, botao in self.botoes_pagamento.items():
            if botao.isChecked():
                return forma
        return "Dinheiro"

    def calcular_totais(self):
        """
        Devolve (subtotal, percentual da taxa, valor da taxa, total, base da taxa).
        A taxa da maquininha incide só sobre a "base": os itens que cobram taxa
        (recargas e boletos ficam de fora).
        """
        subtotal = sum((item["total"] for item in self.carrinho), ZERO)
        percentual = self.config.taxas_maquininha.get(self.forma_escolhida(), ZERO)
        base = base_da_taxa(self.carrinho)
        taxa = arredondar(base * percentual / 100)
        return subtotal, percentual, taxa, subtotal + taxa, base

    def repasse(self):
        """Soma dos boletos/recargas do carrinho: cobrado do cliente, mas não é da loja."""
        return sum((item.get("valor_terceiros", ZERO) for item in self.carrinho), ZERO)

    def _mostrar_troco(self, texto, estado=""):
        self.lbl_troco.setText(texto)
        self.lbl_troco.setProperty("estado", estado)  # "positivo" (verde) ou "negativo" (vermelho)
        repintar(self.lbl_troco)

    def atualizar_totais(self):
        """Atualiza os valores na tela (chamada sempre que algo muda)."""
        subtotal, percentual, taxa, total, base = self.calcular_totais()
        self.lbl_subtotal.setText(formatar_reais(subtotal))
        rotulo_taxa = f"Taxa maquininha ({formatar_percentual(percentual)})"
        if percentual and base != subtotal:
            # Atendimento com recarga/boleto: deixa claro sobre quanto a taxa foi calculada.
            rotulo_taxa = f"Taxa maquininha ({formatar_percentual(percentual)} sobre {formatar_reais(base)})"
        self.lbl_taxa_rotulo.setText(rotulo_taxa)
        self.lbl_taxa.setText(formatar_reais(taxa))
        # Com boleto/recarga, o total grande é o que cobrar do cliente (serviços + boletos).
        repasse = self.repasse()
        self.lbl_repasse_rotulo.setVisible(bool(repasse))
        self.lbl_repasse.setVisible(bool(repasse))
        self.lbl_repasse.setText(formatar_reais(repasse))
        self.lbl_total_rotulo.setText("Cobrar do cliente" if repasse else "Total")
        total += repasse  # daqui para baixo (troco), vale o valor cobrado
        self.lbl_total.setText(formatar_reais(total))

        # O campo "valor recebido" só fica ativo quando o pagamento é em dinheiro.
        if self.forma_escolhida() != "Dinheiro":
            self.entry_recebido.setEnabled(False)
            self._mostrar_troco("")
            return
        self.entry_recebido.setEnabled(True)

        texto = self.entry_recebido.text().strip()
        if not texto:
            self._mostrar_troco("")
            return
        try:
            recebido = converter_valor(texto)
        except ValueError:
            self._mostrar_troco("Valor recebido inválido", "negativo")
            return
        troco = recebido - total
        if troco >= 0:
            self._mostrar_troco(f"Troco: {formatar_reais(troco)}", "positivo")
        else:
            self._mostrar_troco(f"Faltam: {formatar_reais(-troco)}", "negativo")

    def finalizar_atendimento(self):
        """Valida tudo, salva no banco, gera a nota da loja e limpa a tela."""
        if not self.carrinho:
            QMessageBox.warning(self, "Atenção", "Adicione pelo menos um serviço antes de finalizar.")
            return

        nome = self.entry_nome.text().strip()
        telefone = self.entry_telefone.text().strip()
        if telefone and len(so_digitos(telefone)) not in (10, 11):
            QMessageBox.warning(self, "Telefone inválido", "O telefone precisa ter DDD + 8 ou 9 dígitos.\n"
                                                           "Ex.: (21) 99999-9999. Ou deixe o campo vazio.")
            self._focar(self.entry_telefone)
            return

        forma = self.forma_escolhida()
        subtotal, percentual, taxa, total, base = self.calcular_totais()
        repasse = self.repasse()
        cobrado = total + repasse  # o que o cliente paga (o troco sai disso)

        recebido = troco = None
        if forma == "Dinheiro":
            texto = self.entry_recebido.text().strip()
            if texto:
                try:
                    recebido = converter_valor(texto)
                except ValueError as erro:
                    QMessageBox.warning(self, "Valor recebido inválido", str(erro))
                    self._focar_recebido()
                    return
                if recebido < cobrado:
                    QMessageBox.warning(self, "Valor insuficiente",
                                        f"O valor recebido ({formatar_reais(recebido)}) é menor que o "
                                        f"total ({formatar_reais(cobrado)}).")
                    self._focar_recebido()
                    return
            else:
                recebido = cobrado  # campo vazio = cliente pagou o valor exato
            troco = recebido - cobrado

        atendimento = {
            "data_hora": datetime.now(),
            "cliente_nome": nome,
            "cliente_telefone": telefone,
            "forma_pagamento": forma,
            "subtotal": subtotal,
            "taxa_percentual": percentual,
            "taxa_valor": taxa,
            "taxa_base": base,            # sobre quanto a taxa foi calculada
            "total": total,
            "valor_recebido": recebido,
            "troco": troco,
            "repasse": repasse,           # boletos/recargas (fora do total da loja)
        }

        # Privacidade: o nome e o telefone vão inteiros só para a nota do cliente.
        # No banco, só se a opção "Guardar dados do cliente" deixar; na nota da loja
        # (que fica salva em .txt), só com "Guardar sempre".
        guardar = self.config.dados_cliente["guardar"]
        sem_cliente = {**atendimento, "cliente_nome": "", "cliente_telefone": ""}
        para_o_banco = sem_cliente if guardar == "nao" else atendimento
        para_a_loja = atendimento if guardar == "sempre" else sem_cliente

        # 1) Salva no banco. Se falhar, não apagamos nada da tela.
        try:
            numero = banco.salvar_atendimento(para_o_banco, self.carrinho)
        except sqlite3.Error as erro:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar o atendimento no banco:\n{erro}")
            return

        # 2) Gera a nota da loja (sempre) e, se marcado, gera e imprime a do cliente.
        #    Se algo falhar aqui, o atendimento já está salvo: só avisamos.
        avisos = []
        modo_texto = notas.usa_modo_texto(self.layout_das_notas)  # define a largura das linhas do .txt
        try:
            caminho_nota = notas.gerar_nota(self.layout_das_notas, numero, para_a_loja, self.carrinho,
                                            "loja", modo_texto)
            avisos.append(f"Nota da loja salva em:\n{caminho_nota}")
        except OSError as erro:
            avisos.append(f"ATENÇÃO: a nota da loja não pôde ser gerada:\n{erro}")

        if self.check_nota_cliente.isChecked():
            try:
                if guardar == "sempre":  # (senão a nota do cliente só é impressa, não fica salva)
                    notas.gerar_nota(self.layout_das_notas, numero, atendimento, self.carrinho, "cliente",
                                     modo_texto)
                notas.imprimir_nota(self.layout_das_notas, numero, atendimento, self.carrinho, "cliente")
                avisos.append("Nota do cliente enviada para a impressora.")
            except (OSError, impressao.ErroImpressao) as erro:
                avisos.append(f"ATENÇÃO: a nota do cliente não foi impressa:\n{erro}")

        mensagem = f"Atendimento nº {numero:06d} finalizado!\n\nTotal: {formatar_reais(total)}\n"
        if repasse:
            mensagem = (f"Atendimento nº {numero:06d} finalizado!\n\nServiços da loja: {formatar_reais(total)}\n"
                        f"Boletos e recargas: {formatar_reais(repasse)}\n"
                        f"Cobrado do cliente: {formatar_reais(cobrado)}\n")
        if troco is not None:
            mensagem += f"Troco: {formatar_reais(troco)}\n"
        QMessageBox.information(self, "Atendimento finalizado", mensagem + "\n" + "\n\n".join(avisos))

        self.cancelar_atendimento(perguntar=False)
        self._status(f"Atendimento nº {numero:06d} salvo - {formatar_reais(cobrado)} ({forma})")

    # ------------------------------------------------------------------
    # Menu Arquivo
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Modo tablet
    # ------------------------------------------------------------------

    def definir_modo_tablet(self, ligado):
        """
        Exibir › Modo tablet: tudo maior (estilo.ESCALA_TABLET), layout Touch, rolagem
        arrastando o dedo e teclado do Windows ao tocar no Nome. Desligando, volta o
        tamanho normal e o layout que estava antes.
        """
        ligado = bool(ligado)
        self._largura_alvo = self.width()  # (o layout tem que caber na largura de agora)
        self.modo_tablet = ligado
        self.acao_tablet.setChecked(ligado)
        self.preferencias["modo_tablet"] = ligado
        estilo.definir_escala(estilo.ESCALA_TABLET if ligado else 1.0)
        self._aplicar_tema()
        self._rolagem_por_toque(ligado)
        if ligado:
            atual = self.preferencias.get("layout_atual", "Padrão")
            self.preferencias["layout_antes_tablet"] = atual if atual != "Touch" else "Padrão"
            self.usar_layout("Touch")
            self._status("Modo tablet ligado: toque num botão para ver a dica dele aqui embaixo.")
        else:
            self.usar_layout(self.preferencias.get("layout_antes_tablet") or "Padrão")
            self._status("Modo tablet desligado.")
        self._salvar_preferencias()

    def _rolagem_por_toque(self, ligado):
        """Listas e tabelas rolam arrastando o dedo (como no celular)."""
        from PySide6.QtWidgets import QAbstractScrollArea
        for area in self.findChildren(QAbstractScrollArea):
            if ligado:
                QScroller.grabGesture(area.viewport(), QScroller.TouchGesture)
            else:
                QScroller.ungrabGesture(area.viewport())

    def apos_abrir(self, lancamento=None):
        """
        Chamada pelo main.py com a janela já na tela (depois da tela de abertura):
        boas-vindas com os dados da loja (só na primeira vez), pergunta do tablet e atualização.
        """
        if not self.config.loja_confirmada:
            self.boas_vindas()
        if not self.modo_tablet and not self.preferencias["tablet_perguntado"] and toque.tem_tela_touch():
            self.preferencias["tablet_perguntado"] = True
            self._salvar_preferencias()
            resposta = QMessageBox.question(
                self, "Tela de toque",
                "Este computador tem tela de toque.\n\nLigar o modo tablet? (botões e letras maiores, "
                "teclado do Windows no campo Nome)\n\nDá para mudar depois em Exibir › Modo tablet.")
            if resposta == QMessageBox.Yes:
                self.definir_modo_tablet(True)
        if lancamento is not None:
            self.oferecer_atualizacao(lancamento)

    def boas_vindas(self):
        """A janela "Dados da sua loja" (uma vez só: depois fica em Preferências › Loja)."""
        DialogoBoasVindas(self, self.config.loja).exec()
        self.loja_alterada()

    def loja_alterada(self):
        """Os dados da loja mudaram (boas-vindas, Preferências ou Configurar notinhas)."""
        self.recarregar_config("Dados da loja salvos.")

    # ------------------------------------------------------------------
    # Atualizações e dados
    # ------------------------------------------------------------------

    def oferecer_atualizacao(self, lancamento):
        """Mostra a versão nova. Nunca no meio de um atendimento: aí só avisa na barra de baixo."""
        if self.carrinho:
            self._status(f"{versao.NOME_PROGRAMA} {lancamento.versao} disponível: termine o atendimento e use "
                         "Ajuda › Procurar atualizações.")
            return
        DialogoAtualizacao(self, lancamento).exec()

    def procurar_atualizacoes(self):
        if not versao.REPOSITORIO_GITHUB:
            QMessageBox.information(self, "Atualizações", "As atualizações automáticas ainda não foram "
                                    "configuradas nesta versão (falta o endereço do GitHub).")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            situacao, lancamento = atualizacao.verificar()
        finally:
            QApplication.restoreOverrideCursor()
        if situacao == atualizacao.ATUAL:
            QMessageBox.information(self, "Atualizações",
                                    f"Você já está com a versão mais nova ({versao.VERSAO}).")
            return
        if situacao != atualizacao.NOVA:
            QMessageBox.warning(self, "Atualizações", "Não foi possível consultar as atualizações (sem internet?).\n\n"
                                "Confira a conexão e tente de novo em Ajuda › Procurar atualizações.")
            return
        self.oferecer_atualizacao(lancamento)

    # ------------------------------------------------------------------
    # Backup (Arquivo › Backup)
    # ------------------------------------------------------------------

    def fazer_backup_agora(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            caminho = backup.fazer_backup()
        except (backup.ErroBackup, OSError, sqlite3.Error) as erro:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Backup", str(erro))
            return
        QApplication.restoreOverrideCursor()
        self._status(f"Backup salvo: {caminho}")
        QMessageBox.information(self, "Backup", f"Backup salvo em:\n{caminho}")

    def escolher_pasta_backup(self):
        atual = backup.pasta_escolhida(self.config)
        pasta = QFileDialog.getExistingDirectory(self, "Pasta dos backups (ex.: pendrive ou Google Drive)", atual)
        if not pasta:
            return
        pasta = os.path.normpath(pasta)
        opcoes = dict(self.config.backup)
        opcoes["pasta"] = "" if os.path.normcase(pasta) == os.path.normcase(backup.pasta_padrao()) else pasta
        try:
            config.atualizar_config(backup=opcoes)
        except (OSError, ValueError) as erro:
            QMessageBox.critical(self, "Backup", f"Não foi possível gravar o config.json:\n{erro}")
            return
        self.config = config.carregar_config()
        self._status(f"Os backups vão para: {pasta}")

    def abrir_pasta_backup(self):
        pasta = backup.pasta_escolhida(self.config)
        try:
            os.makedirs(pasta, exist_ok=True)
            os.startfile(pasta)
        except OSError as erro:
            QMessageBox.critical(self, "Backup", f"Não foi possível abrir a pasta:\n{pasta}\n\n{erro}")

    def restaurar_backup(self):
        if self.carrinho:
            QMessageBox.information(self, "Restaurar backup", "Finalize ou cancele o atendimento antes.")
            return
        if treino.ativo():
            QMessageBox.information(self, "Restaurar backup", "Saia do modo treinamento antes "
                                    "(Arquivo › Modo treinamento).")
            return
        caminho, _filtro = QFileDialog.getOpenFileName(self, "Restaurar backup", backup.pasta_escolhida(self.config),
                                                       "Backup do EasyServ (*.zip)")
        if not caminho:
            return
        try:
            info = backup.ler_backup(caminho)
        except backup.ErroBackup as erro:
            QMessageBox.critical(self, "Restaurar backup", str(erro))
            return
        resposta = QMessageBox.question(
            self, "Restaurar backup",
            f"{backup.descrever(info)}\n\nTrocar TODOS os dados de agora (atendimentos, serviços, preços, "
            "dados da loja e notinhas) pelos deste backup?\n\nAntes, o programa faz um backup do estado atual "
            "(nada se perde). Depois ele fecha para você abrir de novo.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            seguranca = backup.restaurar_backup(caminho)
        except (backup.ErroBackup, OSError, sqlite3.Error) as erro:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Restaurar backup", str(erro))
            return
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Restaurar backup", "Backup restaurado.\n\nOs dados de antes ficaram em:\n"
                                f"{seguranca}\n\nO programa vai fechar agora; abra de novo.")
        self._sem_salvar_ao_fechar = True  # (senão as preferências de agora apagariam as restauradas)
        self.close()

    def abrir_pasta_dados(self):
        os.startfile(config.pasta_base())

    def importar_dados(self):
        """Arquivo › Importar dados de outra pasta (ex.: a pasta do programa antigo)."""
        if self.carrinho:
            QMessageBox.information(self, "Importar dados", "Finalize ou cancele o atendimento antes.")
            return
        achadas = migracao.encontrar_dados_antigos()
        inicio = achadas[0] if achadas else os.path.expanduser("~")
        origem = QFileDialog.getExistingDirectory(self, "Pasta com os dados antigos (banco .db, config.json...)",
                                                  inicio)
        if not origem:
            return
        if not migracao.tem_dados(origem):
            QMessageBox.warning(self, "Importar dados", "Não achei dados do programa nessa pasta "
                                "(banco .db ou config.json).")
            return
        resposta = QMessageBox.question(
            self, "Importar dados",
            f"Copiar os dados de:\n{origem}\n\npara a pasta de dados do {versao.NOME_PROGRAMA}?\n\n"
            "Os dados de agora vão para uma pasta de backup antes (nada se perde). "
            "Depois o programa fecha para você abrir de novo.")
        if resposta != QMessageBox.Yes:
            return
        try:
            guardados = migracao.guardar_dados_atuais()
            migracao.migrar(origem)
        except OSError as erro:
            QMessageBox.critical(self, "Importar dados", f"Não foi possível copiar os dados:\n{erro}")
            return
        QMessageBox.information(self, "Importar dados", "Dados copiados. Os dados de antes ficaram em:\n"
                                f"{guardados}\n\nO programa vai fechar agora; abra de novo.")
        self._sem_salvar_ao_fechar = True  # (senão as preferências de agora apagariam as importadas)
        self.close()

    def configurar_notinhas(self):
        TelaNotinhas(self, ao_salvar=self._layout_das_notas_salvo).exec()

    def _layout_das_notas_salvo(self, layout):
        """Chamada pela tela de notinhas depois de salvar: passa a usar o layout novo."""
        self.layout_das_notas = layout
        self._status("Layout das notinhas atualizado.")

    def abrir_pasta_notas(self):
        pasta = notas.pasta_notas()  # (no modo treinamento: notas_treino/)
        os.makedirs(pasta, exist_ok=True)
        os.startfile(pasta)  # abre no Explorador de Arquivos do Windows

    def editar_config(self):
        subprocess.Popen(["notepad.exe", config.ARQUIVO_CONFIG])
        QMessageBox.information(self, "Editar configurações",
                                "Para trocar serviços e preços, o mais fácil é Arquivo › Serviços e preços.\n\n"
                                "Se mudar o config.json no Bloco de Notas, salve (Ctrl+S) e depois use\n"
                                "Arquivo › Recarregar configurações.\n"
                                "Use ponto nos números do config.json, ex.: 0.50")

    def relatorio_do_dia(self):
        TelaRelatorio(self).exec()

    def configurar_servicos(self):
        TelaServicos(self, self.atalhos, ao_salvar=self._servicos_salvos).exec()

    def _servicos_salvos(self, teclas):
        """A tela de serviços gravou o config.json: guarda as teclas e passa a usar tudo novo."""
        self.preferencias["atalhos"] = dict(teclas)
        self._salvar_preferencias()
        self.recarregar_config("Serviços e preços salvos e já valendo. Itens que já estavam no atendimento "
                               "mantêm o preço de quando foram adicionados.")

    def configurar(self):
        """Arquivo › Preferências: atendimento, privacidade e aparência."""
        TelaPreferencias(self, ao_salvar=lambda: self.recarregar_config("Preferências salvas.")).exec()

    def recarregar_config(self, mensagem="Configurações recarregadas. Itens já no carrinho mantêm o preço antigo."):
        try:
            self.config = config.carregar_config()
            self.layout_das_notas = layout_notas.carregar_layout()
        except config.ErroConfig as erro:
            QMessageBox.critical(self, "Erro no config.json", str(erro))
            return
        self._carregar_atalhos()  # (serviço novo pega uma tecla livre; o removido larga a dele)
        self._criar_botoes_servicos()
        self._limpar_selecao_servico()
        self._aplicar_textos_atalhos()
        self.atualizar_totais()
        self._atualizar_titulo()  # (o nome da loja pode ter mudado)
        self._status(mensagem)

    def _status(self, texto):
        self.lbl_status.setText(texto)
