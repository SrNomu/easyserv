"""
estilo.py - Cores e aparência do programa (temas, modo claro e modo escuro).

O Qt usa "folhas de estilo" (QSS), muito parecidas com o CSS de sites:
    QPushButton { background: white; }   ->  todos os botões com fundo branco
    QLabel#total { font-size: 32px; }    ->  só o QLabel com objectName "total"
    QPushButton[papel="tecla"] { ... }   ->  só botões com a propriedade papel = "tecla"

COMO FUNCIONAM AS CORES
A pessoa escolhe só 5 cores (na tela "Cores do programa"):
    principal  -> serviço/forma de pagamento escolhidos, o TOTAL, a borda do campo com o cursor
    destaque   -> o fundo do que está selecionado
    fundo      -> o fundo da janela
    texto      -> as letras
    finalizar  -> o botão Finalizar
Todas as outras (fundo dos painéis, bordas, cinzas dos rótulos...) são misturas
dessas, calculadas em 'cores_derivadas'. Assim qualquer combinação fica harmônica.

Existem dois jogos de cores: um para o modo claro e um para o modo escuro.
O modo (Claro / Escuro / Seguir o Windows) é escolhido no menu Exibir.

Regras que seguimos (para a tela ficar limpa e fácil de ler):
  - painéis lisos com borda fina (sem sombra, sem degradê);
  - a cor principal só onde importa: o que está escolhido, o TOTAL e o Finalizar;
  - uma fonte só (Segoe UI) e poucos tamanhos: 12, 14, 16, 18, 24 e 32px;
  - todo texto com bom contraste (a tela de cores avisa quando fica difícil de ler).
"""

import copy
import re
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QWidget

import barra_titulo

# As 5 cores que a pessoa pode escolher: (chave, nome na tela, explicação).
CAMPOS_CORES = [
    ("principal", "Cor principal", "Serviço escolhido, TOTAL, campo com o cursor"),
    ("destaque", "Cor de destaque", "Fundo do que está selecionado"),
    ("fundo", "Fundo", "Fundo da janela"),
    ("texto", "Texto", "Cor das letras"),
    ("finalizar", "Botão Finalizar", "Cor do botão Finalizar"),
]

MODOS = {"claro": "Claro", "escuro": "Escuro", "sistema": "Seguir o Windows"}

# Temas prontos. Cada um tem as cores do modo claro e as do modo escuro.
# ("Padrão" é o rosa de fábrica; "Escuro" é escuro nos dois modos: para quem
# quer a tela sempre escura.) Os temas que a pessoa salva com nome ficam em
# preferencias.json ("temas_salvos") e não podem usar estes nomes.
TEMAS = {
    "Padrão": {
        "claro": {"principal": "#8c2f57", "destaque": "#f8e9f0", "fundo": "#f5f3f4",
                  "texto": "#1d1a1c", "finalizar": "#8c2f57"},
        "escuro": {"principal": "#e891b6", "destaque": "#4a2636", "fundo": "#1b1719",
                   "texto": "#f1ecee", "finalizar": "#a83d70"},
    },
    "Azul": {
        "claro": {"principal": "#1f5fae", "destaque": "#e5eefa", "fundo": "#f2f4f7",
                  "texto": "#1a1d22", "finalizar": "#1f5fae"},
        "escuro": {"principal": "#84b4f2", "destaque": "#1f3452", "fundo": "#15181d",
                   "texto": "#eceff3", "finalizar": "#2b68b8"},
    },
    "Verde": {
        "claro": {"principal": "#1f6e47", "destaque": "#e3f2e9", "fundo": "#f2f5f3",
                  "texto": "#1a1e1b", "finalizar": "#1f6e47"},
        "escuro": {"principal": "#73d19e", "destaque": "#1d3a2a", "fundo": "#151a17",
                   "texto": "#ebf1ed", "finalizar": "#24744d"},
    },
    "Escuro": {
        "claro": {"principal": "#e891b6", "destaque": "#3a2a31", "fundo": "#121212",
                  "texto": "#ededed", "finalizar": "#a83d70"},
        "escuro": {"principal": "#e891b6", "destaque": "#3a2a31", "fundo": "#121212",
                   "texto": "#ededed", "finalizar": "#a83d70"},
    },
}
TEMA_PADRAO = "Padrão"


