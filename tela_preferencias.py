"""
tela_preferencias.py - Tela "Preferências" (menu Arquivo › Preferências...).

Junta as configurações gerais do programa, em abas:
  Loja        -> nome, endereço, telefone, CNPJ e logo (valem para o programa inteiro);
  Atendimento -> "Pedir o valor do boleto/recarga" e "Mostrar repasses no relatório";
  Privacidade -> "Guardar dados do cliente" (nome e telefone):
       - Não guardar: servem só para imprimir a nota do cliente na hora;
       - Apagar automaticamente depois de X dias (padrão: 30): o apagamento roda
         quando o programa abre e apaga só o nome e o telefone;
       - Guardar sempre.
  Aparência   -> modo de cor (claro, escuro ou seguir o Windows) e modo tablet;
  Backup      -> a pasta dos backups e o backup automático ao fechar o expediente.

As opções de Loja, Atendimento, Privacidade e Backup ficam no config.json ("loja",
"atendimento", "dados_cliente" e "backup"; o resto do arquivo não muda). As de Aparência ficam nas
preferências da tela (preferencias.json), como no menu Exibir.
"""

import json
import os

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import backup
import banco
import config
import estilo
from tela_loja import FormularioLoja


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    rotulo.setWordWrap(True)
    return rotulo


def _explicacao(texto):
    """Texto pequeno embaixo de uma opção, alinhado com o texto dela."""
    rotulo = _rotulo(texto, "rotulo")
    rotulo.setContentsMargins(26, 0, 0, 6)
    return rotulo


def _aba():
    pagina = QWidget()
    coluna = QVBoxLayout(pagina)
    coluna.setContentsMargins(14, 12, 14, 12)
    coluna.setSpacing(6)
    return pagina, coluna


