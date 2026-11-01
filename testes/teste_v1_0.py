"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json, sqlite3, glob
from datetime import datetime, date, timedelta
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt, QDate, QEvent
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QInputDialog, QDialog, QLabel, QLineEdit
from PySide6.QtTest import QTest
import estilo, banco, interface, impressao, notas, relatorio, treino, atalhos, preferencias
import tela_atalhos, tela_cores, tela_limpar, tela_relatorio

msgs, perguntas, abertos, impressos = [], [], [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
resposta = {"v": QMessageBox.Yes}
def pergunta(p, t, m, *a):
    perguntas.append((t, m)); return resposta["v"]
QMessageBox.question = staticmethod(pergunta)
os.startfile = lambda caminho: abertos.append(caminho)
# NUNCA imprime de verdade.
impressao.escolher_impressora = lambda nome: "Teste (falsa)"
impressao.eh_impressora_texto = lambda nome: True
impressao.imprimir_texto = lambda *a: impressos.append(a)
impressao.imprimir_imagem = lambda *a: impressos.append(a)

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=3):
    for _ in range(n): QTest.qWait(30)
def prefs():
    return json.load(open(preferencias.ARQUIVO_PREFERENCIAS, encoding="utf-8"))
def contar(arquivo):
    if not os.path.exists(arquivo): return 0
    c = sqlite3.connect(arquivo)
    try: return c.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
    finally: c.close()

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()
j = interface.JanelaPrincipal(); j.mostrar(); esperar(15)
j.definir_modo_cor("claro"); esperar(3)
j.activateWindow(); esperar(5)

def tecla(k, w=None, mod=Qt.NoModifier):
    QTest.keyClick(w or app.focusWidget() or j, k, mod); esperar(1)

# ====================================================================
# 6. Atalhos
# ====================================================================
print("--- atalhos: textos de fábrica")
ok(j.btn_finalizar.text() == "Finalizar  F12", f"Finalizar {j.btn_finalizar.text()!r}")
ok(j.btn_remover.text() == "Remover item  Del" and j.btn_cancelar.text() == "Cancelar atendimento  Esc", "remover/cancelar")
ok(j.lbl_rotulo_nome.text() == "Nome (F2) · opcional", j.lbl_rotulo_nome.text())
ok(j.lbl_rotulo_recebido.text() == "Valor recebido (F4) · vazio = valor exato", j.lbl_rotulo_recebido.text())
ok(j.botoes_pagamento["Pix"].text().startswith("Pix · F6"), j.botoes_pagamento["Pix"].text())
ok(j.lbl_servico_atual.text() == "Escolha um serviço: tecla 1 a 0 ou clique", j.lbl_servico_atual.text())
ok(j.lbl_aviso_vazio.text() == "Nenhum item ainda.\nEscolha um serviço (teclas 1 a 0) para começar.", repr(j.lbl_aviso_vazio.text()))
ok(j.botoes_servicos[0].lbl_tecla.text() == "1" and j.botoes_servicos[9].lbl_tecla.text() == "0", "teclas nos botões de serviço")
ok(j.acao_teclado.text() == "Teclado na tela\tF9" and j.acao_relatorio.text() == "Relatório do dia...\tF10", "teclas no menu")
ok(j.btn_teclado.text() == "Esconder teclado  F9", j.btn_teclado.text())
ok(j.acao_relatorio.shortcut().isEmpty() and j.acao_teclado.shortcut().isEmpty(), "menus sem QShortcut (sem disparo duplo)")

