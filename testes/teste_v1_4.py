"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json, glob, zipfile, tempfile, types
from datetime import datetime
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
# Começa SEM dados: o programa "de fábrica" (como numa instalação nova).
for nome in ("config.json", "layout_notas.json", "preferencias.json"):
    if os.path.exists(nome): os.remove(nome)
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QFileDialog, QTabWidget
from PySide6.QtTest import QTest
from PIL import Image
import atualizacao
def sem_internet(*a, **k):
    raise AssertionError("teste tentou acessar a internet")
atualizacao.abrir_url = sem_internet
import estilo, banco, interface, impressao, notas, relatorio, relatorio_a4, config, versao, layout_notas, toque, treino
import backup, tela_loja, tela_notinhas, tela_preferencias, tela_limpar, tela_relatorio

msgs, perguntas, abertos, impressos = [], [], [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
resposta = {"v": QMessageBox.Yes}
def pergunta(p, t, m, *a):
    perguntas.append((t, m)); return resposta["v"]
QMessageBox.question = staticmethod(pergunta)
os.startfile = lambda caminho: abertos.append(caminho)
# NUNCA imprime, nunca acessa a internet, nunca abre o teclado de verdade.
impressao.escolher_impressora = lambda nome: "Teste (falsa)"
impressao.eh_impressora_texto = lambda nome: True
impressao.imprimir_texto = lambda *a: impressos.append(a)
impressao.imprimir_imagem = lambda *a: impressos.append(a)
toque.abrir_teclado_windows = lambda: True
toque.tem_tela_touch = lambda: False

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=5):
    for _ in range(n): QTest.qWait(30)
def ler_json(nome):
    return json.load(open(nome, encoding="utf-8"))
def item(nome, qtd, preco):
    return {"servico": nome, "tipo": "unidade", "quantidade": qtd, "valor_unitario": D(preco),
            "valor_digitado": D(0), "taxa_servico": D(0), "total": D(preco) * qtd, "cobra_taxa_maquininha": True}
def salvar(quando=None, itens=None):
    itens = itens or [item("Xerox", 2, "0.50")]
    sub = sum(i["total"] for i in itens)
    return banco.salvar_atendimento({"data_hora": quando or datetime.now(), "cliente_nome": "", "cliente_telefone": "",
        "forma_pagamento": "Pix", "subtotal": sub, "taxa_percentual": D(0), "taxa_valor": D(0), "total": sub,
        "valor_recebido": None, "troco": None}, itens)

app = QApplication.instance() or QApplication(sys.argv)
banco.criar_tabelas()  # (o main.py faz isso ao abrir)

# ====================================================================
# 1. Dados da loja num lugar só
# ====================================================================
print("--- dados da loja: de fábrica")
c = config.carregar_config()
ok(c.loja["nome"] == "Minha Loja" and c.nome_loja == "Minha Loja", "loja de fábrica: Minha Loja")
ok(c.loja_confirmada is False, "instalação nova: ainda não confirmou (mostra as boas-vindas)")
ok(c.backup == {"pasta": "", "ao_fechar_expediente": False}, "backup de fábrica: pasta padrão, sem automático")

print("--- dados da loja: instalação antiga (antes da 1.4)")
antigo_cfg = ler_json("config.json")
for chave in ("loja", "loja_confirmada", "backup"):
    antigo_cfg.pop(chave, None)
antigo_cfg["nome_loja"] = "Loja do Bairro"
json.dump(antigo_cfg, open("config.json", "w", encoding="utf-8"), ensure_ascii=False)
antigo_layout = json.loads(json.dumps(layout_notas.layout_padrao()))
antigo_layout["versao"] = 2
antigo_layout["loja"].update({"nome_loja": "Loja do Bairro", "endereco": "Rua A, 10", "telefone": "(21) 3333-4444", "cnpj": ""})
antigo_layout["cliente"].update({"nome_loja": "Loja do Bairro", "endereco": "", "telefone": "(21) 3333-4444", "cnpj": ""})
for via in ("loja", "cliente"):
    for chave in ("loja_nome", "loja_endereco", "loja_telefone", "loja_cnpj"):
        antigo_layout[via]["mostrar"].pop(chave, None)
