"""
tela_relatorio.py - Tela "Relatório do dia" (menu Arquivo › Relatório do dia, tecla F10).

    ┌ Data [01/11/2026 ▾]  ◀ Hoje ▶                     sábado, 01/11/2026 ┐
    │ [Atendimentos 12]   [Taxas R$ 0,33]   [Total do dia R$ 100,00]         │
    │ Por serviço                    │ Por forma de pagamento                │
    │ Atendimentos do dia (nº, hora, itens, pagamento, total)                │
    │ Impressoras: A4 [▾] Retrato/Paisagem [Teste] · Resumo 80mm [▾] [Teste] │
    └ Abrir nota   Imprimir A4 · resumo · PDF · Excel · Fechar expediente    ┘

O desenho da folha A4 fica em relatorio_a4.py; a pré-visualização em
DialogoPrevia (aqui embaixo). Nome e telefone de cliente nunca aparecem aqui.

As contas ficam em relatorio.py. As cores seguem o tema do programa sozinhas,
porque a folha de estilo vale para todas as janelas.
"""

import os
from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import backup
import impressao
import notas
import relatorio as rel
import relatorio_a4
import treino
from utils import formatar_reais


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


def _tabela(cabecalho, colunas_direita, coluna_esticada):
    """Uma tabela só de leitura, no mesmo estilo da tabela do atendimento."""
    tabela = QTableWidget(0, len(cabecalho))
    tabela.setHorizontalHeaderLabels(cabecalho)
    tabela.verticalHeader().hide()
    tabela.setShowGrid(False)
    tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
    tabela.setSelectionMode(QAbstractItemView.SingleSelection)
    tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
    tabela.setWordWrap(True)
    tabela.setTextElideMode(Qt.ElideNone)
    tabela.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    cabecalho_tabela = tabela.horizontalHeader()
    cabecalho_tabela.setHighlightSections(False)
    for coluna in range(len(cabecalho)):
        modo = QHeaderView.Stretch if coluna == coluna_esticada else QHeaderView.ResizeToContents
        cabecalho_tabela.setSectionResizeMode(coluna, modo)
        alinhamento = Qt.AlignRight if coluna in colunas_direita else Qt.AlignLeft
        tabela.horizontalHeaderItem(coluna).setTextAlignment(alinhamento | Qt.AlignVCenter)
    tabela.colunas_direita = colunas_direita
    return tabela


def _preencher(tabela, linhas):
    tabela.setRowCount(len(linhas))
    for numero_linha, linha in enumerate(linhas):
        for coluna, valor in enumerate(linha):
            celula = QTableWidgetItem(str(valor))
            if coluna in tabela.colunas_direita:
                celula.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tabela.setItem(numero_linha, coluna, celula)


def _cartao(titulo, nome_valor):
    """Um "cartão" com um rótulo pequeno e um número grande."""
    cartao = QFrame()
    cartao.setObjectName("painel")
    coluna = QVBoxLayout(cartao)
    coluna.setContentsMargins(16, 10, 16, 12)
    coluna.setSpacing(2)
    coluna.addWidget(_rotulo(titulo, "rotulo"))
    valor = _rotulo("", nome_valor)
    coluna.addWidget(valor)
    return cartao, valor


def impressoras_instaladas():
    """Nomes das impressoras do Windows (pelo Qt, que funciona mesmo sem o pywin32)."""
    try:
        return list(QPrinterInfo.availablePrinterNames())
    except Exception:
        return []


def impressora_padrao_windows():
    try:
        return QPrinterInfo.defaultPrinterName()
    except Exception:
        return ""


def _preencher_impressoras(combo, primeiro_texto, escolhida):
    """Combo com "padrão" (valor vazio) + as impressoras instaladas; seleciona a escolhida."""
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(primeiro_texto, "")
    for nome in impressoras_instaladas():
        combo.addItem(nome, nome)
    if escolhida and combo.findData(escolhida) < 0:
        combo.addItem(f"{escolhida} (não encontrada)", escolhida)  # foi desinstalada?
    combo.setCurrentIndex(max(combo.findData(escolhida), 0))
    combo.blockSignals(False)


