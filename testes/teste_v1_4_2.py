"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py

Versão 1.4.2: módulo de impressão (mensagens e log), Tomate MDK-581 (58mm), ESC/POS direto,
largura ajustável, gaveta, Detectar e o resumo na mesma térmica.

NUNCA imprime de verdade: o win32print, o win32ui, o win32con e o PIL.ImageWin são trocados
por módulos FALSOS (sys.modules), que só anotam o que o programa mandaria para a impressora.
"""
import sys, os, json, types
from datetime import datetime
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
for nome in ("config.json", "layout_notas.json", "preferencias.json"):
    if os.path.exists(nome): os.remove(nome)
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from PIL import Image
import atualizacao
atualizacao.abrir_url = lambda *a, **k: (_ for _ in ()).throw(AssertionError("teste tentou acessar a internet"))
import impressao, notas, layout_notas, relatorio, config, banco, toque, interface, tela_notinhas

msgs, perguntas = [], []
QMessageBox.information = staticmethod(lambda p, t, m, *a: msgs.append(("info", t, m)))
QMessageBox.warning = staticmethod(lambda p, t, m, *a: msgs.append(("aviso", t, m)))
QMessageBox.critical = staticmethod(lambda p, t, m, *a: msgs.append(("erro", t, m)))
respostas = []  # respostas das perguntas, em ordem (vazio = Sim)
def pergunta(p, t, m, *a):
    perguntas.append((t, m)); return respostas.pop(0) if respostas else QMessageBox.Yes
QMessageBox.question = staticmethod(pergunta)
os.startfile = lambda caminho: None
toque.abrir_teclado_windows = lambda: True
toque.tem_tela_touch = lambda: False

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)
def esperar(n=5):
    for _ in range(n): QTest.qWait(30)

# ====================================================================
# Impressoras FALSAS (nada chega a uma impressora de verdade)
# ====================================================================
IMPRESSORAS = {
    # a impressora da loja com o driver "Generic / Text Only" (só texto)
    "Tomate MDK-581 (texto)": {"pDriverName": "Generic / Text Only", "dpi": 203, "largura": 384},
    # a mesma com o driver do fabricante (gráfico), 58mm a 203 dpi
    "Tomate MDK-581": {"pDriverName": "POS-58 Printer Driver", "dpi": 203, "largura": 384},
    "POS-80": {"pDriverName": "POS-80C", "dpi": 203, "largura": 576},
}
estado = {"padrao": "Tomate MDK-581", "falhar_raw": set(), "falhar_dc": set(), "status": {}}
trabalhos = []  # (impressora, tipo, dados)

w32print = types.ModuleType("win32print")
w32print.PRINTER_ENUM_LOCAL, w32print.PRINTER_ENUM_CONNECTIONS = 2, 4
w32print.EnumPrinters = lambda flags: [(0, "", nome, "") for nome in IMPRESSORAS]
w32print.GetDefaultPrinter = lambda: estado["padrao"]
def abrir(nome):
    if nome not in IMPRESSORAS: raise RuntimeError("impressora não existe")
    return {"nome": nome, "dados": b""}
w32print.OpenPrinter = abrir
w32print.GetPrinter = lambda h, nivel: {"pDriverName": IMPRESSORAS[h["nome"]]["pDriverName"],
                                        "Status": estado["status"].get(h["nome"], 0), "Attributes": 0}
w32print.ClosePrinter = lambda h: None
def comecar_doc(h, nivel, info):
    if h["nome"] in estado["falhar_raw"]: raise RuntimeError("(1804, 'StartDocPrinter', 'O tipo de dados especificado é inválido.')")
    h["tipo"] = info[2]; h["documento"] = info[0]; return 77
w32print.StartDocPrinter = comecar_doc
w32print.StartPagePrinter = lambda h: None
def escrever(h, dados):
    h["dados"] += dados; return len(dados)
w32print.WritePrinter = escrever
w32print.EndPagePrinter = lambda h: None
w32print.EndDocPrinter = lambda h: trabalhos.append((h["nome"], h["tipo"], h["dados"]))
def ver_trabalho(h, numero, nivel):
    raise RuntimeError("o trabalho já saiu da fila")
w32print.GetJob = ver_trabalho

w32con = types.ModuleType("win32con")
w32con.LOGPIXELSX, w32con.LOGPIXELSY, w32con.HORZRES, w32con.VERTRES = 88, 90, 8, 10

class DCFalso:
    def CreatePrinterDC(self, nome):
        if nome not in IMPRESSORAS or nome in estado["falhar_dc"]: raise RuntimeError("driver com problema")
        self.nome, self.paginas = nome, []
    def GetDeviceCaps(self, qual):
        info = IMPRESSORAS[self.nome]
        return {88: info["dpi"], 90: info["dpi"], 8: info["largura"], 10: 3000}[qual]
    def StartDoc(self, nome, arquivo=None): self.documento = nome
    def StartPage(self): pass
    def EndPage(self): pass
    def EndDoc(self): trabalhos.append((self.nome, "GDI", self.paginas))
    def DeleteDC(self): pass
    def GetHandleOutput(self): return self
w32ui = types.ModuleType("win32ui")
w32ui.CreateDC = DCFalso
imagewin = types.ModuleType("PIL.ImageWin")
class Dib:
    def __init__(self, imagem): self.imagem = imagem
    def draw(self, dc, caixa): dc.paginas.append((self.imagem.size, caixa))
imagewin.Dib = Dib
sys.modules.update({"win32print": w32print, "win32con": w32con, "win32ui": w32ui, "PIL.ImageWin": imagewin})

def atendimento_exemplo():
    itens = [{"servico": "Impressão colorida A4 frente e verso", "tipo": "unidade", "quantidade": 12,
              "valor_unitario": D("2.50"), "valor_digitado": D(0), "taxa_servico": D(0), "total": D("30.00"),
              "cobra_taxa_maquininha": True},
             {"servico": "Xerox", "tipo": "unidade", "quantidade": 3, "valor_unitario": D("0.50"),
              "valor_digitado": D(0), "taxa_servico": D(0), "total": D("1.50"), "cobra_taxa_maquininha": True}]
    return 123, {"data_hora": datetime(2026, 11, 2, 9, 30), "cliente_nome": "Maria José da Conceição",
                 "cliente_telefone": "(21) 99999-9999", "forma_pagamento": "Crédito", "subtotal": D("31.50"),
                 "taxa_percentual": D("4.99"), "taxa_valor": D("1.57"), "taxa_base": D("31.50"),
                 "total": D("33.07"), "valor_recebido": None, "troco": None}, itens

app = QApplication.instance() or QApplication(sys.argv)
banco.criar_tabelas()
layout = layout_notas.carregar_layout()

# ====================================================================
# 1. Mensagem do módulo de impressão (sem "pip" no programa instalado) e log
# ====================================================================
print("--- módulo de impressão faltando")
guardado = sys.modules["win32ui"]
sys.modules["win32ui"] = None  # (assim o import falha, como no .exe sem a biblioteca)
sys.frozen = True
try:
    impressao.imprimir_imagem("Tomate MDK-581", Image.new("L", (10, 10)), 48)
    ok(False, "sem win32ui: dá erro")
except impressao.ErroImpressao as erro:
    texto = str(erro)
    ok("Erro no módulo de impressão" in texto and "Reinstale o EasyServ ou fale com o suporte" in texto,
       "programa instalado: mensagem pede para reinstalar ou falar com o suporte")
    ok("pip" not in texto.lower() and "terminal" not in texto.lower(), "programa instalado: nunca fala em pip/terminal")
    log = impressao.arquivo_log()
    ok(log.startswith(config.pasta_base()) and os.path.exists(log), "detalhe técnico gravado em logs\\impressao.log (pasta de dados)")
    ok(log in texto, "a mensagem diz onde está o log")
    conteudo = open(log, encoding="utf-8").read()
    ok("win32ui" in conteudo and "Traceback" in conteudo and "programa instalado: sim" in conteudo,
       "log tem o módulo, o traceback e se é o programa instalado")
del sys.frozen
try:
    impressao.imprimir_imagem("Tomate MDK-581", Image.new("L", (10, 10)), 48)
except impressao.ErroImpressao as erro:
    ok("python -m pip install pywin32 pillow" in str(erro), "rodando pelo código: aí sim mostra o pip")
sys.modules["win32ui"] = guardado
ok(impressao.listar_impressoras() == list(IMPRESSORAS), "com as bibliotecas de volta, lista as impressoras")

print("--- autoteste (código)")
nomes = [nome for nome, _, _ in impressao.verificar_modulos()]
ok(all(f"importar {b}" in nomes for b in ("pywintypes", "win32print", "win32con", "win32ui", "PIL.Image", "PIL.ImageWin")),
   "autoteste confere pywintypes, win32print, win32con, win32ui, PIL.Image e PIL.ImageWin")
ok("mfc140u.dll (usada pelo win32ui)" in nomes and "montar nota ESC/POS" in nomes, "e a DLL do win32ui e a nota ESC/POS")
main_py = open("main.py", encoding="utf-8").read()
ok('"--autoteste-impressao"' in main_py, "main.py aceita --autoteste-impressao")
gerar = open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "..", "ferramentas", "gerar_instalador.py"), encoding="utf-8").read()
ok(all(m in gerar for m in ('"win32print"', '"win32ui"', '"win32con"', '"pywintypes"', '"PIL.ImageWin"')),
   "gerar_instalador.py: hidden imports do pywin32 e do Pillow")
ok("mfc140u.dll" in gerar and '"--add-binary"' in gerar and "autoteste_no_exe(" in gerar,
   "gerar_instalador.py: leva o mfc140u.dll e roda o autoteste no .exe gerado")

# ====================================================================
# 2. Opções novas no layout_notas.json
# ====================================================================
print("--- opções de impressão")
op = layout["impressao"]
ok(op["modo"] == "windows" and op["colunas"] == 0 and op["pagina_codigo"] == "cp850", "de fábrica: driver do Windows, largura automática, PC850")
ok(op["cortar_papel"] and not op["abrir_gaveta"] and op["logo_escpos"] and op["letra_grande"], "de fábrica: corta, não abre gaveta, logo e letra grande")
antigo = json.load(open(layout_notas.ARQUIVO_LAYOUT, encoding="utf-8"))
antigo["impressao"] = {"impressora": "Tomate MDK-581", "tirar_acentos": True}  # (arquivo da 1.4.1)
json.dump(antigo, open(layout_notas.ARQUIVO_LAYOUT, "w", encoding="utf-8"))
l2 = layout_notas.carregar_layout()
ok(l2["impressao"]["impressora"] == "Tomate MDK-581" and l2["impressao"]["tirar_acentos"] and l2["impressao"]["modo"] == "windows",
   "arquivo da 1.4.1: mantém impressora e acentos, modo continua o de antes (driver)")
antigo["impressao"] = {"modo": "laser", "colunas": 7, "pagina_codigo": "xyz"}
json.dump(antigo, open(layout_notas.ARQUIVO_LAYOUT, "w", encoding="utf-8"))
l2 = layout_notas.carregar_layout()
ok(l2["impressao"]["modo"] == "windows" and l2["impressao"]["colunas"] == 24 and l2["impressao"]["pagina_codigo"] == "cp850",
   "valores inválidos corrigidos (modo, colunas no mínimo 24, página de código)")
antigo["impressao"]["colunas"] = 500; json.dump(antigo, open(layout_notas.ARQUIVO_LAYOUT, "w", encoding="utf-8"))
ok(layout_notas.carregar_layout()["impressao"]["colunas"] == 64, "colunas no máximo 64")
os.remove(layout_notas.ARQUIVO_LAYOUT)
layout = layout_notas.carregar_layout()

# ====================================================================
# 3. Tomate MDK-581: 58mm, 203 dpi, 32 caracteres no modo texto
# ====================================================================
print("--- Tomate MDK-581 (58mm)")
for via in ("loja", "cliente"):
    layout[via]["papel"] = "58mm"
numero, atend, itens = atendimento_exemplo()
ok(notas.colunas_texto(layout, layout["loja"]) == 32, "58mm: 32 caracteres por linha")
ok(notas.medidas(layout["loja"])[0] == 384, "58mm a 203 dpi = 384 pontos de largura (48 mm úteis)")
for via in ("loja", "cliente"):
    linhas = notas.montar_linhas(layout[via], numero, atend, itens, via, True, 32)
    maior = max(len(t) for t, _ in linhas)
    ok(maior <= 32, f"nota da {via} em 58mm: nenhuma linha passa de 32 ({maior})")
ok(any(t.startswith("TOTAL:") and t.endswith("R$ 33,07") and len(t) == 32 for t, _ in linhas), "TOTAL encostado à direita em 32")
graf = notas.montar_linhas(layout["cliente"], numero, atend, itens, "cliente")
img = notas.renderizar_imagem(layout["cliente"], graf)
ok(img.width == 384, "modo gráfico: imagem com 384 pontos (a largura da cabeça de impressão)")
ok(max(len(t) for t, _ in graf) <= notas.medidas(layout["cliente"])[2], "modo gráfico: linhas cabem na fonte escolhida")
layout["impressao"]["colunas"] = 42
ok(max(len(t) for t, _ in notas.montar_linhas(layout["cliente"], numero, atend, itens, "cliente", True,
       notas.colunas_texto(layout, layout["cliente"]))) <= 42, "letras por linha ajustadas (42) valem")
layout["impressao"]["colunas"] = 0
layout["loja"]["papel"] = "80mm"
ok(notas.colunas_texto(layout, layout["loja"]) == 48, "80mm: 48 caracteres por linha")
layout["loja"]["papel"] = "58mm"

print("--- Imprimir teste: driver de texto e driver gráfico")
t = tela_notinhas.TelaNotinhas(None); t.show(); esperar(5)
for chave in ("cliente", "loja"):  # (pela tela, como a pessoa faria)
    t.radios_modelo[chave].setChecked(True); esperar(2); t.radios_papel["58mm"].setChecked(True); esperar(2)
ok(t.dados["loja"]["papel"] == t.dados["cliente"]["papel"] == "58mm", "papel 58mm nas duas notas")
t.combo_impressora.setCurrentText("Tomate MDK-581 (texto)"); esperar(5)
ok(t._modo_texto and "só imprime TEXTO" in t.lbl_impressora.text(), "driver Generic / Text Only reconhecido")
ok(not t.widget_escpos.isVisibleTo(t) and t.widget_colunas.isVisibleTo(t), "modo driver: sem as opções ESC/POS; letras por linha aparecem")
trabalhos.clear(); msgs.clear()
t.imprimir_teste(); esperar(2)
ok(len(trabalhos) == 1 and trabalhos[0][1] == "RAW", "driver de texto: 1 trabalho RAW na fila")
linhas_impressas = trabalhos[0][2].decode("cp850").split("\r\n")
ok(max(len(l) for l in linhas_impressas) <= 32, f"driver de texto: linhas com até 32 letras ({max(len(l) for l in linhas_impressas)})")
ok("VIA DA LOJA" in trabalhos[0][2].decode("cp850") and "Atendimento nº: 000123" in trabalhos[0][2].decode("cp850"), "saiu a nota de exemplo (via da loja)")
ok(t.lbl_status.text() == "Teste enviado para a impressora." and not msgs, "sem erro na tela")
t.combo_impressora.setCurrentText("Tomate MDK-581"); esperar(5)
ok(not t._modo_texto and "impressora gráfica" in t.lbl_impressora.text(), "driver do fabricante: impressora gráfica")
ok(not t.widget_colunas.isVisibleTo(t), "gráfica: letras por linha somem (quem manda é a fonte)")
trabalhos.clear()
t.imprimir_teste(); esperar(2)
ok(len(trabalhos) == 1 and trabalhos[0][1] == "GDI", "driver gráfico: impresso pelo win32ui")
(tamanho, caixa), = trabalhos[0][2]
ok(tamanho[0] == 384 and caixa[2] == 384, f"driver gráfico: imagem de 384 pontos na largura de 384 ({caixa})")
t.grab().save(os.path.join(saida, "notinhas_modo_driver.png"))

# ====================================================================
# 4. ESC/POS direto (RAW)
# ====================================================================
print("--- comandos ESC/POS")
linhas = [("MINHA LOJA", True), ("=" * 32, False), ("VIA DO CLIENTE", True), ("Serviço: ação", False),
          ("TOTAL:                  R$ 9,00", True)]
dados = impressao.comandos_escpos(linhas)
ok(dados.startswith(b"\x1b@\x1bt\x02"), "começa com ESC @ (reinicia) e ESC t 2 (PC850)")
ok(b"\x1b!\x18MINHA LOJA\n" in dados, "nome da loja: negrito + altura dupla (ESC ! 0x18)")
ok(b"\x1b!\x08VIA DO CLIENTE\n" in dados, "outro negrito depois do cabeçalho: só negrito")
ok(b"\x1b!\x18TOTAL:" in dados, "TOTAL em letra grande")
ok("Serviço: ação".encode("cp850") in dados and b"\x87" in dados, "acentos na página PC850 (ç = 0x87)")
ok(dados.endswith(b"\x1bd\x04\x1dVB\x00"), "no fim: avança o papel e corta (GS V 66 0)")
ok(b"\x1bp" not in dados, "sem gaveta quando não pedida")
dados = impressao.comandos_escpos(linhas, cortar=False, gaveta=True, letra_grande=False)
ok(b"\x1dV" not in dados and dados.endswith(b"\x1bp\x00\x19\xfa"), "sem corte e com o pulso da gaveta (ESC p)")
ok(b"\x1b!\x18" not in dados and b"\x1b!\x08MINHA LOJA" in dados, "letra grande desligada: só negrito")
dados = impressao.comandos_escpos(linhas, "cp860")
ok(dados.startswith(b"\x1b@\x1bt\x03") and "ação".encode("cp860") in dados, "PC860 (Português): ESC t 3")
dados = impressao.comandos_escpos(linhas, sem_acentos=True)
ok(b"Servico: acao" in dados, "Tirar acentos")
print("--- logo em imagem raster")
raster = impressao.imagem_raster(Image.new("L", (100, 40), 0), 384)
ok(raster[:8] == b"\x1dv0\x00" + bytes([13, 0, 40, 0]), "GS v 0 com 13 bytes (100 pontos) x 40 linhas")
ok(len(raster) == 8 + 13 * 40 and raster[8] == 0xFF and raster[8 + 12] == 0xF0, "preto vira 1; a sobra até 8 fica branca")
raster = impressao.imagem_raster(Image.new("L", (1000, 800), 255), 384)
ok(raster[4:6] == bytes([48, 0]) and raster.count(b"\x1dv0\x00") == 3, "logo maior que o papel: reduzida a 384 pontos, em faixas de até 128 linhas")
ok(set(raster[8:8 + 48]) == {0}, "branco vira 0 (não gasta papel)")

print("--- ESC/POS pela tela")
logo = os.path.join(config.pasta_base(), "imagens", "logo_teste.png")
os.makedirs(os.path.dirname(logo), exist_ok=True)
Image.new("RGB", (200, 80), "black").save(logo)
for chave in ("loja", "cliente"):
    t.dados[chave]["logo"] = os.path.join("imagens", "logo_teste.png")
t.check_logo.setChecked(True); esperar(2)
t.combo_modo.setCurrentIndex(t.combo_modo.findData("escpos")); esperar(5)
ok(t.dados["impressao"]["modo"] == "escpos" and t._modo_texto, "modo ESC/POS escolhido (nota sai como texto)")
ok(t.widget_escpos.isVisibleTo(t) and t.widget_colunas.isVisibleTo(t), "aparecem as opções ESC/POS e letras por linha")
ok("ESC/POS direto" in t.lbl_impressora.text(), "explica o modo na tela")
ok("32 caracteres" in t.lbl_info_previa.text(), "pré-visualização: 32 caracteres no 58mm")
t.grab().save(os.path.join(saida, "notinhas_modo_escpos.png"))
trabalhos.clear()
t.imprimir_teste(); esperar(2)
ok(len(trabalhos) == 1 and trabalhos[0][1] == "RAW", "Imprimir teste no ESC/POS: 1 trabalho RAW")
dados = trabalhos[0][2]
ok(dados.startswith(b"\x1b@\x1bt\x02") and b"\x1dv0\x00" in dados and dados.endswith(b"\x1dVB\x00"),
   "nota com reinício, página de código, logo raster e corte")
ok(dados[dados.index(b"\x1dv0\x00") + 4] == (round(384 * 60 / 100) + 7) // 8, "logo no tamanho escolhido (60% de 384 pontos = 29 bytes)")
textos = [l.split(b"\x1b!")[-1][1:].decode("cp850") for l in dados.split(b"\n") if b"\x1b!" in l]
ok(textos and max(len(x) for x in textos) <= 32, "ESC/POS: linhas até 32 letras")
t.check_logo_escpos.setChecked(False); t.check_cortar.setChecked(False); t.combo_pagina.setCurrentIndex(t.combo_pagina.findData("cp860"))
t.spin_colunas.setValue(30); esperar(3)
ok(t.dados["impressao"]["colunas"] == 30 and t.dados["impressao"]["pagina_codigo"] == "cp860", "tela guarda letras por linha e página de código")
trabalhos.clear(); t.imprimir_teste(); esperar(2)
dados = trabalhos[0][2]
ok(b"\x1dv0" not in dados and b"\x1dV" not in dados and dados.startswith(b"\x1b@\x1bt\x03"), "sem logo, sem corte e com PC860")
textos = [l.split(b"\x1b!")[-1][1:] for l in dados.split(b"\n") if b"\x1b!" in l]
ok(max(len(x) for x in textos) <= 30, "30 letras por linha")
t.spin_colunas.setValue(t.spin_colunas.minimum()); esperar(2)
ok(t.dados["impressao"]["colunas"] == 0 and t.spin_colunas.text() == "Automático (pelo papel)", "volta para Automático")
t.check_logo_escpos.setChecked(True); t.check_cortar.setChecked(True); t.combo_pagina.setCurrentIndex(0)

print("--- erro sugere o outro modo")
estado["falhar_raw"].add("Tomate MDK-581"); msgs.clear()
t.imprimir_teste(); esperar(2)
ok(msgs and msgs[-1][0] == "erro" and "Pelo driver do Windows" in msgs[-1][2] and "Detectar" in msgs[-1][2],
   "ESC/POS falhou: erro claro sugerindo \"Pelo driver do Windows\" e o Detectar")
estado["falhar_raw"].clear(); estado["falhar_dc"].add("Tomate MDK-581")
t.combo_modo.setCurrentIndex(t.combo_modo.findData("windows")); esperar(3); msgs.clear()
t.imprimir_teste(); esperar(2)
ok(msgs and "ESC/POS direto (RAW)" in msgs[-1][2], "driver do Windows falhou: sugere \"ESC/POS direto (RAW)\"")
estado["falhar_dc"].clear()

print("--- Detectar")
trabalhos.clear(); perguntas.clear(); msgs.clear()
respostas[:] = [QMessageBox.Yes, QMessageBox.Yes, QMessageBox.Yes]  # imprimir? / saiu o ESC/POS? / saiu o driver?
t.detectar(); esperar(2)
ok([x[1] for x in trabalhos] == ["RAW", "GDI"], "imprime uma página de teste em cada modo (ESC/POS e driver)")
ok(b"TESTE DE IMPRESS" in trabalhos[0][2] and b"Modo: ESC/POS direto (RAW)" in trabalhos[0][2], "página de teste diz o modo")
ok(b"12345678901234567890123456789012" in trabalhos[0][2] and b"123456789012345678901234567890123" not in trabalhos[0][2],
   "régua com exatamente 32 letras")
ok(len(perguntas) == 3 and "Saiu o papel" in perguntas[1][1], "pergunta se o papel saiu em cada modo")
ok(t.dados["impressao"]["modo"] == "escpos" and "ESC/POS direto (RAW)\": funcionou" not in msgs[-1][2]
   and "Modo escolhido: \"ESC/POS direto (RAW)\"" in msgs[-1][2], "os dois funcionaram: escolhe o ESC/POS")
respostas[:] = [QMessageBox.Yes, QMessageBox.No, QMessageBox.Yes]
t.detectar(); esperar(2)
ok(t.dados["impressao"]["modo"] == "windows" and "Modo escolhido: \"Pelo driver do Windows\"" in msgs[-1][2],
   "ESC/POS não saiu certo: escolhe o driver do Windows")
estado["falhar_raw"].add("Tomate MDK-581"); respostas[:] = [QMessageBox.Yes, QMessageBox.Yes]
t.detectar(); esperar(2)
ok("ESC/POS direto (RAW): não deu certo" in msgs[-1][2] and "inválido" in msgs[-1][2] and t.dados["impressao"]["modo"] == "windows",
   "ESC/POS dá erro: diz o motivo e fica o driver")
estado["falhar_raw"].clear(); estado["status"]["Tomate MDK-581"] = 0x10; trabalhos.clear()
t.detectar(); esperar(2)
ok(not trabalhos and "está sem papel" in msgs[-1][2] and "Nenhum modo funcionou" in msgs[-1][2], "sem papel: avisa e nem tenta imprimir")
estado["status"].clear()
t.combo_modo.setCurrentIndex(t.combo_modo.findData("escpos")); t.check_gaveta.setChecked(True); esperar(2)
ok(t.salvar(), "salvou")
salvo = json.load(open(layout_notas.ARQUIVO_LAYOUT, encoding="utf-8"))["impressao"]
ok(salvo["modo"] == "escpos" and salvo["abrir_gaveta"] and salvo["impressora"] == "Tomate MDK-581", "layout_notas.json com o modo e a gaveta")
t.close()

# ====================================================================
# 5. Gaveta de dinheiro ao finalizar
# ====================================================================
print("--- gaveta ao finalizar")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(10)
def indice(nome):
    return next(i for i, s in enumerate(j.config.servicos) if s.nome == nome)
def atender(nota_cliente):
    j.selecionar_servico(indice("Xerox")); j.entry_item.setText("2"); j.adicionar_item()
    j.botoes_pagamento["Dinheiro"].setChecked(True); j.entry_recebido.setText("10")
    j.check_nota_cliente.setChecked(nota_cliente); trabalhos.clear(); msgs.clear()
    j.finalizar_atendimento(); esperar(2)
atender(True)
ok(len(trabalhos) == 1 and trabalhos[0][2].endswith(b"\x1bp\x00\x19\xfa") and b"VIA DO CLIENTE" in trabalhos[0][2],
   "com a nota do cliente: a gaveta abre junto (um trabalho só)")
atender(False)
ok(len(trabalhos) == 1 and trabalhos[0][2] == b"\x1b@\x1bp\x00\x19\xfa", "sem a nota do cliente: só o comando da gaveta")
estado["falhar_raw"].add("Tomate MDK-581"); atender(False)
ok("A gaveta de dinheiro não abriu" in msgs[-1][2] and "finalizado" in msgs[-1][2], "gaveta falhou: o atendimento finaliza e avisa")
estado["falhar_raw"].clear()
j.layout_das_notas["impressao"]["abrir_gaveta"] = False; atender(False)
ok(not trabalhos, "gaveta desligada: nada vai para a impressora")
j.layout_das_notas["impressao"].update(modo="windows", abrir_gaveta=True); atender(False)
ok(not trabalhos, "modo driver do Windows: não manda comando de gaveta")
j.layout_das_notas["impressao"].update(modo="escpos", abrir_gaveta=False)

# ====================================================================
# 6. Resumo de fechamento na mesma térmica de 58mm
# ====================================================================
print("--- resumo na térmica de 58mm")
rel = relatorio.montar_relatorio(datetime.now().date())
trabalhos.clear()
relatorio.imprimir_resumo(j.layout_das_notas, rel, "Minha Loja")
dados = trabalhos[-1][2]
textos = [l.split(b"\x1b!")[-1][1:] for l in dados.split(b"\n") if b"\x1b!" in l]
ok(trabalhos[-1][1] == "RAW" and max(len(x) for x in textos) <= 32, "mesma impressora das notinhas (58mm, ESC/POS): resumo em 32 letras")
ok(b"TOTAL DO DIA" in dados, "resumo saiu inteiro")
trabalhos.clear()
relatorio.imprimir_teste_resumo(j.layout_das_notas, "Minha Loja", "POS-80")
ok(trabalhos[-1][0] == "POS-80" and trabalhos[-1][1] == "GDI" and trabalhos[-1][2][0][1][2] == 575,
   "outra impressora (80mm): pelo driver, em 72 mm (575 pontos a 203 dpi)")
j.close()

print(f"\nFALHAS: {len(falhas)}")
sys.exit(1 if falhas else 0)