json.dump(antigo_layout, open("layout_notas.json", "w", encoding="utf-8"), ensure_ascii=False)
lay = layout_notas.carregar_layout()
c = config.carregar_config()
ok(c.loja["nome"] == "Loja do Bairro" and c.loja["endereco"] == "Rua A, 10" and c.loja["telefone"] == "(21) 3333-4444",
   f"junta o nome e o cabeçalho antigos nos dados da loja: {c.loja}")
ok(c.loja_confirmada is False, "instalação antiga: mostra a janela para confirmar")
gravado = ler_json("layout_notas.json")
ok(gravado["versao"] == 3 and all(k not in gravado[v] for v in ("loja", "cliente") for k in ("nome_loja", "endereco", "telefone", "cnpj", "logo")),
   "layout_notas.json não guarda mais o cabeçalho")
ok(lay["cliente"]["mostrar"]["loja_endereco"] is False and lay["loja"]["mostrar"]["loja_endereco"] is True,
   "endereço que estava vazio na nota do cliente continua escondido nela")
ok(lay["loja"]["nome_loja"] == "Loja do Bairro" and lay["cliente"]["endereco"] == "Rua A, 10", "as duas notas usam os dados da loja")

print("--- dados da loja: gravar")
config.salvar_loja({"nome": "Papelaria Central", "endereco": "Av. B, 20", "telefone": "(21) 2222-1111", "cnpj": "12.345.678/0001-90", "logo": ""})
c = config.carregar_config()
ok(c.nome_loja == "Papelaria Central" and c.loja_confirmada and ler_json("config.json")["nome_loja"] == "Papelaria Central",
   "salvar_loja grava a loja, a cópia nome_loja e confirma")
lay = layout_notas.carregar_layout()
at = {"data_hora": datetime.now(), "cliente_nome": "", "cliente_telefone": "", "forma_pagamento": "Pix",
      "subtotal": D("1"), "taxa_percentual": D(0), "taxa_valor": D(0), "total": D("1"), "valor_recebido": None, "troco": None}
texto = str(notas.montar_linhas(lay["loja"], 1, at, [item("Xerox", 2, "0.50")], "loja", True))
ok("Papelaria Central" in texto and "Av. B, 20" in texto and "12.345.678/0001-90" in texto, "notinha usa os dados da loja")
modelo = json.loads(json.dumps(lay["loja"])); modelo["mostrar"]["loja_cnpj"] = False; modelo["mostrar"]["loja_endereco"] = False
texto = str(notas.montar_linhas(modelo, 1, at, [item("Xerox", 2, "0.50")], "loja", True))
ok("Papelaria Central" in texto and "Av. B, 20" not in texto and "12.345.678" not in texto, "caixas desmarcadas escondem o dado na nota")

print("--- janela de boas-vindas")
config.salvar_loja(config.carregar_config().loja, confirmada=False)
d = tela_loja.DialogoBoasVindas(None, config.carregar_config().loja); d.show(); esperar()
ok(d.formulario.campo_nome.text() == "Papelaria Central", "vem preenchida com o que já estava configurado")
ok("Confira" in " ".join(w.text() for w in d.findChildren(type(d.formulario.previa_logo))), "pede só para conferir (instalação antiga)")
d.grab().save(os.path.join(saida, "print_boas_vindas.png"))
d.formulario.campo_nome.setText(""); n = len(msgs); d.confirmar()
ok(len(msgs) == n + 1 and d.isVisible() and not config.carregar_config().loja_confirmada, "sem nome: avisa e não fecha")
d.formulario.campo_nome.setText("Copiadora Sol"); d.formulario.campo_telefone.setText("21999998888")
d.formulario.campo_telefone.textEdited.emit("21999998888")
d.confirmar(); c = config.carregar_config()
ok(c.nome_loja == "Copiadora Sol" and c.loja_confirmada and not d.isVisible() and d.salvou, "Confirmar grava e fecha")
ok(c.loja["telefone"] == "(21) 99999-8888", f"telefone formatado: {c.loja['telefone']}")
config.salvar_loja(c.loja, confirmada=False)
d = tela_loja.DialogoBoasVindas(None, config.carregar_config().loja); d.show(); esperar(); d.reject()
ok(config.carregar_config().loja_confirmada and not d.isVisible(), "fechar pelo X também conta (não aparece de novo)")
# logo
imagem = os.path.join(saida, "logo_teste.png"); Image.new("RGB", (60, 30), "red").save(imagem)
f = tela_loja.FormularioLoja(config.carregar_config().loja); f.escolher_logo(imagem)
ok(f.valores()["logo"].startswith("imagens") and os.path.exists(os.path.join(pasta, f.valores()["logo"])), f"logo copiada para imagens/: {f.valores()['logo']}")
ok(f.btn_remover_logo.isEnabled() and f.previa_logo.pixmap() is not None and not f.previa_logo.pixmap().isNull(), "mostra a prévia da logo")
lixo = os.path.join(saida, "nao_e_imagem.png"); open(lixo, "w").write("texto")
n = len(msgs); antes = f.valores()["logo"]; f.escolher_logo(lixo)
ok(len(msgs) == n + 1 and f.valores()["logo"] == antes, "arquivo que não é imagem: avisa e mantém a logo")
f.remover_logo(); ok(f.valores()["logo"] == "" and not f.btn_remover_logo.isEnabled(), "remover logo")

