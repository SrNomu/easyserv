"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, sqlite3
pasta, saida = sys.argv[1], sys.argv[2]
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QLabel, QPushButton, QLineEdit, QDockWidget
from PySide6.QtTest import QTest
import estilo, banco, interface
msgs = []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
QMessageBox.question = staticmethod(lambda *a: QMessageBox.Yes)
def ok(c, m): print(("OK    " if c else "FALHA ") + m)

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()
j = interface.JanelaPrincipal(); j.mostrar()
for _ in range(20): QTest.qWait(50)
j.activateWindow(); QTest.qWait(200)

def botao(t): return [b for b in j.teclado.findChildren(QPushButton) if b.text() == t][0]
def clicar(t): QTest.mouseClick(botao(t), Qt.LeftButton); QTest.qWait(30)
def tecla(k, w=None): QTest.keyClick(w or app.focusWidget() or j, k); QTest.qWait(30)

def cortados(rotulo):
    ruins = []
    for w in j.findChildren(QLabel) + j.findChildren(QPushButton):
        if not w.isVisible() or (isinstance(w, QLabel) and w.wordWrap()): continue
        if w.width() + 1 < w.minimumSizeHint().width() or w.height() + 1 < w.minimumSizeHint().height():
            ruins.append(f"{type(w).__name__} '{w.text()[:30]}' {w.width()}x{w.height()} < {w.minimumSizeHint().width()}x{w.minimumSizeHint().height()}")
    ok(not ruins, f"nada cortado ({rotulo})" + ("" if not ruins else ": " + "; ".join(ruins[:6])))

ok(all(p.isVisible() for p in j.paineis.values()), "todos os 7 painéis visíveis")
cortados(f"janela {j.width()}x{j.height()}")

# --- teclado na tela + foco
j._focar(j.tabela); clicar("1")
ok(j.servico_atual and j.servico_atual.nome == "Xerox", "tecla 1 da tela sem campo -> Xerox")
ok(app.focusWidget() is j.entry_item, "foco no campo de quantidade")
clicar("3"); ok(j.entry_item.text() == "3", f"3 substitui o '1' selecionado -> {j.entry_item.text()!r}")
ok(app.focusWidget() is j.entry_item, "clicar no teclado não tirou o foco")
clicar("↵"); ok(len(j.carrinho) == 1 and j.carrinho[0]["quantidade"] == 3, "Enter da tela adicionou 3 xerox")
# teclado físico: tecla 0 com foco na tabela -> boletos
tecla(Qt.Key_0, j.tabela); ok(j.servico_atual.nome == "Pagamento de boletos", "tecla física 0 -> Pagamento de boletos")
ok(j.lbl_campo_item.text() == "Quantidade" and j.entry_item.text() == "1", "boleto agora pede quantidade (não valor)")
clicar("2"); clicar("5")
clicar("⌫"); ok(j.entry_item.text() == "2", "⌫ apaga")
ok(j.lbl_previa.text() == "= R$ 4,00", f"prévia 2 boletos {j.lbl_previa.text()!r}")
tecla(Qt.Key_Return, j.entry_item); ok(len(j.carrinho) == 2, "Enter físico adicionou os boletos")
# Esc no campo do item desiste
tecla(Qt.Key_9, j.tabela); tecla(Qt.Key_Escape, j.entry_item)
ok(j.servico_atual is None and len(j.carrinho) == 2, "Esc no campo do item só desiste do item")
# F-keys
tecla(Qt.Key_F7); ok(j.forma_escolhida() == "Débito", "F7 -> Débito")
ok(j.lbl_total.text() == "R$ 5,58", f"débito: 5% só sobre o xerox: {j.lbl_total.text()} (5,50 + 0,08)")
ok(j.lbl_taxa_rotulo.text() == "Taxa maquininha (5% sobre R$ 1,50)", f"rótulo da taxa {j.lbl_taxa_rotulo.text()!r}")
ok(not j.entry_recebido.isEnabled(), "valor recebido desativado no débito")
tecla(Qt.Key_F4); ok(j.forma_escolhida() == "Dinheiro" and app.focusWidget() is j.entry_recebido, "F4 -> dinheiro e cursor no valor recebido")
clicar("1"); clicar("00"); ok(j.lbl_troco.text() == "Troco: R$ 94,50", f"troco {j.lbl_troco.text()!r}")
clicar("↵"); ok(app.focusWidget() is j.btn_finalizar, "Enter no valor recebido -> botão Finalizar")
tecla(Qt.Key_F3); 
for t in "21987654321": clicar(t)
ok(j.entry_telefone.text() == "(21) 98765-4321", f"telefone {j.entry_telefone.text()!r}")
tecla(Qt.Key_F2); clicar("5"); ok(j.entry_nome.text() == "" and j.servico_atual is None, "no Nome o teclado da tela não faz nada")
QTest.keyClicks(j.entry_nome, "Maria da Silva")
tecla(Qt.Key_F9); ok(not j.paineis["teclado"].isVisible() and j.btn_teclado.text().startswith("Mostrar"), "F9 esconde o teclado")
tecla(Qt.Key_F9); ok(j.paineis["teclado"].isVisible(), "F9 mostra de novo")