def cores_padrao():
    """As cores de fábrica (tema Padrão, o rosa de fábrica), para os dois modos."""
    return copy.deepcopy(TEMAS[TEMA_PADRAO])


def completar_cores(cores):
    """
    Confere as cores lidas das preferências. O que estiver faltando ou não for
    uma cor válida volta para a cor de fábrica (o programa nunca abre "quebrado").
    """
    resultado = cores_padrao()
    if not isinstance(cores, dict):
        return resultado
    for modo in ("claro", "escuro"):
        jogo = cores.get(modo)
        if not isinstance(jogo, dict):
            continue
        for chave, _nome, _dica in CAMPOS_CORES:
            valor = jogo.get(chave)
            if isinstance(valor, str) and QColor.isValidColorName(valor):
                resultado[modo][chave] = QColor(valor).name()  # sempre no formato #rrggbb
    return resultado


def nome_do_tema(cores, temas_salvos=None):
    """
    Se as cores forem exatamente as de um tema (pronto ou salvo pela pessoa),
    devolve o nome dele (senão None).
    """
    for nome, tema in {**TEMAS, **(temas_salvos or {})}.items():
        if tema == cores:
            return nome
    return None


def conferir_temas_salvos(temas):
    """Confere os temas salvos lidos das preferências (o que estiver estragado é descartado)."""
    if not isinstance(temas, dict):
        return {}
    return {nome.strip(): completar_cores(cores) for nome, cores in temas.items()
            if isinstance(nome, str) and nome.strip() and nome.strip() not in TEMAS
            and isinstance(cores, dict)}


# ----------------------------------------------------------------------
# Contas com cores
# ----------------------------------------------------------------------

def misturar(cor_a, cor_b, quanto):
    """Mistura duas cores. quanto=0 -> cor_a pura; quanto=1 -> cor_b pura."""
    a, b = QColor(cor_a), QColor(cor_b)
    return QColor(
        round(a.red() + (b.red() - a.red()) * quanto),
        round(a.green() + (b.green() - a.green()) * quanto),
        round(a.blue() + (b.blue() - a.blue()) * quanto),
    ).name()


def luminancia(cor):
    """Quão clara a cor parece ao olho (0 = preto, 1 = branco), pela fórmula da W3C."""
    def canal(valor):
        valor /= 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4
    c = QColor(cor)
    return 0.2126 * canal(c.red()) + 0.7152 * canal(c.green()) + 0.0722 * canal(c.blue())


def contraste(cor_a, cor_b):
    """Contraste entre duas cores (1 = nenhum, 21 = preto no branco). Texto bom: 4,5 ou mais."""
    claras = sorted((luminancia(cor_a), luminancia(cor_b)), reverse=True)
    return (claras[0] + 0.05) / (claras[1] + 0.05)


def eh_escura(cor):
    return luminancia(cor) < 0.2


def texto_sobre(cor):
    """Branco ou quase preto: o que se lê melhor em cima dessa cor."""
    return "#ffffff" if contraste(cor, "#ffffff") >= contraste(cor, "#1a1a1a") else "#1a1a1a"