print("--- janela principal: boas-vindas só uma vez e título")
config.salvar_loja(config.carregar_config().loja, confirmada=False)
j = interface.JanelaPrincipal(); j.mostrar(); esperar(10)
vistas = []
class BoasVindasFalsa:
    def __init__(self, pai, loja): vistas.append(loja["nome"])
    def exec(self): config.salvar_loja({**config.carregar_config().loja, "nome": "Loja Nova"}); return QDialog.Accepted
interface.DialogoBoasVindas = BoasVindasFalsa
j.apos_abrir(None); esperar()
ok(vistas == ["Copiadora Sol"], "apos_abrir mostra as boas-vindas na primeira vez")
ok(j.windowTitle() == f"{versao.NOME_PROGRAMA} - Loja Nova" and j.config.nome_loja == "Loja Nova", f"título com o nome novo: {j.windowTitle()}")
ok(j.layout_das_notas["loja"]["nome_loja"] == "Loja Nova", "notinhas da janela já com o nome novo")
j.apos_abrir(None); ok(len(vistas) == 1, "não aparece de novo")
j.close(); esperar()
codigo = open(os.path.join(pasta, "main.py"), encoding="utf-8").read()
ok("apos_abrir" in codigo, "main.py chama apos_abrir depois da tela de abertura")

print("--- Configurar notinhas: só mostrar/esconder")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(10)
t = tela_notinhas.TelaNotinhas(j, ao_salvar=lambda layout: None); t.show(); esperar(20)
ok(not any(hasattr(t, a) for a in ("campo_nome", "campo_endereco", "campo_telefone", "campo_cnpj", "campo_logo")),
   "sem campos de texto do cabeçalho")
ok(list(t.checks_cabecalho) == ["loja_nome", "loja_endereco", "loja_telefone", "loja_cnpj"], "uma caixa para cada dado da loja")
ok("Alterar dados da loja" in t.lbl_link_loja.text(), "link Alterar dados da loja")
ok("Loja Nova" in t.checks_cabecalho["loja_nome"].text() and "12.345.678/0001-90" in t.checks_cabecalho["loja_cnpj"].text(),
   f"mostra o valor ao lado: {t.checks_cabecalho['loja_nome'].text()} / {t.checks_cabecalho['loja_cnpj'].text()}")
t.grab().save(os.path.join(saida, "print_notinhas_1_4.png"))
t.checks_cabecalho["loja_telefone"].setChecked(False); esperar(10)
ok(t.dados["loja"]["mostrar"]["loja_telefone"] is False and t.dados["cliente"]["mostrar"]["loja_telefone"] is True, "desmarcar vale só para a nota escolhida")
t.salvar(); g = ler_json("layout_notas.json")
ok(g["loja"]["mostrar"]["loja_telefone"] is False and "nome_loja" not in g["loja"], "salva a caixa, sem gravar o nome da loja no layout")
class DadosLojaFalso:
    def __init__(self, pai):
        self.formulario = types.SimpleNamespace(valores=lambda: {"logo": ""})
    def exec(self):
        config.salvar_loja({**config.carregar_config().loja, "nome": "Loja Alterada", "cnpj": "99.999.999/0001-99"})
        return QDialog.Accepted
tela_loja.DialogoDadosLoja, original_dialogo = DadosLojaFalso, tela_loja.DialogoDadosLoja
t.alterar_dados_da_loja(); esperar(10)
ok(t.dados["loja"]["nome_loja"] == "Loja Alterada" and "99.999.999/0001-99" in t.checks_cabecalho["loja_cnpj"].text(),
   "o link atualiza a tela na hora")