class TelaPreferencias(QDialog):
    """pai = a janela principal; ao_salvar = função chamada (sem argumentos) depois de gravar."""

    def __init__(self, pai, ao_salvar=None):
        super().__init__(pai)
        self.setWindowTitle("Preferências")
        self.pai = pai
        self.ao_salvar = ao_salvar
        self.config = config.carregar_config()

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(12)
        self.abas = QTabWidget()
        self.abas.addTab(self._aba_loja(), "Loja")
        self.abas.addTab(self._aba_atendimento(), "Atendimento")
        self.abas.addTab(self._aba_privacidade(), "Privacidade")
        self.abas.addTab(self._aba_aparencia(), "Aparência")
        self.abas.addTab(self._aba_backup(), "Backup")
        coluna.addWidget(self.abas, 1)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        botoes.addWidget(cancelar)
        salvar = QPushButton("Salvar")
        salvar.setObjectName("finalizar")
        salvar.clicked.connect(self.salvar)
        botoes.addWidget(salvar)
        coluna.addLayout(botoes)
        for botao in (cancelar, salvar):
            botao.setAutoDefault(False)
        self.setMinimumWidth(600)
        self._atualizar()

    # ------------------------------------------------------------------
    # Abas
    # ------------------------------------------------------------------

    def _aba_loja(self):
        pagina, coluna = _aba()
        coluna.addWidget(_rotulo("Dados da loja", "grupo"))
        coluna.addWidget(_rotulo("Aparecem no título da janela, nas notinhas, no relatório (tela, A4, PDF e "
                                 "Excel), no resumo de fechamento e nas páginas de teste de impressão.", "rotulo"))
        coluna.addSpacing(4)
        self.formulario_loja = FormularioLoja(self.config.loja)
        coluna.addWidget(self.formulario_loja)
        coluna.addStretch(1)
        return pagina

    def _aba_atendimento(self):
        pagina, coluna = _aba()
        atual = self.config.atendimento
        self.check_pedir_valor = QCheckBox("Pedir o valor do boleto/recarga")
        self.check_pedir_valor.setChecked(atual["pedir_valor_terceiros"])
        coluna.addWidget(self.check_pedir_valor)
        coluna.addWidget(_explicacao(
            "O funcionário digita o valor do boleto ou da recarga e o programa soma a taxa do serviço "
            "(ex.: boleto de R$ 200,00 + serviço R$ 2,00 = cobrar R$ 202,00). O troco sai do valor cobrado. "
            "A taxa da maquininha não é calculada sobre esses serviços. Nas notinhas e no relatório aparece "
            "só a taxa do serviço: o valor do boleto fica guardado à parte."))
        terceiros = [s.nome for s in self.config.servicos if s.valor_de_terceiros]
        self.lbl_servicos_terceiros = _explicacao(
            ("Vale para: " + ", ".join(terceiros) + "." if terceiros else "Nenhum serviço marcado.")
            + " Para mudar, use Arquivo › Serviços e preços (\"Cobra valor de terceiros\").")
        coluna.addWidget(self.lbl_servicos_terceiros)
        coluna.addSpacing(6)
        self.check_repasses = QCheckBox("Mostrar repasses no relatório")
        self.check_repasses.setChecked(atual["mostrar_repasses"])
        coluna.addWidget(self.check_repasses)
        coluna.addWidget(_explicacao(
            "O relatório do dia ganha a seção \"Repasses (não é faturamento)\", com o total de boletos e "
            "recargas recebidos por forma de pagamento, para ajudar a conferir a gaveta. Esses valores nunca "
            "entram no total do dia."))
        coluna.addStretch(1)
        return pagina

    def _aba_privacidade(self):
        pagina, coluna = _aba()
        atual = self.config.dados_cliente
        coluna.addWidget(_rotulo("Guardar dados do cliente (nome e telefone)", "grupo"))
        coluna.addWidget(_rotulo("O nome e o telefone nunca aparecem no relatório do dia, no PDF, no Excel "
                                 "nem no resumo de fechamento. Aqui você escolhe se eles ficam guardados no "
                                 "banco do programa.", "rotulo"))
        self.grupo = QButtonGroup(self)
        self.radios = {}
        explicacoes = {
            "nao": "Servem só para imprimir a nota do cliente na hora. Não vão para o banco.",
            "apagar": "Ficam guardados e são apagados sozinhos quando o programa abre. "
                      "Só o nome e o telefone saem: o atendimento e os valores continuam.",
            "sempre": "Ficam guardados no banco (e na nota da loja, se ela estiver marcada para mostrar).",
        }
        for chave in config.GUARDAR_DADOS_CLIENTE:
            texto = "Apagar automaticamente depois de" if chave == "apagar" else config.GUARDAR_DADOS_CLIENTE[chave]
            radio = QRadioButton(texto)
            radio.setChecked(chave == atual["guardar"])
            radio.toggled.connect(self._atualizar)
            self.grupo.addButton(radio)
            self.radios[chave] = radio
            if chave == "apagar":
                linha = QHBoxLayout()
                linha.addWidget(radio)
                self.campo_dias = QSpinBox()
                self.campo_dias.setRange(config.DIAS_MINIMO, config.DIAS_MAXIMO)
                self.campo_dias.setValue(atual["dias"])
                self.campo_dias.setSuffix(" dias")
                self.campo_dias.setMinimumWidth(110)
                linha.addWidget(self.campo_dias)
                linha.addStretch(1)
                coluna.addLayout(linha)
            else:
                coluna.addWidget(radio)
            coluna.addWidget(_explicacao(explicacoes[chave]))
        self.check_apagar_agora = QCheckBox("Apagar também os nomes e telefones que já estão guardados")
        coluna.addWidget(self.check_apagar_agora)
        coluna.addStretch(1)
        return pagina

    def _aba_aparencia(self):
        pagina, coluna = _aba()
        preferencias = getattr(self.pai, "preferencias", {}) or {}
        coluna.addWidget(_rotulo("Modo de cor", "grupo"))
        self.grupo_cor = QButtonGroup(self)
        self.radios_cor = {}
        for modo, texto in estilo.MODOS.items():
            radio = QRadioButton(texto)
            radio.setChecked(modo == preferencias.get("modo_cor", "sistema"))
            self.grupo_cor.addButton(radio)
            self.radios_cor[modo] = radio
            coluna.addWidget(radio)
        coluna.addWidget(_explicacao("As cores de cada modo ficam em Exibir › Cores do programa."))
        coluna.addSpacing(6)
        self.check_tablet = QCheckBox("Modo tablet")
        self.check_tablet.setChecked(bool(getattr(self.pai, "modo_tablet", False)))
        coluna.addWidget(self.check_tablet)
        coluna.addWidget(_explicacao("Tudo maior, para usar com o dedo: usa o layout Touch e abre o teclado "
                                     "do Windows ao tocar no campo Nome."))
        coluna.addStretch(1)
        return pagina

    def _aba_backup(self):
        pagina, coluna = _aba()
        atual = self.config.backup
        coluna.addWidget(_rotulo("Pasta dos backups", "grupo"))
        self._pasta_backup = atual["pasta"]
        self.lbl_pasta_backup = _rotulo("", None)
        coluna.addWidget(self.lbl_pasta_backup)
        linha = QHBoxLayout()
        self.btn_pasta_backup = QPushButton("Escolher pasta...")
        self.btn_pasta_backup.clicked.connect(self.escolher_pasta_backup)
        linha.addWidget(self.btn_pasta_backup)
        self.btn_pasta_padrao = QPushButton("Usar a pasta padrão")
        self.btn_pasta_padrao.clicked.connect(lambda: self._definir_pasta_backup(""))
        linha.addWidget(self.btn_pasta_padrao)
        linha.addStretch(1)
        coluna.addLayout(linha)
        coluna.addWidget(_rotulo("Dica: escolha um pendrive ou uma pasta do Google Drive ou do OneDrive, para "
                                 "os dados não ficarem só neste computador.", "rotulo"))
        coluna.addSpacing(8)
        self.check_backup_fechar = QCheckBox("Fazer backup automático ao fechar o expediente")
        self.check_backup_fechar.setChecked(atual["ao_fechar_expediente"])
        coluna.addWidget(self.check_backup_fechar)
        coluna.addWidget(_explicacao("Em Relatório do dia › Fechar expediente, o programa salva um backup "
                                     "completo (.zip) nesta pasta, além do PDF e do Excel."))
        for botao in (self.btn_pasta_backup, self.btn_pasta_padrao):
            botao.setAutoDefault(False)
        coluna.addStretch(1)
        self._definir_pasta_backup(self._pasta_backup)
        return pagina

    def _definir_pasta_backup(self, pasta):
        self._pasta_backup = pasta
        self.lbl_pasta_backup.setText(pasta or f"{backup.pasta_padrao()}  (padrão)")
        self.btn_pasta_padrao.setEnabled(bool(pasta))

    def escolher_pasta_backup(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta dos backups",
                                                 self._pasta_backup or backup.pasta_padrao())
        if pasta:
            self._definir_pasta_backup(os.path.normpath(pasta))

    # ------------------------------------------------------------------

    def escolha(self):
        return next(chave for chave, radio in self.radios.items() if radio.isChecked())

    def modo_cor(self):
        return next(modo for modo, radio in self.radios_cor.items() if radio.isChecked())

    def _atualizar(self, *_args):
        escolha = self.escolha()
        self.campo_dias.setEnabled(escolha == "apagar")
        # "Já guardados": no "Não guardar" apaga todos; no "Apagar depois de X dias", os mais antigos.
        self.check_apagar_agora.setVisible(escolha != "sempre")
        self.check_apagar_agora.setText(
            "Apagar também os nomes e telefones que já estão guardados" if escolha == "nao"
            else "Apagar agora os que já passaram do prazo (sem esperar o programa abrir de novo)")

    def salvar(self):
        erro_loja = self.formulario_loja.erro()
        if erro_loja:
            self.abas.setCurrentIndex(0)
            QMessageBox.warning(self, "Preferências", erro_loja)
            self.formulario_loja.campo_nome.setFocus()
            return
        escolha, dias = self.escolha(), self.campo_dias.value()
        try:
            with open(config.ARQUIVO_CONFIG, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            dados["loja"] = config.conferir_loja(self.formulario_loja.valores())
            dados["nome_loja"] = dados["loja"]["nome"]
            dados["loja_confirmada"] = True
            dados["backup"] = {"pasta": self._pasta_backup,
                               "ao_fechar_expediente": self.check_backup_fechar.isChecked()}
            dados["dados_cliente"] = {"guardar": escolha, "dias": dias}
            dados["atendimento"] = {"pedir_valor_terceiros": self.check_pedir_valor.isChecked(),
                                    "mostrar_repasses": self.check_repasses.isChecked()}
            config.salvar_config(dados)
        except (OSError, json.JSONDecodeError) as erro:
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível gravar o config.json:\n{erro}")
            return
        if self.check_apagar_agora.isChecked() and escolha != "sempre":
            try:
                apagados = banco.apagar_dados_clientes(None if escolha == "nao" else dias)
            except Exception as erro:  # (banco ocupado...): a preferência já foi salva
                QMessageBox.warning(self, "Preferências", f"A opção foi salva, mas não deu para apagar agora:\n{erro}")
            else:
                QMessageBox.information(self, "Preferências",
                                        f"Nome e telefone apagados de {apagados} atendimento(s).")
        # Aparência: usa os mesmos caminhos do menu Exibir (que também salvam as preferências).
        pai = self.pai
        if pai is not None and hasattr(pai, "definir_modo_cor"):
            if self.modo_cor() != pai.preferencias.get("modo_cor"):
                pai.definir_modo_cor(self.modo_cor())
            if self.check_tablet.isChecked() != bool(pai.modo_tablet):
                pai.definir_modo_tablet(self.check_tablet.isChecked())
        if self.ao_salvar:
            self.ao_salvar()
        self.accept()
