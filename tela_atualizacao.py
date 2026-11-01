"""
tela_atualizacao.py - Janela "Nova versão disponível".

Mostra as notas da versão nova (do GitHub) e os botões "Atualizar agora" e "Depois".
Regras:
  - nunca atualiza sem a pessoa apertar "Atualizar agora";
  - nunca no meio de um atendimento (com item na tela, pede para terminar antes);
  - baixa, confere o SHA-256, faz backup do banco e da versão atual e só então
    entrega para o atualizador separado (atualizacao.py explica o caminho todo).
"""

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

import atualizacao
import versao
from config import recurso


def _rotulo(texto="", nome=None):
    rotulo = QLabel(texto)
    if nome:
        rotulo.setObjectName(nome)
    rotulo.setWordWrap(True)
    return rotulo


class DialogoAtualizacao(QDialog):
    """
    pai        = a janela principal (para saber se tem atendimento em andamento e fechar no fim);
    lancamento = atualizacao.Lancamento com a versão nova.
    """

    def __init__(self, pai, lancamento):
        super().__init__(pai)
        self.pai, self.lancamento = pai, lancamento
        self.setWindowTitle("Atualização disponível")
        self._estado = {}        # o download (em segundo plano) escreve aqui; o relógio lê
        self._cancelar = False
        self.atualizou = False

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(22, 18, 22, 16)
        coluna.setSpacing(10)
        topo = QHBoxLayout()
        topo.setSpacing(14)
        logo = QLabel()
        imagem = QPixmap(recurso("easyserv.png"))
        if not imagem.isNull():
            logo.setPixmap(imagem.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        topo.addWidget(logo, 0, Qt.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(_rotulo(f"{versao.NOME_PROGRAMA} {lancamento.versao} está disponível", "servicoAtual"))
        textos.addWidget(_rotulo(f"Você está usando a versão {versao.VERSAO}. Seus dados (atendimentos, "
                                 "configurações, layouts, temas e notas) não são alterados.", "rotulo"))
        topo.addLayout(textos, 1)
        coluna.addLayout(topo)

        coluna.addWidget(_rotulo("O que mudou nesta versão", "grupo"))
        self.notas = QTextBrowser()
        self.notas.setOpenExternalLinks(True)
        self.notas.setMarkdown(lancamento.notas or "Sem notas para esta versão.")
        coluna.addWidget(self.notas, 1)

        self.lbl_situacao = _rotulo("", "rotulo")
        self.lbl_situacao.hide()
        coluna.addWidget(self.lbl_situacao)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(8)
        self.barra.hide()
        coluna.addWidget(self.barra)

        botoes = QHBoxLayout()
        botoes.addStretch(1)
        self.btn_depois = QPushButton("Depois")
        self.btn_depois.clicked.connect(self.reject)
        botoes.addWidget(self.btn_depois)
        self.btn_atualizar = QPushButton("Atualizar agora")
        self.btn_atualizar.setObjectName("finalizar")
        self.btn_atualizar.clicked.connect(self.atualizar)
        botoes.addWidget(self.btn_atualizar)
        coluna.addLayout(botoes)
        for botao in (self.btn_depois, self.btn_atualizar):
            botao.setAutoDefault(False)

        self.relogio = QTimer(self)
        self.relogio.setInterval(100)
        self.relogio.timeout.connect(self._acompanhar)
        self.resize(560, 520)

    # ------------------------------------------------------------------

    def _situacao(self, texto):
        self.lbl_situacao.setText(texto)
        self.lbl_situacao.show()

    def atualizar(self):
        if getattr(self.pai, "carrinho", None):
            QMessageBox.information(self, "Atualização",
                                    "Tem um atendimento em andamento. Finalize ou cancele o atendimento e "
                                    "depois use Ajuda › Procurar atualizações.")
            return
        self.btn_atualizar.setEnabled(False)
        self.btn_depois.setText("Cancelar")
        self.barra.setRange(0, 0)
        self.barra.show()
        self._situacao("Baixando a atualização...")
        self._estado = {"baixados": 0, "total": self.lancamento.tamanho}
        threading.Thread(target=self._baixar, daemon=True).start()
        self.relogio.start()

    def _baixar(self):
        """Roda em segundo plano: baixa e confere. Não mexe na tela (só no _estado)."""
        estado = self._estado
        try:
            sha = atualizacao.sha256_publicado(self.lancamento)
            if not sha:
                estado["erro"] = ("Esta versão foi publicada sem o código de conferência (SHA-256), "
                                  "então ela não será instalada por segurança.")
                return

            def progresso(baixados, total):
                estado["baixados"], estado["total"] = baixados, total

            caminho = atualizacao.baixar(self.lancamento, progresso, lambda: self._cancelar)
            estado["conferindo"] = True
            if not atualizacao.conferir(caminho, sha):
                estado["erro"] = ("O arquivo baixado não passou na conferência de segurança (SHA-256) e foi "
                                  "apagado. Nada foi instalado.")
                return
            estado["pronto"] = (caminho, sha)
        except atualizacao.Cancelado:
            estado["cancelado"] = True
        except Exception as erro:  # sem internet no meio do download, disco cheio...
            estado["erro"] = f"Não foi possível baixar a atualização:\n{erro}"

    def _acompanhar(self):
        estado = self._estado
        total = estado.get("total") or 0
        if total:
            self.barra.setRange(0, 1000)
            self.barra.setValue(int(1000 * estado.get("baixados", 0) / total))
            self._situacao(f"Baixando a atualização... {estado.get('baixados', 0) / 1048576:.1f} de "
                           f"{total / 1048576:.1f} MB")
        if estado.get("conferindo"):
            self._situacao("Conferindo o arquivo (SHA-256)...")
        if "erro" in estado or estado.get("cancelado"):
            self.relogio.stop()
            if "erro" in estado:
                QMessageBox.warning(self, "Atualização", estado["erro"] + "\n\nO EasyServ continua funcionando "
                                    "normalmente na versão atual.")
            self.reject()
        elif "pronto" in estado:
            self.relogio.stop()
            self._instalar(*estado["pronto"])

    def _instalar(self, caminho, sha):
        self._situacao("Fazendo backup do banco e da versão atual...")
        self.barra.setRange(0, 0)
        QApplication.processEvents()
        try:
            atualizacao.fazer_backups()
        except Exception as erro:
            QMessageBox.warning(self, "Atualização", f"Não foi possível fazer o backup, então a atualização "
                                f"não foi instalada:\n{erro}")
            self.reject()
            return
        try:
            atualizacao.iniciar_atualizador(caminho, sha)
        except Exception as erro:
            QMessageBox.warning(self, "Atualização", f"Não foi possível iniciar o atualizador:\n{erro}")
            self.reject()
            return
        self.atualizou = True
        QMessageBox.information(self, "Atualização",
                                "Tudo pronto. O EasyServ vai fechar, instalar a versão nova e abrir de novo "
                                "sozinho em alguns segundos.")
        self.accept()
        if self.pai is not None:
            self.pai.close()
        QApplication.instance().quit()

    def reject(self):
        if self.relogio.isActive():  # "Cancelar" durante o download
            self._cancelar = True
            self._situacao("Cancelando...")
            return
        super().reject()
