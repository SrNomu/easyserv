"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QApplication, QMessageBox, QLabel, QPushButton, QInputDialog,
                               QColorDialog)
from PySide6.QtTest import QTest
import estilo, banco, interface, tela_cores

msgs = []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.question = staticmethod(lambda *a: QMessageBox.Yes)
falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=10):
    for _ in range(n): QTest.qWait(40)

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()
j = interface.JanelaPrincipal(); j.mostrar(); esperar(20)

def cortados(rotulo):
    ruins = []
    for w in j.findChildren(QLabel) + j.findChildren(QPushButton):
        if not w.isVisible() or (isinstance(w, QLabel) and w.wordWrap()): continue
        if w.width() + 1 < w.minimumSizeHint().width() or w.height() + 1 < w.minimumSizeHint().height():
            ruins.append(f"{type(w).__name__} '{w.text()[:30]}' {w.width()}x{w.height()}")
    ok(not ruins, f"nada cortado ({rotulo})" + ("" if not ruins else ": " + "; ".join(ruins[:6])))

from PySide6.QtWidgets import QTabBar
def sem_rolagem(rotulo, nomes):
    com = [n for n in nomes if j.paineis[n].isVisible() and not j.paineis[n].visibleRegion().isEmpty()
           and j.paineis[n].widget().verticalScrollBar().maximum() > 0]
    ok(not com, f"sem barra de rolagem nos painéis de cima ({rotulo})" + (f": {com}" if com else ""))
    for barra in j.findChildren(QTabBar):
        if not barra.isVisible(): continue
        for i in range(barra.count()):
            precisa = barra.fontMetrics().horizontalAdvance(barra.tabText(i)) + 28  # texto + espaçamento (14px de cada lado)
            ok(barra.tabRect(i).width() >= precisa, f"aba '{barra.tabText(i)}' inteira ({barra.tabRect(i).width()} >= {precisa})")