def cores_derivadas(cores):
    """
    A partir das 5 cores escolhidas, calcula todas as que a folha de estilo usa.
    'cores' é o jogo de UM modo, ex.: {"principal": "#8c2f57", "fundo": "#f5f3f4", ...}.
    """
    fundo, texto, principal = cores["fundo"], cores["texto"], cores["principal"]
    escura = eh_escura(fundo)
    # Painéis: no claro, quase brancos; no escuro, um pouco mais claros que o fundo.
    superficie = misturar(fundo, "#ffffff", 0.06 if escura else 0.85)
    k = SimpleNamespace(**cores)
    k.superficie = superficie
    k.regra = misturar(superficie, texto, 0.06)          # linhas da tabela, teclas de ação
    k.regra_forte = misturar(superficie, texto, 0.10)    # tecla de ação com o mouse em cima
    k.borda = misturar(fundo, texto, 0.10)               # borda dos painéis
    k.controle = misturar(superficie, texto, 0.22)       # borda de campos e botões
    k.controle_forte = misturar(superficie, texto, 0.32)
    k.marcador = misturar(superficie, texto, 0.50)       # borda das caixinhas de marcar
    k.suave = misturar(texto, superficie, 0.36)          # rótulos (cinza, mas legível)
    k.desativado = misturar(texto, superficie, 0.58)
    k.passar_mouse = misturar(superficie, texto, 0.04)
    k.selecao_texto = misturar(superficie, principal, 0.30)
    k.separador = misturar(fundo, principal, 0.35)
    # Texto do que está selecionado: na cor principal, se der para ler em cima do destaque.
    k.texto_selecionado = principal if contraste(principal, cores["destaque"]) >= 4.5 else texto
    k.borda_selecionado = principal
    k.finalizar_mouse = misturar(cores["finalizar"], texto_sobre(cores["finalizar"]), 0.15)
    k.texto_finalizar = texto_sobre(cores["finalizar"])
    # Tecla Enter do teclado na tela: escura no modo claro; no escuro, um cinza
    # (branco puro ficaria chamativo demais).
    k.enter = misturar(superficie, texto, 0.30 if escura else 1.0)
    k.enter_mouse = misturar(superficie, texto, 0.40 if escura else 0.82)
    k.texto_enter = texto_sobre(k.enter)
    k.positivo = "#6fd39a" if escura else "#247b50"       # troco
    k.negativo = "#ff8a80" if escura else "#b3261e"       # falta dinheiro
    # Barra de título da janela: a cor principal, se for escura o bastante para o
    # título em branco; senão (cor principal clara, comum no modo escuro) uma
    # mistura do fundo com a principal, que fica escura e ainda "da cor do tema".
    k.barra_titulo = principal if luminancia(principal) < 0.25 else misturar(fundo, principal, 0.30)
    k.texto_barra_titulo = texto_sobre(k.barra_titulo)
    return k


# ----------------------------------------------------------------------
# Folha de estilo e paleta
# ----------------------------------------------------------------------

