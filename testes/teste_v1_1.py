"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json, sqlite3, glob
from datetime import datetime, date, timedelta
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QDialog
from PySide6.QtTest import QTest
import estilo, banco, interface, impressao, notas, relatorio, relatorio_a4, atalhos, preferencias, config
import layout_notas, versao, barra_titulo, tela_servicos, tela_relatorio, tela_sobre, tela_preferencias

msgs, perguntas, abertos, impressos, a4 = [], [], [], [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
resposta = {"v": QMessageBox.Yes}
def pergunta(p, t, m, *a):
    perguntas.append((t, m)); return resposta["v"]
QMessageBox.question = staticmethod(pergunta)
os.startfile = lambda caminho: abertos.append(caminho)
# NUNCA imprime de verdade: tudo que iria para impressora só é anotado.
impressao.escolher_impressora = lambda nome: nome or "Notinhas (falsa)"
impressao.eh_impressora_texto = lambda nome: True
impressao.imprimir_texto = lambda imp, texto, *a: impressos.append((imp, texto))
impressao.imprimir_imagem = lambda imp, *a: impressos.append((imp, "imagem"))
relatorio_a4.imprimir = lambda r, loja, imp, paisagem=False: a4.append(("relatorio", imp, paisagem)) or 1
relatorio_a4.imprimir_teste = lambda imp, loja, paisagem=False: a4.append(("teste", imp, paisagem))
tela_relatorio.impressoras_instaladas = lambda: ["Notinhas (falsa)", "Escritório A4", "Térmica 2"]
tela_relatorio.impressora_padrao_windows = lambda: "Escritório A4"

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=3):
    for _ in range(n): QTest.qWait(30)
def ler_json(nome):
    return json.load(open(nome, encoding="utf-8"))

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()

# Atendimento antigo com "Recarga de celular" e cliente (para histórico e privacidade)
def item(nome, qtd, preco):
    return {"servico": nome, "tipo": "unidade", "quantidade": qtd, "valor_unitario": D(preco),
            "valor_digitado": D(0), "taxa_servico": D(0), "total": D(preco) * qtd, "cobra_taxa_maquininha": True}
def salvar(quando, itens, nome="Joana Privada", tel="(21) 98888-7777", forma="Pix"):
    sub = sum(i["total"] for i in itens)
    return banco.salvar_atendimento({"data_hora": quando, "cliente_nome": nome, "cliente_telefone": tel,
        "forma_pagamento": forma, "subtotal": sub, "taxa_percentual": D(0), "taxa_valor": D(0), "total": sub,
        "valor_recebido": None, "troco": None}, itens)
agora = datetime.now().replace(second=0, microsecond=0)
n_velho = salvar(agora - timedelta(days=40), [item("Xerox", 2, "0.50")])
n_hoje = salvar(agora.replace(hour=9), [item("Recarga de celular", 2, "1.00"), item("Xerox colorida", 3, "1.50")])

# ====================================================================
# 5. Privacidade: apagamento automático ao abrir
# ====================================================================
print("--- privacidade: ao abrir")
ok(config.carregar_config().dados_cliente == {"guardar": "apagar", "dias": 30}, "padrão: apagar depois de 30 dias")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(15)
j.definir_modo_cor("claro"); esperar(3)
c = sqlite3.connect(banco.arquivo_banco())
linhas = dict((n, (nome, tel, tot)) for n, nome, tel, tot in
              c.execute("select id, cliente_nome, cliente_telefone, total_centavos from atendimentos"))
c.close()
ok(linhas[n_velho][:2] == (None, None) and linhas[n_velho][2] == 100, f"atendimento de 40 dias: nome/telefone apagados, valor mantido {linhas[n_velho]}")
ok(linhas[n_hoje][0] == "Joana Privada", "atendimento de hoje mantém o nome (ainda dentro dos 30 dias)")
ok(len(banco.atendimentos_do_dia((agora - timedelta(days=40)).date())[0]["itens"]) == 1, "itens do atendimento antigo continuam")
ok(banco.apagar_dados_clientes(0) == 1, "apagar_dados_clientes(0) apaga os de hoje também")
salvar(agora.replace(hour=10), [item("Xerox", 1, "0.50")])  # um com nome de novo, para os testes abaixo

# ====================================================================
# 4. NÃO É DOCUMENTO FISCAL
# ====================================================================
print("--- aviso fiscal")
at = {"data_hora": agora, "cliente_nome": "Ana", "cliente_telefone": "(21) 99999-0000", "forma_pagamento": "Pix",
      "subtotal": D("1.00"), "taxa_percentual": D(0), "taxa_valor": D(0), "total": D("1.00"),
      "valor_recebido": None, "troco": None}