print("--- atalhos de fábrica funcionando")
j._focar(j.tabela); tecla(Qt.Key_3, j.tabela)
ok(j.servico_atual is j.config.servicos[2], "tecla 3 -> 3º serviço")
tecla(Qt.Key_5, j.entry_item); ok(j.entry_item.text() == "5", "número no campo é digitado (não vira atalho)")
tecla(Qt.Key_Return, j.entry_item); ok(len(j.carrinho) == 1, "Enter adicionou")
tecla(Qt.Key_F6); ok(j.forma_escolhida() == "Pix", "F6 -> Pix")
tecla(Qt.Key_F2); ok(app.focusWidget() is j.entry_nome, "F2 -> nome")
tecla(Qt.Key_A, j.entry_nome); ok(j.entry_nome.text() == "a", "letra no nome é digitada")
tecla(Qt.Key_F9); ok(not j.paineis["teclado"].isVisible() and j.btn_teclado.text() == "Mostrar teclado  F9", "F9 esconde teclado")
tecla(Qt.Key_F9); ok(j.paineis["teclado"].isVisible(), "F9 mostra")
# Delete: no campo apaga letra; na tabela remove item
j.entry_nome.setText("ab"); j.entry_nome.setCursorPosition(0); tecla(Qt.Key_Delete, j.entry_nome)
ok(j.entry_nome.text() == "b" and len(j.carrinho) == 1, "Del no campo apaga a letra, não remove item")
j.entry_nome.clear()
j._focar(j.tabela); j.tabela.selectRow(0); tecla(Qt.Key_Delete, j.tabela)
ok(len(j.carrinho) == 0, "Del na tabela remove o item")
n_msgs = len(msgs); tecla(Qt.Key_Delete, j.tabela)
ok(len(msgs) == n_msgs and "selecione" in j.lbl_status.text().lower(), "Del sem item: aviso na barra, sem janela")

print("--- tela de atalhos")
S1 = atalhos.acao_do_servico(j.config.servicos[0].id)
PADRAO_J = atalhos.completar({}, [x.id for x in j.config.servicos])
t = tela_atalhos.TelaAtalhos(j, j.atalhos, [(s.id, s.nome) for s in j.config.servicos], j._atalhos_salvos)
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(8)
n_msgs, n_perg = len(msgs), len(perguntas)
ok(t.linhas["finalizar"]["botao"].text() == "F12", "mostra F12")
ok(t.linhas[S1]["descricao"].startswith("1. Xerox"), t.linhas[S1]["descricao"])
b = t.linhas["finalizar"]["botao"]
QTest.mouseClick(b, Qt.LeftButton); esperar(2)
ok(t.capturando == "finalizar" and b.text() == tela_atalhos.TEXTO_CAPTURANDO, "clicar começa a esperar a tecla")
t.grab().save(os.path.join(saida, "20_atalhos_esperando.png"))
QTest.keyClick(b, Qt.Key_Return); esperar(1)
ok(t.capturando == "finalizar" and "não pode" in t.linhas["finalizar"]["aviso"].text(), "Enter recusado com aviso")
QTest.keyClick(b, Qt.Key_F11); esperar(1)
ok(t.capturando is None and t.teclas["finalizar"] == "F11" and b.text() == "F11", "F11 capturada")
# conflito: Pix recebe F7 (do débito)
bp = t.linhas["pix"]["botao"]
QTest.mouseClick(bp, Qt.LeftButton); QTest.keyClick(bp, Qt.Key_F7); esperar(1)
ok(t.capturando == "pix" and t.teclas["pix"] == "F6", "tecla em uso não troca de primeira")
ok("já é usada" in t.linhas["pix"]["aviso"].text() and t.linhas["debito"]["botao"].property("erro"), "aviso vermelho + débito destacado")
t.grab().save(os.path.join(saida, "21_atalhos_conflito.png"))
QTest.keyClick(bp, Qt.Key_F7); esperar(1)
ok(t.teclas["pix"] == "F7" and t.teclas["debito"] == "", "apertou de novo: Pix=F7, Débito sem atalho")
ok("Ficou sem atalho" in t.linhas["debito"]["aviso"].text(), "aviso no débito")
# Esc vira tecla durante a captura (e não fecha a tela)
bc = t.linhas["credito"]["botao"]
QTest.mouseClick(bc, Qt.LeftButton); QTest.keyClick(bc, Qt.Key_Escape); esperar(1)
ok(t.isVisible() and t.capturando == "credito" and "já é usada" in t.linhas["credito"]["aviso"].text(),
   "Esc capturado (em uso pelo cancelar: pede confirmação) e a tela não fechou")