def folha_de_estilo(cores):
    """Monta a folha de estilo (QSS) com as cores de um modo."""
    k = cores_derivadas(cores)
    return f"""
* {{
    font-family: "Segoe UI";
}}
QWidget {{
    font-size: 14px;
    color: {k.texto};
}}
QMainWindow, QDialog {{
    background: {k.fundo};
}}

/* ---------- Painéis encaixáveis ---------- */
QDockWidget {{
    font-size: 13px;
    font-weight: 600;
    color: {k.suave};
}}
QDockWidget::title {{
    background: {k.fundo};
    padding: 8px 10px 6px 12px;
    text-align: left;
}}
QMainWindow::separator {{
    background: {k.fundo};
    width: 6px;
    height: 6px;
}}
QMainWindow::separator:hover {{
    background: {k.separador};
}}
/* O "cartão" dentro de cada painel */
QFrame#painel {{
    background: {k.superficie};
    border: 1px solid {k.borda};
    border-radius: 8px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget#painel {{
    background: {k.superficie};
}}
QWidget#qt_scrollarea_viewport {{
    background: transparent;
}}

/* Abas que aparecem quando painéis são empilhados.
   (o tamanho da letra fica no QTabBar e não no ::tab, e sem negrito: o Qt mede
   a aba com a letra do QTabBar e, se fossem diferentes, cortaria o texto com "...") */
QTabBar {{
    font-size: 13px;
}}
QTabBar::tab {{
    background: {k.fundo};
    color: {k.suave};
    border: none;
    padding: 6px 14px;
}}
QTabBar::tab:selected {{
    color: {k.texto};
    border-bottom: 2px solid {k.principal};
}}

/* ---------- Textos ---------- */
QLabel {{
    background: transparent;
}}
QLabel#rotulo {{
    font-size: 12px;
    color: {k.suave};
}}
QLabel#grupo {{
    font-size: 12px;
    font-weight: 600;
    color: {k.suave};
    padding-top: 6px;
}}
QLabel#rotulo[destaque="true"] {{
    font-weight: 600;
    color: {k.principal};
}}
QLabel#servicoAtual {{
    font-size: 18px;
    font-weight: 600;
    color: {k.principal};
}}
QLabel#servicoAtual[vazio="true"] {{
    color: {k.suave};
    font-weight: 400;
    font-size: 16px;
}}
QLabel#previa {{
    font-size: 18px;
    color: {k.suave};
}}
QLabel#valor {{
    font-size: 16px;
}}
QLabel#valorGrande {{
    font-size: 24px;
    font-weight: 600;
}}
QLabel#rotuloTotal {{
    font-size: 16px;
    font-weight: 600;
}}
QLabel#total {{
    font-size: 32px;
    font-weight: 700;
    color: {k.principal};
}}
QLabel#troco {{
    font-size: 18px;
    font-weight: 600;
}}
QLabel#troco[estado="positivo"] {{ color: {k.positivo}; }}
QLabel#troco[estado="negativo"] {{ color: {k.negativo}; }}
QLabel#vazio {{
    color: {k.suave};
    font-size: 14px;
}}
QLabel#aviso {{
    color: {k.negativo};
    font-size: 12px;
}}

/* ---------- Campos de digitação ---------- */
/* (o QSpinBox fica com o desenho padrão: estilizar ele estraga as setinhas) */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {k.superficie};
    border: 1px solid {k.controle};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {k.selecao_texto};
    selection-color: {k.texto};
}}
QLineEdit {{
    font-size: 16px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {k.principal};
}}
QLineEdit:disabled {{
    background: {k.regra};
    color: {k.desativado};
    border-color: {k.borda};
}}
QLineEdit[readOnly="true"] {{
    background: {k.fundo};
}}
/* Campo com valor inválido (tela Preços e taxas) */
QLineEdit[erro="true"] {{
    border: 2px solid {k.negativo};
}}
QComboBox QAbstractItemView {{
    background: {k.superficie};
    selection-background-color: {k.destaque};
    selection-color: {k.texto_selecionado};
}}

/* ---------- Botões ---------- */
QPushButton {{
    background: {k.superficie};
    border: 1px solid {k.controle};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background: {k.passar_mouse};
    border-color: {k.controle_forte};
}}
QPushButton:pressed {{
    background: {k.destaque};
}}
QPushButton:focus {{
    border: 1px solid {k.principal};
}}
QPushButton:disabled {{
    background: {k.fundo};
    color: {k.desativado};
    border-color: {k.borda};
}}

/* Botões dos serviços (o texto fica em QLabels dentro do botão) */
QPushButton[papel="servico"] {{
    padding: 0px;
    text-align: left;
}}
QPushButton[papel="servico"] QLabel#teclaServico {{
    color: {k.suave};
    font-weight: 600;
}}
QPushButton[papel="servico"] QLabel#precoServico {{
    color: {k.suave};
}}
QPushButton[papel="servico"][selecionado="true"] {{
    background: {k.destaque};
    border: 1px solid {k.borda_selecionado};
}}
QPushButton[papel="servico"][selecionado="true"] QLabel {{
    color: {k.texto_selecionado};
}}

/* Formas de pagamento: botões que ficam "marcados" */
QPushButton[papel="forma"] {{
    padding: 10px 8px;
    text-align: center;
}}
QPushButton[papel="forma"]:checked {{
    background: {k.destaque};
    border: 1px solid {k.borda_selecionado};
    color: {k.texto_selecionado};
    font-weight: 600;
}}

/* Botão principal: Finalizar */
QPushButton#finalizar {{
    background: {k.finalizar};
    color: {k.texto_finalizar};
    border: 1px solid {k.finalizar};
    font-size: 18px;
    font-weight: 600;
    padding: 14px;
}}
QPushButton#finalizar:hover {{
    background: {k.finalizar_mouse};
}}
QPushButton#finalizar:focus {{
    border: 2px solid {k.texto};
}}

/* Teclado na tela (no layout "Touch" as teclas ficam maiores: grande="true") */
QPushButton[papel="tecla"], QPushButton[papel="tecla-acao"], QPushButton[papel="tecla-enter"] {{
    font-size: 22px;
    font-weight: 600;
    padding: 0px;
}}
QPushButton[papel="tecla"][grande="true"], QPushButton[papel="tecla-acao"][grande="true"],
QPushButton[papel="tecla-enter"][grande="true"] {{
    font-size: 32px;
}}
QPushButton[papel="tecla-acao"] {{
    background: {k.regra};
}}
QPushButton[papel="tecla-acao"]:hover {{
    background: {k.regra_forte};
}}
QPushButton[papel="tecla-enter"] {{
    background: {k.enter};
    border-color: {k.enter};
    color: {k.texto_enter};
}}
QPushButton[papel="tecla-enter"]:hover {{
    background: {k.enter_mouse};
}}

/* Botão que apaga dados (Limpar dados) */
QPushButton#perigo {{
    background: {k.negativo};
    color: {texto_sobre(k.negativo)};
    border: 1px solid {k.negativo};
    font-weight: 600;
}}
QPushButton#perigo:disabled {{
    background: {k.fundo};
    color: {k.desativado};
    border-color: {k.borda};
}}

/* Faixa do modo treinamento: amarelo forte com letra escura nos dois modos */
QToolBar#faixa_treino {{
    background: #ffc400;
    border: none;
    border-bottom: 2px solid #8a6a00;
    padding: 4px 10px;
    spacing: 10px;
}}
QToolBar#faixa_treino QLabel {{
    color: #1a1400;
    font-size: 18px;
    font-weight: 700;
}}
QToolBar#faixa_treino QPushButton {{
    background: #fff4c2;
    color: #1a1400;
    border: 1px solid #8a6a00;
    padding: 5px 12px;
}}
QToolBar#faixa_treino QPushButton:hover {{
    background: #ffffff;
}}

/* Tela de atalhos: o botão que mostra a tecla */
QPushButton[papel="atalho"] {{
    font-weight: 600;
    min-width: 130px;
}}
QPushButton[papel="atalho"][vazio="true"] {{
    color: {k.suave};
    font-weight: normal;
}}
QPushButton[papel="atalho"][capturando="true"] {{
    background: {k.destaque};
    color: {k.texto_selecionado};
    border: 2px solid {k.principal};
}}
QPushButton[papel="atalho"][erro="true"] {{
    border: 2px solid {k.negativo};
}}

/* Calendário (escolha da data no Relatório do dia) */
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {k.destaque};
}}
QCalendarWidget QToolButton {{
    color: {k.texto_selecionado};
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background: {k.superficie};
    border-radius: 4px;
}}

/* ---------- Tabela do atendimento ---------- */
QTableWidget {{
    background: {k.superficie};
    border: none;
    gridline-color: transparent;
    selection-background-color: {k.destaque};
    selection-color: {k.texto};
    outline: 0;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {k.regra};
}}
QHeaderView::section {{
    background: {k.superficie};
    color: {k.suave};
    font-size: 12px;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid {k.borda};
    padding: 6px 8px;
}}

/* ---------- Caixas de grupo (telas de configuração) ---------- */
QGroupBox {{
    background: {k.superficie};
    border: 1px solid {k.borda};
    border-radius: 8px;
    margin-top: 24px;
    padding: 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    padding: 0 4px;
    color: {k.texto};
}}
QCheckBox, QRadioButton {{
    spacing: 8px;
    font-weight: 400;
}}
/* As caixinhas e bolinhas de marcar (sem isto ficariam invisíveis no fundo do painel) */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    background: {k.superficie};
    border: 1px solid {k.marcador};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {k.principal};
    border: 1px solid {k.principal};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {k.principal};
}}

/* ---------- Menus e barra de status ---------- */
QMenuBar {{
    background: {k.fundo};
}}
QMenuBar::item:selected {{
    background: {k.destaque};
}}
QMenu {{
    background: {k.superficie};
    border: 1px solid {k.borda};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {k.destaque};
    color: {k.texto};
}}
QMenu::item:disabled {{
    color: {k.desativado};
}}
QMenu::separator {{
    height: 1px;
    background: {k.borda};
    margin: 4px 8px;
}}
QStatusBar {{
    background: {k.fundo};
    border-top: 1px solid {k.borda};
}}
QStatusBar QLabel {{
    color: {k.suave};
    padding: 2px 8px;
}}
QToolTip {{
    background: {k.texto};
    color: {k.superficie};
    border: none;
    padding: 4px 8px;
}}
"""