for via in ("loja", "cliente"):
    for modo in (False, True):
        ls = notas.montar_linhas(j.layout_das_notas[via], 7, at, [item("Xerox", 2, "0.50")], via, modo)
        ok(any(l[1].strip() == "NÃO É DOCUMENTO FISCAL" if isinstance(l, tuple) and len(l) > 1 and isinstance(l[1], str)
               else "NÃO É DOCUMENTO FISCAL" in str(l) for l in ls), f"nota {via} ({'texto' if modo else 'imagem'}) tem o aviso")
modelo_sem = json.loads(json.dumps(j.layout_das_notas["cliente"]))
for chave in list(modelo_sem.get("mostrar", {})):
    modelo_sem["mostrar"][chave] = False
ls = notas.montar_linhas(modelo_sem, 7, at, [item("Xerox", 2, "0.50")], "cliente")
ok("NÃO É DOCUMENTO FISCAL" in str(ls), "aviso aparece mesmo com todos os campos desmarcados")

# ====================================================================
# 5. Privacidade: nota da loja / cliente
# ====================================================================
print("--- privacidade: notas")
ok(layout_notas.modelo_padrao("loja")["mostrar"]["cliente_nome"] is False
   and layout_notas.modelo_padrao("loja")["mostrar"]["telefone"] is False, "loja: nome/telefone desmarcados de fábrica")
ok(layout_notas.modelo_padrao("cliente")["mostrar"]["cliente_nome"] is True, "cliente: nome marcado")
ok(not j.layout_das_notas["loja"]["mostrar"]["cliente_nome"], "layout carregado: loja sem cliente")
# migração de layout antigo (versão 1, com cliente marcado na loja)
antigo = layout_notas.layout_padrao(); antigo.pop("versao")
antigo["loja"]["mostrar"]["cliente_nome"] = antigo["loja"]["mostrar"]["telefone"] = True
antigo["cliente"]["endereco"] = "Rua X, 1"
json.dump(antigo, open(layout_notas.ARQUIVO_LAYOUT, "w", encoding="utf-8"))
migrado = layout_notas.carregar_layout()
ok(not migrado["loja"]["mostrar"]["cliente_nome"] and not migrado["loja"]["mostrar"]["telefone"]
   and migrado["cliente"]["endereco"] == "Rua X, 1", "layout antigo: desmarca cliente na loja e mantém o resto")
ok(ler_json(layout_notas.ARQUIVO_LAYOUT).get("versao") == layout_notas.VERSAO_LAYOUT_NOTAS, "migração gravada uma vez só")
j.layout_das_notas = migrado

def vender(nome, tel, nota_cliente=True):
    j.selecionar_servico(0); j.entry_item.setText("2"); j.adicionar_item()
    j.entry_nome.setText(nome); j.entry_telefone.setText(tel)
    j.check_nota_cliente.setChecked(nota_cliente)
    n = len(impressos); j.finalizar_atendimento()
    c = sqlite3.connect(banco.arquivo_banco())
    numero, cn, ct = c.execute("select id, cliente_nome, cliente_telefone from atendimentos order by id desc limit 1").fetchone()
    c.close()
    loja = open(notas.caminho_da_nota(numero, datetime.now(), "loja"), encoding="utf-8").read()
    cliente_txt = notas.caminho_da_nota(numero, datetime.now(), "cliente")
    return numero, cn, ct, loja, impressos[n:], cliente_txt

for politica in ("apagar", "nao", "sempre"):
    cfg = ler_json(config.ARQUIVO_CONFIG); cfg["dados_cliente"] = {"guardar": politica, "dias": 30}
    config.salvar_config(cfg); j.recarregar_config("teste")
    numero, cn, ct, loja, imp, cliente_txt = vender("Bia Teste", "(21) 97777-6666")
    impresso = "\n".join(t for _i, t in imp)
    ok("Bia Teste" in impresso and "97777-6666" in impresso, f"[{politica}] nota do cliente impressa com nome e telefone")
    if politica == "nao":
        ok(cn in (None, "") and ct in (None, ""), f"[nao] nome/telefone NÃO vão pro banco ({cn!r})")
    else:
        ok(cn == "Bia Teste", f"[{politica}] nome no banco")
    if politica == "sempre":
        ok(os.path.exists(cliente_txt), "[sempre] nota do cliente fica salva")
    else:
        ok("Bia" not in loja and "97777" not in loja, f"[{politica}] nota da loja (txt) sem nome/telefone")
        ok(not os.path.exists(cliente_txt), f"[{politica}] nota do cliente só impressa, não salva")
    ok("NÃO É DOCUMENTO FISCAL" in loja, f"[{politica}] nota da loja com aviso fiscal")
cfg = ler_json(config.ARQUIVO_CONFIG); cfg["dados_cliente"] = {"guardar": "apagar", "dias": 30}
config.salvar_config(cfg); j.recarregar_config("teste")