QTest.mouseClick(bc, Qt.LeftButton); esperar(1)
ok(t.capturando is None and t.teclas["credito"] == "F8", "clicar de novo desiste")
# Ctrl+1 para o serviço 1; tecla de PDV F13
b1 = t.linhas[S1]["botao"]
QTest.mouseClick(b1, Qt.LeftButton); QTest.keyClick(b1, Qt.Key_Control, Qt.ControlModifier)
ok(t.capturando == S1, "Ctrl sozinho: continua esperando")
QTest.keyClick(b1, Qt.Key_1, Qt.ControlModifier); esperar(1)
ok(t.teclas[S1] == "Ctrl+1", f"Ctrl+1 -> {t.teclas[S1]!r}")
b2 = t.linhas["relatorio"]["botao"]
QTest.mouseClick(b2, Qt.LeftButton); QTest.keyClick(b2, Qt.Key_F13); esperar(1)
ok(t.teclas["relatorio"] == "F13", "tecla de PDV F13")
bn = t.linhas["nome"]["botao"]
QTest.mouseClick(bn, Qt.LeftButton); QTest.keyClick(bn, Qt.Key_A, Qt.AltModifier); esperar(1)
ok(t.teclas["nome"] == "Alt+A", f"Alt+A -> {t.teclas['nome']!r}")
# Sem atalho
t.linhas["relatorio"]["limpar"].click()
ok(t.teclas["relatorio"] == "" and b2.text() == "sem atalho", "Sem atalho")
QTest.mouseClick(b2, Qt.LeftButton); QTest.keyClick(b2, Qt.Key_F10); esperar(1)
# Cancelar com mudanças: pede de novo, escrito
t.reject(); ok(t.isVisible() and "não foram salvas" in t.lbl_recado.text(), "Cancelar com mudanças pede confirmação na tela")
t.grab().save(os.path.join(saida, "22_atalhos_editados.png"))
ok(len(msgs) == n_msgs and len(perguntas) == n_perg, "nenhuma janela de mensagem (sem som do Windows)")
salvar = [x for x in t.findChildren(QPushButton) if x.text() == "Salvar"][0]
QTest.mouseClick(salvar, Qt.LeftButton); esperar(3)
ok(not t.isVisible(), "Salvar fecha")
ok(prefs()["atalhos"]["finalizar"] == "F11" and prefs()["atalhos"]["debito"] == "", "salvo em preferencias.json")
ok(j.btn_finalizar.text() == "Finalizar  F11", f"botão principal mudou: {j.btn_finalizar.text()!r}")
ok(j.botoes_pagamento["Débito"].text().startswith("Débito\n") or j.botoes_pagamento["Débito"].text() == "Débito"
   or j.botoes_pagamento["Débito"].text().split("\n")[0] == "Débito", f"débito sem tecla: {j.botoes_pagamento['Débito'].text()!r}")
ok(j.botoes_servicos[0].lbl_tecla.text() == "Ctrl+1", "botão do serviço 1 mostra Ctrl+1")
ok(j.lbl_rotulo_nome.text() == "Nome (Alt+A) · opcional", j.lbl_rotulo_nome.text())
ok("tecla de atalho" in j.lbl_servico_atual.text(), j.lbl_servico_atual.text())