def paleta(cores):
    """
    A paleta é usada pelo Qt nas partes que a folha de estilo não alcança
    (barras de rolagem, a marcação dentro das caixinhas, o seletor de cor...).
    """
    k = cores_derivadas(cores)
    p = QPalette()
    for papel, cor in (
        (QPalette.Window, k.fundo),
        (QPalette.Base, k.superficie),
        (QPalette.AlternateBase, k.regra),
        (QPalette.Button, k.superficie),
        (QPalette.Text, k.texto),
        (QPalette.WindowText, k.texto),
        (QPalette.ButtonText, k.texto),
        (QPalette.PlaceholderText, k.desativado),
        (QPalette.ToolTipBase, k.texto),
        (QPalette.ToolTipText, k.superficie),
        (QPalette.Highlight, k.principal),
        (QPalette.HighlightedText, texto_sobre(k.principal)),
        (QPalette.Mid, k.controle),
        (QPalette.Midlight, k.regra),
        (QPalette.Light, k.superficie),
        (QPalette.Dark, k.controle_forte),
    ):
        p.setColor(papel, QColor(cor))
    # Textos de coisas desativadas.
    for papel in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, papel, QColor(k.desativado))
    return p


# ----------------------------------------------------------------------
# Aplicar no programa
# ----------------------------------------------------------------------

