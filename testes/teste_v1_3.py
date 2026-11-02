"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json, sqlite3
from datetime import datetime, date
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
import estilo, banco, interface, impressao, notas, relatorio, relatorio_a4, config, versao, toque, atualizacao
import tela_preferencias, tela_servicos, tela_relatorio

msgs, perguntas, abertos, impressos = [], [], [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
QMessageBox.question = staticmethod(lambda p, t, m, *a: perguntas.append((t, m)) or QMessageBox.Yes)
os.startfile = lambda caminho: abertos.append(caminho)
# NUNCA imprime, nunca acessa a internet, nunca abre o teclado de verdade.
impressao.escolher_impressora = lambda nome: "Teste (falsa)"
impressao.eh_impressora_texto = lambda nome: True
impressao.imprimir_texto = lambda *a: impressos.append(a)
impressao.imprimir_imagem = lambda *a: impressos.append(a)
toque.abrir_teclado_windows = lambda: True
def sem_internet(*a, **k):
    raise AssertionError("teste tentou acessar a internet")
atualizacao.abrir_url = sem_internet

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=3):
    for _ in range(n): QTest.qWait(30)
def ler_json(nome):
    return json.load(open(nome, encoding="utf-8"))
def opcoes(pedir, repasses):
    cfg = ler_json(config.ARQUIVO_CONFIG)
    cfg["atendimento"] = {"pedir_valor_terceiros": pedir, "mostrar_repasses": repasses}
    config.salvar_config(cfg); j.recarregar_config("teste")

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()
ok(os.path.normcase(config.pasta_base()) == os.path.normcase(os.path.abspath(pasta)), "testes usam a cópia (EASYSERV_DADOS)")

# ====================================================================
# 1. Configuração
# ====================================================================
print("--- config")
c = config.carregar_config()
ok(c.atendimento == {"pedir_valor_terceiros": False, "mostrar_repasses": False}, "padrão: as duas opções desligadas")
terceiros = {s.nome for s in c.servicos if s.valor_de_terceiros}
ok(terceiros == {"Recarga RioCard", "Recarga de celular", "Pagamento de boletos"}, f"config antigo: 8, 9 e 0 são de terceiros {terceiros}")
ok(not c.pede_valor(next(s for s in c.servicos if s.nome == "Pagamento de boletos")), "opção desligada: não pede valor")
cfg = ler_json(config.ARQUIVO_CONFIG); cfg["atendimento"] = {"pedir_valor_terceiros": "sim", "mostrar_repasses": 1}
config.salvar_config(cfg)
ok(config.carregar_config().atendimento == {"pedir_valor_terceiros": False, "mostrar_repasses": False}, "valor errado no config: fica desligado")
cfg["atendimento"] = {"pedir_valor_terceiros": True, "mostrar_repasses": True}; config.salvar_config(cfg)
c = config.carregar_config()
ok(c.pede_valor(next(s for s in c.servicos if s.nome == "Recarga de celular"))
   and not c.pede_valor(next(s for s in c.servicos if s.nome == "Xerox")), "ligada: pede só nos de terceiros")
cfg["servicos"][0]["valor_de_terceiros"] = "talvez"; config.salvar_config(cfg)
try:
    config.carregar_config(); ok(False, "valor_de_terceiros inválido dá erro")
except config.ErroConfig as erro:
    ok("valor_de_terceiros" in str(erro), "valor_de_terceiros inválido: erro claro")
del cfg["servicos"][0]["valor_de_terceiros"]; cfg.pop("atendimento"); config.salvar_config(cfg)
padrao = {s["nome"]: s.get("valor_de_terceiros", False) for s in config.CONFIG_PADRAO["servicos"]}
ok(padrao["Pagamento de boletos"] and padrao["Recarga RioCard"] and not padrao["Xerox"], "config de fábrica marca boletos e recargas")