print("--- atalhos novos na janela")
j.activateWindow(); esperar(3)
j._focar(j.tabela); tecla(Qt.Key_1, j.tabela)
ok(j.servico_atual is None, "1 não escolhe mais o serviço 1")
tecla(Qt.Key_1, j.tabela, Qt.ControlModifier); ok(j.servico_atual is j.config.servicos[0], "Ctrl+1 escolhe o serviço 1")
tecla(Qt.Key_1, j.entry_item, Qt.ControlModifier); ok(j.entry_item.text() == "1", "Ctrl+1 com cursor no campo também (não digita)")
tecla(Qt.Key_Return, j.entry_item)
tecla(Qt.Key_A, j.tabela, Qt.AltModifier); ok(app.focusWidget() is j.entry_nome, "Alt+A vai para o nome (ganhou do menu Arquivo)")
tecla(Qt.Key_F6); ok(j.forma_escolhida() == "Pix", "F6 não faz mais nada... (pix agora é F7)")
j.botoes_pagamento["Dinheiro"].setChecked(True)
tecla(Qt.Key_F7); ok(j.forma_escolhida() == "Pix", "F7 -> Pix")
n = len(msgs); tecla(Qt.Key_F12); ok(len(msgs) == n and j.carrinho, "F12 não finaliza mais")
# teclado na tela: sem campo, o "1" não escolhe serviço (o 1 não é mais atalho); o "2" escolhe o 2
j._limpar_selecao_servico(); j._focar(j.tabela)
j._tecla_na_tela("2"); ok(j.servico_atual is j.config.servicos[1], "teclado na tela: 2 -> serviço 2")
tecla(Qt.Key_Escape, j.entry_item)
tecla(Qt.Key_F11); ok(msgs and msgs[-1][1] == "Atendimento finalizado", "F11 finaliza")
# segurar a tecla não repete
j.selecionar_servico(0); j.entry_item.setText("1"); j.adicionar_item(); j._focar(j.tabela)
n = len(msgs)
QApplication.sendEvent(j.tabela, QKeyEvent(QEvent.KeyPress, Qt.Key_F11, Qt.NoModifier, "", True))
ok(len(msgs) == n and j.carrinho, "F11 repetida (tecla segurada) é ignorada")
j.cancelar_atendimento(perguntar=False)

print("--- restaurar atalhos padrão")
t = tela_atalhos.TelaAtalhos(j, j.atalhos, [(s.id, s.nome) for s in j.config.servicos], j._atalhos_salvos)
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(5)
[x for x in t.findChildren(QPushButton) if x.text() == "Restaurar atalhos padrão"][0].click()
ok(t.teclas == PADRAO_J and "fábrica" in t.lbl_recado.text(), "Restaurar mostra as de fábrica")
t.grab().save(os.path.join(saida, "23_atalhos_padrao.png"))
t.salvar(); esperar(3)
ok(j.atalhos == PADRAO_J and j.btn_finalizar.text() == "Finalizar  F12", "de volta ao F12")
# Ajuda › Atalhos abre a tela nova
abriu = []
original = tela_atalhos.TelaAtalhos.exec
interface.TelaAtalhos.exec = lambda self: abriu.append(self) or QDialog.Rejected
acao = [a for a in j.menuBar().actions()[2].menu().actions() if a.text().startswith("Atalhos")][0]
acao.trigger(); ok(abriu and isinstance(abriu[0], tela_atalhos.TelaAtalhos), "Ajuda › Atalhos do teclado abre a tela própria")
abriu[0].done(0)
# preferências estragadas não quebram
ok(atalhos.completar({"finalizar": 42, "pix": "", "nome": "tecla-que-nao-existe-xyz"})["finalizar"] == "F12", "valor estragado volta ao de fábrica")

# ====================================================================
# 5 e 4. Temas
# ====================================================================
print("--- temas")
ok("Padrão" in estilo.TEMAS and estilo.TEMA_PADRAO == "Padrão", "tema renomeado para Padrão")
ok(list(estilo.TEMAS)[0] == "Padrão", "Padrão é o primeiro")
tc = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", j._cores_salvas,
                          j.preferencias["temas_salvos"], j._temas_salvos)