def windows_esta_escuro():
    """True se o Windows estiver no modo escuro (Configurações › Personalização › Cores)."""
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def modo_efetivo(modo):
    """Transforma 'sistema' em 'claro' ou 'escuro', conforme o Windows."""
    if modo == "sistema":
        return "escuro" if windows_esta_escuro() else "claro"
    return modo if modo in ("claro", "escuro") else "claro"


# Modo tablet: tudo maior (fontes, espaçamentos e botões) multiplicando as medidas
# da folha de estilo. 1.0 = tamanho normal.
ESCALA_TABLET = 1.3
_escala = 1.0


def definir_escala(valor):
    """Muda o tamanho de tudo (vale na próxima vez que aplicar() rodar)."""
    global _escala
    _escala = float(valor)


def escala():
    return _escala


def escalar(folha, fator):
    """Multiplica as medidas em px da folha de estilo (bordas finas, de 1 e 2px, ficam como estão)."""
    def trocar(achado):
        valor = int(achado.group(1))
        return achado.group(0) if valor <= 2 else f"{round(valor * fator)}px"
    return re.sub(r"(\d+)px", trocar, folha)


def preparar(app):
    """Chamada uma vez, ao abrir: o estilo base e as cores de fábrica."""
    # "Fusion" é o estilo do Qt que respeita as nossas cores (o estilo do Windows ignora algumas).
    app.setStyle("Fusion")
    aplicar(app, "sistema", cores_padrao())


def aplicar(app, modo, cores):
    """
    Aplica o tema no programa inteiro.
    modo  = "claro", "escuro" ou "sistema";
    cores = {"claro": {...5 cores...}, "escuro": {...5 cores...}}.
    Devolve o modo que ficou valendo ("claro" ou "escuro").
    """
    dicas = QGuiApplication.styleHints()
    # Diz ao Windows se o programa é claro ou escuro (a barra de título acompanha).
    # No "Seguir o Windows" deixamos o Windows decidir.
    if modo == "claro":
        dicas.setColorScheme(Qt.ColorScheme.Light)
    elif modo == "escuro":
        dicas.setColorScheme(Qt.ColorScheme.Dark)
    else:
        dicas.unsetColorScheme()
    efetivo = modo_efetivo(modo)
    app.setPalette(paleta(cores[efetivo]))
    folha = folha_de_estilo(cores[efetivo])
    app.setStyleSheet(escalar(folha, _escala) if _escala != 1.0 else folha)
    k = cores_derivadas(cores[efetivo])
    barra_titulo.definir_cores(app, k.barra_titulo, k.texto_barra_titulo, eh_escura(k.barra_titulo))
    return efetivo


def repintar(widget):
    """
    Reaplica o estilo depois de mudar uma propriedade usada na folha de estilo
    (ex.: widget.setProperty("selecionado", True)). Sem isso o Qt não percebe a mudança.
    """
    for item in [widget, *widget.findChildren(QWidget)]:  # o próprio widget e tudo dentro dele
        item.style().unpolish(item)
        item.style().polish(item)