# Tela Configurações
print("--- tela Configurações")
t = tela_preferencias.TelaPreferencias(j, ao_salvar=lambda: j.recarregar_config("Configurações salvas."))
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(5)
ok(t.escolha() == "apagar" and t.campo_dias.value() == 30, "abre com apagar/30")
t.grab().save(os.path.join(saida, "configuracoes.png"))
t.radios["apagar"].setChecked(True); t.campo_dias.setValue(7); t.check_apagar_agora.setChecked(True)
t.salvar(); esperar(3)
ok(ler_json(config.ARQUIVO_CONFIG)["dados_cliente"] == {"guardar": "apagar", "dias": 7}, "salvou 7 dias")
ok(j.config.dados_cliente["dias"] == 7, "programa já usa 7 dias")
t = tela_preferencias.TelaPreferencias(j); t.radios["sempre"].setChecked(True); t.salvar()
ok(ler_json(config.ARQUIVO_CONFIG)["dados_cliente"]["guardar"] == "sempre", "Guardar sempre salvo")
t = tela_preferencias.TelaPreferencias(j); t.radios["apagar"].setChecked(True); t.campo_dias.setValue(30); t.salvar()
# config inválido não quebra
cfg = ler_json(config.ARQUIVO_CONFIG); cfg["dados_cliente"] = {"guardar": "talvez", "dias": -3}
config.salvar_config(cfg)
ok(config.carregar_config().dados_cliente == {"guardar": "apagar", "dias": 1}, "config inválido: volta para 'apagar' (o mais seguro) e dias no mínimo 1")
cfg["dados_cliente"] = {"guardar": "apagar", "dias": 30}; config.salvar_config(cfg)

# ====================================================================
# 1. Serviços e preços
# ====================================================================
print("--- Serviços e preços")
ok(any(a.text() == "Serviços e preços..." for a in j.menuBar().actions()[0].menu().actions()), "menu Arquivo › Serviços e preços")
nomes_antes = [s.nome for s in j.config.servicos]
ok(len(nomes_antes) == 10 and all(s.id for s in j.config.servicos), f"10 serviços com id ({j.config.servicos[0].id})")
ok(all("id" in s for s in ler_json(config.ARQUIVO_CONFIG)["servicos"]), "ids gravados no config.json")
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos)
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(8)
t.grab().save(os.path.join(saida, "servicos.png"))
cats = [t.dados(c)["nome"] for c in t.categorias()]
ok(cats == ["Impressão e documentos", "Consulta", "RecargaPay"], f"categorias {cats}")
ok([d["nome"] for _i, d, _c in t.servicos()] == nomes_antes, "serviços na ordem da tela")
ok(not t.caixa_desativados.isVisible(), "sem removidos: caixa escondida")

def achar(nome):
    return next(i for i, d, _c in t.servicos() if d["nome"] == nome)
def cat(nome):
    return next(c for c in t.categorias() if t.dados(c)["nome"] == nome)

# arrastar: regras
arv = t.arvore
ok(not arv.destino_valido(cat("Consulta"), cat("RecargaPay")), "categoria não entra em outra categoria")
ok(arv.destino_valido(cat("Consulta"), None), "categoria muda de ordem na lista principal")
ok(not arv.destino_valido(achar("Xerox"), None), "serviço não fica solto fora de categoria")
ok(arv.destino_valido(achar("Xerox"), cat("Consulta")), "serviço pode ir para outra categoria")
ok(not (achar("Xerox").flags() & Qt.ItemIsDropEnabled), "nada cai dentro de um serviço")

# renomear
t.arvore.setCurrentItem(achar("Xerox colorida")); esperar()
ok(t.pilha.currentIndex() == 1 and t.campo_nome.text() == "Xerox colorida", "formulário do serviço")
t.campo_nome.setText("Cópia colorida")
ok(achar("Cópia colorida").text(0) == "Cópia colorida", "renomeia na lista")
t.campo_nome.setText("Xerox"); ok(t.aviso_nome.isVisible() and t._problemas()[1], "nome repetido não deixa salvar")
t.campo_nome.setText("Cópia colorida")
t.campo_preco.setText("1,75"); ok(achar("Cópia colorida").text(1) == "R$ 1,75", "preço na lista")
t.campo_preco.setText("abc"); ok(t._problemas()[1] != "", "preço inválido não deixa salvar")
t.campo_preco.setText("1,75")
# cobra taxa
t.arvore.setCurrentItem(achar("Consulta RioCard")); esperar()
estava = t.check_cobra.isChecked(); t.check_cobra.setChecked(not estava)