def cor_no_meio(w):
    img = w.grab().toImage()
    return img.pixelColor(img.width() // 2, 6).name()

def prefs():
    with open(os.path.join(pasta, "preferencias.json"), encoding="utf-8") as f:
        return json.load(f)

esperar(25)
sem_rolagem("primeira abertura", ["item", "cliente", "pagamento"])

# ---------- 4. Categorias ----------
grupos = [l.text() for l in j.findChildren(QLabel) if l.objectName() == "grupo"]
ok(grupos == ["Impressão e documentos", "Consulta", "RecargaPay"], f"categorias {grupos}")
for tecla, nome in (("7", "Consulta RioCard"), ("8", "Recarga RioCard"), ("9", "Recarga de celular"), ("0", "Pagamento de boletos")):
    j._focar(j.tabela); QTest.keyClick(j.tabela, tecla); esperar(1)
    ok(j.servico_atual.nome == nome, f"tecla {tecla} -> {j.servico_atual.nome}")
j._limpar_selecao_servico()

# ---------- 1. Modo claro / escuro / sistema ----------
rosa = estilo.TEMAS["Padrão"]
j.definir_modo_cor("claro"); esperar(3)
ok(app.palette().color(QPalette.Window).name() == rosa["claro"]["fundo"], "modo claro: fundo claro")
ok(cor_no_meio(j.btn_finalizar) == rosa["claro"]["finalizar"], f"Finalizar claro pintado {cor_no_meio(j.btn_finalizar)}")
j.grab().save(os.path.join(saida, "5_modo_claro.png"))
j.definir_modo_cor("escuro"); esperar(3)
ok(app.palette().color(QPalette.Window).name() == rosa["escuro"]["fundo"], "modo escuro: fundo escuro")
ok(cor_no_meio(j.btn_finalizar) == rosa["escuro"]["finalizar"], f"Finalizar escuro pintado {cor_no_meio(j.btn_finalizar)}")
ok(prefs()["modo_cor"] == "escuro", "modo salvo na hora em preferencias.json")
# Um atendimento na tela, para o print escuro mostrar algo de verdade
j.selecionar_servico(0); j.entry_item.setText("10"); j.adicionar_item()
j.selecionar_servico(6); j.entry_item.setText("1"); j.adicionar_item()
j.selecionar_servico(8); j.entry_item.setText("20"); j.adicionar_item()
j.entry_recebido.setText("50"); esperar(3)
j.selecionar_servico(6); esperar(3)
j.grab().save(os.path.join(saida, "6_modo_escuro.png"))
cortados("modo escuro com itens")
sem_rolagem("com serviço escolhido", ["item", "cliente", "pagamento"])
j.definir_modo_cor("sistema"); esperar(3)
esperado = "escuro" if estilo.windows_esta_escuro() else "claro"
ok(j._modo_efetivo == esperado, f"Seguir o Windows -> {j._modo_efetivo} (Windows está {esperado})")
ok(j.acoes_modo["sistema"].isChecked() and not j.acoes_modo["escuro"].isChecked(), "menu marca só 'Seguir o Windows'")
j._windows_mudou_cor()  # simula o aviso do Windows: não pode travar nem repetir sem fim
ok(True, "aviso do Windows tratado sem loop")
j.definir_modo_cor("claro"); esperar(2)

# ---------- 2. Tela de cores ----------
salvas = []
t = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", lambda c: (salvas.append(c), j._cores_salvas(c)))
t.resize(980, 640); t.show(); esperar(5)
ok(t.botoes_tema["Padrão"].isChecked(), "tema atual marcado (Padrão)")
t.grab().save(os.path.join(saida, "7_cores_rosa.png"))
t.usar_tema("Azul"); esperar(3)
fin = [b for b in t.previa.findChildren(QPushButton) if b.objectName() == "finalizar"][0]
ok(cor_no_meio(fin) == estilo.TEMAS["Azul"]["claro"]["finalizar"], f"pré-visualização ficou azul {cor_no_meio(fin)}")
ok(app.palette().color(QPalette.Window).name() == rosa["claro"]["fundo"], "programa NÃO mudou antes de salvar")
QColorDialog.getColor = staticmethod(lambda *a, **k: QColor("#d4af37"))
t.escolher_cor("finalizar"); esperar(2)
ok(t.cores["claro"]["finalizar"] == "#d4af37" and t.cores["escuro"] == estilo.TEMAS["Azul"]["escuro"], "seletor muda só a cor do modo editado")
ok(not any(b.isChecked() for b in t.botoes_tema.values()), "cor mudada -> nenhum tema marcado")
ok(cor_no_meio(fin) == "#d4af37", "pré-visualização com a cor escolhida")
t.campos_cor["texto"].setText("#e0e0e0"); t._codigo_digitado("texto")
ok("Atenção" in t.lbl_aviso.text(), f"aviso de contraste: {t.lbl_aviso.text()!r}")
t.campos_cor["texto"].setText("xyz"); t._codigo_digitado("texto")
ok(t.cores["claro"]["texto"] == "#e0e0e0", "código inválido é ignorado")
t.campos_cor["texto"].setText("1a1d22"); t._codigo_digitado("texto")
ok(t.cores["claro"]["texto"] == "#1a1d22" and t.lbl_aviso.text() == "", "código sem # aceito e aviso some")
t.grab().save(os.path.join(saida, "8_cores_azul_editado.png"))
t.salvar(); esperar(3)
ok(salvas and cor_no_meio(j.btn_finalizar) == "#d4af37", "Salvar aplicou no programa")
ok(prefs()["cores"]["claro"]["finalizar"] == "#d4af37", "cores salvas em preferencias.json")
# Restaurar padrão
t2 = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", j._cores_salvas)
t2._trocar_modo("escuro")
ok(t2.campos_cor["fundo"].text() == estilo.TEMAS["Azul"]["escuro"]["fundo"], "trocar para editar o modo escuro mostra as cores dele")
botao_padrao = [b for b in t2.findChildren(QPushButton) if b.text() == "Restaurar padrão"][0]
botao_padrao.click()
ok(t2.cores == estilo.cores_padrao() and t2.botoes_tema["Padrão"].isChecked(), "Restaurar padrão -> Padrão")
t2.salvar(); esperar(2)
ok(estilo.nome_do_tema(j.preferencias["cores"]) == "Padrão", "padrão salvo")
# Tema Escuro no modo claro
t3 = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", j._cores_salvas)
t3.usar_tema("Escuro"); t3.salvar(); esperar(2)
ok(app.palette().color(QPalette.Window).name() == "#121212", "tema Escuro deixa escuro mesmo no modo claro")
t4 = tela_cores.TelaCores(j, j.preferencias["cores"], "claro", j._cores_salvas)
t4.usar_tema("Padrão"); t4.salvar(); esperar(2)
# Contraste dos temas prontos
for nome, tema in estilo.TEMAS.items():
    for modo, c in tema.items():
        k = estilo.cores_derivadas(c)
        ruim = [n for n, a, b in (("texto", k.texto, k.superficie), ("rótulos", k.suave, k.superficie),
                                  ("principal", k.principal, k.superficie), ("seleção", k.texto_selecionado, k.destaque),
                                  ("finalizar", k.texto_finalizar, k.finalizar)) if estilo.contraste(a, b) < 4.5]
        ok(not ruim, f"contraste do tema {nome}/{modo}" + (f" ruim: {ruim}" if ruim else ""))

# ---------- 3. Layouts ----------
j.usar_layout("Touch"); esperar(10)
p = j.paineis
ok(j.teclado.grande and j.teclado.botoes[0][0].width() >= 72, f"Touch: teclas grandes ({j.teclado.botoes[0][0].width()}px)")
ok(p["teclado"].height() > p["atendimento"].height() * 0.8, "Touch: teclado ocupa a coluna inteira")
ok(p["servicos"].x() < p["item"].x() < p["teclado"].x() < p["cliente"].x(), "Touch: colunas na ordem")
cortados("layout Touch")
sem_rolagem("Touch", ["item", "cliente", "pagamento"])
j.grab().save(os.path.join(saida, "9_layout_touch.png"))
QInputDialog.getText = staticmethod(lambda *a, **k: ("Caixa da tarde", True))
j.salvar_layout_como()
ok("Caixa da tarde" in j.preferencias["layouts_salvos"] and j.preferencias["layouts_salvos"]["Caixa da tarde"]["teclado_grande"], "salvou o layout com nome")
ok(prefs()["layout_atual"] == "Caixa da tarde", "layout atual salvo")
QInputDialog.getText = staticmethod(lambda *a, **k: ("touch", True))
n = len(msgs); j.salvar_layout_como()
ok(len(msgs) == n + 1 and "touch" not in j.preferencias["layouts_salvos"], "não deixa usar nome de layout pronto")

j.usar_layout("Padrão"); esperar(10)
ok(not j.teclado.grande and all(d.isVisible() for d in p.values()), "Padrão: teclado normal e tudo visível")
sem_rolagem("Padrão", ["item", "cliente", "pagamento"])
ok(p["teclado"].x() > p["atendimento"].x() and p["teclado"].y() == p["atendimento"].y(), "Padrão: teclado ao lado do atendimento")
j.usar_layout("Caixa da tarde"); esperar(10)
ok(j.teclado.grande and p["teclado"].height() > p["atendimento"].height() * 0.8, "trocou para o layout salvo")

j.showNormal(); esperar(5); j.resize(1366, 728); esperar(5)
j.usar_layout("Compacto"); esperar(10)
ok(not p["teclado"].isVisible(), "Compacto: teclado escondido")
ok(p["cliente"] in j.tabifiedDockWidgets(p["pagamento"]), "Compacto: Cliente em aba com Pagamento")
ok(not j.entry_recebido.visibleRegion().isEmpty() and j.entry_nome.visibleRegion().isEmpty(), "Compacto: aba do Pagamento na frente")
cortados(f"layout Compacto {j.width()}x{j.height()}")
sem_rolagem("Compacto", ["item", "pagamento"])
j.grab().save(os.path.join(saida, "10_layout_compacto_1366.png"))
j.paineis["teclado"].toggleViewAction().trigger(); esperar(5)
ok(p["teclado"].isVisible() and not p["teclado"].isFloating(), "Compacto: F9 mostra o teclado encaixado")
j.paineis["teclado"].toggleViewAction().trigger(); esperar(3)
j._focar(j.entry_nome); esperar(3)
ok(not j.entry_nome.visibleRegion().isEmpty(), "Compacto: F2 traz a aba do Cliente para a frente")
j.selecionar_servico(1); esperar(3)
ok(j.servico_atual.nome == "Xerox colorida", "Compacto: atalhos continuam")

j.excluir_layout("Caixa da tarde")
ok("Caixa da tarde" not in prefs()["layouts_salvos"], "excluiu o layout salvo")
QInputDialog.getText = staticmethod(lambda *a, **k: ("Compacto da Ana", True))
j.salvar_layout_como()
j._montar_menu_layouts()
nomes = [a.text() for a in j.menu_layouts.actions() if a.text()]
ok(nomes[:4] == ["Padrão", "Compacto", "Touch", "Compacto da Ana"], f"menu Layouts {nomes}")
marcados = [a.text() for a in j.menu_layouts.actions() if a.isChecked()]
ok(marcados == ["Compacto da Ana"], f"menu marca o layout atual {marcados}")

# ---------- Tudo salvo para a próxima vez ----------
j.definir_modo_cor("escuro")
j.close(); esperar(3)
pr = prefs()
ok(pr["modo_cor"] == "escuro" and pr["layout_atual"] == "Compacto da Ana" and pr["teclado_grande"] is False, "preferências gravadas ao fechar")
j2 = interface.JanelaPrincipal(); j2.mostrar(); esperar(15)
ok(app.palette().color(QPalette.Window).name() == rosa["escuro"]["fundo"], "reabriu no modo escuro")
ok(j2.acoes_modo["escuro"].isChecked(), "menu reabriu marcando Escuro")
ok(not j2.paineis["teclado"].isVisible() and j2.paineis["cliente"] in j2.tabifiedDockWidgets(j2.paineis["pagamento"]), "reabriu com o layout compacto")
ok(abs(j2.width() - 1366) < 20, f"reabriu com o mesmo tamanho ({j2.width()}x{j2.height()})")
j2.close()
print("\nFALHAS:", len(falhas))