ok(j.windowTitle().endswith("Loja Alterada"), "o link atualiza o título da janela principal")
ok(t._como_texto() == t._dados_salvos, "mudar os dados da loja não conta como alteração pendente das notinhas")
t.reject(); tela_loja.DialogoDadosLoja = original_dialogo
d = tela_loja.DialogoDadosLoja(j); ok(d.formulario.campo_nome.text() == "Loja Alterada", "janela Dados da loja vem preenchida")
d.formulario.campo_nome.setText(""); n = len(msgs); d.salvar(); ok(len(msgs) == n + 1, "Dados da loja: sem nome avisa")
d.reject()

print("--- Preferências: abas Loja e Backup")
p = tela_preferencias.TelaPreferencias(j, ao_salvar=lambda: j.recarregar_config("Preferências salvas."))
nomes_abas = [p.abas.tabText(i) for i in range(p.abas.count())]
ok(nomes_abas[0] == "Loja" and "Backup" in nomes_abas, f"abas: {nomes_abas}")
ok(p.formulario_loja.campo_nome.text() == "Loja Alterada", "aba Loja preenchida")
p.abas.setCurrentIndex(0); p.show(); esperar(); p.grab().save(os.path.join(saida, "print_preferencias_loja.png"))
p.abas.setCurrentIndex(nomes_abas.index("Backup")); esperar(); p.grab().save(os.path.join(saida, "print_preferencias_backup.png"))
ok("(padrão)" in p.lbl_pasta_backup.text() and not p.btn_pasta_padrao.isEnabled(), "pasta padrão mostrada")
pasta_pendrive = os.path.join(saida, "pendrive")
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: pasta_pendrive)
p.escolher_pasta_backup(); ok(p.lbl_pasta_backup.text() == os.path.normpath(pasta_pendrive) and p.btn_pasta_padrao.isEnabled(), "escolher pasta")
p.formulario_loja.campo_nome.setText(""); n = len(msgs); p.salvar()
ok(len(msgs) == n + 1 and p.abas.currentIndex() == 0 and p.isVisible(), "nome vazio: volta para a aba Loja e avisa")
p.formulario_loja.campo_nome.setText("Loja Preferida"); p.check_backup_fechar.setChecked(True); p.salvar()
c = config.carregar_config()
ok(c.nome_loja == "Loja Preferida" and c.backup == {"pasta": os.path.normpath(pasta_pendrive), "ao_fechar_expediente": True},
   f"salva loja e backup: {c.backup}")
ok(j.windowTitle().endswith("Loja Preferida"), "título atualizado depois das Preferências")
config.atualizar_config(backup={"pasta": "", "ao_fechar_expediente": False}); j.recarregar_config()

print("--- relatórios e testes de impressão usam o nome da loja")
salvar(); salvar()
tr = tela_relatorio.TelaRelatorio(j); esperar()
usados = []
relatorio.imprimir_teste_resumo = lambda layout, nome, imp="": usados.append(("resumo", nome))
relatorio_a4.imprimir_teste = lambda imp, nome, paisagem=False: usados.append(("a4", nome))
relatorio.exportar_pdf = lambda r, nome, caminho, paisagem=False: usados.append(("pdf", nome)) or caminho
relatorio.exportar_excel = lambda r, nome, caminho: usados.append(("excel", nome)) or caminho
tr.imprimir_teste_resumo(); tr.imprimir_teste_a4()
tr._salvar("pdf", os.path.join(saida, "r.pdf")); tr._salvar("xlsx", os.path.join(saida, "r.xlsx"))
ok({u[0] for u in usados} == {"resumo", "a4", "pdf", "excel"} and all(u[1] == "Loja Preferida" for u in usados), f"todos com o nome da loja: {usados}")
ok("Loja Preferida" in str(relatorio.linhas_resumo(tr.relatorio, j.config.nome_loja, 48)), "resumo de fechamento com o nome")

# ====================================================================
# 2. Backup
# ====================================================================
print("--- backup: fazer")
qtd = banco.contar_atendimentos()
zip1 = backup.fazer_backup()
ok(os.path.dirname(zip1) == banco.PASTA_BACKUPS and os.path.basename(zip1).startswith("EasyServ_backup_") and zip1.endswith(".zip"),
   f"zip com data e hora em backups/: {os.path.basename(zip1)}")