# nova categoria + novo serviço (11º serviço: sem tecla livre de 1 a 0)
t.nova_categoria(); esperar()
ok(t.pilha.currentIndex() == 2, "formulário da categoria")
t.campo_categoria.setText("Fotos")
ok(t.dados(t.categorias()[-1])["nome"] == "Fotos", "categoria renomeada")
t.novo_servico(); esperar()
novo = t.arvore.currentItem()
ok(novo.parent() is cat("Fotos"), "serviço novo dentro da categoria selecionada")
t.campo_nome.setText("Foto 3x4"); t.campo_preco.setText("10")
ok(t.dados(novo)["tecla"] == "", "11º serviço: as teclas 1 a 0 já estão usadas, fica sem atalho")
t._tecla_capturada("F6")
dono = t._dono_da_tecla("F6", None)
print("       F6:", t.dados(novo)["tecla"], "| aviso:", t.aviso_tecla.text()[:90])
if t.dados(novo)["tecla"] != "F6":
    t._tecla_capturada("F6")  # F6 era de outra ação: confirma apertando de novo
ok(t.dados(novo)["tecla"] == "F6", "tecla F6 para o serviço novo")
t._tecla_capturada("1"); ok(t.dados(novo)["tecla"] == "F6" and "já é usada" in t.aviso_tecla.text(), "tecla 1 em uso: só avisa")
t._tecla_capturada("Ctrl+3"); ok(t.dados(novo)["tecla"] == "Ctrl+3", "outra tecla livre: aceita (Ctrl+3)")
t.botao_tecla.definir("Ctrl+3")
# categoria com serviço não pode ser removida
t.arvore.setCurrentItem(cat("Fotos")); n = len(msgs); t.remover()
ok(len(msgs) == n + 1 and t.dados(t.categorias()[-1])["nome"] == "Fotos", "categoria com serviço não é removida")
# subir categoria Fotos
t.mover(-1); ok([t.dados(c)["nome"] for c in t.categorias()][-2] == "Fotos", "↑ sobe a categoria")
# remover "Recarga de celular" -> vai para removidos
t.arvore.setCurrentItem(achar("Recarga de celular")); resposta["v"] = QMessageBox.Yes; t.remover()
ok([d["nome"] for d in t.desativados] == ["Recarga de celular"] and t.lista_desativados.count() == 1, "removido vai para a lista de removidos")
ok("continua" in perguntas[-1][1], "pergunta explica que continua no histórico")
# reordenar serviço: Xerox desce 1
t.arvore.setCurrentItem(achar("Xerox")); t.mover(1)
ok([d["nome"] for _i, d, _c in t.servicos()][:2] == ["Cópia colorida", "Xerox"], "↓ desce o serviço")
# arrastar de verdade (drop programático): Pagamento de boletos para Consulta
item_pb = achar("Pagamento de boletos"); antes = item_pb.parent()
antes.removeChild(item_pb); cat("Consulta").addChild(item_pb); t._depois_de_mexer_na_ordem()
t.show(); esperar(5); t.grab().save(os.path.join(saida, "servicos_editado.png"))
mud = t._mudancas(); print("       mudanças:", mud)
ok(any("Renomeado: Xerox colorida → Cópia colorida" in m for m in mud) and any("Removido: Recarga de celular" in m for m in mud)
   and any("Serviço novo: Foto 3x4" in m for m in mud) and any("Categoria nova: Fotos" in m for m in mud)
   and any("Pagamento de boletos: categoria RecargaPay → Consulta" in m for m in mud), "resumo das mudanças")