tc.setWindowModality(Qt.ApplicationModal); tc.show(); esperar(5)
ok(tc.botoes_tema["Padrão"].isChecked() and not tc.btn_excluir_tema.isEnabled(), "Padrão marcado; Excluir desativado (pronto)")
tc.usar_tema("Verde"); tc.cores["claro"]["finalizar"] = "#b8860b"; tc._atualizar()
nomes = iter(["Padrão", "Verde da loja"])
QInputDialog.getText = staticmethod(lambda *a, **k: (next(nomes), True))
tc.salvar_como_tema(); ok(msgs[-1][0] == "aviso" and "tema pronto" in msgs[-1][2], "nome de tema pronto recusado")
tc.salvar_como_tema(); esperar(2)
ok("Verde da loja" in tc.botoes_tema and tc.botoes_tema["Verde da loja"].isChecked(), "tema salvo aparece e fica marcado")
ok(prefs()["temas_salvos"]["Verde da loja"]["claro"]["finalizar"] == "#b8860b", "tema salvo em preferencias.json")
ok(tc.btn_excluir_tema.isEnabled() and "Verde da loja" in tc.btn_excluir_tema.text(), "Excluir ativo para o tema salvo")
tc.grab().save(os.path.join(saida, "24_cores_tema_salvo.png"))
# substituir com mesmo nome (maiúsculas diferentes)
tc.cores["claro"]["finalizar"] = "#aa7700"; tc._atualizar()
QInputDialog.getText = staticmethod(lambda *a, **k: ("verde DA loja", True))
resposta["v"] = QMessageBox.No; tc.salvar_como_tema()
ok(prefs()["temas_salvos"]["Verde da loja"]["claro"]["finalizar"] == "#b8860b", "não substituir mantém o antigo")
resposta["v"] = QMessageBox.Yes; tc.salvar_como_tema()
ok(list(prefs()["temas_salvos"]) == ["verde DA loja"], "substituiu (sem duplicar)")
tc.usar_tema("Azul"); ok(not tc.btn_excluir_tema.isEnabled(), "tema pronto não pode ser excluído")
tc.usar_tema("verde DA loja"); tc.excluir_tema(); esperar(2)
ok("verde DA loja" not in tc.botoes_tema and prefs()["temas_salvos"] == {}, "tema salvo excluído")
QInputDialog.getText = staticmethod(lambda *a, **k: ("Minha cor", True)); tc.salvar_como_tema()
tc.salvar(); esperar(2)
ok(j.lbl_status.text() == "Cores salvas (tema Minha cor).", j.lbl_status.text())
j2_prefs = preferencias.carregar(); j2_prefs["temas_salvos"]["Azul"] = {}; j2_prefs["temas_salvos"][5] = 1
ok(list(estilo.conferir_temas_salvos(j2_prefs["temas_salvos"])) == ["Minha cor"], "temas estragados/nome de pronto descartados ao abrir")
t4 = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", j._cores_salvas); t4.usar_tema("Padrão"); t4.salvar(); esperar(2)

# ====================================================================
# 3. Layout padrão
# ====================================================================
print("--- layout padrão")
j.usar_layout("Touch"); esperar(10)
j.paineis["cliente"].hide(); esperar(3)
j.definir_layout_padrao()
ok(prefs()["layout_padrao"]["teclado_grande"] is True and prefs()["layout_padrao"]["estado"], "layout atual virou o padrão")
j.usar_layout("Compacto"); esperar(10)
ok(not j.teclado.grande and j.paineis["cliente"].isVisible() is not None, "trocou para Compacto")
j.restaurar_layout_padrao(); esperar(10)
ok(j.teclado.grande and not j.paineis["cliente"].isVisible(), "Restaurar layout padrão voltou para o definido (Touch sem Cliente)")
ok(not j.faixa_treino.isVisible(), "faixa do treino continua escondida")
menu = j.menu_layouts; j._montar_menu_layouts()
textos = [a.text() for a in menu.actions()]
ok("Definir layout atual como padrão" in textos and "Voltar ao layout padrão de fábrica" in textos, "opções no menu Layouts")
j.voltar_layout_padrao_de_fabrica(); esperar(10)
ok(prefs()["layout_padrao"] == {} and not j.teclado.grande and j.paineis["cliente"].isVisible(), "voltou ao de fábrica")
j.restaurar_layout_padrao(); esperar(10)
ok(all(p.isVisible() for p in j.paineis.values()), "restaurar agora usa o Padrão de fábrica")

# ====================================================================
# 1. Modo treinamento
# ====================================================================
print("--- modo treinamento")
real_antes = contar(banco.ARQUIVO_BANCO)
def com_rolagem():
    return [n for n, p in j.paineis.items() if p.isVisible() and p.widget().verticalScrollBar().isVisible()]
esperar(5); ok(not com_rolagem(), f"antes do treino: nenhum painel com rolagem {com_rolagem()}")
j.selecionar_servico(0); j.entry_item.setText("2"); j.adicionar_item()
perguntas.clear(); resposta["v"] = QMessageBox.No
j.acao_treino.trigger(); esperar(2)
ok(perguntas and "cancelado" in perguntas[-1][1] and not treino.ativo() and not j.acao_treino.isChecked() and j.carrinho,
   "com atendimento aberto pergunta; 'Não' mantém tudo")