with zipfile.ZipFile(zip1) as z:
    nomes = z.namelist(); info = json.loads(z.read("backup_easyserv.json"))
ok({"easyserv.db", "config.json", "layout_notas.json", "backup_easyserv.json"} <= set(nomes), f"tem banco e configurações: {nomes}")
ok(info["atendimentos"] == qtd and info["versao"] == versao.VERSAO, f"ficha do backup: {info}")
ok(not any("treino" in n for n in nomes), "o treino não entra no backup")
lido = backup.ler_backup(zip1)
ok(lido["atendimentos"] == qtd and abs((datetime.now() - lido["data_hora"]).total_seconds()) < 120, "ler_backup: data e quantidade")
ok(f"{qtd} atendimento" in backup.descrever(lido) and lido["data_hora"].strftime("%d/%m/%Y") in backup.descrever(lido), backup.descrever(lido))
zip2 = backup.fazer_backup(); ok(zip2 != zip1 and os.path.exists(zip1), "dois backups seguidos não se sobrescrevem")
config.atualizar_config(backup={"pasta": pasta_pendrive, "ao_fechar_expediente": False})
zip3 = backup.fazer_backup(); ok(os.path.dirname(zip3) == pasta_pendrive, "vai para a pasta escolhida (ex.: pendrive)")
arquivo_no_lugar = os.path.join(saida, "nao_e_pasta.txt"); open(arquivo_no_lugar, "w").close()
config.atualizar_config(backup={"pasta": os.path.join(arquivo_no_lugar, "x"), "ao_fechar_expediente": False})
try:
    backup.fazer_backup(); ok(False, "pasta impossível deveria dar erro")
except backup.ErroBackup as erro:
    ok("pendrive" in str(erro), "pasta que não existe (pendrive tirado): erro explicado")
config.atualizar_config(backup={"pasta": "", "ao_fechar_expediente": False})

print("--- backup: arquivos ruins")
ruim = os.path.join(saida, "ruim.zip"); open(ruim, "w").write("não é zip")
try: backup.ler_backup(ruim); ok(False, "zip estragado")
except backup.ErroBackup: ok(True, "zip estragado: erro claro")
outro = os.path.join(saida, "outro.zip")
with zipfile.ZipFile(outro, "w") as z: z.writestr("fotos/a.txt", "x")
try: backup.ler_backup(outro); ok(False, "zip de outra coisa")
except backup.ErroBackup as erro: ok("não é um backup" in str(erro), "zip que não é backup: recusa")

print("--- backup: restaurar")
salvar(); salvar(); salvar()
config.salvar_loja({**config.carregar_config().loja, "nome": "Nome Depois do Backup"})
qtd_agora = banco.contar_atendimentos()
seguranca = backup.restaurar_backup(zip1)
ok(banco.contar_atendimentos() == qtd and config.carregar_config().nome_loja == "Loja Preferida", "restaurou banco e config.json")
ok("_antes_de_restaurar" in seguranca and backup.ler_backup(seguranca)["atendimentos"] == qtd_agora, "antes, guardou o estado atual")
perigoso = os.path.join(saida, "perigoso.zip")
with zipfile.ZipFile(zip1) as z, zipfile.ZipFile(perigoso, "w") as novo:
    for n in z.namelist(): novo.writestr(n, z.read(n))
    novo.writestr("../fora.txt", "x"); novo.writestr("imagens/../../fora2.txt", "x"); novo.writestr("main.py", "# trocado")
backup.restaurar_backup(perigoso)
ok(not os.path.exists(os.path.join(os.path.dirname(pasta), "fora.txt")) and not os.path.exists(os.path.join(os.path.dirname(pasta), "fora2.txt"))
   and "# trocado" not in open(os.path.join(pasta, "main.py"), encoding="utf-8").read(), "só arquivos conhecidos saem do zip")