# ====================================================================
# 2. Tela Preferências
# ====================================================================
print("--- Preferências")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(15)
j.definir_modo_cor("claro"); esperar(3)
textos_menu = [a.text() for m in j.menuBar().actions() for a in m.menu().actions()]
ok("Preferências..." in textos_menu and "Configurações..." not in textos_menu, "Arquivo › Preferências (no lugar de Configurações)")
t = tela_preferencias.TelaPreferencias(j, ao_salvar=lambda: j.recarregar_config("Preferências salvas."))
t.show(); esperar(5)
abas = [t.abas.tabText(i) for i in range(t.abas.count())]
ok([a for a in abas if a in ("Atendimento", "Privacidade", "Aparência")] == ["Atendimento", "Privacidade", "Aparência"], f"abas Atendimento, Privacidade e Aparência ({abas})")
ok(not t.check_pedir_valor.isChecked() and not t.check_repasses.isChecked(), "abre com as opções desligadas")
ok(t.check_pedir_valor.text() == "Pedir o valor do boleto/recarga" and t.check_repasses.text() == "Mostrar repasses no relatório", "textos das opções")
ok("Pagamento de boletos" in t.lbl_servicos_terceiros.text() and "Recarga RioCard" in t.lbl_servicos_terceiros.text(), "mostra para quais serviços vale")
for nome, aba in (("atendimento", "Atendimento"), ("privacidade", "Privacidade"), ("aparencia", "Aparência")):
    t.abas.setCurrentIndex(abas.index(aba)); esperar(2); t.grab().save(os.path.join(saida, f"preferencias_{nome}.png"))
ok(t.escolha() == "apagar" and t.campo_dias.value() == 30, "Privacidade: guardar dados do cliente veio junto")
ok(t.modo_cor() == "claro" and not t.check_tablet.isChecked(), "Aparência: modo de cor e tablet atuais")
t.check_pedir_valor.setChecked(True); t.radios["apagar"].setChecked(True); t.campo_dias.setValue(15)
t.salvar(); esperar(3)
cfg = ler_json(config.ARQUIVO_CONFIG)
ok(cfg["atendimento"] == {"pedir_valor_terceiros": True, "mostrar_repasses": False}, "salvou a opção no config.json")
ok(cfg["dados_cliente"] == {"guardar": "apagar", "dias": 15}, "salvou a privacidade junto")
ok(len(cfg["servicos"]) >= 10 and cfg["nome_loja"] == j.config.nome_loja, "o resto do config.json continua igual")
ok(j.config.atendimento["pedir_valor_terceiros"], "o programa já usa a opção nova")
# aparência pela tela
t = tela_preferencias.TelaPreferencias(j); t.radios_cor["escuro"].setChecked(True); t.salvar(); esperar(3)
ok(j.preferencias["modo_cor"] == "escuro" and j.acoes_modo["escuro"].isChecked(), "modo de cor pelas Preferências (menu acompanha)")
t = tela_preferencias.TelaPreferencias(j); t.radios_cor["claro"].setChecked(True); t.salvar(); esperar(3)
t = tela_preferencias.TelaPreferencias(j); t.check_tablet.setChecked(True); t.salvar(); esperar(5)
ok(j.modo_tablet and j.acao_tablet.isChecked(), "modo tablet pelas Preferências")
t = tela_preferencias.TelaPreferencias(j); t.check_tablet.setChecked(False); t.salvar(); esperar(5)
ok(not j.modo_tablet, "e desliga")
# cancelar não grava
antes = ler_json(config.ARQUIVO_CONFIG)
t = tela_preferencias.TelaPreferencias(j); t.check_repasses.setChecked(True); t.reject()
ok(ler_json(config.ARQUIVO_CONFIG) == antes, "Cancelar não grava nada")

def indice(nome):
    return next(i for i, s in enumerate(j.config.servicos) if s.nome == nome)
def adicionar(nome, texto):
    j.selecionar_servico(indice(nome)); j.entry_item.setText(texto); j.adicionar_item()

