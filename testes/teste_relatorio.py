"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json
from datetime import datetime, date, timedelta
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog, QDialog
from PySide6.QtTest import QTest
import estilo, banco, interface, impressao, relatorio, tela_relatorio, notas

msgs, perguntas, abertos, impressos = [], [], [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
resposta = {"v": QMessageBox.No}
def pergunta(p, t, m, *a):
    perguntas.append((t, m)); return resposta["v"]
QMessageBox.question = staticmethod(pergunta)
os.startfile = lambda caminho: abertos.append(caminho)
# NUNCA imprime de verdade: as funções de impressão só anotam o que receberam.
modo = {"texto": True}
impressao.escolher_impressora = lambda nome: "MTI-773 Texto (teste)"
impressao.eh_impressora_texto = lambda nome: modo["texto"]
impressao.imprimir_texto = lambda imp, texto, tirar, doc: impressos.append(("texto", imp, texto, doc))
impressao.imprimir_imagem = lambda imp, img, mm, doc, *a: impressos.append(("imagem", imp, img, mm, doc))

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=3):
    for _ in range(n): QTest.qWait(30)

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()

# --- Atendimentos de teste: ontem (2) e hoje (3, um deles pela tela) ---
hoje, ontem = date.today(), date.today() - timedelta(days=1)
def item(nome, qtd, preco, cobra=True):
    return {"servico": nome, "tipo": "unidade", "quantidade": qtd, "valor_unitario": D(preco),
            "valor_digitado": D(0), "taxa_servico": D(0), "total": D(preco) * qtd, "cobra_taxa_maquininha": cobra}
def salvar(quando, forma, itens, taxa=D(0), pct=D(0), recebido=None):
    sub = sum(i["total"] for i in itens)
    return banco.salvar_atendimento({"data_hora": quando, "cliente_nome": "Ana <teste> & cia", "cliente_telefone": "",
        "forma_pagamento": forma, "subtotal": sub, "taxa_percentual": pct, "taxa_valor": taxa, "total": sub + taxa,
        "valor_recebido": recebido, "troco": None if recebido is None else recebido - sub - taxa}, itens)
salvar(datetime.combine(ontem, datetime.min.time()).replace(hour=9), "Pix", [item("Xerox", 10, "0.50")])
# atendimento antigo, do tempo em que boleto era "valor + taxa"
salvar(datetime.combine(ontem, datetime.min.time()).replace(hour=17, minute=30), "Dinheiro",
       [{"servico": "Pagamento de boletos", "tipo": "valor", "quantidade": 1, "valor_unitario": D("87.40"),
         "valor_digitado": D("85.40"), "taxa_servico": D(2), "total": D("87.40")}], recebido=D(100))
n_hoje1 = salvar(datetime.now().replace(hour=8, minute=5, second=0, microsecond=0), "Crédito",
                 [item("Xerox", 3, "0.50"), item("Pagamento de boletos", 2, "2.00", False)], taxa=D("0.08"), pct=D(5))
n_hoje2 = salvar(datetime.now().replace(hour=8, minute=40, second=0, microsecond=0), "Débito",
                 [item("Impressão colorida", 4, "2.50")], taxa=D("0.50"), pct=D(5))

j = interface.JanelaPrincipal(); j.mostrar(); esperar(15)
j.definir_modo_cor("claro")
# terceiro de hoje pela tela (gera a nota .txt de verdade)
j.selecionar_servico(6); j.entry_item.setText("1"); j.adicionar_item()
j.selecionar_servico(0); j.entry_item.setText("2"); j.adicionar_item()
j.finalizar_atendimento()

# F10 / menu abre o relatório
chamadas = []
original_exec = tela_relatorio.TelaRelatorio.exec
tela_relatorio.TelaRelatorio.exec = lambda self: chamadas.append(self) or QDialog.Rejected
acao = [a for a in j.menuBar().actions()[0].menu().actions() if a.text().startswith("Relatório do dia...")][0]
ok(acao.text() == "Relatório do dia...	F10", "menu Arquivo › Relatório do dia... mostra o atalho F10")
QTest.keyClick(j, Qt.Key_F10); esperar()
ok(len(chamadas) == 1, "F10 abre o relatório")
tela_relatorio.TelaRelatorio.exec = original_exec

t = tela_relatorio.TelaRelatorio(j)
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(8)
r = t.relatorio
ok(t.campo_data.date() == QDate.currentDate() and t.campo_data.calendarPopup(), "data padrão hoje, com calendário")
ok(t.campo_data.maximumDate() == QDate.currentDate(), "não deixa escolher dia do futuro")
ok(r.quantidade == 3 and t.lbl_quantidade.text() == "3", f"hoje: 3 atendimentos ({t.lbl_quantidade.text()})")
ok(r.por_servico == [("Xerox", 5, D("2.50")), ("Impressão colorida", 4, D("10.00")),
                     ("Consulta RioCard", 1, D("3.00")), ("Pagamento de boletos", 2, D("4.00"))],
   f"por serviço na ordem da tela {r.por_servico}")
