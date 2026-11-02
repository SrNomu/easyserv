"""
tela_limpar.py - Tela "Limpar dados" (menu Arquivo › Limpar dados...).

Apaga atendimentos do banco: todos, ou só os de um período (de tal data a tal data).
Para não apagar sem querer:
  - é preciso digitar a palavra LIMPAR para o botão funcionar;
  - antes de apagar, uma cópia do banco é salva em backups/ com data e hora no nome.
    Se a cópia falhar, nada é apagado.

Só apaga atendimentos. Configurações (preços), cores, temas, layouts, atalhos e
as notas já salvas em .txt continuam como estão.
No modo treinamento, a limpeza vale para o banco do treino.
"""

import os

from PySide6.QtCore import QDate, QLocale
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

import banco
import treino

PALAVRA = "LIMPAR"


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    return rotulo


def _campo_data():
    campo = QDateEdit(QDate.currentDate())
    campo.setCalendarPopup(True)  # a setinha abre um calendário
    campo.setDisplayFormat("dd/MM/yyyy")
    portugues = QLocale(QLocale.Portuguese, QLocale.Brazil)
    campo.setLocale(portugues)
    campo.calendarWidget().setLocale(portugues)
    campo.setMinimumWidth(130)
    return campo


class TelaLimpar(QDialog):
    """pai = a janela principal; ao_limpar = função chamada (sem argumentos) depois de apagar."""

    def __init__(self, pai, ao_limpar=None):
        super().__init__(pai)
        self.setWindowTitle("Limpar dados")
        self.ao_limpar = ao_limpar

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 16)
        coluna.setSpacing(12)

        if treino.ativo():
            qual = "o banco do TREINAMENTO (treino.db). O caixa de verdade não é tocado."
        else:
            qual = f"o banco do caixa de verdade ({os.path.basename(banco.ARQUIVO_BANCO)})."
        coluna.addWidget(_rotulo(f"Apaga atendimentos d{qual}"))

        # --- O que apagar ---
        caixa = QGroupBox("O que apagar")
        coluna_caixa = QVBoxLayout(caixa)
        self.grupo = QButtonGroup(self)
        self.radio_tudo = QRadioButton("Todos os atendimentos")
        self.radio_periodo = QRadioButton("Só um período:")
        self.radio_periodo.setChecked(True)  # o mais seguro já vem escolhido
        for radio in (self.radio_tudo, self.radio_periodo):
            self.grupo.addButton(radio)
            radio.toggled.connect(self._atualizar)
        coluna_caixa.addWidget(self.radio_tudo)
        linha_periodo = QHBoxLayout()
        linha_periodo.addWidget(self.radio_periodo)
        linha_periodo.addWidget(_rotulo("de"))
        self.campo_inicio = _campo_data()
        linha_periodo.addWidget(self.campo_inicio)
        linha_periodo.addWidget(_rotulo("até"))
        self.campo_fim = _campo_data()
        linha_periodo.addWidget(self.campo_fim)
        linha_periodo.addStretch(1)
        coluna_caixa.addLayout(linha_periodo)
        for campo in (self.campo_inicio, self.campo_fim):
            campo.dateChanged.connect(self._atualizar)
        self.lbl_quantos = _rotulo("", "servicoAtual")
        coluna_caixa.addWidget(self.lbl_quantos)
        coluna.addWidget(caixa)

        explicacao = _rotulo(
            "Antes de apagar, uma cópia de segurança do banco é salva na pasta backups/ (com a data e a "
            "hora no nome).\nNão são apagados: preços e configurações, cores e temas, layouts, atalhos e "
            "as notas já salvas.\nA numeração dos atendimentos continua de onde parou.", "rotulo")
        explicacao.setWordWrap(True)
        coluna.addWidget(explicacao)

        # --- Confirmação ---
        coluna.addWidget(_rotulo(f"Para confirmar, digite a palavra {PALAVRA} no campo abaixo:"))
        self.campo_confirmar = QLineEdit()
        self.campo_confirmar.setPlaceholderText(PALAVRA)
        self.campo_confirmar.textChanged.connect(self._atualizar)
        coluna.addWidget(self.campo_confirmar)
        # Texto de ajuda SEMPRE visível (a dica apagada dentro do campo some ao digitar).
        self.lbl_ajuda_confirmar = _rotulo("", "rotulo")
        self.lbl_ajuda_confirmar.setWordWrap(True)
        coluna.addWidget(self.lbl_ajuda_confirmar)
        self.lbl_aviso = _rotulo("", "aviso")
        self.lbl_aviso.setWordWrap(True)
        coluna.addWidget(self.lbl_aviso)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        btn_cancelar = QPushButton("Cancelar  Esc")
        btn_cancelar.clicked.connect(self.reject)
        botoes.addWidget(btn_cancelar)
        self.btn_apagar = QPushButton("Fazer backup e apagar")
        self.btn_apagar.setObjectName("perigo")
        self.btn_apagar.clicked.connect(self.apagar)
        botoes.addWidget(self.btn_apagar)
        coluna.addLayout(botoes)
        for botao in (btn_cancelar, self.btn_apagar):
            botao.setAutoDefault(False)  # Enter no campo não apaga sozinho

        self.setMinimumWidth(560)
        self._atualizar()
        self.campo_confirmar.setFocus()

    def periodo(self):
        """(inicio, fim) como datetime.date, ou (None, None) para "todos"."""
        if self.radio_tudo.isChecked():
            return None, None
        inicio, fim = self.campo_inicio.date().toPython(), self.campo_fim.date().toPython()
        return min(inicio, fim), max(inicio, fim)  # (se a pessoa inverter as datas, tudo bem)

    def _atualizar(self, *_args):
        periodo = self.radio_periodo.isChecked()
        self.campo_inicio.setEnabled(periodo)
        self.campo_fim.setEnabled(periodo)
        inicio, fim = self.periodo()
        self.quantidade = banco.contar_atendimentos(inicio, fim)
        total = banco.contar_atendimentos()
        if self.quantidade == 0:
            self.lbl_quantos.setText("Nenhum atendimento para apagar" + (" nesse período." if periodo else "."))
        else:
            plural = "s" if self.quantidade != 1 else ""
            self.lbl_quantos.setText(f"Serão apagados {self.quantidade} atendimento{plural} (de {total} no banco).")
        digitou = self.campo_confirmar.text().strip().upper() == PALAVRA
        self.btn_apagar.setEnabled(digitou and self.quantidade > 0)
        if not digitou:
            self.lbl_ajuda_confirmar.setText(f"O botão \"Fazer backup e apagar\" só é liberado depois que você "
                                             f"digitar {PALAVRA} (com todas as letras) no campo acima.")
        elif self.quantidade == 0:
            self.lbl_ajuda_confirmar.setText("Palavra certa, mas não há atendimentos para apagar.")
        else:
            self.lbl_ajuda_confirmar.setText("Pronto: o botão \"Fazer backup e apagar\" está liberado.")

    def apagar(self):
        if self.campo_confirmar.text().strip().upper() != PALAVRA or self.quantidade == 0:
            return
        # 1) Cópia de segurança. Se não der certo, para por aqui (nada é apagado).
        try:
            copia = banco.fazer_backup()
        except Exception as erro:  # (disco cheio, pasta sem permissão...)
            self.lbl_aviso.setText(f"Não foi possível fazer a cópia de segurança, por isso nada foi apagado: {erro}")
            return
        # 2) Apaga.
        inicio, fim = self.periodo()
        try:
            apagados = banco.apagar_atendimentos(inicio, fim)
        except Exception as erro:
            self.lbl_aviso.setText(f"Erro ao apagar (o banco ficou como estava): {erro}")
            return
        if self.ao_limpar:
            self.ao_limpar()
        plural = "s" if apagados != 1 else ""
        QMessageBox.information(self, "Limpar dados",
                                f"{apagados} atendimento{plural} apagado{plural}.\n\n"
                                f"Cópia de segurança salva em:\n{copia}\n\n"
                                "Para desfazer, feche o programa e troque o arquivo "
                                f"{os.path.basename(banco.arquivo_banco())} por essa cópia "
                                "(renomeando-a para o mesmo nome).")
        self.accept()