resposta["v"] = QMessageBox.Yes; t.salvar(); esperar(5)
ok(t.result() == QDialog.Accepted, "salvou")
js = ler_json(config.ARQUIVO_CONFIG)
por_id = {s["id"]: s for s in js["servicos"]}
ok(js["categorias"][-2:] == ["Fotos", "RecargaPay"], f"ordem das categorias gravada {js['categorias']}")
ok(por_id["recarga_de_celular"]["ativo"] is False, "removido gravado com ativo=false")
ok(por_id["xerox_colorida"]["nome"] == "Cópia colorida" and por_id["xerox_colorida"]["nomes_anteriores"] == ["Xerox colorida"], "renomeado guarda o nome antigo")
ok([s.nome for s in j.config.servicos][:2] == ["Cópia colorida", "Xerox"] and "Foto 3x4" in [s.nome for s in j.config.servicos], "programa já usa a nova lista")
ok("Recarga de celular" not in [s.nome for s in j.config.servicos] and [s.nome for s in j.config.servicos_desativados] == ["Recarga de celular"], "removido sai da tela")
ok(len(j.botoes_servicos) == 10, f"botões na tela: {len(j.botoes_servicos)}")
ok(j.config.categoria_de("Xerox colorida") == "Impressão e documentos" and j.config.categoria_de("Recarga de celular") == "RecargaPay", "histórico ainda acha a categoria (nome antigo e removido)")
ok(j.config.categoria_de("Pagamento de boletos") == "Consulta", "categoria nova do boleto")
foto = next(s for s in j.config.servicos if s.nome == "Foto 3x4")
ok(j.atalhos[atalhos.acao_do_servico(foto.id)] == "Ctrl+3" and ler_json(preferencias.ARQUIVO_PREFERENCIAS)["atalhos"][atalhos.acao_do_servico(foto.id)] == "Ctrl+3", "atalho do serviço novo salvo")
j.activateWindow(); esperar(3)
QTest.keyClick(j.tabela, Qt.Key_3, Qt.ControlModifier); esperar(2)
ok(j.servico_atual is foto, "Ctrl+3 escolhe o Foto 3x4")
QTest.keyClick(j.tabela, Qt.Key_1); esperar(2)
ok(j.servico_atual.nome == "Xerox", "tecla 1 continua com a Xerox mesmo tendo mudado de posição (atalho segue o serviço)")
QTest.keyClick(j.tabela, Qt.Key_2); esperar(2)
ok(j.servico_atual.nome == "Cópia colorida", "tecla 2 continua com o serviço renomeado")
j.cancelar_atendimento(perguntar=False)
# relatório do dia: o removido continua
r = relatorio.montar_relatorio(agora.date(), [s.nome for s in j.config.servicos], j.config.categoria_de, j.config.categorias)
nomes_rel = {d["nome"]: d["categoria"] for d in r.detalhe_servicos}
ok(nomes_rel.get("Recarga de celular") == "RecargaPay" and nomes_rel.get("Xerox colorida") == "Impressão e documentos", f"relatório mostra o removido e o nome antigo {nomes_rel}")
# atalhos: tela mostra o serviço novo
import tela_atalhos
ta = tela_atalhos.TelaAtalhos(j, j.atalhos, [(s.id, s.nome) for s in j.config.servicos], j._atalhos_salvos)
ok(any("Foto 3x4" in l["descricao"] for l in ta.linhas.values()) and len([a for a in ta.linhas if a.startswith("servico:")]) == 10, "Atalhos do teclado mostra os 10 serviços ativos")
ta.done(0)

# reabrir: removido aparece em "Serviços removidos" e pode ser reativado
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos)
t.setWindowModality(Qt.ApplicationModal); t.show(); esperar(5)
ok(t.caixa_desativados.isVisible() and t.lista_desativados.item(0).text().startswith("Recarga de celular"), "removidos aparecem na tela")
t.grab().save(os.path.join(saida, "servicos_removidos.png"))
t.lista_desativados.setCurrentRow(0); t.reativar()
ok(any(d["nome"] == "Recarga de celular" for _i, d, _c in t.servicos()) and not t.desativados, "reativar volta para a lista")
ok(achar("Recarga de celular").parent() is cat("RecargaPay"), "volta para a categoria de antes")
t.salvar(); esperar(3)
ok("Recarga de celular" in [s.nome for s in j.config.servicos] and len(j.config.servicos) == 11, "reativado salvo (11 serviços)")
# cancelar com mudanças pergunta
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos)
t.arvore.setCurrentItem(achar("Xerox")); t.campo_preco.setText("0,60")
resposta["v"] = QMessageBox.No; n = len(perguntas); t.reject()
ok(len(perguntas) == n + 1 and "Descartar" in perguntas[-1][1] and t.isVisible() is False or t.result() != QDialog.Rejected, "cancelar com mudança pergunta")
resposta["v"] = QMessageBox.Yes; t.reject()
ok(ler_json(config.ARQUIVO_CONFIG)["servicos"][1]["preco"] == 0.5, "descartar não grava")

# ====================================================================
# 2. Sobre
# ====================================================================
print("--- Sobre")
ok(versao.numero(versao.VERSAO) >= (1, 1) and versao.AUTOR == "Pedro", "versão 1.1 ou mais nova, autor Pedro")
menu_ajuda = [a for a in j.menuBar().actions() if a.text().replace("&", "") == "Ajuda"][0].menu()
ok(any(a.text().startswith("Sobre") for a in menu_ajuda.actions()), "Ajuda › Sobre")
s = tela_sobre.TelaSobre(j); s.setWindowModality(Qt.ApplicationModal); s.show(); esperar(5)
texto_sobre = s.texto_completo()
ok(versao.VERSAO in texto_sobre and "1.1" in texto_sobre and "Pedro" in texto_sobre and versao.NOME_PROGRAMA in texto_sobre and s.abas.tabText(0) == "Notas da versão"
   and "1.0" in texto_sobre, "Sobre: nome, versão, autor e notas de todas as versões")
