"""
teclado.py - Teclado numérico na tela, no estilo de calculadora (PySide6).

    ┌────┬────┬────┬────┐
    │ 7  │ 8  │ 9  │ ⌫  │
    ├────┼────┼────┼────┤
    │ 4  │ 5  │ 6  │ C  │
    ├────┼────┼────┼────┤
    │ 1  │ 2  │ 3  │    │
    ├────┼────┼────┤ ↵  │
    │ 0  │ 00 │ ,  │    │
    └────┴────┴────┴────┘

O teclado não sabe nada sobre os campos da tela: quando um botão é apertado,
ele emite o sinal 'tecla_apertada' com o nome da tecla
("0" a "9", "00", ",", "apagar", "limpar" ou "enter").
Quem decide o que fazer com a tecla é a janela principal (interface.py).

Os botões usam Qt.NoFocus: assim, clicar neles não tira o cursor
do campo que estava selecionado.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from estilo import repintar

# (texto do botão, nome da tecla, linha, coluna, quantas linhas ocupa, papel no estilo)
BOTOES = [
    ("7", "7", 0, 0, 1, "tecla"),
    ("8", "8", 0, 1, 1, "tecla"),
    ("9", "9", 0, 2, 1, "tecla"),
    ("⌫", "apagar", 0, 3, 1, "tecla-acao"),
    ("4", "4", 1, 0, 1, "tecla"),
    ("5", "5", 1, 1, 1, "tecla"),
    ("6", "6", 1, 2, 1, "tecla"),
    ("C", "limpar", 1, 3, 1, "tecla-acao"),
    ("1", "1", 2, 0, 1, "tecla"),
    ("2", "2", 2, 1, 1, "tecla"),
    ("3", "3", 2, 2, 1, "tecla"),
    ("↵", "enter", 2, 3, 2, "tecla-enter"),  # Enter ocupa 2 linhas, como na calculadora
    ("0", "0", 3, 0, 1, "tecla"),
    ("00", "00", 3, 1, 1, "tecla"),
    (",", ",", 3, 2, 1, "tecla"),
]

# (tamanho mínimo, altura máxima) de cada botão, em pixels.
TAMANHO_NORMAL = (56, 88)    # já é bom para o dedo numa tela touch
TAMANHO_GRANDE = (84, 140)   # layout "Touch": teclas bem grandes

DICAS = {"apagar": "Apagar", "limpar": "Limpar o campo", "enter": "Enter"}


def digitar_no_campo(campo, tecla):
    """Faz no campo (QLineEdit) o mesmo que a tecla faria se fosse digitada no teclado físico."""
    if tecla == "limpar":
        campo.clear()
    elif tecla == "apagar":
        campo.backspace()  # apaga o texto selecionado ou o caractere antes do cursor
    else:
        campo.insert(tecla)  # se tiver texto selecionado, substitui a seleção


class TecladoNumerico(QWidget):
    """Os botões do teclado. Conecte-se ao sinal 'tecla_apertada' para saber o que foi apertado."""

    # Signal = um "aviso" que outros objetos podem escutar com .connect(função).
    tecla_apertada = Signal(str)

    def __init__(self, pai=None):
        super().__init__(pai)
        # A grade de botões fica no alto; o espaço que sobrar vai para baixo dela.
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(12, 12, 12, 12)
        self.grade = grade = QGridLayout()
        grade.setSpacing(6)
        coluna.addLayout(grade)
        coluna.addStretch(1)
        self.botoes = []  # (botão, quantas linhas ocupa)
        self.grande = False

        for texto, tecla, linha, coluna, altura, papel in BOTOES:
            botao = QPushButton(texto)
            botao.setProperty("papel", papel)       # usado na folha de estilo (estilo.py)
            botao.setFocusPolicy(Qt.NoFocus)        # clicar não tira o cursor do campo
            botao.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            if tecla in DICAS:
                botao.setToolTip(DICAS[tecla])
            if tecla == "apagar":
                botao.setAutoRepeat(True)  # segurar o ⌫ apaga vários caracteres
            # "tecla=tecla" guarda o valor atual do laço (sem isso, todos os botões
            # mandariam a última tecla da lista).
            botao.clicked.connect(lambda _marcado=False, tecla=tecla: self.tecla_apertada.emit(tecla))
            grade.addWidget(botao, linha, coluna, altura, 1)
            self.botoes.append((botao, altura))

        # Todas as linhas e colunas do mesmo tamanho.
        for i in range(4):
            grade.setRowStretch(i, 1)
            grade.setColumnStretch(i, 1)
        self.definir_grande(False)

    def definir_grande(self, grande):
        """Teclas normais ou grandes (layout "Touch"). As letras também crescem (estilo.py)."""
        self.grande = grande
        minimo, maximo = TAMANHO_GRANDE if grande else TAMANHO_NORMAL
        espaco = self.grade.spacing()
        for botao, altura in self.botoes:
            botao.setProperty("grande", grande)
            botao.setMinimumSize(minimo, minimo * altura + espaco * (altura - 1))
            # Os botões crescem junto com o painel (até um limite, para não virarem tijolos).
            botao.setMaximumHeight(maximo * altura + espaco * (altura - 1))
        repintar(self)