class TelaRelatorio(QDialog):
    """
    pai = a janela principal (de onde vêm o nome da loja, a ordem dos serviços
          e o layout das notinhas, usado para imprimir o resumo).
    """

    def __init__(self, pai):
        super().__init__(pai)
        self.setWindowTitle("Relatório do dia" + (" - TREINAMENTO (sem valor)" if treino.ativo() else ""))
        self.pai = pai
        self.relatorio = None

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(12)

        # --- Escolha da data ---
        linha_data = QHBoxLayout()
        linha_data.setSpacing(8)
        linha_data.addWidget(_rotulo("Data"))
        self.campo_data = QDateEdit(QDate.currentDate())
        self.campo_data.setCalendarPopup(True)  # a setinha abre um calendário
        self.campo_data.setDisplayFormat("dd/MM/yyyy")
        self.campo_data.setMaximumDate(QDate.currentDate())  # não existe relatório do futuro
        portugues = QLocale(QLocale.Portuguese, QLocale.Brazil)
        self.campo_data.setLocale(portugues)
        self.campo_data.calendarWidget().setLocale(portugues)
        self.campo_data.setMinimumWidth(130)
        self.campo_data.dateChanged.connect(self.atualizar)
        linha_data.addWidget(self.campo_data)
        for texto, dica, dias in (("‹ Anterior", "Dia anterior", -1), ("Hoje", "Voltar para hoje", None),
                                  ("Próximo ›", "Próximo dia", 1)):
            botao = QPushButton(texto)
            botao.setToolTip(dica)
            botao.setAutoDefault(False)
            botao.clicked.connect(lambda _marcado=False, dias=dias: self._mudar_dia(dias))
            linha_data.addWidget(botao)
        linha_data.addStretch(1)
        self.lbl_dia = _rotulo("", "servicoAtual")
        linha_data.addWidget(self.lbl_dia)
        coluna.addLayout(linha_data)

        # --- Cartões com os números principais ---
        cartoes = QHBoxLayout()
        cartoes.setSpacing(12)
        cartao, self.lbl_quantidade = _cartao("Atendimentos", "valorGrande")
        cartoes.addWidget(cartao, 1)
        cartao, self.lbl_servicos = _cartao("Serviços", "valorGrande")
        cartoes.addWidget(cartao, 1)
        cartao, self.lbl_taxas = _cartao("Taxas da maquininha", "valorGrande")
        cartoes.addWidget(cartao, 1)
        cartao, self.lbl_total = _cartao("Total do dia", "total")
        cartoes.addWidget(cartao, 1)
        coluna.addLayout(cartoes)

        # --- Por serviço e por forma de pagamento ---
        meio = QHBoxLayout()
        meio.setSpacing(12)
        self.tabela_servicos = _tabela(["Serviço", "Quantidade", "Valor", "%"], (1, 2, 3), 0)
        meio.addWidget(self._secao("Por serviço", self.tabela_servicos), 5)
        self.tabela_formas = _tabela(["Forma", "Atendimentos", "Total", "Taxa"], (1, 2, 3), 0)
        meio.addWidget(self._secao("Por forma de pagamento", self.tabela_formas), 4)
        # Boletos e recargas (só com "Mostrar repasses no relatório" ligada em Preferências).
        self.tabela_repasses = _tabela(["Forma", "Qtd", "Valor"], (1, 2), 0)
        self.secao_repasses = self._secao(rel.TITULO_REPASSES, self.tabela_repasses)
        self.secao_repasses.setToolTip("Valores de boletos e recargas recebidos. Não entram no total do dia.")
        self.secao_repasses.hide()
        meio.addWidget(self.secao_repasses, 3)
        coluna.addLayout(meio, 2)

        # --- Lista dos atendimentos ---
        self.tabela_atendimentos = _tabela(["Nº", "Hora", "Itens", "Pagamento", "Total"], (4,), 2)
        self.tabela_atendimentos.doubleClicked.connect(lambda *_: self.abrir_nota())
        self.tabela_atendimentos.itemSelectionChanged.connect(self._atualizar_botoes)
        self.pilha_lista = QStackedWidget()
        vazio = _rotulo("Nenhum atendimento neste dia.", "vazio")
        vazio.setAlignment(Qt.AlignCenter)
        self.pilha_lista.addWidget(vazio)
        self.pilha_lista.addWidget(self.tabela_atendimentos)
        coluna.addWidget(self._secao("Atendimentos do dia · dois cliques abrem a nota", self.pilha_lista), 3)

        # --- Impressoras (lembradas nas preferências) ---
        coluna.addWidget(self._painel_impressoras())

        # --- Botões ---
        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.btn_abrir_nota = QPushButton("Abrir nota")
        self.btn_abrir_nota.clicked.connect(self.abrir_nota)
        botoes.addWidget(self.btn_abrir_nota)
        botoes.addStretch(1)
        self.btn_imprimir_a4 = QPushButton("Imprimir relatório (A4)...")
        self.btn_imprimir_a4.setToolTip("Mostra todas as páginas antes de imprimir")
        self.btn_imprimir_a4.clicked.connect(self.imprimir_a4)
        botoes.addWidget(self.btn_imprimir_a4)
        self.btn_imprimir = QPushButton("Imprimir resumo (80mm)")
        self.btn_imprimir.clicked.connect(self.imprimir)
        botoes.addWidget(self.btn_imprimir)
        self.btn_pdf = QPushButton("Exportar PDF")
        self.btn_pdf.clicked.connect(lambda: self.exportar("pdf"))
        botoes.addWidget(self.btn_pdf)
        self.btn_excel = QPushButton("Exportar Excel")
        self.btn_excel.clicked.connect(lambda: self.exportar("xlsx"))
        botoes.addWidget(self.btn_excel)
        self.btn_fechar_expediente = QPushButton("Fechar expediente")
        self.btn_fechar_expediente.setObjectName("finalizar")
        self.btn_fechar_expediente.clicked.connect(self.fechar_expediente)
        botoes.addWidget(self.btn_fechar_expediente)
        btn_fechar = QPushButton("Fechar  Esc")
        btn_fechar.clicked.connect(self.reject)
        botoes.addWidget(btn_fechar)
        coluna.addLayout(botoes)
        for botao in self.findChildren(QPushButton):
            botao.setAutoDefault(False)  # Enter não aperta nenhum botão sem querer

        tela = (pai.screen() if pai else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1180, tela.width() - 40), min(900, tela.height() - 60))
        self.atualizar()

    def _painel_impressoras(self):
        """Escolha da impressora do relatório A4 e da do resumo de 80mm, cada uma com um teste."""
        prefs = self.pai.preferencias
        painel = QFrame()
        painel.setObjectName("painel")
        grade = QGridLayout(painel)
        grade.setContentsMargins(16, 8, 16, 8)
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(6)

        grade.addWidget(_rotulo("Impressora do relatório A4:"), 1, 0)
        self.combo_a4 = QComboBox()
        padrao = impressora_padrao_windows()
        _preencher_impressoras(self.combo_a4, f"Padrão do Windows ({padrao})" if padrao else "Padrão do Windows",
                               prefs.get("impressora_relatorio", ""))
        self.combo_a4.currentIndexChanged.connect(lambda *_: self._guardar_escolhas())
        grade.addWidget(self.combo_a4, 1, 1)
        self.radio_retrato = QRadioButton("Retrato")
        self.radio_paisagem = QRadioButton("Paisagem")
        grupo = QButtonGroup(self)
        grupo.addButton(self.radio_retrato)
        grupo.addButton(self.radio_paisagem)
        (self.radio_paisagem if prefs.get("relatorio_paisagem") else self.radio_retrato).setChecked(True)
        self.radio_paisagem.toggled.connect(lambda *_: self._guardar_escolhas())
        grade.addWidget(self.radio_retrato, 1, 2)
        grade.addWidget(self.radio_paisagem, 1, 3)
        teste_a4 = QPushButton("Imprimir teste")
        teste_a4.clicked.connect(self.imprimir_teste_a4)
        grade.addWidget(teste_a4, 1, 4)

        grade.addWidget(_rotulo("Impressora do resumo (80mm):"), 2, 0)
        self.combo_resumo = QComboBox()
        _preencher_impressoras(self.combo_resumo, f"Mesma das notinhas ({self._impressora_das_notinhas()})",
                               prefs.get("impressora_resumo", ""))
        self.combo_resumo.currentIndexChanged.connect(lambda *_: self._guardar_escolhas())
        grade.addWidget(self.combo_resumo, 2, 1)
        teste_resumo = QPushButton("Imprimir teste")
        teste_resumo.clicked.connect(self.imprimir_teste_resumo)
        grade.addWidget(teste_resumo, 2, 4)
        grade.setColumnStretch(1, 1)
        grade.setColumnStretch(5, 1)
        for combo in (self.combo_a4, self.combo_resumo):
            combo.setMinimumWidth(320)
        return painel

    def _impressora_das_notinhas(self):
        """O nome da impressora do Configurar notinhas (vazio lá = a padrão do Windows)."""
        return self.pai.layout_das_notas["impressao"]["impressora"] or "padrão do Windows"

    def _guardar_escolhas(self):
        """O programa lembra as impressoras e a orientação (preferencias.json)."""
        self.pai.preferencias["impressora_relatorio"] = self.combo_a4.currentData() or ""
        self.pai.preferencias["impressora_resumo"] = self.combo_resumo.currentData() or ""
        self.pai.preferencias["relatorio_paisagem"] = self.radio_paisagem.isChecked()
        self.pai._salvar_preferencias()

    def impressora_a4(self):
        """Nome da impressora do relatório A4 ('' = a padrão do Windows)."""
        return self.combo_a4.currentData() or ""

    def impressora_resumo(self):
        """Nome da impressora do resumo ('' = a mesma das notinhas)."""
        return self.combo_resumo.currentData() or ""

    def paisagem(self):
        return self.radio_paisagem.isChecked()

    def _nome_a4_para_mostrar(self):
        return self.impressora_a4() or impressora_padrao_windows() or "padrão do Windows"

    def _secao(self, titulo, conteudo):
        """Um cartão com título em cima e a tabela embaixo."""
        cartao = QFrame()
        cartao.setObjectName("painel")
        coluna = QVBoxLayout(cartao)
        coluna.setContentsMargins(8, 8, 8, 8)
        coluna.setSpacing(4)
        cabecalho = _rotulo(titulo, "grupo")
        cabecalho.setContentsMargins(8, 0, 0, 0)
        coluna.addWidget(cabecalho)
        coluna.addWidget(conteudo, 1)
        return cartao

    # ------------------------------------------------------------------
    # Dados
    # ------------------------------------------------------------------

    def dia(self):
        return self.campo_data.date().toPython()  # QDate -> datetime.date

    def _mudar_dia(self, dias):
        if dias is None:
            self.campo_data.setDate(QDate.currentDate())
        else:
            self.campo_data.setDate(self.campo_data.date().addDays(dias))

    def atualizar(self):
        """Lê o banco de novo e mostra o relatório do dia escolhido."""
        config = self.pai.config
        ordem = [servico.nome for servico in config.servicos]
        self.relatorio = r = rel.montar_relatorio(self.dia(), ordem, config.categoria_de, config.categorias,
                                                  config.atendimento["mostrar_repasses"])
        hoje = self.dia() == date.today()
        self.lbl_dia.setText(("Hoje · " if hoje else "") + rel.data_por_extenso(r.dia))

        self.lbl_quantidade.setText(str(r.quantidade))
        self.lbl_servicos.setText(formatar_reais(r.subtotal))
        self.lbl_taxas.setText(formatar_reais(r.total_taxas))
        self.lbl_total.setText(formatar_reais(r.total))
        _preencher(self.tabela_servicos, [(d["nome"], d["quantidade"], formatar_reais(d["total"]),
                                           rel.formatar_porcento(d["percentual"])) for d in r.detalhe_servicos])
        _preencher(self.tabela_formas, [(forma, qtd, formatar_reais(total), formatar_reais(r.taxa_por_forma[forma]))
                                        for forma, (qtd, total) in r.por_forma.items()])
        self.secao_repasses.setVisible(r.mostrar_repasses)
        if r.mostrar_repasses:
            _preencher(self.tabela_repasses,
                       [(forma, qtd, formatar_reais(valor)) for forma, (qtd, valor) in r.repasse_por_forma.items()]
                       + [("Total", sum(q for q, _v in r.repasse_por_forma.values()),
                           formatar_reais(r.total_repasses))])
        _preencher(self.tabela_atendimentos, [
            (f"{a['numero']:06d}", a["data_hora"].strftime("%H:%M"), rel.descrever_itens(a),
             a["forma_pagamento"], formatar_reais(a["total"])) for a in r.atendimentos])
        self.pilha_lista.setCurrentIndex(1 if r.atendimentos else 0)
        if r.atendimentos:
            self.tabela_atendimentos.selectRow(len(r.atendimentos) - 1)  # o último atendimento
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        tem_dados = bool(self.relatorio and self.relatorio.atendimentos)
        for botao in (self.btn_imprimir_a4, self.btn_imprimir, self.btn_pdf, self.btn_excel,
                      self.btn_fechar_expediente):
            botao.setEnabled(tem_dados)
        self.btn_abrir_nota.setEnabled(tem_dados and bool(self.tabela_atendimentos.selectionModel().selectedRows()))

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def abrir_nota(self):
        """Abre o .txt da nota da loja do atendimento selecionado (gera de novo se tiver sumido)."""
        linhas = self.tabela_atendimentos.selectionModel().selectedRows()
        if not linhas or not self.relatorio.atendimentos:
            return
        atendimento = self.relatorio.atendimentos[linhas[0].row()]
        caminho = notas.caminho_da_nota(atendimento["numero"], atendimento["data_hora"], "loja")
        if not os.path.exists(caminho):
            try:
                caminho = notas.gerar_nota(self.pai.layout_das_notas, atendimento["numero"], atendimento,
                                           atendimento["itens"], "loja")
            except OSError as erro:
                QMessageBox.warning(self, "Abrir nota", f"Não foi possível criar a nota:\n{erro}")
                return
        os.startfile(caminho)  # abre no Bloco de Notas

    def _nome_impressora(self):
        """A impressora do resumo: a escolhida aqui ou, se vazio, a das notinhas."""
        try:
            return self.impressora_resumo() or impressao.escolher_impressora(
                self.pai.layout_das_notas["impressao"]["impressora"])
        except impressao.ErroImpressao as erro:
            QMessageBox.warning(self, "Impressora", str(erro))
            return None

    def imprimir_teste_resumo(self):
        impressora = self._nome_impressora()
        if impressora is None:
            return
        if QMessageBox.question(self, "Imprimir teste",
                                f"Imprimir um teste do resumo (80mm) em “{impressora}”?") != QMessageBox.Yes:
            return
        try:
            rel.imprimir_teste_resumo(self.pai.layout_das_notas, self.pai.config.nome_loja, impressora)
        except impressao.ErroImpressao as erro:
            QMessageBox.warning(self, "Erro ao imprimir", str(erro))

    def imprimir_teste_a4(self):
        nome = self._nome_a4_para_mostrar()
        if QMessageBox.question(self, "Imprimir teste",
                                f"Imprimir uma folha de teste (A4) em “{nome}”?") != QMessageBox.Yes:
            return
        try:
            relatorio_a4.imprimir_teste(self.impressora_a4(), self.pai.config.nome_loja, self.paisagem())
        except Exception as erro:
            QMessageBox.warning(self, "Erro ao imprimir", f"Não foi possível imprimir o teste:\n{erro}")

    def imprimir_a4(self):
        """Abre a pré-visualização com todas as páginas; de lá se imprime."""
        previa = DialogoPrevia(self, self.relatorio, self.pai.config.nome_loja, self.impressora_a4(),
                               self._nome_a4_para_mostrar(), self.paisagem())
        previa.exec()
        if previa.paisagem() != self.paisagem():  # mudou a orientação lá: fica lembrada
            (self.radio_paisagem if previa.paisagem() else self.radio_retrato).setChecked(True)

    def imprimir(self, perguntar=True):
        """Imprime o resumo (80mm) na impressora escolhida. Devolve True se imprimiu."""
        impressora = self._nome_impressora()
        if impressora is None:
            return False
        if perguntar:
            resposta = QMessageBox.question(self, "Imprimir resumo",
                                            f"Imprimir o resumo do dia na impressora “{impressora}”?")
            if resposta != QMessageBox.Yes:
                return False
        try:
            rel.imprimir_resumo(self.pai.layout_das_notas, self.relatorio, self.pai.config.nome_loja, impressora)
        except impressao.ErroImpressao as erro:
            QMessageBox.warning(self, "Erro ao imprimir", str(erro))
            return False
        return True

    def _salvar(self, extensao, caminho):
        """Salva o PDF ou o Excel. Devolve o caminho, ou None se der erro."""
        try:
            if extensao == "pdf":
                return rel.exportar_pdf(self.relatorio, self.pai.config.nome_loja, caminho, self.paisagem())
            return rel.exportar_excel(self.relatorio, self.pai.config.nome_loja, caminho)
        except OSError as erro:  # ex.: o arquivo está aberto no Excel
            QMessageBox.warning(self, "Erro ao salvar",
                                f"Não foi possível salvar:\n{caminho}\n\n{erro}\n\n"
                                "Se o arquivo estiver aberto em outro programa, feche e tente de novo.")
            return None

    def exportar(self, extensao):
        """Botões Exportar PDF / Exportar Excel: a pessoa escolhe onde salvar."""
        sugestao = rel.caminho_padrao(self.dia(), extensao)
        os.makedirs(os.path.dirname(sugestao), exist_ok=True)
        filtro = "PDF (*.pdf)" if extensao == "pdf" else "Excel (*.xlsx)"
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar relatório", sugestao, filtro)
        if not caminho:
            return
        if self._salvar(extensao, caminho):
            resposta = QMessageBox.question(self, "Relatório salvo", f"Relatório salvo em:\n{caminho}\n\nAbrir agora?")
            if resposta == QMessageBox.Yes:
                os.startfile(caminho)

    def fechar_expediente(self):
        """Mostra o resumo e pergunta se quer imprimir e/ou salvar (na pasta relatorios/)."""
        dialogo = DialogoFechamento(self, self.relatorio, self.pai.config.nome_loja)
        if dialogo.exec() != QDialog.Accepted:
            return
        feito = []
        for extensao, marcado in (("pdf", dialogo.check_pdf.isChecked()), ("xlsx", dialogo.check_excel.isChecked())):
            if marcado:
                caminho = self._salvar(extensao, rel.caminho_padrao(self.dia(), extensao))
                if caminho:
                    feito.append(f"Salvo: {caminho}")
        if dialogo.check_imprimir.isChecked() and self.imprimir(perguntar=False):
            feito.append("Resumo enviado para a impressora.")
        if self._backup_ao_fechar():
            # Preferências › Backup: "Fazer backup automático ao fechar o expediente"
            try:
                feito.append(f"Backup: {backup.fazer_backup()}")
            except backup.ErroBackup as erro:
                feito.append(f"O backup NÃO foi feito: {erro}")
        texto = "\n".join(feito) if feito else "Nada foi salvo nem impresso."
        QMessageBox.information(self, "Expediente fechado",
                                f"Expediente de {self.relatorio.dia.strftime('%d/%m/%Y')} fechado.\n\n"
                                f"Total do dia: {formatar_reais(self.relatorio.total)}\n\n{texto}")


    def _backup_ao_fechar(self):
        """Backup automático ligado? (nunca no modo treinamento: lá nada é de verdade)"""
        cfg = getattr(self.pai, "config", None)
        opcoes = getattr(cfg, "backup", None) or {}
        return bool(opcoes.get("ao_fechar_expediente")) and not treino.ativo()