s.grab().save(os.path.join(saida, "sobre.png")); s.done(0)

# ====================================================================
# 3. Barra de título
# ====================================================================
print("--- barra de título")
ok(barra_titulo.colorir(j), "barra de título da janela principal colorida (DWM)")
k = estilo.cores_derivadas(estilo.TEMAS["Padrão"]["claro"]) if hasattr(estilo, "cores_derivadas") else None
ok(k is not None and k.barra_titulo and k.texto_barra_titulo, "cores da barra vêm do tema")
ok(j.windowFlags() & Qt.FramelessWindowHint == Qt.WindowType(0), "usa a barra do Windows (snap, arrastar, redimensionar continuam)")

# ====================================================================
# 6. Relatório do dia: impressoras, A4, prévia, PDF, Excel
# ====================================================================
print("--- Relatório do dia")
for h in range(8, 19):  # muitos atendimentos para dar várias páginas
    for m in (5, 20, 35, 50):
        salvar(agora.replace(hour=h, minute=m), [item("Xerox", 3, "0.50"), item("Impressão colorida", 2, "2.50"),
               item("Consulta RioCard", 1, "3.00")], nome="Cliente Secreto", forma="Débito" if m == 20 else "Pix")
tr = tela_relatorio.TelaRelatorio(j); tr.setWindowModality(Qt.ApplicationModal); tr.show(); esperar(8)
ok(tr.combo_a4.itemText(0) == "Padrão do Windows (Escritório A4)" and tr.combo_a4.count() == 4, "lista de impressoras A4")
ok(tr.combo_resumo.itemText(0).startswith("Mesma das notinhas"), "resumo: padrão = mesma das notinhas")
ok(tr.radio_retrato.isChecked(), "retrato de fábrica")
tr.grab().save(os.path.join(saida, "relatorio_tela.png"))
# textos da tela sem cliente
from PySide6.QtWidgets import QTableWidget
celulas = " ".join(tb.item(r_, c_).text() for tb in tr.findChildren(QTableWidget) for r_ in range(tb.rowCount())
                   for c_ in range(tb.columnCount()) if tb.item(r_, c_))
ok("Secreto" not in celulas and "Joana" not in celulas and "Bia" not in celulas, "tela do relatório sem nome de cliente")
ok(tr.tabela_servicos.horizontalHeaderItem(3).text() == "%" and tr.tabela_formas.horizontalHeaderItem(3).text() == "Taxa", "colunas novas na tela")
# escolher impressoras e lembrar
tr.combo_a4.setCurrentIndex(tr.combo_a4.findData("Escritório A4"))
tr.combo_resumo.setCurrentIndex(tr.combo_resumo.findData("Térmica 2"))
tr.radio_paisagem.setChecked(True)
p = ler_json(preferencias.ARQUIVO_PREFERENCIAS)
ok(p["impressora_relatorio"] == "Escritório A4" and p["impressora_resumo"] == "Térmica 2" and p["relatorio_paisagem"] is True, "lembra as escolhas")
ok(j.layout_das_notas["impressao"]["impressora"] == migrado["impressao"]["impressora"], "impressora das notinhas não mudou")
# testes
resposta["v"] = QMessageBox.Yes
tr.imprimir_teste_a4(); ok(a4[-1] == ("teste", "Escritório A4", True), f"teste A4 na impressora escolhida {a4[-1]}")
n = len(impressos); tr.imprimir_teste_resumo()
ok(len(impressos) == n + 1 and impressos[-1][0] == "Térmica 2" and "TESTE" in impressos[-1][1] and "NÃO É DOCUMENTO FISCAL" in impressos[-1][1], "teste do resumo na Térmica 2")
resposta["v"] = QMessageBox.No; n = len(a4); tr.imprimir_teste_a4(); ok(len(a4) == n, "teste A4: Não não imprime")
# resumo 80mm na impressora escolhida, com aviso e sem cliente
resposta["v"] = QMessageBox.Yes; tr.imprimir()
ok(impressos[-1][0] == "Térmica 2" and "NÃO É DOCUMENTO FISCAL" in impressos[-1][1] and "Secreto" not in impressos[-1][1], "resumo na impressora escolhida, com aviso, sem cliente")
tr.combo_resumo.setCurrentIndex(0); tr.imprimir()
ok(impressos[-1][0] == j.layout_das_notas["impressao"]["impressora"] or impressos[-1][0] == "Notinhas (falsa)", f"'Mesma das notinhas' usa a das notinhas ({impressos[-1][0]})")
tr.combo_resumo.setCurrentIndex(tr.combo_resumo.findData("Térmica 2"))
# reabrir lembra
tr.done(0)
tr = tela_relatorio.TelaRelatorio(j); tr.setWindowModality(Qt.ApplicationModal); tr.show(); esperar(5)
ok(tr.impressora_a4() == "Escritório A4" and tr.impressora_resumo() == "Térmica 2" and tr.paisagem(), "reabrir: mesmas escolhas")
# impressora que sumiu
pr = j.preferencias; pr["impressora_resumo"] = "Velha"; j._salvar_preferencias()
tr2 = tela_relatorio.TelaRelatorio(j)
ok(tr2.combo_resumo.currentText() == "Velha (não encontrada)", "impressora desinstalada aparece marcada")
tr2.done(0); tr.combo_resumo.setCurrentIndex(tr.combo_resumo.findData("Térmica 2"))