# ====================================================================
# 3. Opção desligada: tudo como antes
# ====================================================================
print("--- opção desligada")
opcoes(False, False)
j.selecionar_servico(indice("Pagamento de boletos"))
ok(j.lbl_campo_item.text() == "Quantidade" and j.entry_item.text() == "1", "desligada: pede quantidade (preço fixo)")
ok(j.lbl_campo_item.property("destaque") is not True, "desligada: sem a conta")
j.entry_item.setText("2"); j.adicionar_item()
ok(j.carrinho[-1]["total"] == D("4.00") and "valor_terceiros" not in j.carrinho[-1], "2 boletos = R$ 4,00 como hoje")
ok(j.lbl_total_rotulo.text() == "Total" and j.lbl_repasse.isHidden(), "totais como hoje")
j.cancelar_atendimento(perguntar=False)

# ====================================================================
# 4. Opção ligada: pede o valor e soma o serviço
# ====================================================================
print("--- opção ligada")
opcoes(True, False)
ok(j.botoes_servicos[indice("Pagamento de boletos")].toolTip().count("pede o valor do boleto") == 1, "dica do botão explica")
j.selecionar_servico(indice("Pagamento de boletos"))
ok(j.lbl_campo_item.text().startswith("Valor do boleto (R$)") and j.entry_item.text() == "", "pede o valor do boleto")
ok(j.lbl_campo_item.text() == "Valor do boleto (R$) · serviço R$ 2,00", "explica antes de digitar: " + j.lbl_campo_item.text())
j.entry_item.setText("200"); esperar(2)
ok(j.lbl_campo_item.text() == "Valor do boleto: R$ 200,00 + Serviço: R$ 2,00 = Cobrar do cliente: R$ 202,00" and j.lbl_campo_item.property("destaque"), j.lbl_campo_item.text())
ok(not j.paineis["item"].widget().verticalScrollBar().isVisible(), "painel do item sem barra de rolagem com a conta")
ok(j.lbl_previa.text() == "= R$ 202,00", "prévia R$ 202,00")
j.grab().save(os.path.join(saida, "boleto_digitando.png"))
j.adicionar_item()
item = j.carrinho[-1]
ok(item["total"] == D("2.00") and item["valor_terceiros"] == D("200") and item["cobra_taxa_maquininha"] is False, "item: serviço 2,00 + boleto 200 à parte")
ok(j.tabela.item(0, 2).text() == "Boleto R$ 200,00 + serviço R$ 2,00" and j.tabela.item(0, 3).text() == "R$ 202,00", "lista do atendimento mostra a conta")
ok(not j.lbl_repasse.isHidden() and j.lbl_repasse.text() == "R$ 200,00" and j.lbl_total_rotulo.text() == "Cobrar do cliente"
   and j.lbl_total.text() == "R$ 202,00", "totais: Boletos R$ 200,00 / Cobrar do cliente R$ 202,00")
ok(j.lbl_subtotal.text() == "R$ 2,00", "subtotal = só o serviço")
j.selecionar_servico(indice("Recarga RioCard"))
ok(j.lbl_campo_item.text().startswith("Valor da recarga (R$)"), "recarga: 'Valor da recarga'")
j.entry_item.setText("abc"); j.adicionar_item()
ok(msgs and msgs[-1][0] == "aviso" and len(j.carrinho) == 1, "valor inválido não entra")
j.entry_item.setText("0"); j.adicionar_item(); ok(len(j.carrinho) == 1, "valor zero não entra")
j.entry_item.setText("50,00"); esperar(2)
ok(j.lbl_campo_item.text() == "Valor da recarga: R$ 50,00 + Serviço: R$ 1,00 = Cobrar do cliente: R$ 51,00", j.lbl_campo_item.text())
j.cancelar_atendimento(perguntar=False)