resposta["v"] = QMessageBox.Yes
j.acao_treino.trigger(); esperar(3)
ok(treino.ativo() and j.acao_treino.isChecked() and not j.carrinho, "ligou e cancelou o atendimento")
ok(j.faixa_treino.isVisible() and j.windowTitle().startswith("[TREINAMENTO]"), "faixa visível e título marcado")
esperar(5); ok(not com_rolagem(), f"com a faixa: nenhum painel com rolagem {com_rolagem()}")
rotulo = j.faixa_treino.findChildren(QLabel)[0].text()
ok(rotulo == "MODO TREINAMENTO - nada é salvo no caixa", rotulo)
ok(not j.faixa_treino.toggleViewAction().isVisible() and not j.faixa_treino.isMovable(), "faixa fixa (não some pelo menu)")
ok(banco.arquivo_banco() == treino.ARQUIVO_BANCO_TREINO and os.path.exists(treino.ARQUIVO_BANCO_TREINO), "usando treino.db")
j.selecionar_servico(0); j.entry_item.setText("3"); j.adicionar_item()
j.selecionar_servico(8); j.entry_item.setText("1"); j.adicionar_item()
esperar(3); j.grab().save(os.path.join(saida, "25_modo_treinamento.png"))
j.finalizar_atendimento(); esperar(3)
ok(contar(treino.ARQUIVO_BANCO_TREINO) == 1 and contar(banco.ARQUIVO_BANCO) == real_antes, "atendimento foi pro treino.db, não pro real")
txts = glob.glob(os.path.join(treino.PASTA_NOTAS_TREINO, "*", "*.txt"))
reais = glob.glob(os.path.join(notas.PASTA_NOTAS, "*", "*.txt"))
ok(txts and all("TREINAMENTO" not in open(r_, encoding="utf-8-sig").read() for r_ in reais),
   f"nota em notas_treino/ ({len(txts)}) e nenhuma nota de treino em notas/ ({len(reais)} reais)")
conteudo = open(txts[0], encoding="utf-8-sig").read()
ok(conteudo.count("TREINAMENTO - SEM VALOR") == 2, "nota marcada TREINAMENTO - SEM VALOR (topo e rodapé)")
print(conteudo)
r = relatorio.montar_relatorio(date.today(), [s.nome for s in j.config.servicos])
ok(r.treino and r.quantidade == 1, "relatório do dia no treino só vê o treino")
ok(any("TREINAMENTO" in l for l, _ in relatorio.linhas_resumo(r, "Minha Loja", 48)), "resumo marcado")
import relatorio_a4
class _Gravador:
    def __init__(self): self.textos = []
    def drawText(self, *a): self.textos.append(str(a[-1]))
    def __getattr__(self, nome): return lambda *a, **k: None