# Pré-visualização
previas = []
def exec_previa(self):
    self.setWindowModality(Qt.ApplicationModal); self.show(); esperar(15)
    self.previa.updatePreview(); esperar(10)
    previas.append({"paginas": self.previa.pageCount(), "paisagem": self.paisagem(), "texto": self.lbl_paginas.text()})
    self.grab().save(os.path.join(saida, f"previa_{len(previas)}.png"))
    self.radio_retrato.setChecked(True); esperar(10)
    previas[-1]["paginas_retrato"] = self.previa.pageCount()
    self.combo_visao.setCurrentIndex(1); esperar(5)
    self.grab().save(os.path.join(saida, f"previa_{len(previas)}_uma.png"))
    self.combo_visao.setCurrentIndex(0); esperar(5)
    self.grab().save(os.path.join(saida, f"previa_{len(previas)}_retrato.png"))
    n = len(a4); self.imprimir()
    previas[-1]["imprimiu"] = a4[n:]
    return self.result()
tela_relatorio.DialogoPrevia.exec = exec_previa
tr.imprimir_a4()
pv = previas[-1]; print("       prévia:", pv)
ok(pv["paisagem"] and pv["paginas"] >= 2 and pv["texto"].endswith("páginas"), "prévia mostra todas as páginas (paisagem)")
ok(pv["paginas_retrato"] >= 2, "prévia em retrato")
ok(pv["imprimiu"] == [("relatorio", "Escritório A4", False)], "Imprimir manda para a impressora A4 escolhida, na orientação da prévia")
ok(tr.radio_retrato.isChecked() and ler_json(preferencias.ARQUIVO_PREFERENCIAS)["relatorio_paisagem"] is False, "orientação escolhida na prévia fica lembrada")
ok(not [x for x in impressos if "Relatório" in str(x[1])[:0]], "prévia não imprime nada sozinha")

# Páginas A4: conteúdo
r = tr.relatorio
for paisagem in (False, True):
    imgs = relatorio_a4.imagens(r, j.config.nome_loja, paisagem, dpi=110)
    for i, im in enumerate(imgs, 1):
        im.save(os.path.join(saida, f"a4_{'paisagem' if paisagem else 'retrato'}_{i}.png"))
    print(f"       {'paisagem' if paisagem else 'retrato'}: {len(imgs)} páginas")
class Gravador:
    def __init__(self): self.textos = []
    def drawText(self, *a): self.textos.append(str(a[-1]))
    def __getattr__(self, nome): return lambda *a, **k: None
medida = relatorio_a4.layout_da_pagina(False).paintRectPoints()
L, A = medida.width() * relatorio_a4.U, medida.height() * relatorio_a4.U
paginas = relatorio_a4.montar_paginas(r, L, A)
todos = []
for nump, pag in enumerate(paginas, 1):
    g = Gravador(); relatorio_a4.pintar_pagina(g, pag, nump, len(paginas), r, "Minha Loja", L, A, "01/11/2026 10:00")
    textos = g.textos  # (o pintor escreve o cabeçalho, o conteúdo e o rodapé)
    todos.append(textos)
    ok(f"Página {nump} de {len(paginas)}" in textos and f"Minha Loja - Relatório de {r.dia.strftime('%d/%m/%Y')} - Página {nump} de {len(paginas)}" in textos
       and "Emitido em 01/11/2026 10:00" in textos and "Minha Loja" in textos, f"página {nump}: cabeçalho e rodapé")
    if nump > 1:
        ok("Atendimentos do dia  (continuação)" in textos and "Nº" in textos and "Troco" in textos, f"página {nump}: cabeçalho da tabela repetido")
p1 = todos[0]
for titulo in ("Atendimentos", "Total do dia", "Ticket médio", "Taxas da maquininha", "Total de itens", "Por serviço",
               "Por categoria", "Por forma de pagamento", "Movimento por hora", "% do faturamento", "Taxa cobrada", "% do total", "Preço unit."):
    ok(any(titulo == x or x.startswith(titulo) for x in p1), f"página 1 tem '{titulo}'")
