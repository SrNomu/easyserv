"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, sqlite3, re
from decimal import Decimal
pasta = sys.argv[1]
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
import estilo, banco, interface, config, notas, layout_notas, tela_notinhas

msgs = []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.question = staticmethod(lambda *a: QMessageBox.Yes)
falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()

# --- config ---
cfg = config.carregar_config()
s = {x.nome: x for x in cfg.servicos}
for nome, preco in (("Recarga RioCard", "1"), ("Recarga de celular", "1"), ("Pagamento de boletos", "2")):
    x = s[nome]
    ok(x.tipo == "unidade" and x.preco == Decimal(preco) and not x.cobra_taxa_maquininha,
       f"{nome}: preço fixo R$ {preco},00, sem taxa da maquininha")
ok(s["Xerox"].cobra_taxa_maquininha and s["Consulta RioCard"].cobra_taxa_maquininha, "xerox e consulta continuam com taxa")
ok([x.nome for x in cfg.servicos][7:] == ["Recarga RioCard", "Recarga de celular", "Pagamento de boletos"], "ordem (teclas 8, 9, 0) mantida")

j = interface.JanelaPrincipal(); j.mostrar()
for _ in range(15): QTest.qWait(40)

def adicionar(indice, qtd):
    j.selecionar_servico(indice)
    ok(j.lbl_campo_item.text() == "Quantidade", f"{j.servico_atual.nome}: pede quantidade")
    j.entry_item.setText(str(qtd)); QTest.qWait(20)
    previa = j.lbl_previa.text()
    j.adicionar_item()
    return previa

ok(adicionar(9, 2) == "= R$ 4,00", "2 boletos = R$ 4,00 na prévia")
j.botoes_pagamento["Crédito"].setChecked(True); QTest.qWait(20)
ok(j.lbl_total.text() == "R$ 4,00", f"só boletos no crédito: sem taxa ({j.lbl_total.text()})")
adicionar(0, 3)        # 3 xerox = 1,50
adicionar(8, 1)        # recarga de celular = 1,00
QTest.qWait(20)
ok(j.lbl_subtotal.text() == "R$ 6,50", f"subtotal {j.lbl_subtotal.text()}")
ok(j.lbl_taxa.text() == "R$ 0,08", f"taxa 5% só sobre o xerox (1,50 -> 0,075 -> 0,08): {j.lbl_taxa.text()}")
ok(j.lbl_total.text() == "R$ 6,58", f"total {j.lbl_total.text()}")
ok(j.lbl_taxa_rotulo.text() == "Taxa maquininha (5% sobre R$ 1,50)", f"rótulo {j.lbl_taxa_rotulo.text()!r}")
detalhes = [j.tabela.item(r, 2).text() for r in range(j.tabela.rowCount())]
ok(detalhes == ["R$ 2,00 cada", "R$ 0,50 cada", "R$ 1,00 cada"], f"tabela igual aos outros itens {detalhes}")
j.botoes_pagamento["Pix"].setChecked(True); QTest.qWait(20)
ok(j.lbl_total.text() == "R$ 6,50" and j.lbl_taxa_rotulo.text() == "Taxa maquininha (0%)", "no Pix não tem taxa")
j.botoes_pagamento["Débito"].setChecked(True); QTest.qWait(20)

n = len(msgs)
j.finalizar_atendimento()
ok(len(msgs) == n + 1 and msgs[-1][1] == "Atendimento finalizado", "finalizou")
c = sqlite3.connect(banco.ARQUIVO_BANCO)
at = c.execute("select forma_pagamento, subtotal_centavos, taxa_percentual, taxa_centavos, total_centavos from atendimentos order by id desc").fetchone()
ok(at[:2] == ("Débito", 650) and Decimal(at[2]) == 5 and at[3:] == (8, 658), f"banco: {at}")
itens = c.execute("select servico, tipo, quantidade, valor_unitario_centavos, valor_digitado_centavos, taxa_servico_centavos, total_centavos from itens order by id").fetchall()
ok(itens[0] == ("Pagamento de boletos", "unidade", 2, 200, 0, 0, 400), f"boleto no banco {itens[0]}")
ok(itens[2] == ("Recarga de celular", "unidade", 1, 100, 0, 0, 100), f"recarga no banco {itens[2]}")

caminho = re.search(r"Nota da loja salva em:\n(.+)", msgs[-1][2]).group(1).strip()
texto = open(caminho, encoding="utf-8-sig").read()
print(texto)
ok("Pagamento de boletos" in texto and "2 x R$ 2,00" in texto and "+ taxa" not in texto, "nota: boleto igual aos outros itens")
ok(re.search(r"Taxa maquininha \(5%\): +R\$ 0,08\n  sobre R\$ 1,50 \(sem recarga/boleto\)", texto) and "R$ 6,58" in texto, "nota: taxa só sobre o xerox")

# nota de um atendimento antigo (sem 'taxa_base') continua funcionando
antigo = {"data_hora": __import__("datetime").datetime.now(), "cliente_nome": "", "cliente_telefone": "",
          "forma_pagamento": "Crédito", "subtotal": Decimal("21"), "taxa_percentual": Decimal("5"),
          "taxa_valor": Decimal("1.05"), "total": Decimal("22.05"), "valor_recebido": None, "troco": None}
item_antigo = [{"servico": "Recarga de celular", "tipo": "valor", "quantidade": 1, "valor_unitario": Decimal("21"),
                "valor_digitado": Decimal("20"), "taxa_servico": Decimal("1"), "total": Decimal("21")}]
modelo = layout_notas.carregar_layout()["loja"]
linhas = notas.montar_linhas(modelo, 1, antigo, item_antigo, "loja", True)
txt = "\n".join(t for t, _ in linhas)
ok("Taxa maquininha (5%):" in txt and "R$ 20,00 + taxa R$ 1,00" in txt, "nota no formato antigo continua funcionando")

# editor de notinhas: exemplo com a regra nova
t = tela_notinhas.TelaNotinhas(j, ao_salvar=lambda *a: None)
t.radio_exemplo_credito.setChecked(True)
_, at_ex, itens_ex = t._dados_exemplo()
ok(any(i["servico"] == "Pagamento de boletos" and i["total"] == Decimal("4.00") for i in itens_ex), "exemplo tem 2 boletos = R$ 4,00")
ok(at_ex["taxa_base"] == Decimal("6.50") and at_ex["taxa_valor"] == Decimal("0.33") and at_ex["total"] == Decimal("10.83"),
   f"exemplo: 5% só sobre 6,50 -> {at_ex['taxa_valor']}, total {at_ex['total']}")
linhas = notas.montar_linhas(t.dados["loja"], 123, at_ex, itens_ex, "loja", True)
txt = "\n".join(x for x, _ in linhas)
ok("sobre R$ 6,50" in txt and "+ taxa" not in txt, "pré-visualização do editor com a regra nova")
t.show(); QTest.qWait(400)
t.grab().save(os.path.join(sys.argv[2], "notinhas_regra_nova.png"))
t.reject()
j.close()
print("\nFALHAS:", len(falhas))