# print do depois (com itens, como no antes)
j.selecionar_servico(8); j.entry_item.setText("20"); QTest.qWait(300)
j.grab().save(os.path.join(saida, "print_depois.png"))
cortados("com dados")

# janela menor
j.showNormal(); j.resize(1280, 720); QTest.qWait(400)
j.grab().save(os.path.join(saida, "print_1280.png"))
cortados(f"janela {j.width()}x{j.height()}")
j.showMaximized(); QTest.qWait(300)

# finalizar
j._limpar_selecao_servico(); tecla(Qt.Key_F12)
ok(msgs and msgs[-1][1] == "Atendimento finalizado", "F12 finalizou")
print("      ", msgs[-1][2].replace("\n", " | ")[:150])
c = sqlite3.connect(banco.ARQUIVO_BANCO)
print("       banco:", c.execute("select forma_pagamento, subtotal_centavos, total_centavos, recebido_centavos, troco_centavos, cliente_nome, cliente_telefone from atendimentos").fetchall())
ok(j.carrinho == [] and j.pilha_atendimento.currentIndex() == 0, "tela limpa e aviso 'Nenhum item ainda'")

# Enter num botão
j._focar(j.btn_finalizar); tecla(Qt.Key_Return, j.btn_finalizar); QTest.qWait(300)
ok(msgs[-1][2].startswith("Adicione pelo menos"), "Enter no botão Finalizar aperta o botão")

# layout: desgrudar teclado, travar, fechar e reabrir
j.paineis["teclado"].setFloating(True); QTest.qWait(200)
j.acao_travar.setChecked(True)
ok(j.paineis["servicos"].features() == QDockWidget.NoDockWidgetFeatures, "Travar layout tira mover/desgrudar/fechar")
# teclado flutuando ainda digita no campo
j.selecionar_servico(0); clicar("7"); ok(j.entry_item.text() == "7", "teclado flutuando digita no campo")
j.close(); QTest.qWait(200)
j2 = interface.JanelaPrincipal(); j2.mostrar(); QTest.qWait(500)
ok(j2._restaurado, "layout salvo foi restaurado")
ok(j2.paineis["teclado"].isFloating(), "teclado continua desgrudado")
ok(j2.acao_travar.isChecked(), "continua travado")
j2.restaurar_layout_padrao(); QTest.qWait(300)
ok(not j2.paineis["teclado"].isFloating() and all(p.isVisible() for p in j2.paineis.values()), "Restaurar layout padrão encaixa tudo de volta")
j2.acao_travar.setChecked(False); j2.close()

# --- tela Configurar notinhas
import tela_notinhas, json
j3 = interface.JanelaPrincipal(); j3.mostrar(); QTest.qWait(300)
salvos = []
t = tela_notinhas.TelaNotinhas(j3, ao_salvar=salvos.append); t.show(); QTest.qWait(600)
ok(t.lbl_imagem.pixmap() is not None and not t.lbl_imagem.pixmap().isNull(), "pré-visualização desenhada")
t.radios_modelo["cliente"].setChecked(True); QTest.qWait(50)
t.campo_endereco.setText("Rua das Flores, 123"); t.checks_mostrar["quantidade"].setChecked(False)
t.radios_papel["58mm"].setChecked(True); t.spin_fonte.setValue(8); QTest.qWait(400)
ok(t.dados["cliente"]["endereco"] == "Rua das Flores, 123" and t.dados["cliente"]["papel"] == "58mm"
   and t.dados["loja"]["papel"] == "80mm", "edita só o modelo do cliente")
ok("58mm" in t.lbl_info_previa.text(), f"info: {t.lbl_info_previa.text()}")
t.grab().save(os.path.join(saida, "print_notinhas.png"))
t.salvar(); ok(json.load(open("layout_notas.json", encoding="utf-8"))["cliente"]["papel"] == "58mm" and salvos, "salvou layout_notas.json e avisou a janela")
t.reject(); ok(not t.isVisible(), "fechou sem perguntar (nada pendente)")
j3.close()