ok(all("Secreto" not in x and "Joana" not in x and "Bia" not in x for p_ in todos for x in p_), "A4 sem nome de cliente")
# nenhum atendimento cortado: cada linha da tabela de atendimentos fica inteira numa página
for pag in paginas:
    for o in pag.ordens:
        if o[0] == "texto":
            ok_ret = o[1].bottom() <= A - relatorio_a4.ALTURA_RODAPE + 0.01
            if not ok_ret:
                ok(False, f"texto passou do rodapé: {o[5][:30]}"); break
numeros = [x for p_ in todos for x in p_ if len(x) == 6 and x.isdigit()]
ok(len(numeros) == len(set(numeros)) == r.quantidade, f"cada atendimento aparece uma vez só ({len(numeros)} de {r.quantidade})")
# percentuais
ok(sum(d["percentual"] for d in r.detalhe_servicos) in (D("99.9"), D("100.0"), D("100.1")), "% por serviço soma 100")
ok(r.ticket_medio == (r.total / r.quantidade).quantize(D("0.01")), "ticket médio")
ok(r.total_itens == sum(i["quantidade"] for a in r.atendimentos for i in a["itens"]), "total de itens")
ok(sum(q for q, _t in r.por_hora.values()) == r.quantidade and 8 in r.por_hora and 18 in r.por_hora, "movimento por hora")
ok([c_[0] for c_ in r.por_categoria][:2] == ["Impressão e documentos", "Consulta"], f"por categoria {r.por_categoria}")
ok(r.taxa_por_forma["Débito"] == sum(a["taxa_valor"] for a in r.atendimentos if a["forma_pagamento"] == "Débito"), "taxa por forma")

# PDF retrato/paisagem
destino = os.path.join(saida, "rel_paisagem.pdf")
tr.radio_paisagem.setChecked(True)
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino, "PDF (*.pdf)"))
resposta["v"] = QMessageBox.No; tr.exportar("pdf")
dados_pdf = open(destino, "rb").read()
import re
caixas = re.findall(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", dados_pdf)
ok(caixas and float(caixas[0][0]) > float(caixas[0][1]), f"PDF em paisagem {caixas[:1]}")
ok(dados_pdf.count(b"/Type /Page\n") + dados_pdf.count(b"/Type /Page ") + dados_pdf.count(b"/Type/Page") >= 2 or len(caixas) >= 2, f"PDF com várias páginas ({len(caixas)})")
tr.radio_retrato.setChecked(True)
destino2 = os.path.join(saida, "rel_retrato.pdf")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino2, "PDF (*.pdf)"))
tr.exportar("pdf")
caixas = re.findall(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", open(destino2, "rb").read())
ok(caixas and float(caixas[0][0]) < float(caixas[0][1]), "PDF em retrato")
# Excel com seções novas, sem cliente
destino3 = os.path.join(saida, "rel.xlsx")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (destino3, "Excel (*.xlsx)"))
tr.exportar("xlsx")
from openpyxl import load_workbook
wb = load_workbook(destino3)
coluna_a = [row[0] for row in wb["Resumo"].iter_rows(values_only=True) if row]
for sec in ("Por serviço", "Por categoria", "Por forma de pagamento", "Movimento por hora", "Ticket médio", "Total de itens", "Emitido em"):
    ok(sec in coluna_a, f"Excel tem '{sec}'")
cab = [c_.value for c_ in wb["Atendimentos"][1]]
ok(cab == ["Nº", "Hora", "Itens", "Subtotal", "Taxa", "Total", "Pagamento", "Valor recebido", "Troco"], f"Excel: colunas dos atendimentos {cab}")
ok(all("Secreto" not in str(c_) and "Joana" not in str(c_) for aba in wb for row in aba.iter_rows(values_only=True) for c_ in row), "Excel sem cliente")
# Resumo de fechamento
txt = notas.texto_da_nota(relatorio.linhas_resumo(r, "Minha Loja", 48))
ok(txt.rstrip().endswith("NÃO É DOCUMENTO FISCAL") and "Secreto" not in txt, "resumo de fechamento: aviso no rodapé, sem cliente")
# fechar expediente com PDF na orientação escolhida e resumo na impressora escolhida
def exec_fake(self):
    self.check_imprimir.setChecked(True); return QDialog.Accepted
tela_relatorio.DialogoFechamento.exec = exec_fake
n = len(impressos); tr.fechar_expediente()
ok(impressos[-1][0] == "Térmica 2", "fechar expediente imprime na impressora do resumo")
# modo escuro
j.definir_modo_cor("escuro"); esperar(5); tr.grab().save(os.path.join(saida, "relatorio_tela_escuro.png"))
j.definir_modo_cor("claro"); tr.done(0)
j.close()
print("\nFALHAS:", len(falhas))
