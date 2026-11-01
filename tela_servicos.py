"""
tela_servicos.py - Tela "Serviços e preços" (menu Arquivo › Serviços e preços...).

À esquerda, a lista de categorias e serviços. Dá para:
  - criar categoria e serviço (botões "+ Categoria" e "+ Serviço");
  - mudar a ordem arrastando (ou com ↑ ↓), inclusive levar um serviço para
    outra categoria;
  - remover: o serviço removido fica DESATIVADO - sai da tela de atendimento,
    mas continua nos atendimentos antigos e nos relatórios (e pode ser reativado).
À direita, os dados do que está selecionado:
  serviço   -> nome, preço, categoria, tecla de atalho, se cobra a taxa da maquininha e se
               cobra valor de terceiros (boleto/recarga: pede o valor na hora, quando a opção
               "Pedir o valor do boleto/recarga" estiver ligada em Preferências);
  categoria -> nome.
E, embaixo, a taxa da maquininha (débito e crédito) e o teclado na tela.

Nada é gravado até apertar Salvar. Antes de gravar aparece um resumo do que mudou.
Os atendimentos já feitos guardam o nome e o preço de quando foram feitos:
mudar ou remover um serviço não altera nada do que já aconteceu.

As teclas dos serviços usam o mesmo sistema de Ajuda › Atalhos do teclado
(atalhos.py): uma tecla não pode ser de duas ações ao mesmo tempo.
"""

import copy
import json
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import atalhos
import config
from estilo import repintar
from tela_atalhos import BotaoTecla
from teclado import TecladoNumerico, digitar_no_campo
from utils import converter_percentual, converter_valor, formatar_percentual, formatar_reais, numero_para_campo

# Formas de pagamento que pagam a taxa da maquininha (um campo só vale para as duas).
FORMAS_COM_TAXA = ["Débito", "Crédito"]
# Cada linha da lista guarda só uma "chave"; os dados ficam no dicionário self.registro
# da tela. (O Qt devolve uma CÓPIA do que se guarda na linha: mudar a cópia não mudaria nada.)
PAPEL = Qt.UserRole
COLUNAS = ["Nome", "Preço", "Tecla", "Taxa maquininha"]


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


class ArvoreServicos(QTreeWidget):
    """
    A lista de categorias (em cima) com os serviços dentro, que dá para arrastar.
    Regras do arrastar: categoria só muda de ordem (não entra dentro de outra) e
    serviço só fica dentro de uma categoria. O resto é recusado.
    """

    def __init__(self, ao_soltar, eh_categoria):
        super().__init__()
        self.ao_soltar = ao_soltar
        self.eh_categoria = eh_categoria
        self.setColumnCount(len(COLUNAS))
        self.setHeaderLabels(COLUNAS)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setRootIsDecorated(False)
        self.setIndentation(18)
        self.setUniformRowHeights(True)
        cabecalho = self.header()
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(0, QHeaderView.Stretch)
        for coluna in (1, 2, 3):
            cabecalho.setSectionResizeMode(coluna, QHeaderView.ResizeToContents)

    def destino_valido(self, arrastado, pai_destino):
        """True se 'arrastado' pode ir para dentro de 'pai_destino' (None = lista principal)."""
        if self.eh_categoria(arrastado):
            return pai_destino is None
        return self.eh_categoria(pai_destino)

    def pai_do_destino(self, posicao, indicador):
        """Onde o item vai cair, pelo lugar do mouse e pela "linha" que o Qt desenha."""
        alvo = self.itemAt(posicao)
        if alvo is None or indicador == QAbstractItemView.OnViewport:
            return None
        if indicador == QAbstractItemView.OnItem:
            return alvo
        return alvo.parent()  # acima ou abaixo de um item: fica junto com ele

    def dropEvent(self, evento):
        arrastados = self.selectedItems()
        destino = self.pai_do_destino(evento.position().toPoint(), self.dropIndicatorPosition())
        if not arrastados or not self.destino_valido(arrastados[0], destino):
            evento.ignore()
            return
        super().dropEvent(evento)
        self.expandAll()
        self.setCurrentItem(arrastados[0])
        self.ao_soltar()