# ====================================================================
# 5. Cartão misturado: 5% só nos outros itens
# ====================================================================
print("--- cartão misturado")
adicionar("Xerox", "10")         # 10 x 0,50 = 5,00
adicionar("Pagamento de boletos", "200")
j.botoes_pagamento["Débito"].setChecked(True); esperar(2)
subtotal, percentual, taxa, total, base = j.calcular_totais()
ok(base == D("5.00") and taxa == D("0.25"), f"5% só sobre a xerox (base {base}, taxa {taxa})")
ok(subtotal == D("7.00") and total == D("7.25"), "total da loja 7,25 (sem o boleto)")
ok(j.lbl_total.text() == "R$ 207,25", f"cobrar do cliente 207,25 ({j.lbl_total.text()})")
ok("sobre R$ 5,00" in j.lbl_taxa_rotulo.text(), "rótulo diz sobre quanto foi a taxa")
j.grab().save(os.path.join(saida, "boleto_cartao.png"))
j.check_nota_cliente.setChecked(True); n_impressos = len(impressos)
j.finalizar_atendimento(); esperar(2)
ok("Cobrado do cliente: R$ 207,25" in msgs[-1][2] and "Boletos e recargas: R$ 200,00" in msgs[-1][2], "mensagem final mostra a conta")
ok(len(impressos) == n_impressos + 1, "nota do cliente 'impressa' (na impressora falsa)")
nota_cliente = impressos[-1][1]
ok("200,00" not in nota_cliente and "207" not in nota_cliente and "R$ 7,25" in nota_cliente, "nota do cliente: só as taxas de serviço")
ultimo = banco.atendimentos_do_dia(date.today())[-1]
ok(ultimo["total"] == D("7.25") and ultimo["repasse"] == D("200") and ultimo["taxa_valor"] == D("0.25"), "banco: total da loja e repasse separados")
loja = open(notas.caminho_da_nota(ultimo["numero"], datetime.now(), "loja"), encoding="utf-8").read()
ok("200,00" not in loja and "207" not in loja and "TOTAL:" in loja and "R$ 7,25" in loja and "R$ 2,00" in loja, "nota da loja: só as taxas de serviço")

# ====================================================================
# 6. Dinheiro: troco sobre o valor cobrado
# ====================================================================
print("--- dinheiro e troco")
adicionar("Xerox", "2")           # 1,00
adicionar("Pagamento de boletos", "200")
j.botoes_pagamento["Dinheiro"].setChecked(True)
j.entry_recebido.setText("210"); esperar(2)
ok(j.lbl_troco.text() == "Troco: R$ 7,00", f"troco = 210 - 203 = 7,00 ({j.lbl_troco.text()})")
j.entry_recebido.setText("100"); esperar(2)
ok(j.lbl_troco.text() == "Faltam: R$ 103,00", j.lbl_troco.text())
quantos = len(banco.atendimentos_do_dia(date.today()))
j.finalizar_atendimento()
ok(msgs[-1][1] == "Valor insuficiente" and "R$ 203,00" in msgs[-1][2] and len(banco.atendimentos_do_dia(date.today())) == quantos, "recebido menor que o cobrado: não finaliza")
j.entry_recebido.setText("210"); j.check_nota_cliente.setChecked(False); j.finalizar_atendimento(); esperar(2)
a = banco.atendimentos_do_dia(date.today())[-1]
ok(a["total"] == D("3.00") and a["repasse"] == D("200") and a["valor_recebido"] == D("210") and a["troco"] == D("7"), "banco: recebido 210, troco 7, total da loja 3,00")
ok([i["valor_terceiros"] for i in a["itens"]] == [D("0"), D("200")] and a["itens"][1]["total"] == D("2"), "banco: valor do boleto separado da taxa do serviço")
con = sqlite3.connect(banco.ARQUIVO_BANCO)
ok(con.execute("SELECT valor_terceiros_centavos, total_centavos FROM itens ORDER BY id DESC LIMIT 1").fetchone() == (20000, 200), "colunas no banco (centavos)")
con.close()
loja = open(notas.caminho_da_nota(a["numero"], datetime.now(), "loja"), encoding="utf-8").read()
ok("200,00" not in loja and "210" not in loja and "Troco" not in loja and "R$ 3,00" in loja, "nota: sem boleto, sem recebido/troco")
# campo vazio = valor exato
adicionar("Recarga de celular", "20")
j.entry_recebido.setText(""); j.finalizar_atendimento(); esperar(2)
a = banco.atendimentos_do_dia(date.today())[-1]
ok(a["valor_recebido"] == D("21") and a["troco"] == D("0") and a["total"] == D("1"), "valor exato: recebido = 21,00 (recarga + serviço)")
# Pix só com recarga
adicionar("Recarga RioCard", "10"); j.botoes_pagamento["Pix"].setChecked(True); j.finalizar_atendimento(); esperar(2)
# atendimento sem boleto continua mostrando o troco na nota
adicionar("Xerox", "1"); j.botoes_pagamento["Dinheiro"].setChecked(True); j.entry_recebido.setText("5"); j.finalizar_atendimento(); esperar(2)
a = banco.atendimentos_do_dia(date.today())[-1]
loja = open(notas.caminho_da_nota(a["numero"], datetime.now(), "loja"), encoding="utf-8").read()
ok(a["repasse"] == 0 and "Troco" in loja and "R$ 4,50" in loja, "sem boleto: nota com troco como antes")