ok(r.por_forma == {"Dinheiro": (1, D("4.00")), "Pix": (0, D(0)), "Débito": (1, D("10.50")), "Crédito": (1, D("5.58"))},
   f"por forma {r.por_forma}")
ok(t.lbl_taxas.text() == "R$ 0,58" and t.lbl_servicos.text() == "R$ 19,50" and t.lbl_total.text() == "R$ 20,08",
   f"taxas {t.lbl_taxas.text()}, serviços {t.lbl_servicos.text()}, total {t.lbl_total.text()}")
ok(t.tabela_formas.rowCount() == 4, "as 4 formas aparecem (mesmo com zero)")
lin = [[t.tabela_atendimentos.item(i, c).text() for c in range(5)] for i in range(3)]
ok(lin[0] == [f"{n_hoje1:06d}", "08:05", "3x Xerox, 2x Pagamento de boletos", "Crédito", "R$ 5,58"], f"lista {lin[0]}")
ok(lin[2][2] == "1x Consulta RioCard, 2x Xerox" and lin[2][3] == "Dinheiro", f"atendimento feito pela tela {lin[2]}")
t.grab().save(os.path.join(saida, "15_relatorio_claro.png"))

# abrir nota: a feita pela tela existe; a gravada direto no banco é gerada na hora
t.tabela_atendimentos.selectRow(2); t.abrir_nota()
ok(abertos and abertos[-1].endswith("_loja.txt") and os.path.exists(abertos[-1]), "abre a nota existente")
t.tabela_atendimentos.selectRow(0); esperar(1)
caminho = notas.caminho_da_nota(n_hoje1, datetime.now(), "loja")
ok(not os.path.exists(caminho), "(a nota do 1º ainda não existe)")
ponto = t.tabela_atendimentos.visualItemRect(t.tabela_atendimentos.item(0, 2)).center()
QTest.mouseClick(t.tabela_atendimentos.viewport(), Qt.LeftButton, pos=ponto)
QTest.mouseDClick(t.tabela_atendimentos.viewport(), Qt.LeftButton, pos=ponto); esperar()
ok(abertos[-1] == caminho and os.path.exists(caminho), "dois cliques: gerou a nota que faltava e abriu")
txt = open(caminho, encoding="utf-8-sig").read()
ok("2 x R$ 2,00" in txt and "R$ 5,58" in txt, "nota gerada com os dados do banco")

# ontem
QTest.mouseClick([b for b in t.findChildren(QPushButton) if b.text() == "‹ Anterior"][0], Qt.LeftButton); esperar()
r2 = t.relatorio
ok(r2.dia == ontem and r2.quantidade == 2, f"◀ dia anterior: {r2.dia} com {r2.quantidade}")
ok(dict((n, (q, v)) for n, q, v in r2.por_servico) == {"Xerox": (10, D("5.00")), "Pagamento de boletos": (1, D("87.40"))},
   "ontem por serviço (atendimento antigo mantém o valor que foi gravado)")
ok(t.lbl_total.text() == "R$ 92,40" and t.lbl_taxas.text() == "R$ 0,00", f"ontem total {t.lbl_total.text()}")
ok(not t.lbl_dia.text().startswith("Hoje"), f"rótulo do dia: {t.lbl_dia.text()}")
# dia vazio
t.campo_data.setDate(QDate.currentDate().addDays(-5)); esperar()
ok(t.relatorio.quantidade == 0 and t.pilha_lista.currentIndex() == 0 and not t.btn_pdf.isEnabled()
   and not t.btn_fechar_expediente.isEnabled() and t.lbl_total.text() == "R$ 0,00", "dia sem atendimento: aviso e botões desligados")
QTest.mouseClick([b for b in t.findChildren(QPushButton) if b.text() == "Hoje"][0], Qt.LeftButton); esperar()
ok(t.relatorio.dia == hoje and t.btn_pdf.isEnabled(), "botão Hoje volta")

# mudar preço não muda o relatório
cfg = json.load(open("config.json", encoding="utf-8")); cfg["servicos"][0]["preco"] = 9.99
json.dump(cfg, open("config.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
j.recarregar_config(); t.atualizar()
ok(t.relatorio.por_servico[0] == ("Xerox", 5, D("2.50")) and t.lbl_total.text() == "R$ 20,08", "preço novo não altera o relatório")

# Exportar PDF
destino_pdf = os.path.join(saida, "relatorio_teste.pdf")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino_pdf, "PDF (*.pdf)"))
resposta["v"] = QMessageBox.Yes
t.exportar("pdf")
ok(os.path.exists(destino_pdf) and open(destino_pdf, "rb").read(5) == b"%PDF-" and os.path.getsize(destino_pdf) > 3000,
   f"PDF salvo ({os.path.getsize(destino_pdf)} bytes)")