print("--- backup: menu e janela")
j.close(); esperar()
j = interface.JanelaPrincipal(); j.mostrar(); esperar(10)
menu_arquivo = j.menuBar().actions()[0].menu()
sub = next(a.menu() for a in menu_arquivo.actions() if a.menu() and a.text() == "Backup")
textos = [a.text() for a in sub.actions() if a.text()]
ok(textos == ["Fazer backup agora", "Escolher pasta do backup...", "Abrir pasta do backup", "Restaurar backup..."], f"Arquivo › Backup: {textos}")
n = len(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.zip"))); j.fazer_backup_agora()
ok(len(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.zip"))) == n + 1 and "Backup salvo em" in msgs[-1][2], "Fazer backup agora")
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: pasta_pendrive)
j.escolher_pasta_backup(); ok(config.carregar_config().backup["pasta"] == os.path.normpath(pasta_pendrive), "Escolher pasta do backup grava no config")
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: banco.PASTA_BACKUPS)
j.escolher_pasta_backup(); ok(config.carregar_config().backup["pasta"] == "", "escolher a pasta padrão volta para o padrão")
j.abrir_pasta_backup(); ok(abertos[-1] == banco.PASTA_BACKUPS, "Abrir pasta do backup")
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (zip1, ""))
j.carrinho.append({"x": 1}); n = len(msgs); j.restaurar_backup()
ok(len(msgs) == n + 1 and "Finalize" in msgs[-1][2], "não restaura no meio de um atendimento"); j.carrinho.clear()
resposta["v"] = QMessageBox.No; n = len(perguntas); j.restaurar_backup()
ok(len(perguntas) == n + 1 and "atendimento(s)" in perguntas[-1][1] and "backup do estado atual" in perguntas[-1][1] and j.isVisible(),
   "mostra data e quantidade e pede confirmação (Não = nada muda)")
resposta["v"] = QMessageBox.Yes; j.restaurar_backup(); esperar(5)
ok(not j.isVisible() and j._sem_salvar_ao_fechar and "restaurado" in msgs[-1][2], "Sim: restaura e fecha para abrir de novo")

print("--- backup automático ao fechar o expediente")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(10)
avisos = []
def fechamento_sem_pdf(self):
    """Simula a pessoa clicando em Fechar expediente sem PDF, Excel nem impressão."""
    for check in (self.check_pdf, self.check_excel, self.check_imprimir):
        check.setChecked(False)
    avisos.append(hasattr(self, "lbl_backup"))
    return QDialog.Accepted