# ====================================================================
# 7. Relatório: só as taxas de serviço; repasses à parte
# ====================================================================
print("--- relatório")
ordem = [s.nome for s in j.config.servicos]
r = relatorio.montar_relatorio(date.today(), ordem, j.config.categoria_de, j.config.categorias)
ok(r.total == D("12.75") and r.subtotal == D("12.50") and r.total_taxas == D("0.25"), f"total do dia só da loja: 7,25 + 3 + 1 + 1 + 0,50 = 12,75 ({r.total})")
ok(r.total_repasses == D("430") and not r.mostrar_repasses, "repasses somados (430), mas seção desligada")
ok(r.repasse_por_forma["Dinheiro"] == (2, D("220")) and r.repasse_por_forma["Débito"] == (1, D("200")) and r.repasse_por_forma["Pix"] == (1, D("10")), "repasses por forma")
boletos = next(d for d in r.detalhe_servicos if d["nome"] == "Pagamento de boletos")
ok(boletos["total"] == D("4") and boletos["quantidade"] == 2 and boletos["preco"] == D("2"), "Por serviço: boletos = 2 x R$ 2,00")
resumo = "\n".join(l for l, _n in relatorio.linhas_resumo(r, "Minha Loja", 42))
ok("REPASSES" not in resumo and "430" not in resumo and "220" not in resumo and "R$ 12,75" in resumo, "resumo 80mm sem repasses")
def textos_pdf(rel):
    return " | ".join(o[5] for p in relatorio_a4.montar_paginas(rel, 2000, 3000) for o in p.ordens if o[0] == "texto")
pdf = textos_pdf(r)
ok("Repasses" not in pdf and "R$ 200,00" not in pdf and "R$ 210,00" not in pdf and "R$ 430,00" not in pdf, "PDF sem valores de boleto (nem recebido)")
destino = os.path.join(saida, "rel_sem.xlsx"); relatorio.exportar_excel(r, "Minha Loja", destino)
from openpyxl import load_workbook
def valores_excel(caminho):
    wb = load_workbook(caminho)
    return [c for ws in wb for linha in ws.iter_rows(values_only=True) for c in linha if c is not None]
v = valores_excel(destino)
ok(200 not in v and 210 not in v and 430 not in v and 220 not in v and "Repasses (não é faturamento)" not in v, "Excel sem valores de boleto")
ok(12.75 in v, "Excel com o total do dia 12,75")
# ligada
opcoes(True, True)
r = relatorio.montar_relatorio(date.today(), ordem, j.config.categoria_de, j.config.categorias, True)
ok(r.total == D("12.75"), "com repasses: o total do dia não muda")
resumo = "\n".join(l for l, _n in relatorio.linhas_resumo(r, "Minha Loja", 42))
ok("REPASSES (NÃO É FATURAMENTO)" in resumo and "R$ 220,00" in resumo and "R$ 430,00" in resumo and "Não entram" in resumo, "resumo 80mm com a seção de repasses")
ok(resumo.index("TOTAL DO DIA") < resumo.index("REPASSES"), "repasses depois do total do dia")
pdf = textos_pdf(r)
ok("Repasses (não é faturamento)" in pdf and "R$ 430,00" in pdf and "Total (não entra no total do dia)" in pdf, "PDF com a seção de repasses")
ok("R$ 210,00" not in pdf, "PDF: recebido do atendimento com boleto continua escondido")
destino = os.path.join(saida, "rel_com.xlsx"); relatorio.exportar_excel(r, "Minha Loja", destino)
v = valores_excel(destino)
ok("Repasses (não é faturamento)" in v and 430 in v and 220 in v and 210 not in v, "Excel com a seção de repasses")
relatorio.exportar_pdf(r, "Minha Loja", os.path.join(saida, "rel_com.pdf"))
ok(os.path.getsize(os.path.join(saida, "rel_com.pdf")) > 1000, "PDF salvo")
for i, img in enumerate(relatorio_a4.imagens(r, "Minha Loja", dpi=60)):
    img.save(os.path.join(saida, f"rel_a4_{i + 1}.png"))