ok(abertos[-1] == destino_pdf, "pergunta e abre o PDF")
import relatorio_a4
html_txt = " ".join(o[5] for p in relatorio_a4.montar_paginas(t.relatorio, 2000, 3000) for o in p.ordens if o[0] == "texto")
ok("R$ 20,08" in html_txt and "Pagamento de boletos" in html_txt and "Ana" not in html_txt, "conteúdo do PDF (sem cliente)")

# Exportar Excel
destino_xlsx = os.path.join(saida, "relatorio_teste.xlsx")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino_xlsx, "Excel (*.xlsx)"))
resposta["v"] = QMessageBox.No
t.exportar("xlsx")
from openpyxl import load_workbook
wb = load_workbook(destino_xlsx)
ok(wb.sheetnames == ["Resumo", "Atendimentos"], f"abas {wb.sheetnames}")
res = {row[0]: row[1] for row in wb["Resumo"].iter_rows(values_only=True) if row and row[0]}
ok(res["Atendimentos"] == 3 and res["Total do dia"] == 20.08 and res["Taxas da maquininha"] == 0.58, f"resumo Excel {res['Total do dia']}")
ok(wb["Resumo"]["B7"].number_format == '"R$" #,##0.00', "valores como dinheiro no Excel")
linhas = list(wb["Atendimentos"].iter_rows(min_row=2, values_only=True))
ok(len(linhas) == 3 and round(sum(l[5] or 0 for l in linhas), 2) == 20.08, f"aba Atendimentos: 3 atendimentos, soma = {sum(l[5] or 0 for l in linhas)}")
ok(all("Ana" not in str(c) for aba in wb for row in aba.iter_rows(values_only=True) for c in row), "nome do cliente NÃO vai pro Excel")

# Imprimir resumo 80mm: impressora de texto
resposta["v"] = QMessageBox.Yes
t.imprimir()
ok(impressos and impressos[-1][0] == "texto" and "MTI-773" in perguntas[-1][1], "imprimir pergunta a impressora e manda texto")
texto80 = impressos[-1][2]
print(texto80)
ok(all(len(l) <= 48 for l in texto80.splitlines()) and "RELATÓRIO DO DIA" in texto80 and "TOTAL DO DIA:" in texto80
   and "R$ 20,08" in texto80, "resumo em 48 colunas (80mm)")
# impressora gráfica
modo["texto"] = False
t.imprimir()
ok(impressos[-1][0] == "imagem" and impressos[-1][3] == 72 and abs(impressos[-1][2].width - 575) < 3,
   f"impressora gráfica: imagem de 80mm ({impressos[-1][2].width}px)")
impressos[-1][2].save(os.path.join(saida, "resumo_80mm.png"))
n = len(impressos); resposta["v"] = QMessageBox.No; t.imprimir()
ok(len(impressos) == n, "responder Não não imprime")

# Fechar expediente
mostrado = {}
def exec_fake(self):
    mostrado["texto"] = self.findChild(__import__("PySide6.QtWidgets", fromlist=["QPlainTextEdit"]).QPlainTextEdit).toPlainText()
    mostrado["padrao"] = (self.check_imprimir.isChecked(), self.check_pdf.isChecked(), self.check_excel.isChecked())
    self.show(); esperar(3); self.grab().save(os.path.join(saida, "17_fechar_expediente.png"))
    self.check_imprimir.setChecked(True)
    return QDialog.Accepted
tela_relatorio.DialogoFechamento.exec = exec_fake
n = len(impressos)
t.fechar_expediente()
ok("TOTAL DO DIA:" in mostrado["texto"] and "R$ 20,08" in mostrado["texto"], "fechar expediente mostra o resumo")
ok(mostrado["padrao"] == (False, True, True), "padrão: salvar PDF e Excel, imprimir desmarcado")
pdf = relatorio.caminho_padrao(hoje, "pdf"); xlsx = relatorio.caminho_padrao(hoje, "xlsx")
ok(os.path.exists(pdf) and os.path.exists(xlsx) and os.path.dirname(pdf).endswith("relatorios"), "salvou na pasta relatorios/")
ok(len(impressos) == n + 1, "imprimiu (sem perguntar de novo)")
ok(msgs[-1][1] == "Expediente fechado" and "R$ 20,08" in msgs[-1][2] and "relatorio_" in msgs[-1][2], "mensagem final")
def exec_cancela(self): return QDialog.Rejected
tela_relatorio.DialogoFechamento.exec = exec_cancela
n = len(msgs); t.fechar_expediente()
ok(len(msgs) == n, "cancelar não faz nada")

# Modo escuro
j.definir_modo_cor("escuro"); esperar(5)
t.grab().save(os.path.join(saida, "16_relatorio_escuro.png"))
ok(app.palette().color(app.palette().ColorRole.Window).name() == estilo.TEMAS["Padrão"]["escuro"]["fundo"], "segue o modo escuro")
t.campo_data.calendarWidget().show(); esperar(3)
t.campo_data.calendarWidget().grab().save(os.path.join(saida, "calendario_escuro.png"))
t.campo_data.calendarWidget().hide()
j.definir_modo_cor("sistema")
t.reject(); j.close()
print("\nFALHAS:", len(falhas))