class TelaServicos(QDialog):
    """
    pai       = a janela principal;
    teclas    = os atalhos atuais {"acao": "tecla"} (de atalhos.completar);
    ao_salvar = função chamada com as teclas novas {"acao": "tecla"} depois de gravar o config.json.
    """

    def __init__(self, pai, teclas, ao_salvar):
        super().__init__(pai)
        self.setWindowTitle("Serviços e preços")
        self.ao_salvar = ao_salvar
        self.config = config.carregar_config()
        with open(config.ARQUIVO_CONFIG, "r", encoding="utf-8") as arquivo:
            self.json_original = json.load(arquivo)
        # Teclas das ações que não são serviços (Finalizar, Pix...): uma tecla nova
        # de serviço não pode repetir nenhuma delas sem confirmar.
        self.teclas_fixas = {acao: tecla for acao, tecla in teclas.items() if atalhos.id_do_servico(acao) is None}
        self.teclas_originais = dict(teclas)
        self.desativados = [self._dados_do_servico(s, teclas) for s in self.config.servicos_desativados]
        self._preenchendo = False   # (evita que encher o formulário conte como "editar")
        self._pendente = None       # tecla já usada, esperando a confirmação (apertar de novo)
        # Teclas tiradas de outra ação/serviço nesta tela: tecla -> função que devolve.
        # Se a pessoa mudar de ideia (troca a tecla, "Sem atalho" ou remove o serviço),
        # a tecla volta para quem era dona. (Cancelar não grava nada, então tudo volta.)
        self._tomadas = {}
        self._ultimo_campo = None
        self.registro = {}          # chave da linha -> dados do serviço ou da categoria

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(12)
        corpo = QHBoxLayout()
        corpo.setSpacing(12)
        coluna.addLayout(corpo, 1)

        # --- Esquerda: categorias e serviços ---
        esquerda = QVBoxLayout()
        caixa_lista = QGroupBox("Categorias e serviços")
        coluna_lista = QVBoxLayout(caixa_lista)
        self.arvore = ArvoreServicos(self._depois_de_mexer_na_ordem, self.eh_categoria)
        self.arvore.currentItemChanged.connect(lambda *_: self._mostrar_selecionado())
        coluna_lista.addWidget(self.arvore, 1)
        dica = _rotulo("Arraste para mudar a ordem ou para levar um serviço para outra categoria.", "rotulo")
        dica.setWordWrap(True)
        coluna_lista.addWidget(dica)
        botoes_lista = QHBoxLayout()
        botoes_lista.setSpacing(6)
        for texto, dica_botao, funcao in (
                ("+ Categoria", "Criar uma categoria nova", self.nova_categoria),
                ("+ Serviço", "Criar um serviço na categoria selecionada", self.novo_servico),
                ("↑", "Subir (mudar a ordem)", lambda: self.mover(-1)),
                ("↓", "Descer (mudar a ordem)", lambda: self.mover(1)),
                ("Remover", "Remover o serviço ou a categoria selecionada", self.remover)):
            botao = QPushButton(texto)
            botao.setToolTip(dica_botao)
            botao.clicked.connect(funcao)
            botoes_lista.addWidget(botao)
            if texto == "Remover":
                self.btn_remover = botao
        botoes_lista.insertStretch(4, 1)
        coluna_lista.addLayout(botoes_lista)
        esquerda.addWidget(caixa_lista, 3)

        self.caixa_desativados = QGroupBox("Serviços removidos (continuam no histórico e nos relatórios)")
        coluna_desativados = QHBoxLayout(self.caixa_desativados)
        self.lista_desativados = QListWidget()
        self.lista_desativados.setMaximumHeight(110)
        coluna_desativados.addWidget(self.lista_desativados, 1)
        self.btn_reativar = QPushButton("Reativar")
        self.btn_reativar.setToolTip("Volta o serviço para a tela de atendimento")
        self.btn_reativar.clicked.connect(self.reativar)
        coluna_desativados.addWidget(self.btn_reativar, 0, Qt.AlignTop)
        esquerda.addWidget(self.caixa_desativados, 1)
        corpo.addLayout(esquerda, 3)

        # --- Direita: dados do selecionado, taxa da maquininha e teclado ---
        direita = QVBoxLayout()
        direita.setSpacing(12)
        self.pilha = QStackedWidget()
        nada = _rotulo("Escolha um serviço ou uma categoria na lista.", "vazio")
        nada.setAlignment(Qt.AlignCenter)
        self.pilha.addWidget(nada)
        self.pilha.addWidget(self._criar_formulario_servico())
        self.pilha.addWidget(self._criar_formulario_categoria())
        direita.addWidget(self.pilha)

        caixa_taxa = QGroupBox("Taxa da maquininha (débito e crédito)")
        grade_taxa = QGridLayout(caixa_taxa)
        grade_taxa.setColumnStretch(0, 1)
        taxas = [self.config.taxas_maquininha.get(forma, Decimal("0")) for forma in FORMAS_COM_TAXA]
        self.taxa_original = max(taxas)
        explicacao = _rotulo("Só vale para os serviços marcados com \"cobra a taxa da maquininha\".", "rotulo")
        explicacao.setWordWrap(True)
        grade_taxa.addWidget(explicacao, 0, 0)
        caixa = QHBoxLayout()
        caixa.addWidget(_rotulo("%", "rotulo"))
        self.campo_taxa = QLineEdit(formatar_percentual(self.taxa_original)[:-1])
        self.campo_taxa.setFixedWidth(90)
        self.campo_taxa.setAlignment(Qt.AlignRight)
        self.campo_taxa.textChanged.connect(lambda *_: self._validar_taxa())
        caixa.addWidget(self.campo_taxa)
        grade_taxa.addLayout(caixa, 0, 1)
        self.aviso_taxa = _rotulo("", "aviso")
        self.aviso_taxa.setWordWrap(True)
        self.aviso_taxa.hide()
        grade_taxa.addWidget(self.aviso_taxa, 1, 0, 1, 2)
        if taxas[0] != taxas[1]:
            diferente = _rotulo(f"Hoje o débito está com {formatar_percentual(taxas[0])} e o crédito com "
                                f"{formatar_percentual(taxas[1])}. Ao salvar, os dois ficam com a taxa acima.",
                                "aviso")
            diferente.setWordWrap(True)
            grade_taxa.addWidget(diferente, 2, 0, 1, 2)
        direita.addWidget(caixa_taxa)

        caixa_teclado = QGroupBox("Teclado")
        coluna_teclado = QVBoxLayout(caixa_teclado)
        coluna_teclado.setContentsMargins(0, 0, 0, 0)
        self.teclado = TecladoNumerico()
        self.teclado.tecla_apertada.connect(self._tecla_na_tela)
        coluna_teclado.addWidget(self.teclado)
        direita.addWidget(caixa_teclado)
        direita.addStretch(1)
        corpo.addLayout(direita, 2)

        # --- Botões de baixo ---
        botoes = QHBoxLayout()
        btn_padrao = QPushButton("Restaurar preços padrão")
        btn_padrao.setToolTip("Preços e taxa de fábrica nos serviços que vieram com o programa")
        btn_padrao.clicked.connect(self.restaurar_precos)
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
            botao.setAutoDefault(False)  # Enter num campo não aperta o "Salvar"

        self._montar_arvore()
        self._montar_desativados()
        tela = (pai.screen() if pai else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1180, tela.width() - 40), min(820, tela.height() - 60))
        QApplication.instance().focusChanged.connect(self._foco_mudou)
        primeiro = self.arvore.topLevelItem(0)
        self.arvore.setCurrentItem(primeiro.child(0) if primeiro and primeiro.childCount() else primeiro)

    # ------------------------------------------------------------------
    # Montagem
    # ------------------------------------------------------------------

    @staticmethod
    def _dados_do_servico(servico, teclas):
        """Os dados de um serviço do config, no formato que a tela usa (o preço como texto do campo)."""
        valor = servico.preco if servico.tipo == "unidade" else servico.taxa
        return {
            "id": servico.id,
            "nome": servico.nome,
            "nome_original": servico.nome,
            "preco": numero_para_campo(valor),
            "preco_original": valor,
            "tipo": servico.tipo,
            "grupo_original": servico.grupo,
            "cobra": servico.cobra_taxa_maquininha,
            "cobra_original": servico.cobra_taxa_maquininha,
            "terceiros": servico.valor_de_terceiros,
            "terceiros_original": servico.valor_de_terceiros,
            "tecla": teclas.get(atalhos.acao_do_servico(servico.id), ""),
            "nomes_anteriores": list(servico.nomes_anteriores),
            "novo": False,
        }

    def _criar_formulario_servico(self):
        caixa = QGroupBox("Serviço selecionado")
        grade = QGridLayout(caixa)
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(4)
        grade.setColumnStretch(1, 1)

        grade.addWidget(_rotulo("Nome"), 0, 0)
        self.campo_nome = QLineEdit()
        self.campo_nome.setMaxLength(40)
        self.campo_nome.textChanged.connect(lambda texto: self._editar("nome", texto))
        self.campo_nome.returnPressed.connect(lambda: self._focar(self.campo_preco))
        grade.addWidget(self.campo_nome, 0, 1, 1, 2)
        self.aviso_nome = self._aviso(grade, 1)

        grade.addWidget(_rotulo("Preço (R$)"), 2, 0)
        self.campo_preco = QLineEdit()
        self.campo_preco.setAlignment(Qt.AlignRight)
        self.campo_preco.setFixedWidth(110)
        self.campo_preco.textChanged.connect(lambda texto: self._editar("preco", texto))
        self.campo_preco.returnPressed.connect(self._proximo_servico)
        grade.addWidget(self.campo_preco, 2, 1)
        self.lbl_tipo = _rotulo("", "rotulo")
        grade.addWidget(self.lbl_tipo, 2, 2)
        self.aviso_preco = self._aviso(grade, 3)

        grade.addWidget(_rotulo("Categoria"), 4, 0)
        self.combo_categoria = QComboBox()
        self.combo_categoria.activated.connect(lambda _indice: self._mudar_categoria())
        grade.addWidget(self.combo_categoria, 4, 1, 1, 2)

        grade.addWidget(_rotulo("Tecla de atalho"), 5, 0)
        linha_tecla = QHBoxLayout()
        self.botao_tecla = BotaoTecla()
        self.botao_tecla.setToolTip("Clique e aperte a tecla (vale tecla de PDV e combinações com Ctrl/Alt)")
        self.botao_tecla.tecla_apertada.connect(self._tecla_capturada)
        self.botao_tecla.captura_mudou.connect(self._captura_mudou)
        linha_tecla.addWidget(self.botao_tecla)
        sem_atalho = QPushButton("Sem atalho")
        sem_atalho.clicked.connect(lambda: self._definir_tecla(""))
        linha_tecla.addWidget(sem_atalho)
        linha_tecla.addStretch(1)
        grade.addLayout(linha_tecla, 5, 1, 1, 2)
        self.aviso_tecla = self._aviso(grade, 6)

        self.check_cobra = QCheckBox("Cobra a taxa da maquininha (débito/crédito)")
        self.check_cobra.setToolTip("Desmarque para recargas e boletos: o valor deles é cobrado à parte, "
                                    "direto na maquininha")
        self.check_cobra.toggled.connect(lambda marcado: self._editar("cobra", marcado))
        grade.addWidget(self.check_cobra, 7, 0, 1, 3)
        self.check_terceiros = QCheckBox("Cobra valor de terceiros (boleto/recarga)")
        self.check_terceiros.setToolTip("Com \"Pedir o valor do boleto/recarga\" ligada em Preferências, o "
                                        "funcionário digita o valor e o programa soma o preço do serviço "
                                        "(sem taxa da maquininha)")
        self.check_terceiros.toggled.connect(lambda marcado: self._editar("terceiros", marcado))
        grade.addWidget(self.check_terceiros, 8, 0, 1, 3)
        return caixa

    def _criar_formulario_categoria(self):
        caixa = QGroupBox("Categoria selecionada")
        grade = QGridLayout(caixa)
        grade.setHorizontalSpacing(10)
        grade.setColumnStretch(1, 1)
        grade.addWidget(_rotulo("Nome"), 0, 0)
        self.campo_categoria = QLineEdit()
        self.campo_categoria.setMaxLength(40)
        self.campo_categoria.textChanged.connect(self._renomear_categoria)
        grade.addWidget(self.campo_categoria, 0, 1)
        self.aviso_categoria = self._aviso(grade, 1)
        self.lbl_categoria_info = _rotulo("", "rotulo")
        self.lbl_categoria_info.setWordWrap(True)
        grade.addWidget(self.lbl_categoria_info, 2, 0, 1, 2)
        return caixa

    @staticmethod
    def _aviso(grade, linha):
        aviso = _rotulo("", "aviso")
        aviso.setWordWrap(True)
        aviso.hide()
        grade.addWidget(aviso, linha, 0, 1, 3)
        return aviso

    def _item_categoria(self, nome, original):
        item = QTreeWidgetItem([nome, "", "", ""])
        item.setData(0, PAPEL, self._guardar({"categoria": True, "nome": nome, "original": original}))
        fonte = QFont(item.font(0))
        fonte.setBold(True)
        item.setFont(0, fonte)
        # Categoria: pode ser arrastada e receber serviços.
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
        return item

    def _item_servico(self, dados):
        item = QTreeWidgetItem(["", "", "", ""])
        item.setData(0, PAPEL, self._guardar(dados))
        # Serviço: pode ser arrastado, mas nada cai "dentro" dele.
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
        self._atualizar_linha(item)
        return item

    def _montar_arvore(self):
        self.arvore.clear()
        categorias = {}
        for nome in self.config.categorias:
            # (categoria que só tem serviços removidos não aparece, a não ser que fique vazia de propósito)
            if any(s.grupo == nome for s in self.config.servicos) or not any(
                    s.grupo == nome for s in self.config.servicos_desativados):
                categorias[nome] = self._item_categoria(nome, nome)
                self.arvore.addTopLevelItem(categorias[nome])
        for servico in self.config.servicos:
            categorias[servico.grupo].addChild(self._item_servico(self._dados_do_servico(servico,
                                                                                        self.teclas_originais)))
        self.arvore.expandAll()
        self._atualizar_categorias()

    def _montar_desativados(self):
        self.lista_desativados.clear()
        for dados in self.desativados:
            item = QListWidgetItem(f"{dados['nome']}  ·  {dados['grupo_original']}")
            self.lista_desativados.addItem(item)
        self.caixa_desativados.setVisible(bool(self.desativados))
        if self.desativados:
            self.lista_desativados.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Leitura da lista
    # ------------------------------------------------------------------

    def _guardar(self, dados):
        chave = f"linha{len(self.registro)}"
        self.registro[chave] = dados
        return chave

    def dados(self, item):
        """Os dados (dicionário de verdade, não cópia) de uma linha da lista."""
        return self.registro[item.data(0, PAPEL)]

    def eh_categoria(self, item):
        return item is not None and self.dados(item).get("categoria", False)

    def categorias(self):
        return [self.arvore.topLevelItem(i) for i in range(self.arvore.topLevelItemCount())]

    def servicos(self):
        """(item, dados, nome da categoria) de todos os serviços ativos, na ordem da tela."""
        resultado = []
        for categoria in self.categorias():
            for i in range(categoria.childCount()):
                item = categoria.child(i)
                resultado.append((item, self.dados(item), self.dados(categoria)["nome"]))
        return resultado

    def _atualizar_linha(self, item):
        dados = self.dados(item)
        item.setText(0, dados["nome"] or "(sem nome)")
        try:  # preço válido aparece formatado (10 -> R$ 10,00); inválido, como foi digitado
            preco = formatar_reais(converter_valor(dados["preco"])) if dados["preco"] else ""
        except ValueError:
            preco = f"R$ {dados['preco']}"
        item.setText(1, preco)
        item.setText(2, dados["tecla"])
        item.setText(3, "cobra" if dados["cobra"] else "não cobra")

    def _atualizar_categorias(self):
        """Contagem de serviços de cada categoria e a lista do campo "Categoria"."""
        nomes = []
        for categoria in self.categorias():
            dados = self.dados(categoria)
            nomes.append(dados["nome"])
            quantos = categoria.childCount()
            categoria.setText(1, f"{quantos} serviço" + ("s" if quantos != 1 else ""))
        self.combo_categoria.clear()
        self.combo_categoria.addItems(nomes)
        item = self.arvore.currentItem()
        if item is not None and not self.eh_categoria(item):
            self.combo_categoria.setCurrentText(self.dados(item.parent())["nome"])

    # ------------------------------------------------------------------
    # Selecionar e editar
    # ------------------------------------------------------------------

    def _mostrar_selecionado(self):
        self.botao_tecla.parar()
        self._pendente = None
        item = self.arvore.currentItem()
        self._preenchendo = True
        if item is None:
            self.pilha.setCurrentIndex(0)
        elif self.eh_categoria(item):
            self.pilha.setCurrentIndex(2)
            self.campo_categoria.setText(self.dados(item)["nome"])
            quantos = item.childCount()
            self.lbl_categoria_info.setText(
                f"{quantos} serviço(s). Para remover a categoria, remova ou leve os serviços para outra.")
        else:
            self.pilha.setCurrentIndex(1)
            dados = self.dados(item)
            self.campo_nome.setText(dados["nome"])
            self.campo_preco.setText(dados["preco"])
            self.lbl_tipo.setText("por unidade" if dados["tipo"] == "unidade" else "somado ao valor informado")
            self.combo_categoria.setCurrentText(self.dados(item.parent())["nome"])
            self.botao_tecla.definir(dados["tecla"])
            self.check_cobra.setChecked(dados["cobra"])
            self.check_terceiros.setChecked(dados.get("terceiros", False))
            self._avisar(self.aviso_tecla, "")
        self._preenchendo = False
        self._validar_formulario()
        self.btn_remover.setEnabled(item is not None)

    def _editar(self, chave, valor):
        """Algo mudou no formulário do serviço: guarda nos dados da linha e confere."""
        item = self.arvore.currentItem()
        if self._preenchendo or item is None or self.eh_categoria(item):
            return
        self.dados(item)[chave] = valor
        self._atualizar_linha(item)
        self._validar_formulario()

    def _mudar_categoria(self):
        """Escolheu outra categoria no campo: o serviço vai para o fim dela."""
        item = self.arvore.currentItem()
        if item is None or self.eh_categoria(item):
            return
        destino = self.categorias()[self.combo_categoria.currentIndex()]
        if destino is item.parent():
            return
        item.parent().removeChild(item)
        destino.addChild(item)
        self.arvore.expandAll()
        self.arvore.setCurrentItem(item)
        self._atualizar_categorias()

    def _renomear_categoria(self, texto):
        item = self.arvore.currentItem()
        if self._preenchendo or not self.eh_categoria(item):
            return
        self.dados(item)["nome"] = texto.strip()
        item.setText(0, texto.strip() or "(sem nome)")
        self._atualizar_categorias()
        self._validar_formulario()

    def _depois_de_mexer_na_ordem(self):
        self._atualizar_categorias()
        self._mostrar_selecionado()

    # ------------------------------------------------------------------
    # Validação
    # ------------------------------------------------------------------

    @staticmethod
    def _avisar(aviso, texto, campo=None):
        aviso.setText(texto)
        aviso.setVisible(bool(texto))
        if campo is not None:
            campo.setProperty("erro", bool(texto))
            repintar(campo)

    def _erro_do_servico(self, dados, item=None):
        """(campo, mensagem) do primeiro problema de um serviço, ou (None, "") se estiver tudo certo."""
        nome = dados["nome"].strip()
        if not nome:
            return "nome", "Digite o nome do serviço."
        mesmo_nome = [d for _i, d, _c in self.servicos() if d is not dados and d["nome"].strip().casefold()
                      == nome.casefold()]
        if mesmo_nome:
            return "nome", "Já existe um serviço com esse nome."
        if any(d["nome"].casefold() == nome.casefold() for d in self.desativados):
            return "nome", "Esse nome é de um serviço removido. Para usar de novo, reative-o (lista de baixo)."
        try:
            converter_valor(dados["preco"])
        except ValueError as erro:
            return "preco", str(erro).replace("\n", " ")
        return None, ""

    def _erro_da_categoria(self, item):
        nome = self.dados(item)["nome"]
        if not nome:
            return "Digite o nome da categoria."
        if [c for c in self.categorias() if c is not item and self.dados(c)["nome"].casefold() == nome.casefold()]:
            return "Já existe uma categoria com esse nome."
        return ""

    def _validar_formulario(self):
        item = self.arvore.currentItem()
        if item is None:
            return
        if self.eh_categoria(item):
            self._avisar(self.aviso_categoria, self._erro_da_categoria(item), self.campo_categoria)
            return
        campo, mensagem = self._erro_do_servico(self.dados(item))
        self._avisar(self.aviso_nome, mensagem if campo == "nome" else "", self.campo_nome)
        self._avisar(self.aviso_preco, mensagem if campo == "preco" else "", self.campo_preco)

    def _validar_taxa(self):
        try:
            converter_percentual(self.campo_taxa.text())
            erro = ""
        except ValueError as e:
            erro = str(e).replace("\n", " ")
        self._avisar(self.aviso_taxa, erro, self.campo_taxa)
        return not erro

    # ------------------------------------------------------------------
    # Tecla de atalho do serviço
    # ------------------------------------------------------------------

    def _dono_da_tecla(self, tecla, menos):
        """
        (descrição, função que tira a tecla dele, função que devolve) de quem já usa
        a tecla, ou None. Só devolve se o antigo dono continuar sem tecla.
        """
        if not tecla:
            return None
        for _item, dados, _categoria in self.servicos():
            if dados is not menos and dados["tecla"] == tecla:
                def devolver_servico(d=dados, t=tecla):
                    if not d["tecla"]:
                        d["tecla"] = t
                return (f"o serviço \"{dados['nome']}\"", lambda d=dados: d.update(tecla=""), devolver_servico)
        for acao, atual in self.teclas_fixas.items():
            if atual == tecla:
                def devolver_acao(a=acao, t=tecla):
                    if not self.teclas_fixas.get(a):
                        self.teclas_fixas[a] = t
                return (f"\"{atalhos.DESCRICOES[acao]}\"", lambda a=acao: self.teclas_fixas.update({a: ""}),
                        devolver_acao)
        return None

    def _devolver_tecla(self, tecla):
        """Se 'tecla' foi tirada de alguém nesta tela e ficou livre, volta para o dono antigo."""
        devolver = self._tomadas.pop(tecla, None) if tecla else None
        if devolver is not None and self._dono_da_tecla(tecla, None) is None:
            devolver()
            for item, _dados, _categoria in self.servicos():
                self._atualizar_linha(item)

    def _captura_mudou(self, capturando):
        if capturando:
            self.aviso_tecla.setObjectName("rotulo")  # cinza: é só uma instrução
            repintar(self.aviso_tecla)
            self._avisar(self.aviso_tecla, "Aperte a tecla nova (Esc também vale). Para desistir, clique de novo.")
        else:
            self._pendente = None
            if self.aviso_tecla.objectName() == "rotulo":
                self._avisar(self.aviso_tecla, "")

    def _tecla_capturada(self, tecla):
        item = self.arvore.currentItem()
        if item is None or self.eh_categoria(item):
            return
        self.aviso_tecla.setObjectName("aviso")
        repintar(self.aviso_tecla)
        if not tecla:
            self._avisar(self.aviso_tecla, "Essa tecla não pode ser atalho (Enter, Tab, espaço e Backspace "
                                           "são usados para digitar). Aperte outra tecla.")
            return
        dados = self.dados(item)
        dono = self._dono_da_tecla(tecla, dados)
        if dono is not None and self._pendente != tecla:
            self._pendente = tecla  # primeira vez: só avisa
            self._avisar(self.aviso_tecla, f"{tecla} já é usada em {dono[0]}. Aperte {tecla} de novo para "
                                           "passar para cá (lá fica sem atalho), ou aperte outra tecla.")
            return
        if dono is not None:
            dono[1]()
            self._tomadas[tecla] = dono[2]
            for outro, _dados, _categoria in self.servicos():
                self._atualizar_linha(outro)
            self._definir_tecla(tecla)
            self._avisar(self.aviso_tecla, f"{tecla} agora é deste serviço; {dono[0]} ficou sem atalho.")
            return
        self._definir_tecla(tecla)

    def _definir_tecla(self, tecla):
        item = self.arvore.currentItem()
        if item is None or self.eh_categoria(item):
            return
        self._pendente = None
        dados = self.dados(item)
        antiga, dados["tecla"] = dados["tecla"], tecla
        self.botao_tecla.definir(tecla)
        self._atualizar_linha(item)
        if antiga != tecla:
            self._devolver_tecla(antiga)  # mudou de ideia: a tecla tirada de outro volta
        self._avisar(self.aviso_tecla, "")

    def _primeira_tecla_livre(self):
        usadas = {d["tecla"] for _i, d, _c in self.servicos()} | set(self.teclas_fixas.values())
        return next((tecla for tecla in atalhos.TECLAS_SERVICOS if tecla not in usadas), "")

    # ------------------------------------------------------------------
    # Botões da lista
    # ------------------------------------------------------------------

    def _nome_livre(self, base, existentes):
        existentes = {nome.casefold() for nome in existentes}
        nome, numero = base, 2
        while nome.casefold() in existentes:
            nome, numero = f"{base} {numero}", numero + 1
        return nome

    def nova_categoria(self):
        nome = self._nome_livre("Nova categoria", [self.dados(c)["nome"] for c in self.categorias()])
        item = self._item_categoria(nome, None)
        self.arvore.addTopLevelItem(item)
        self._atualizar_categorias()
        self.arvore.setCurrentItem(item)
        self._focar(self.campo_categoria)

    def novo_servico(self):
        atual = self.arvore.currentItem()
        if atual is None:
            if not self.categorias():
                self.nova_categoria()
            categoria = self.categorias()[0]
        else:
            categoria = atual if self.eh_categoria(atual) else atual.parent()
        usados = {d["id"] for _i, d, _c in self.servicos()} | {d["id"] for d in self.desativados}
        todos_os_nomes = [d["nome"] for _i, d, _c in self.servicos()] + [d["nome"] for d in self.desativados]
        nome = self._nome_livre("Novo serviço", todos_os_nomes)
        dados = {"id": config.criar_id(nome, usados), "nome": nome, "nome_original": None, "preco": "",
                 "preco_original": None, "tipo": "unidade", "grupo_original": None, "cobra": True,
                 "cobra_original": None, "terceiros": False, "terceiros_original": None, "tecla": self._primeira_tecla_livre(), "nomes_anteriores": [],
                 "novo": True}
        item = self._item_servico(dados)
        categoria.addChild(item)
        self.arvore.expandAll()
        self.arvore.setCurrentItem(item)
        self._atualizar_categorias()
        self._focar(self.campo_nome)

    def mover(self, passo):
        """↑ ↓: troca o selecionado de lugar com o vizinho (dentro da mesma categoria)."""
        item = self.arvore.currentItem()
        if item is None:
            return
        pai = item.parent() or self.arvore.invisibleRootItem()
        posicao = pai.indexOfChild(item)
        nova = posicao + passo
        if not 0 <= nova < pai.childCount():
            return
        aberto = item.isExpanded()
        pai.takeChild(posicao)
        pai.insertChild(nova, item)
        item.setExpanded(aberto)
        self.arvore.expandAll()
        self.arvore.setCurrentItem(item)
        self._atualizar_categorias()

    def remover(self):
        item = self.arvore.currentItem()
        if item is None:
            return
        if self.eh_categoria(item):
            if item.childCount():
                QMessageBox.information(self, "Remover categoria",
                                        "A categoria ainda tem serviços. Remova os serviços ou leve-os "
                                        "para outra categoria antes.")
                return
            self.arvore.takeTopLevelItem(self.arvore.indexOfTopLevelItem(item))
        else:
            dados = self.dados(item)
            if not dados["novo"]:
                resposta = QMessageBox.question(
                    self, "Remover serviço",
                    f"Remover \"{dados['nome_original']}\"?\n\nEle sai da tela de atendimento, mas continua nos "
                    "atendimentos antigos e nos relatórios. Dá para reativar depois.")
                if resposta != QMessageBox.Yes:
                    return
                # Volta o nome de antes (o histórico usa o nome com que o serviço foi vendido).
                dados = {**dados, "nome": dados["nome_original"], "grupo_original": self.dados(item.parent())["nome"]}
                self.desativados.append(dados)
                self._montar_desativados()
            item.parent().removeChild(item)
            self._devolver_tecla(self.dados(item)["tecla"])
        self._atualizar_categorias()
        self._mostrar_selecionado()

    def reativar(self):
        linha = self.lista_desativados.currentRow()
        if linha < 0:
            return
        dados = self.desativados.pop(linha)
        nomes = {self.dados(c)["nome"]: c for c in self.categorias()}
        categoria = nomes.get(dados["grupo_original"])
        if categoria is None:
            categoria = self._item_categoria(dados["grupo_original"], dados["grupo_original"])
            self.arvore.addTopLevelItem(categoria)
        dados["tecla"] = dados["tecla"] if dados["tecla"] and not self._dono_da_tecla(dados["tecla"], dados) \
            else self._primeira_tecla_livre()
        item = self._item_servico(dados)
        categoria.addChild(item)
        self.arvore.expandAll()
        self.arvore.setCurrentItem(item)
        self._montar_desativados()
        self._atualizar_categorias()

    def restaurar_precos(self):
        resposta = QMessageBox.question(
            self, "Restaurar preços padrão",
            "Colocar de volta os preços de fábrica (nos serviços que vieram com o programa) e a taxa de "
            "fábrica da maquininha?\n(Nada é gravado até você apertar Salvar.)")
        if resposta != QMessageBox.Yes:
            return
        padrao = {s["nome"]: s for s in config.CONFIG_PADRAO["servicos"]}
        for item, dados, _categoria in self.servicos():
            de_fabrica = padrao.get(dados["nome"]) or padrao.get(dados["nome_original"] or "")
            if de_fabrica is not None:
                chave = "preco" if de_fabrica["tipo"] == "unidade" else "taxa"
                dados["preco"] = numero_para_campo(Decimal(str(de_fabrica[chave])))
                self._atualizar_linha(item)
        self.campo_taxa.setText(formatar_percentual(
            Decimal(str(config.CONFIG_PADRAO["taxas_maquininha"]["Crédito"])))[:-1])
        self._mostrar_selecionado()

    # ------------------------------------------------------------------
    # Teclado na tela e Enter
    # ------------------------------------------------------------------

    def _focar(self, campo):
        campo.setFocus()
        campo.selectAll()

    def _foco_mudou(self, _antigo, novo):
        if novo in (self.campo_preco, self.campo_taxa):
            self._ultimo_campo = novo

    def _tecla_na_tela(self, tecla):
        campo = self._ultimo_campo
        if campo is None or not campo.isVisible():
            return
        campo.setFocus()
        if tecla == "enter":
            campo.returnPressed.emit()
        else:
            digitar_no_campo(campo, tecla)

    def _proximo_servico(self):
        """Enter no preço: vai para o preço do próximo serviço (para mudar vários preços rápido)."""
        lista = [item for item, _d, _c in self.servicos()]
        atual = self.arvore.currentItem()
        if atual in lista and lista.index(atual) + 1 < len(lista):
            self.arvore.setCurrentItem(lista[lista.index(atual) + 1])
            self._focar(self.campo_preco)
        else:
            self.btn_salvar.setFocus()

    def keyPressEvent(self, evento):
        # Enter num botão aperta o botão; Enter em outro lugar não fecha a tela.
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter):
            foco = QApplication.focusWidget()
            if isinstance(foco, QPushButton):
                foco.animateClick()
            return
        super().keyPressEvent(evento)

    # ------------------------------------------------------------------
    # Salvar
    # ------------------------------------------------------------------

    def _problemas(self):
        """O primeiro problema da tela: (item, mensagem), ou (None, "") se dá para salvar."""
        for categoria in self.categorias():
            erro = self._erro_da_categoria(categoria)
            if erro:
                return categoria, erro
        for item, dados, _categoria in self.servicos():
            _campo, erro = self._erro_do_servico(dados)
            if erro:
                return item, erro
        if not self.servicos():
            return None, "Deixe pelo menos um serviço na lista."
        if not self._validar_taxa():
            return None, "A taxa da maquininha está inválida."
        return None, ""

    def _mudancas(self):
        """Lista de textos com tudo o que mudou (para o resumo antes de salvar)."""
        mudancas = []
        originais = {s.id: s for s in self.config.servicos}
        ordem_original = [s.id for s in self.config.servicos]
        for categoria in self.categorias():
            dados = self.dados(categoria)
            if dados["original"] is None:
                mudancas.append(f"Categoria nova: {dados['nome']}")
            elif dados["original"] != dados["nome"]:
                mudancas.append(f"Categoria renomeada: {dados['original']} → {dados['nome']}")
        for _item, dados, categoria in self.servicos():
            preco = converter_valor(dados["preco"])
            if dados["novo"] or dados["id"] not in originais:
                if dados["novo"]:
                    mudancas.append(f"Serviço novo: {dados['nome']} ({formatar_reais(preco)}) em {categoria}")
                else:
                    mudancas.append(f"Reativado: {dados['nome']} (em {categoria})")
                continue
            if dados["nome"] != dados["nome_original"]:
                mudancas.append(f"Renomeado: {dados['nome_original']} → {dados['nome']}")
            if preco != dados["preco_original"]:
                mudancas.append(f"{dados['nome']}: {formatar_reais(dados['preco_original'])} → {formatar_reais(preco)}")
            if categoria != originais[dados["id"]].grupo:
                mudancas.append(f"{dados['nome']}: categoria {originais[dados['id']].grupo} → {categoria}")
            if dados["cobra"] != dados["cobra_original"]:
                mudancas.append(f"{dados['nome']}: " + ("passa a cobrar" if dados["cobra"] else "deixa de cobrar")
                                + " a taxa da maquininha")
            if dados["terceiros"] != dados["terceiros_original"]:
                mudancas.append(f"{dados['nome']}: " + ("passa a cobrar" if dados["terceiros"] else
                                                        "deixa de cobrar") + " valor de terceiros (boleto/recarga)")
        for dados in self.desativados:
            if dados["id"] in originais:
                mudancas.append(f"Removido: {dados['nome']} (continua no histórico)")
        teclas = self.teclas_novas()
        for acao, tecla in teclas.items():
            antes = self.teclas_originais.get(acao, "")
            id_servico = atalhos.id_do_servico(acao)
            if tecla != antes and (id_servico is None or id_servico in originais):
                nome = atalhos.DESCRICOES.get(acao) or next(
                    (d["nome"] for _i, d, _c in self.servicos() if d["id"] == id_servico), acao)
                mudancas.append(f"Tecla de {nome}: {atalhos.texto_para_mostrar(antes)} → "
                                f"{atalhos.texto_para_mostrar(tecla)}")
        nova_ordem = [d["id"] for _i, d, _c in self.servicos() if d["id"] in originais]
        if nova_ordem != [i for i in ordem_original if i in nova_ordem]:
            mudancas.append("Ordem dos serviços mudou")
        categorias_originais = [c for c in self.config.categorias]
        novas = [self.dados(c)["original"] for c in self.categorias() if self.dados(c)["original"]]
        if novas != [c for c in categorias_originais if c in novas]:
            mudancas.append("Ordem das categorias mudou")
        taxa = converter_percentual(self.campo_taxa.text())
        if taxa != self.taxa_original:
            mudancas.append(f"Taxa da maquininha: {formatar_percentual(self.taxa_original)} → "
                            f"{formatar_percentual(taxa)}")
        return mudancas

    def teclas_novas(self):
        """Os atalhos depois das mudanças: os fixos + um por serviço ativo."""
        teclas = dict(self.teclas_fixas)
        for _item, dados, _categoria in self.servicos():
            teclas[atalhos.acao_do_servico(dados["id"])] = dados["tecla"]
        return teclas

    def json_novo(self):
        """O config.json com os serviços e categorias da tela (as outras chaves continuam como estavam)."""
        dados_json = copy.deepcopy(self.json_original)
        originais = {s.get("id"): s for s in dados_json.get("servicos", []) if isinstance(s, dict)}
        servicos = []

        def montar(dados, categoria, ativo):
            servico = copy.deepcopy(originais.get(dados["id"], {}))
            servico.update({"id": dados["id"], "grupo": categoria, "nome": dados["nome"].strip(),
                            "tipo": dados["tipo"]})
            servico["preco" if dados["tipo"] == "unidade" else "taxa"] = float(converter_valor(dados["preco"]))
            servico["cobra_taxa_maquininha"] = dados["cobra"]
            servico["valor_de_terceiros"] = dados["terceiros"]
            servico["ativo"] = ativo
            anteriores = list(dados["nomes_anteriores"])
            if dados["nome_original"] and dados["nome_original"] != servico["nome"] \
                    and dados["nome_original"] not in anteriores:
                anteriores.append(dados["nome_original"])  # o relatório ainda acha a categoria
            if anteriores:
                servico["nomes_anteriores"] = anteriores
            return servico

        for _item, dados, categoria in self.servicos():
            servicos.append(montar(dados, categoria, True))
        for dados in self.desativados:
            servicos.append(montar(dados, dados["grupo_original"], False))
        dados_json["servicos"] = servicos
        dados_json["categorias"] = [self.dados(c)["nome"] for c in self.categorias()]
        taxa = float(converter_percentual(self.campo_taxa.text()))
        taxas = dados_json.setdefault("taxas_maquininha", {})
        for forma in FORMAS_COM_TAXA:
            taxas[forma] = taxa
        return dados_json

    def salvar(self):
        self.botao_tecla.parar()
        item, erro = self._problemas()
        if erro:
            if item is not None:
                self.arvore.setCurrentItem(item)
            QMessageBox.warning(self, "Serviços e preços", f"{erro}\n\nCorrija o que está em vermelho antes de salvar.")
            return
        mudancas = self._mudancas()
        if not mudancas:
            QMessageBox.information(self, "Serviços e preços", "Nada foi alterado.")
            self.accept()
            return
        resposta = QMessageBox.question(
            self, "Confirmar mudanças",
            "Estas mudanças vão ser gravadas:\n\n" + "\n".join(f"• {m}" for m in mudancas) +
            "\n\nValem a partir de agora. Atendimentos já feitos não mudam.\n\nSalvar?")
        if resposta != QMessageBox.Yes:
            return
        try:
            config.salvar_config(self.json_novo())
        except OSError as erro_arquivo:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível gravar o config.json:\n{erro_arquivo}")
            return
        self.ao_salvar(self.teclas_novas())
        self.accept()

    def _mexeu(self):
        try:
            return bool(self._mudancas())
        except ValueError:
            return True  # tem campo inválido: com certeza a pessoa mexeu

    def reject(self):
        """Cancelar / Esc / X: se algo mudou, pergunta antes de descartar."""
        self.botao_tecla.parar()
        if self._mexeu():
            resposta = QMessageBox.question(self, "Serviços e preços", "Descartar as mudanças que não foram salvas?")
            if resposta != QMessageBox.Yes:
                return
        super().reject()

    def done(self, resultado):
        QApplication.instance().focusChanged.disconnect(self._foco_mudou)
        super().done(resultado)