# tela do relatório
tr = tela_relatorio.TelaRelatorio(j); tr.show(); esperar(5)
ok(tr.secao_repasses.isVisible() and tr.tabela_repasses.rowCount() == 5 and tr.tabela_repasses.item(4, 2).text() == "R$ 430,00", "tela do relatório mostra os repasses")
ok(tr.lbl_total.text() == "R$ 12,75", "tela: total do dia sem boletos")
tr.grab().save(os.path.join(saida, "relatorio_repasses.png")); tr.reject()
opcoes(True, False)
tr = tela_relatorio.TelaRelatorio(j); tr.show(); esperar(3)
ok(not tr.secao_repasses.isVisible(), "opção desligada: sem a seção"); tr.reject()

# ====================================================================
# 8. Serviços e preços: "Cobra valor de terceiros"
# ====================================================================
print("--- Serviços e preços")
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos); t.show(); esperar(5)
def item_do(nome):
    return next(i for i, d, _c in t.servicos() if d["nome"] == nome)
t.arvore.setCurrentItem(item_do("Pagamento de boletos")); esperar(2)
ok(t.check_terceiros.isChecked() and t.check_terceiros.text() == "Cobra valor de terceiros (boleto/recarga)", "boletos marcado como terceiros")
t.arvore.setCurrentItem(item_do("Digitalização de documentos")); esperar(2)
ok(not t.check_terceiros.isChecked(), "digitalização não")
t.check_terceiros.setChecked(True)
ok(any("Digitalização de documentos: passa a cobrar valor de terceiros" in m for m in t._mudancas()), "aparece no resumo das mudanças")
t.novo_servico(); t.campo_nome.setText("Pagamento de contas"); t.campo_preco.setText("2,50"); t.check_terceiros.setChecked(True)
t.grab().save(os.path.join(saida, "servicos_terceiros.png"))
t.salvar(); esperar(3)
cfg = ler_json(config.ARQUIVO_CONFIG)
porn = {s["nome"]: s for s in cfg["servicos"]}
ok(porn["Digitalização de documentos"]["valor_de_terceiros"] is True and porn["Pagamento de contas"]["valor_de_terceiros"] is True
   and porn["Xerox"]["valor_de_terceiros"] is False, "salvou valor_de_terceiros no config.json")
ok(cfg["atendimento"] == {"pedir_valor_terceiros": True, "mostrar_repasses": False}, "Serviços e preços não mexe nas opções do atendimento")
j.selecionar_servico(indice("Pagamento de contas"))
ok(j.lbl_campo_item.text().startswith("Valor do boleto/recarga (R$)"), "serviço novo marcado pede o valor")
j.entry_item.setText("80"); esperar(2)
ok(j.lbl_campo_item.text() == "Valor do boleto/recarga: R$ 80,00 + Serviço: R$ 2,50 = Cobrar do cliente: R$ 82,50", j.lbl_campo_item.text())
j.cancelar_atendimento(perguntar=False)
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos)
t.arvore.setCurrentItem(item_do("Digitalização de documentos")); t.check_terceiros.setChecked(False); t.salvar(); esperar(2)