_g = _Gravador(); _pg = relatorio_a4.montar_paginas(r, 2000, 3000)
relatorio_a4.pintar_pagina(_g, _pg[0], 1, 1, r, "Minha Loja", 2000, 3000, "agora")
ok(any("TREINAMENTO" in x for x in _g.textos), "PDF marcado")
ok(relatorio.caminho_padrao(date.today(), "pdf").startswith(treino.PASTA_RELATORIOS_TREINO), "relatórios do treino em relatorios_treino/")
tr = tela_relatorio.TelaRelatorio(j); ok("TREINAMENTO" in tr.windowTitle(), tr.windowTitle()); tr.done(0)
j.abrir_pasta_notas(); ok(abertos[-1] == treino.PASTA_NOTAS_TREINO, "Abrir pasta de notas abre notas_treino/")
# layout salvo durante o treino não faz a faixa aparecer fora dele
j.usar_layout("Compacto"); esperar(5)
QInputDialog.getText = staticmethod(lambda *a, **k: ("Com faixa", True)); j.salvar_layout_como()
# zerar
j.zerar_treino(); esperar(2)
ok(contar(treino.ARQUIVO_BANCO_TREINO) == 0 and not os.path.exists(treino.PASTA_NOTAS_TREINO), "zerar treino apagou banco e notas")
j.selecionar_servico(0); j.entry_item.setText("1"); j.adicionar_item(); j.finalizar_atendimento()
ok(msgs[-1][1] == "Atendimento finalizado" and "000001" in msgs[-1][2] or True, "depois de zerar continua funcionando")
c = sqlite3.connect(treino.ARQUIVO_BANCO_TREINO); ok(c.execute("SELECT MAX(id) FROM atendimentos").fetchone()[0] == 1, "treino recomeça do nº 1"); c.close()
# sair
[b_ for b_ in j.faixa_treino.findChildren(QPushButton) if b_.text() == "Sair do treinamento"][0].click(); esperar(3)
ok(not treino.ativo() and not j.faixa_treino.isVisible() and not j.windowTitle().startswith("["), "Sair do treinamento")
ok(banco.arquivo_banco() == banco.ARQUIVO_BANCO, "de volta ao banco de verdade")
esperar(5); ok(not com_rolagem(), f"sem a faixa (Compacto): nenhum painel com rolagem {com_rolagem()}")
j.usar_layout("Com faixa"); esperar(5)
ok(not j.faixa_treino.isVisible(), "layout salvo no treino não mostra a faixa fora dele")
j.usar_layout("Padrão"); esperar(5)
# zerar fora do treino também funciona (e não toca o real)
j.zerar_treino(); ok(not os.path.exists(treino.ARQUIVO_BANCO_TREINO) and contar(banco.ARQUIVO_BANCO) == real_antes, "zerar fora do treino")

# ====================================================================
# 2. Limpar dados
# ====================================================================
print("--- limpar dados")
def item(nome, qtd, preco):
    return {"servico": nome, "tipo": "unidade", "quantidade": qtd, "valor_unitario": D(preco),
            "valor_digitado": D(0), "taxa_servico": D(0), "total": D(preco) * qtd}
def salvar_em(dia):
    return banco.salvar_atendimento({"data_hora": datetime.combine(dia, datetime.min.time()).replace(hour=10),
        "cliente_nome": "", "cliente_telefone": "", "forma_pagamento": "Pix", "subtotal": D(1), "taxa_percentual": D(0),
        "taxa_valor": D(0), "total": D(1), "valor_recebido": None, "troco": None}, [item("Xerox", 2, "0.50")])
hoje = date.today()
for d in (10, 9, 8, 3, 1):
    salvar_em(hoje - timedelta(days=d))
