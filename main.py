"""
main.py - Ponto de partida do EasyServ. É este arquivo que você executa.

    python main.py

A abertura acontece nesta ordem, com a tela de abertura mostrando cada etapa:
  1. Verificando arquivos...       (programa inteiro? dados de versão antiga para trazer?)
  2. Carregando banco de dados...  (configurações e banco abrem sem erro?)
  3. Procurando atualizações...    (no GitHub; sem internet, segue normal)
  4. Abre a janela principal e, se tiver versão nova, pergunta se quer atualizar.
"""

import ctypes
import sqlite3
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

import atualizacao
import banco
import config
import estilo
import integridade
import migracao
import versao
from tela_abertura import TelaAbertura

LIMITE_ATUALIZACAO = 6  # segundos esperando o GitHub responder na abertura


def identificar_no_windows():
    """
    Faz a barra de tarefas mostrar o ícone do EasyServ (e não o do Python) e cria o
    "mutex" EasyServMutex: é por ele que o instalador sabe que o programa está aberto.
    """
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Pedro.EasyServ")
        ctypes.windll.kernel32.CreateMutexW(None, False, "EasyServMutex")
    except Exception:
        pass


def oferecer_migracao(abertura):
    """Primeira vez com a pasta de dados vazia: oferece trazer os dados da versão antiga."""
    if not migracao.precisa_oferecer():
        return
    achadas = migracao.encontrar_dados_antigos()
    if not achadas:
        return
    abertura.hide()
    if len(achadas) == 1:
        origem = achadas[0]
        resposta = QMessageBox.question(
            None, "Dados da versão antiga",
            f"Encontrei dados da versão antiga do programa em:\n{origem}\n\nCopiar tudo (atendimentos, "
            "configurações, layouts, temas, notas, relatórios e backups) para a pasta nova?\n"
            f"{config.pasta_base()}\n\nA pasta antiga não é apagada.")
        origem = origem if resposta == QMessageBox.Yes else ""
    else:
        origem, escolheu = QInputDialog.getItem(
            None, "Dados da versão antiga", "Encontrei dados antigos em mais de uma pasta.\n"
            "Escolha de qual copiar (a primeira é a mais recente) ou Cancelar para começar do zero:",
            achadas, 0, False)
        origem = origem if escolheu else ""
    if origem:
        try:
            copiados = migracao.migrar(origem)
            QMessageBox.information(None, "Dados da versão antiga",
                                    f"Pronto! Copiado: {', '.join(copiados)}.")
        except OSError as erro:
            QMessageBox.warning(None, "Dados da versão antiga", f"Não foi possível copiar tudo:\n{erro}\n\n"
                                "Dá para tentar de novo em Arquivo › Importar dados de outra pasta.")
    else:
        migracao.marcar_perguntado("não")
    abertura.show()


def avisar_problemas(abertura, problemas):
    abertura.hide()
    QMessageBox.warning(
        None, f"{versao.NOME_PROGRAMA} - verificação",
        "Encontrei problemas nos arquivos:\n\n" + "\n".join(f"• {p}" for p in problemas) +
        "\n\nO programa vai tentar abrir mesmo assim.\n"
        "Se for o programa: reinstale com o instalador (os dados não são apagados).\n"
        f"Se for o banco de dados: há cópias na pasta backups, dentro de\n{config.pasta_base()}")
    abertura.show()


def main():
    identificar_no_windows()
    app = QApplication(sys.argv)  # o "motor" do Qt: precisa existir antes de qualquer janela
    app.setApplicationName(versao.NOME_PROGRAMA)
    app.setApplicationVersion(versao.VERSAO)
    app.setWindowIcon(QIcon(config.recurso("easyserv.ico")))
    estilo.preparar(app)  # estilo base; a janela aplica depois o modo e as cores salvos

    abertura = TelaAbertura()
    abertura.show()
    abertura.etapa("Verificando arquivos...", 8)
    problemas = integridade.verificar_programa()
    oferecer_migracao(abertura)

    abertura.etapa("Carregando banco de dados...", 35)
    problemas += integridade.verificar_dados()
    try:
        banco.criar_tabelas()
    except sqlite3.Error as erro:
        problemas.append(f"Não foi possível abrir o banco de dados: {erro}")
    if problemas:
        avisar_problemas(abertura, problemas)

    abertura.etapa("Procurando atualizações...", 65)
    lancamento = abertura.esperar(atualizacao.consultar, LIMITE_ATUALIZACAO) if versao.REPOSITORIO_GITHUB else None

    abertura.etapa("Abrindo...", 90)
    # (importado só agora: assim a tela de abertura aparece antes de carregar o resto)
    from interface import JanelaPrincipal
    try:
        janela = JanelaPrincipal()
    except config.ErroConfig as erro:
        abertura.close()
        QMessageBox.critical(None, "Erro no config.json", str(erro))
        return 1
    abertura.etapa("Pronto.", 100)
    janela.mostrar()
    abertura.close()
    # Depois que a janela aparecer: pergunta do tablet e da atualização (se tiver).
    QTimer.singleShot(600, lambda: janela.apos_abrir(lancamento))
    return app.exec()  # mantém o programa aberto, esperando cliques e teclas


if __name__ == "__main__":
    sys.exit(main())