class DialogoFechamento(QDialog):
    """Mostra o resumo do dia (como sai na notinha) e as opções de imprimir e salvar."""

    def __init__(self, pai, relatorio, nome_loja):
        super().__init__(pai)
        self.setWindowTitle("Fechar expediente")
        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(10)
        coluna.addWidget(_rotulo(f"Resumo de {rel.data_por_extenso(relatorio.dia)}", "servicoAtual"))

        resumo = QPlainTextEdit(notas.texto_da_nota(rel.linhas_resumo(relatorio, nome_loja, 48)))
        resumo.setReadOnly(True)
        # Letras de mesma largura (como na impressora), para os valores ficarem alinhados.
        resumo.setStyleSheet("font-family: Consolas, 'Courier New'; font-size: 13px;")
        # Do tamanho do resumo (48 letras de largura e todas as linhas), sem passar da tela.
        resumo.ensurePolished()
        metrica = resumo.fontMetrics()
        largura = metrica.horizontalAdvance("M" * 48) + 40
        altura_tela = (pai.screen() if pai else QApplication.primaryScreen()).availableGeometry().height()
        altura = min(metrica.lineSpacing() * (resumo.blockCount() + 1) + 16, int(altura_tela * 0.6))
        resumo.setFixedSize(largura, altura)
        coluna.addWidget(resumo, 0, Qt.AlignHCenter)

        grade = QGridLayout()
        grade.setVerticalSpacing(6)
        grade.addWidget(_rotulo("O que fazer:", "rotulo"), 0, 0)
        self.check_imprimir = QCheckBox("Imprimir o resumo (80mm)")
        grade.addWidget(self.check_imprimir, 1, 0)
        self.check_pdf = QCheckBox("Salvar em PDF")
        self.check_pdf.setChecked(True)
        grade.addWidget(self.check_pdf, 2, 0)
        self.check_excel = QCheckBox("Salvar em Excel")
        self.check_excel.setChecked(True)
        grade.addWidget(self.check_excel, 3, 0)
        pasta = _rotulo(f"Os arquivos vão para a pasta: {rel.pasta_relatorios()}", "rotulo")
        pasta.setWordWrap(True)  # o caminho é comprido: quebra a linha em vez de alargar a janela
        grade.addWidget(pasta, 4, 0)
        if hasattr(pai, "_backup_ao_fechar") and pai._backup_ao_fechar():
            self.lbl_backup = _rotulo("Backup automático ligado: um backup completo (.zip) vai para "
                                      f"{backup.pasta_escolhida()}", "rotulo")
            self.lbl_backup.setWordWrap(True)
            grade.addWidget(self.lbl_backup, 5, 0)
        coluna.addLayout(grade)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        botoes.addWidget(cancelar)
        confirmar = QPushButton("Fechar expediente")
        confirmar.setObjectName("finalizar")
        confirmar.clicked.connect(self.accept)
        botoes.addWidget(confirmar)
        coluna.addLayout(botoes)
        for botao in (cancelar, confirmar):
            botao.setAutoDefault(False)