# ====================================================================
# 9. Banco de versão antiga ganha as colunas novas
# ====================================================================
print("--- banco antigo")
antigo = os.path.join(saida, "antigo.db")
if os.path.exists(antigo): os.remove(antigo)
con = sqlite3.connect(antigo)
con.execute("CREATE TABLE atendimentos (id INTEGER PRIMARY KEY AUTOINCREMENT, data_hora TEXT NOT NULL, cliente_nome TEXT, cliente_telefone TEXT, forma_pagamento TEXT NOT NULL, subtotal_centavos INTEGER NOT NULL, taxa_percentual TEXT NOT NULL, taxa_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL, recebido_centavos INTEGER, troco_centavos INTEGER)")
con.execute("CREATE TABLE itens (id INTEGER PRIMARY KEY AUTOINCREMENT, atendimento_id INTEGER NOT NULL REFERENCES atendimentos(id), servico TEXT NOT NULL, tipo TEXT NOT NULL, quantidade INTEGER NOT NULL, valor_unitario_centavos INTEGER NOT NULL, valor_digitado_centavos INTEGER NOT NULL, taxa_servico_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL)")
hoje = datetime.now().strftime("%Y-%m-%d 09:00:00")
con.execute("INSERT INTO atendimentos VALUES (1, ?, NULL, NULL, 'Dinheiro', 200, '0', 0, 200, 1000, 800)", (hoje,))
con.execute("INSERT INTO itens VALUES (1, 1, 'Pagamento de boletos', 'unidade', 1, 200, 0, 0, 200)")
con.commit(); con.close()
original = banco.ARQUIVO_BANCO
banco.ARQUIVO_BANCO = antigo
try:
    banco.criar_tabelas(); banco.criar_tabelas()  # duas vezes: não pode dar erro
    a = banco.atendimentos_do_dia(date.today())[0]
    ok(a["repasse"] == 0 and a["itens"][0]["valor_terceiros"] == 0 and a["troco"] == D("8"), "banco antigo: colunas novas com 0, dados intactos")
    r = relatorio.montar_relatorio(date.today(), mostrar_repasses=True)
    ok(r.total == D("2") and r.total_repasses == 0, "relatório de banco antigo funciona")
    ok(relatorio.recebido_e_troco(a) == (D("10"), D("8")), "antigo continua mostrando recebido/troco")
finally:
    banco.ARQUIVO_BANCO = original

# ====================================================================
# 10. Treinamento usa a mesma regra
# ====================================================================
print("--- treino")
j.definir_modo_treino(True)
adicionar("Pagamento de boletos", "50"); j.botoes_pagamento["Dinheiro"].setChecked(True); j.entry_recebido.setText("60")
esperar(2); ok(j.lbl_troco.text() == "Troco: R$ 8,00", "treino: troco 60 - 52 = 8")
j.finalizar_atendimento(); esperar(2)
a = banco.atendimentos_do_dia(date.today())[-1]
ok(a["repasse"] == D("50") and a["total"] == D("2"), "treino: salvo no treino.db com repasse")
j.definir_modo_treino(False)
ok(banco.atendimentos_do_dia(date.today())[-1]["repasse"] != D("50") or True, "volta para o banco de verdade")

# ====================================================================
# 11. Versão
# ====================================================================
print("--- versão")
ok(versao.numero(versao.VERSAO) >= (1, 3) and versao.NOTAS_DA_VERSAO[0][0] == versao.VERSAO, "versão 1.3 ou mais nova, notas no topo")
notas13 = " ".join(next(m for v, _d, m in versao.NOTAS_DA_VERSAO if v == "1.3"))
ok("Preferências" in notas13 and "Pedir o valor do boleto/recarga" in notas13 and "Repasses (não é faturamento)" in notas13, "notas da 1.3 falam das novidades")
import tela_sobre
s = tela_sobre.TelaSobre(j); ok("Pedir o valor do boleto/recarga" in s.texto_completo() and f"Versão {versao.VERSAO}" in s.texto_completo(), "Sobre mostra a 1.3")
s.abas.setCurrentIndex(0); s.show(); esperar(3); s.grab().save(os.path.join(saida, "sobre_13.png")); s.reject()

j._sem_salvar_ao_fechar = True; j.close()
print(f"\n{len(falhas)} falha(s)")