tela_relatorio.DialogoFechamento.exec = fechamento_sem_pdf
def fechar_expediente():
    tr = tela_relatorio.TelaRelatorio(j); esperar()
    n = len(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.zip")))
    tr.fechar_expediente()
    return avisos[-1], len(glob.glob(os.path.join(banco.PASTA_BACKUPS, "*.zip"))) - n
aviso, novos = fechar_expediente()
ok(novos == 0 and not aviso, "desligado: não faz backup")
config.atualizar_config(backup={"pasta": "", "ao_fechar_expediente": True}); j.recarregar_config()
aviso, novos = fechar_expediente()
ok(novos == 1 and aviso and "Backup:" in msgs[-1][2], "ligado: faz o backup e avisa no fechamento")
treino.ligar(True); banco.criar_tabelas()  # (como o menu Modo treinamento faz)
aviso, novos = fechar_expediente(); ok(novos == 0 and not aviso, "no modo treinamento nunca faz backup")
treino.ligar(False)
config.atualizar_config(backup={"pasta": "", "ao_fechar_expediente": False}); j.recarregar_config()

# ====================================================================
# 3. Limpar dados: ajuda visível
# ====================================================================
print("--- limpar dados")
tl = tela_limpar.TelaLimpar(j); tl.show(); esperar()
ok(tl.lbl_ajuda_confirmar.isVisible() and "LIMPAR" in tl.lbl_ajuda_confirmar.text() and not tl.btn_apagar.isEnabled(),
   f"texto de ajuda visível: {tl.lbl_ajuda_confirmar.text()}")
tl.radio_tudo.setChecked(True); tl.campo_confirmar.setText("limpar"); esperar()
ok(tl.btn_apagar.isEnabled() and "liberado" in tl.lbl_ajuda_confirmar.text(), "depois de digitar: avisa que liberou")
tl.grab().save(os.path.join(saida, "print_limpar.png"))
tl.campo_confirmar.setText("LIMPA"); ok(not tl.btn_apagar.isEnabled() and "só é liberado" in tl.lbl_ajuda_confirmar.text(), "palavra incompleta: volta a explicar")
tl.reject()

# ====================================================================
# 4. Atualização: mensagens separadas
# ====================================================================
print("--- atualização")
import io
class Resposta(io.BytesIO):
    def __init__(self, dados): super().__init__(dados); self.headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
def github(tag):
    def abrir(pedido, timeout=None):
        return Resposta(json.dumps({"tag_name": tag, "name": tag, "draft": False, "prerelease": False, "body": "",
            "assets": [{"name": f"EasyServ_Setup_{tag.lstrip('v')}.exe", "size": 1, "browser_download_url": "https://x/s.exe"}]}).encode())
    return abrir
atualizacao.abrir_url = github("v" + versao.VERSAO)
ok(atualizacao.verificar("x/y") == (atualizacao.ATUAL, None), "mesma versão: ATUAL")
atualizacao.abrir_url = github("v9.9")
s, l = atualizacao.verificar("x/y"); ok(s == atualizacao.NOVA and l.versao == "9.9", "versão nova: NOVA")
atualizacao.abrir_url = sem_internet
ok(atualizacao.verificar("x/y") == (atualizacao.SEM_RESPOSTA, None) and atualizacao.consultar("x/y") is None, "sem internet: SEM_RESPOSTA")
atualizacao.abrir_url = lambda *a, **k: Resposta(b"<html>erro</html>")
ok(atualizacao.verificar("x/y")[0] == atualizacao.SEM_RESPOSTA, "resposta estranha: SEM_RESPOSTA")
atualizacao.verificar = lambda *a, **k: (atualizacao.ATUAL, None); n = len(msgs); j.procurar_atualizacoes()
ok(msgs[-1][2].startswith("Você já está com a versão mais nova") and "internet" not in msgs[-1][2], f"mensagem 1: {msgs[-1][2]!r}")
atualizacao.verificar = lambda *a, **k: (atualizacao.SEM_RESPOSTA, None); j.procurar_atualizacoes()
ok(msgs[-1][2].startswith("Não foi possível consultar as atualizações (sem internet?)") and "versão mais nova" not in msgs[-1][2],
   f"mensagem 2: {msgs[-1][2][:60]!r}")
atualizacao.abrir_url = sem_internet

# ====================================================================
# 5. Layout Touch e modo tablet em telas de 1440 px ou menores
# ====================================================================
print("--- layout Touch / modo tablet")
# (mede pela janela: o computador do teste pode ter outro monitor maior ou em pé)
j._largura_disponivel = types.MethodType(lambda self: getattr(self, "_largura_alvo", None) or self.width(), j)
def conferir(rotulo, largura):
    esperar(15)
    apertados = [n for n, p in j.paineis.items() if p.isVisible() and p.width() + 2 < p.widget().minimumSizeHint().width()]
    fin = j.btn_finalizar
    inteiro = fin.visibleRegion().boundingRect().height() >= fin.height() - 1
    ok(j.width() <= largura and not apertados and inteiro,
       f"{rotulo}: janela {j.width()} <= {largura}, nada cortado {apertados}, Finalizar inteiro ({'3' if j._touch_estreito else '4'} colunas)")
for largura, altura in ((1440, 900), (1366, 768), (1280, 800)):
    j.definir_modo_tablet(False); j.usar_layout("Padrão"); esperar(5)
    j.showNormal(); j.resize(largura, altura); j.usar_layout("Touch"); esperar(5); j.resize(largura, altura); j.usar_layout("Touch")
    conferir(f"Touch {largura}x{altura}", largura)
    if largura == 1440: j.grab().save(os.path.join(saida, "print_touch_1440.png"))
    j.definir_modo_tablet(True)
    conferir(f"tablet {largura}x{altura}", largura)
    j.grab().save(os.path.join(saida, f"print_tablet_{largura}.png"))
ok(j._touch_estreito and j.paineis["cliente"] in j.tabifiedDockWidgets(j.paineis["pagamento"]), "3 colunas: Cliente em aba com o Pagamento")
j.definir_modo_tablet(False); esperar(15)
j.resize(1920, 1000); j.usar_layout("Touch"); esperar(15)
ok(not j._touch_estreito, "tela larga: Touch continua com 4 colunas")
j.usar_layout("Padrão"); esperar(15)
largura_padrao = j.minimumSizeHint().width()
j.definir_modo_tablet(True); esperar(10); j.definir_modo_tablet(False); esperar(15)
ok(j.preferencias["layout_atual"] == "Padrão" and j.minimumSizeHint().width() <= largura_padrao + 2, f"depois de desligar o tablet a janela não fica mais larga ({j.minimumSizeHint().width()} x {largura_padrao})")
j._sem_salvar_ao_fechar = True; j.close()

print(f"\n{len(falhas)} falha(s)")