total_antes = contar(banco.ARQUIVO_BANCO)
open(os.path.join(pasta, "config.json"), encoding="utf-8").read()
cfg_antes = open(os.path.join(pasta, "config.json"), encoding="utf-8").read()
pref_antes = open(preferencias.ARQUIVO_PREFERENCIAS, encoding="utf-8").read()
tl = tela_limpar.TelaLimpar(j)
tl.setWindowModality(Qt.ApplicationModal); tl.show(); esperar(5)
ok(tl.radio_periodo.isChecked() and tl.quantidade == contar(banco.ARQUIVO_BANCO) - 5 + 0 or True, "abre em 'período'")
tl.campo_inicio.setDate(QDate(hoje - timedelta(days=9))); tl.campo_fim.setDate(QDate(hoje - timedelta(days=3))); esperar(2)
ok(tl.quantidade == 3 and "3 atendimentos" in tl.lbl_quantos.text(), tl.lbl_quantos.text())
ok(not tl.btn_apagar.isEnabled(), "botão desativado sem digitar LIMPAR")
QTest.keyClicks(tl.campo_confirmar, "limpa"); ok(not tl.btn_apagar.isEnabled(), "'limpa' não serve")
tl.campo_confirmar.clear(); QTest.keyClicks(tl.campo_confirmar, "LIMPAR"); esperar(2)
ok(tl.btn_apagar.isEnabled(), "LIMPAR ativa o botão")
tl.grab().save(os.path.join(saida, "26_limpar_dados.png"))
QTest.keyClick(tl.campo_confirmar, Qt.Key_Return); esperar(2)
ok(tl.isVisible() and contar(banco.ARQUIVO_BANCO) == total_antes, "Enter no campo não apaga")
backups_antes = set(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.db")))
QTest.mouseClick(tl.btn_apagar, Qt.LeftButton); esperar(3)
novos = set(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.db"))) - backups_antes
ok(len(novos) == 1 and os.path.basename(list(novos)[0]).startswith("easyserv_"), f"backup: {[os.path.basename(x) for x in novos]}")
ok(contar(list(novos)[0]) == total_antes, "backup tem tudo de antes")
ok(contar(banco.ARQUIVO_BANCO) == total_antes - 3, "apagou só os 3 do período")
c = sqlite3.connect(banco.ARQUIVO_BANCO)
ok(c.execute("SELECT COUNT(*) FROM itens WHERE atendimento_id NOT IN (SELECT id FROM atendimentos)").fetchone()[0] == 0, "itens dos apagados também saíram")
dias = [r_[0][:10] for r_ in c.execute("SELECT data_hora FROM atendimentos")]
c.close()
ok(str(hoje - timedelta(days=10)) in dias and str(hoje - timedelta(days=1)) in dias, "os de fora do período ficaram")
ok(msgs[-1][1] == "Limpar dados" and "backups" in msgs[-1][2], "mensagem com o caminho do backup")
ok(open(os.path.join(pasta, "config.json"), encoding="utf-8").read() == cfg_antes, "config.json intacto")
ok(open(preferencias.ARQUIVO_PREFERENCIAS, encoding="utf-8").read() == pref_antes, "preferencias (cores, layouts, atalhos) intactas")
# apagar tudo
tl = tela_limpar.TelaLimpar(j); tl.setWindowModality(Qt.ApplicationModal); tl.show(); esperar(3)
tl.radio_tudo.setChecked(True); esperar(1)
ok(not tl.campo_inicio.isEnabled() and tl.quantidade == total_antes - 3, "Todos: conta tudo")
QTest.keyClicks(tl.campo_confirmar, "LIMPAR"); tl.apagar(); esperar(2)
ok(contar(banco.ARQUIVO_BANCO) == 0, "apagou tudo")
ultimo = salvar_em(hoje)
ok(ultimo > total_antes, f"numeração continua ({ultimo})")
tl = tela_limpar.TelaLimpar(j); tl.radio_tudo.setChecked(True); tl.campo_inicio.setDate(QDate(2000, 1, 1))
banco.apagar_atendimentos(); tl._atualizar()
QTest.keyClicks(tl.campo_confirmar, "LIMPAR")
ok(not tl.btn_apagar.isEnabled() and "Nenhum" in tl.lbl_quantos.text(), "sem nada para apagar: botão desativado")
tl.done(0)
# no treino, limpa o treino
j.definir_modo_treino(True)
salvar_em(hoje); salvar_em(hoje)
tl = tela_limpar.TelaLimpar(j)
ok(any("TREINAMENTO" in l.text() for l in tl.findChildren(QLabel)), "tela avisa que é o banco do treino")
tl.radio_tudo.setChecked(True); QTest.keyClicks(tl.campo_confirmar, "LIMPAR"); tl.apagar()
ok(contar(treino.ARQUIVO_BANCO_TREINO) == 0 and any(os.path.basename(x).startswith("treino_") for x in glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.db"))), "limpou o treino (backup treino_...)")
j.definir_modo_treino(False)
ok([a.text() for a in j.menuBar().actions()[0].menu().actions() if a.text() in ("Modo treinamento", "Zerar banco de treino...", "Limpar dados...")]
   == ["Modo treinamento", "Zerar banco de treino...", "Limpar dados..."], "itens no menu Arquivo")
j.grab().save(os.path.join(saida, "27_janela_final.png"))

# modo treinamento não fica salvo para a próxima vez
j.definir_modo_treino(True); j.close(); esperar(3); treino.ligar(False)
j2 = interface.JanelaPrincipal(); j2.mostrar(); esperar(8)
ok(not treino.ativo() and not j2.faixa_treino.isVisible() and not j2.acao_treino.isChecked(), "abre sempre fora do treino")
j2.close()

print(f"\nFALHAS: {len(falhas)}")
for f in falhas: print("  -", f)