class DialogoPrevia(QDialog):
    """
    Pré-visualização do relatório A4: mostra todas as páginas antes de imprimir.
    A prévia é desenhada num "papel virtual" (PDF), então abrir esta tela nunca
    imprime nada; só o botão Imprimir manda para a impressora escolhida.
    """

    def __init__(self, pai, relatorio, nome_loja, impressora, nome_para_mostrar, paisagem):
        super().__init__(pai)
        self.setWindowTitle("Pré-visualização do relatório" + (" - TREINAMENTO (sem valor)" if relatorio.treino else ""))
        self.relatorio, self.nome_loja, self.impressora = relatorio, nome_loja, impressora
        self.impresso = False

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(12, 10, 12, 12)
        coluna.setSpacing(8)

        barra = QHBoxLayout()
        barra.setSpacing(8)
        self.combo_visao = QComboBox()
        self.combo_visao.addItem("Todas as páginas", QPrintPreviewWidget.AllPagesView)
        self.combo_visao.addItem("Uma página por vez", QPrintPreviewWidget.SinglePageView)
        self.combo_visao.currentIndexChanged.connect(self._mudar_visao)
        barra.addWidget(self.combo_visao)
        for texto, dica, acao in (("−", "Diminuir", lambda: self.previa.zoomOut()),
                                  ("+", "Aumentar", lambda: self.previa.zoomIn()),
                                  ("Ajustar", "Página inteira na tela", lambda: self.previa.fitInView())):
            botao = QPushButton(texto)
            botao.setToolTip(dica)
            botao.clicked.connect(acao)
            barra.addWidget(botao)
        self.radio_retrato = QRadioButton("Retrato")
        self.radio_paisagem = QRadioButton("Paisagem")
        grupo = QButtonGroup(self)
        grupo.addButton(self.radio_retrato)
        grupo.addButton(self.radio_paisagem)
        (self.radio_paisagem if paisagem else self.radio_retrato).setChecked(True)
        self.radio_paisagem.toggled.connect(self._mudar_orientacao)
        barra.addSpacing(12)
        barra.addWidget(self.radio_retrato)
        barra.addWidget(self.radio_paisagem)
        barra.addStretch(1)
        self.lbl_paginas = _rotulo("", "rotulo")
        barra.addWidget(self.lbl_paginas)
        coluna.addLayout(barra)

        # Papel virtual (PDF) só para desenhar a prévia: nunca vai para a impressora.
        self.papel = QPrinter(QPrinter.HighResolution)
        self.papel.setOutputFormat(QPrinter.PdfFormat)
        self.papel.setPageLayout(relatorio_a4.layout_da_pagina(paisagem))
        self.previa = QPrintPreviewWidget(self.papel)
        self.previa.paintRequested.connect(self._desenhar)
        self.previa.previewChanged.connect(self._contar_paginas)
        self.previa.setViewMode(QPrintPreviewWidget.AllPagesView)
        self.previa.setZoomMode(QPrintPreviewWidget.FitInView)
        coluna.addWidget(self.previa, 1)

        botoes = QHBoxLayout()
        botoes.addWidget(_rotulo(f"Impressora: {nome_para_mostrar}", "rotulo"))
        botoes.addStretch(1)
        cancelar = QPushButton("Fechar")
        cancelar.clicked.connect(self.reject)
        botoes.addWidget(cancelar)
        self.btn_imprimir = QPushButton("Imprimir")
        self.btn_imprimir.setObjectName("finalizar")
        self.btn_imprimir.clicked.connect(self.imprimir)
        botoes.addWidget(self.btn_imprimir)
        coluna.addLayout(botoes)
        for botao in self.findChildren(QPushButton):
            botao.setAutoDefault(False)

        tela = (pai.screen() if pai else QApplication.primaryScreen()).availableGeometry()
        self.resize(min(1100, tela.width() - 60), min(860, tela.height() - 60))

    def paisagem(self):
        return self.radio_paisagem.isChecked()

    def _desenhar(self, papel):
        relatorio_a4.desenhar(papel, self.relatorio, self.nome_loja)

    def _contar_paginas(self):
        total = self.previa.pageCount()
        self.lbl_paginas.setText(f"{total} página" + ("s" if total != 1 else ""))

    def showEvent(self, evento):
        super().showEvent(evento)
        self.previa.fitInView()  # todas as páginas cabendo na janela

    def _mudar_visao(self):
        self.previa.setViewMode(self.combo_visao.currentData())
        self.previa.fitInView()

    def _mudar_orientacao(self):
        self.papel.setPageLayout(relatorio_a4.layout_da_pagina(self.paisagem()))
        self.previa.updatePreview()
        self.previa.fitInView()

    def imprimir(self):
        try:
            relatorio_a4.imprimir(self.relatorio, self.nome_loja, self.impressora, self.paisagem())
        except Exception as erro:
            QMessageBox.warning(self, "Erro ao imprimir", f"Não foi possível imprimir o relatório:\n{erro}")
            return
        self.impresso = True
        self.accept()
