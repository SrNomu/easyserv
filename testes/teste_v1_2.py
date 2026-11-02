"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, json, sqlite3, shutil, hashlib, struct, io, importlib.util, tempfile
from datetime import datetime
from decimal import Decimal as D
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QWidget, QInputDialog, QFileDialog, QScroller
from PySide6.QtTest import QTest
import estilo, banco, interface, impressao, notas, relatorio, atalhos, preferencias, config, versao
import tela_servicos, tela_sobre, tela_abertura, tela_atualizacao, atualizacao, integridade, migracao, toque, main

msgs, perguntas, abertos, impressos, teclados = [], [], [], [], []
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
toque.abrir_teclado_windows = lambda: teclados.append(1) or True
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
tmp = tempfile.mkdtemp(prefix="easyserv_teste_", dir=saida)

app = QApplication(sys.argv); estilo.preparar(app); banco.criar_tabelas()

# ====================================================================
# 0. Pasta de dados (nunca a pasta do programa quando instalado)
# ====================================================================
print("--- pasta de dados")
ok(os.path.normcase(config.pasta_base()) == os.path.normcase(os.path.abspath(pasta)), "testes usam a cópia (EASYSERV_DADOS)")
antes_env = dict(os.environ); antes_frozen = getattr(sys, "frozen", None); antes_exe = sys.executable
try:
    os.environ.pop("EASYSERV_DADOS"); os.environ["APPDATA"] = os.path.join(tmp, "appdata")
    instalado = os.path.join(tmp, "Programs", "EasyServ"); os.makedirs(instalado)
    sys.frozen = True; sys.executable = os.path.join(instalado, "EasyServ.exe")
    ok(config.pasta_programa() == instalado, "pasta do programa = pasta do .exe")
    ok(config.pasta_base() == os.path.join(tmp, "appdata", "EasyServ") and os.path.isdir(config.pasta_base()),
       "instalado: dados em %APPDATA%\\EasyServ")
    open(os.path.join(instalado, "portatil.txt"), "w").close()
    ok(config.pasta_base() == instalado, "com portatil.txt: dados ao lado do .exe")
finally:
    os.environ.clear(); os.environ.update(antes_env); sys.executable = antes_exe
    if antes_frozen is None: del sys.frozen
ok(not hasattr(sys, "frozen") and os.path.normcase(os.path.abspath(config.pasta_base())) == os.path.normcase(os.path.abspath(pasta)), "voltou ao normal")

# ====================================================================
# 1. Nome EasyServ
# ====================================================================
print("--- nome")
j = interface.JanelaPrincipal(); j.mostrar(); esperar(15)
j.definir_modo_cor("claro"); esperar(3)
ok(versao.NOME_PROGRAMA == "EasyServ" and versao.VERSAO >= "1.2", "EasyServ 1.2+")
ok(j.windowTitle() == f"EasyServ - {j.config.nome_loja}", j.windowTitle())
ok("Calculadora" not in j.windowTitle(), "sem o nome antigo no título")
textos_menu = [a.text() for m in j.menuBar().actions() for a in m.menu().actions()]
ok("Sobre o EasyServ" in textos_menu and "Procurar atualizações..." in textos_menu and "Modo tablet" in textos_menu
   and "Importar dados de outra pasta..." in textos_menu and "Abrir pasta de dados" in textos_menu, "menus novos")
ls = notas.montar_linhas(j.layout_das_notas["loja"], 1, {"data_hora": datetime.now(), "cliente_nome": "", "cliente_telefone": "",
     "forma_pagamento": "Pix", "subtotal": D(1), "taxa_percentual": D(0), "taxa_valor": D(0), "total": D(1),
     "valor_recebido": None, "troco": None}, [], "loja")
ok(j.layout_das_notas["loja"]["nome_loja"] in str(ls) and "EasyServ" not in str(ls), "notinha continua com o nome da loja")
r = relatorio.montar_relatorio(datetime.now().date())
ok(j.config.nome_loja in str(relatorio.linhas_resumo(r, j.config.nome_loja, 48)), "resumo com o nome da loja")
codigo = " ".join(open(f, encoding="utf-8").read() for f in os.listdir(".") if f.endswith(".py"))
ok("Calculadora de Serviços" not in codigo, "nome antigo não sobrou no código")

# ====================================================================
# 2. Logo e ícone
# ====================================================================
print("--- logo e ícone")
from PySide6.QtSvg import QSvgRenderer
ok(QSvgRenderer(config.recurso("easyserv.svg")).isValid(), "logo SVG válida")
dados_ico = open(config.recurso("easyserv.ico"), "rb").read()
_r, tipo, qtd = struct.unpack("<HHH", dados_ico[:6])
lados = [dados_ico[6 + 16 * i] or 256 for i in range(qtd)]
ok(tipo == 1 and lados == [16, 20, 24, 32, 40, 48, 64, 128, 256], f"ícone .ico com {lados}")
icone = QIcon(config.recurso("easyserv.ico"))
ok(not icone.isNull() and len(icone.availableSizes()) >= 5, f"Qt lê o ícone ({len(icone.availableSizes())} tamanhos)")
for nome in ("instalador_fundo_1x.png", "instalador_lateral_1x.png", "instalador_pequena_1x.png", "easyserv.png"):
    ok(os.path.exists(config.recurso(nome)), f"recurso {nome}")

# ====================================================================
# 3. Tela de abertura e verificação
# ====================================================================
print("--- tela de abertura")
ab = tela_abertura.TelaAbertura(); ab.show()
ab.etapa("Verificando arquivos...", 10); esperar(2)
ok(ab.texto == "Verificando arquivos..." and ab.progresso == 10, "etapa mostrada")
ab.etapa("Procurando atualizações...", 65); esperar(2)
ab.grab().save(os.path.join(saida, "abertura.png"))
ok(ab.esperar(lambda: 42, 2) == 42, "esperar devolve o resultado")
import time
t0 = time.monotonic(); ok(ab.esperar(lambda: time.sleep(3) or 1, 0.5) is None and time.monotonic() - t0 < 1.5, "esperar desiste no limite (internet lenta)")
ab.close()
ok(integridade.verificar_programa() == [], f"programa inteiro (dev): {integridade.verificar_programa()}")
falso = os.path.join(tmp, "programa"); os.makedirs(os.path.join(falso, "_internal"))
for nome, conteudo in (("EasyServ.exe", b"x" * 100), ("_internal/a.dll", b"y" * 50), ("_internal/b.pyd", b"z" * 10)):
    open(os.path.join(falso, nome), "wb").write(conteudo)
ok(integridade.gerar_manifesto(falso, "1.2") == 3, "manifesto gerado")
ok(integridade.verificar_programa(falso) == [], "manifesto confere")
os.remove(os.path.join(falso, "_internal", "a.dll")); open(os.path.join(falso, "_internal", "b.pyd"), "wb").write(b"z")
probs = integridade.verificar_programa(falso)
ok(any("faltando" in p and "a.dll" in p for p in probs) and any("corrompido" in p and "b.pyd" in p for p in probs), f"acha faltando e corrompido: {probs}")
dados_ruins = os.path.join(tmp, "dados_ruins"); os.makedirs(dados_ruins)
shutil.copy(banco.ARQUIVO_BANCO, os.path.join(dados_ruins, "maisbella.db"))
open(os.path.join(dados_ruins, "config.json"), "w").write('{"nome_loja": "x",}')
open(os.path.join(dados_ruins, "treino.db"), "wb").write(b"lixo que nao e banco" * 20)
probs = integridade.verificar_dados(dados_ruins)
ok(len(probs) == 2 and any("config.json" in p for p in probs) and any("treino.db" in p for p in probs), f"dados: {probs}")
ok(integridade.verificar_dados() == [], "dados de verdade sem problema")
# banco com página estragada
estragado = os.path.join(dados_ruins, "maisbella.db")
b = bytearray(open(estragado, "rb").read()); b[4096:8192] = b"\x07" * 4096; open(estragado, "wb").write(bytes(b))
ok(integridade.verificar_banco(estragado) is not None, f"banco estragado detectado: {integridade.verificar_banco(estragado)}")

# ====================================================================
# 7. Migração dos dados antigos
# ====================================================================
print("--- migração")
antigo = os.path.join(tmp, "Desktop", "Calculadora"); os.makedirs(os.path.join(antigo, "notas"))
shutil.copy(banco.ARQUIVO_BANCO, os.path.join(antigo, "maisbella.db"))
shutil.copy(config.ARQUIVO_CONFIG, os.path.join(antigo, "config.json"))
open(os.path.join(antigo, "notas", "nota_1.txt"), "w").write("nota velha")
open(os.path.join(antigo, "Calculadora.exe"), "wb").write(b"exe velho")
vazio = os.path.join(tmp, "Desktop", "outra"); os.makedirs(vazio)
ok(migracao.encontrar_dados_antigos([antigo, vazio, config.pasta_base()]) == [antigo], "acha só a pasta com dados (e não a atual)")
novo = os.path.join(tmp, "appdata_novo")
os.environ["EASYSERV_DADOS"] = novo
try:
    ok(migracao.precisa_oferecer(), "pasta de dados vazia: oferece")
    migracao.encontrar_dados_antigos = lambda pastas=None: [antigo]
    resposta["v"] = QMessageBox.Yes
    class AberturaFalsa:
        def hide(self): pass
        def show(self): pass
    main.oferecer_migracao(AberturaFalsa())
    ok(os.path.exists(os.path.join(novo, "maisbella.db")) and os.path.exists(os.path.join(novo, "notas", "nota_1.txt"))
       and os.path.exists(os.path.join(novo, "config.json")), "copiou banco, config e notas")
    ok(not os.path.exists(os.path.join(novo, "Calculadora.exe")), "não copia o programa velho")
    ok(os.path.exists(os.path.join(antigo, "maisbella.db")) and os.path.exists(os.path.join(antigo, migracao.AVISO_NA_ORIGEM)),
       "pasta antiga intacta, com aviso de para onde foi")
    ok(not migracao.precisa_oferecer(), "não pergunta de novo")
    c = sqlite3.connect(os.path.join(novo, "maisbella.db")); n_novo = c.execute("select count(*) from atendimentos").fetchone()[0]; c.close()
    ok(n_novo == banco.contar_atendimentos() if hasattr(banco, "contar_atendimentos") else True, "mesmos atendimentos")
    # recusar
    novo2 = os.path.join(tmp, "appdata_novo2"); os.environ["EASYSERV_DADOS"] = novo2
    resposta["v"] = QMessageBox.No; main.oferecer_migracao(AberturaFalsa())
    ok(not os.path.exists(os.path.join(novo2, "maisbella.db")) and not migracao.precisa_oferecer(), "recusou: começa do zero e não pergunta mais")
    # importar por cima guarda os de agora
    os.environ["EASYSERV_DADOS"] = novo
    guarda = migracao.guardar_dados_atuais()
    ok(os.path.exists(os.path.join(guarda, "maisbella.db")) and not os.path.exists(os.path.join(novo, "maisbella.db")), "importar: dados de agora vão para backups/")
finally:
    os.environ["EASYSERV_DADOS"] = os.path.abspath(pasta)
resposta["v"] = QMessageBox.Yes

# ====================================================================
# 4. Atualização (GitHub falso, sem internet)
# ====================================================================
print("--- atualização")
ok(versao.numero("v1.10") > versao.numero("1.9") and versao.numero("1.2.0") == versao.numero("1.2"), "comparação de versões")
ok(atualizacao.eh_mais_nova("1.9") and not atualizacao.eh_mais_nova(versao.VERSAO) and not atualizacao.eh_mais_nova("v1.1"), "mais nova?")
repo_real = versao.REPOSITORIO_GITHUB; versao.REPOSITORIO_GITHUB = ""
ok(atualizacao.consultar() is None, "sem repositório configurado: não consulta")
conteudo = b"MZ instalador falso " * 5000
sha_certo = hashlib.sha256(conteudo).hexdigest()
class Resposta(io.BytesIO):
    def __init__(self, dados): super().__init__(dados); self.headers = {"Content-Length": str(len(dados))}
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
pedidos = []
def github(tag="v1.9", sha=None, draft=False, com_sha=True, digest=""):
    sha = sha or sha_certo
    def abrir(pedido, timeout=None):
        url = pedido.full_url; pedidos.append((url, dict(pedido.headers)))
        if url.endswith("/releases/latest"):
            assets = [{"name": f"EasyServ_Setup_{tag.lstrip('v')}.exe", "size": len(conteudo), "digest": digest,
                       "browser_download_url": "https://github.com/x/y/releases/download/setup.exe"}]
            if com_sha:
                assets.append({"name": f"EasyServ_Setup_{tag.lstrip('v')}.exe.sha256", "size": 90,
                               "browser_download_url": "https://github.com/x/y/releases/download/setup.sha256"})
            return Resposta(json.dumps({"tag_name": tag, "name": f"EasyServ {tag}", "draft": draft, "prerelease": False,
                                        "body": "## Novidades\n- Coisa nova **legal**\n- Outra", "html_url": "https://github.com/x/y",
                                        "assets": assets}).encode())
        if url.endswith(".sha256"):
            return Resposta(f"{sha}  EasyServ_Setup_{tag.lstrip('v')}.exe\n".encode())
        if url.endswith("setup.exe"):
            return Resposta(conteudo)
        raise OSError("url inesperada " + url)
    return abrir
atualizacao.abrir_url = github()
l = atualizacao.consultar("x/y")
ok(l is not None and l.versao == "1.9" and l.nome_instalador == "EasyServ_Setup_1.9.exe" and "Coisa nova" in l.notas, f"acha a 1.9 ({l and l.versao})")
ok(pedidos[0][0] == "https://api.github.com/repos/x/y/releases/latest", "consulta a API pública")
ok(all("Authorization" not in h and "authorization" not in {k.lower() for k in h} for _u, h in pedidos), "sem token/senha nos pedidos")
atualizacao.abrir_url = github("v" + versao.VERSAO); ok(atualizacao.consultar("x/y") is None, "mesma versão: nada")
atualizacao.abrir_url = github("v1.1"); ok(atualizacao.consultar("x/y") is None, "versão mais velha: nada")
atualizacao.abrir_url = github(draft=True); ok(atualizacao.consultar("x/y") is None, "rascunho: nada")
atualizacao.abrir_url = sem_internet; ok(atualizacao.consultar("x/y") is None, "sem internet: nada (sem erro)")
def lixo(*a, **k): return Resposta(b"<html>erro</html>")
atualizacao.abrir_url = lixo; ok(atualizacao.consultar("x/y") is None, "resposta estranha: nada")
atualizacao.abrir_url = github(com_sha=False, digest="sha256:" + sha_certo.upper())
l2 = atualizacao.consultar("x/y"); ok(l2 and atualizacao.sha256_publicado(l2) == sha_certo, "usa o digest do GitHub quando não tem .sha256")
atualizacao.abrir_url = github()
progresso = []
caminho = atualizacao.baixar(l, lambda b, t: progresso.append((b, t)))
ok(os.path.dirname(caminho) == os.path.join(config.pasta_base(), "atualizacoes") and open(caminho, "rb").read() == conteudo, "baixou na pasta atualizacoes")
ok(progresso and progresso[-1] == (len(conteudo), len(conteudo)), "progresso do download")
ok(atualizacao.sha256_publicado(l) == sha_certo and atualizacao.conferir(caminho, sha_certo), "SHA-256 confere")
ok(not atualizacao.conferir(caminho, "0" * 64) and not os.path.exists(caminho), "SHA-256 errado: arquivo apagado")
try:
    atualizacao.baixar(l, cancelado=lambda: True); ok(False, "cancelar")
except atualizacao.Cancelado:
    ok(True, "cancelar interrompe o download")
# backups: banco sim; programa só quando instalado
antes_bk = set(os.listdir(banco.PASTA_BACKUPS)) if os.path.isdir(banco.PASTA_BACKUPS) else set()
criados = atualizacao.fazer_backups()
ok(len(criados) == 1 and criados[0].endswith(".db") and os.path.exists(criados[0]), f"backup do banco antes de atualizar {criados}")
# janela
class PaiFalso(QWidget):
    def __init__(self): super().__init__(); self.carrinho = []; self.fechou = False
    def close(self): self.fechou = True; return True
ordem = []
atualizacao.fazer_backups = lambda: ordem.append("backup") or ["x.db"]
atualizacao.iniciar_atualizador = lambda inst, sha: ordem.append(("atualizador", os.path.basename(inst), sha)) or True
quit_original = QApplication.quit
pai = PaiFalso(); pai.carrinho = [{"servico": "Xerox"}]
d = tela_atualizacao.DialogoAtualizacao(pai, l); d.setWindowModality(Qt.ApplicationModal); d.show(); esperar(5)
ok("1.9" in d.findChildren(tela_atualizacao.QLabel)[1].text() + d.findChildren(tela_atualizacao.QLabel)[0].text() or any("1.9" in x.text() for x in d.findChildren(tela_atualizacao.QLabel)), "mostra a versão nova")
ok("Coisa nova" in d.notas.toPlainText() and "legal" in d.notas.toPlainText(), "mostra as notas (Markdown)")
ok(d.btn_atualizar.text() == "Atualizar agora" and d.btn_depois.text() == "Depois", "botões Atualizar agora / Depois")
d.grab().save(os.path.join(saida, "atualizacao.png"))
n = len(msgs); d.atualizar(); esperar(3)
ok(len(msgs) == n + 1 and "atendimento" in msgs[-1][2] and not ordem and d.isVisible(), "no meio de um atendimento: não atualiza")
pai.carrinho = []
d.atualizar()
for _ in range(100):
    if not d.isVisible(): break
    QTest.qWait(50)
ok(ordem == ["backup", ("atualizador", "EasyServ_Setup_1.9.exe", sha_certo)], f"baixa, confere, faz backup e chama o atualizador {ordem}")
ok(pai.fechou and d.atualizou, "o programa fecha para o atualizador trabalhar")
# SHA errado na publicação
ordem.clear(); atualizacao.abrir_url = github(sha="1" * 64)
d = tela_atualizacao.DialogoAtualizacao(PaiFalso(), atualizacao.consultar("x/y")); d.show(); n = len(msgs); d.atualizar()
for _ in range(100):
    if not d.isVisible(): break
    QTest.qWait(50)
ok(not ordem and "SHA-256" in msgs[-1][2] and "normalmente" in msgs[-1][2], "SHA-256 não bate: não instala e avisa")
# Depois
ordem.clear(); atualizacao.abrir_url = github()
d = tela_atualizacao.DialogoAtualizacao(PaiFalso(), l); d.show(); d.btn_depois.click(); esperar()
ok(not d.isVisible() and not ordem, "Depois: não faz nada")
# janela principal
abriu = []
tela_atualizacao.DialogoAtualizacao.exec = lambda self: abriu.append(self.lancamento.versao) or 0
j.carrinho = [{"x": 1}]; j.oferecer_atualizacao(l)
ok(not abriu and "1.9" in j.lbl_status.text(), "janela: com atendimento só avisa na barra")
j.carrinho = []; j.oferecer_atualizacao(l); ok(abriu == ["1.9"], "janela: sem atendimento mostra a janela")
n = len(msgs); j.procurar_atualizacoes(); ok("configuradas" in msgs[-1][2], "Procurar atualizações sem repositório avisa")
versao.REPOSITORIO_GITHUB = repo_real

# Atualizador separado
print("--- atualizador")
spec = importlib.util.spec_from_file_location("atualizador", os.path.join(pasta, "atualizador", "atualizador.py"))
at = importlib.util.module_from_spec(spec); spec.loader.exec_module(at)
avisos_at = []; at.avisar = lambda texto, erro=True: avisos_at.append(texto)
inst = os.path.join(tmp, "EasyServ_Setup_1.3.exe"); open(inst, "wb").write(conteudo)
log = os.path.join(tmp, "atualizacao.log")
rodados, abertos_at = [], []
class Res: returncode = 0
cod = at.main(["--instalador", inst, "--sha256", sha_certo, "--pid", "999999", "--programa", "C:/x/EasyServ.exe", "--log", log],
              executar=lambda c: rodados.append(c) or Res(), abrir=lambda c: abertos_at.append(c))
ok(cod == 0 and rodados and rodados[0][0] == inst and "/SILENT" in rodados[0] and "/CLOSEAPPLICATIONS" in rodados[0], f"roda o instalador silencioso {rodados and rodados[0][1:3]}")
ok(abertos_at == [["C:/x/EasyServ.exe"]], "abre o EasyServ no fim")
ok("Instalador terminou com código 0" in open(log, encoding="utf-8").read(), "anota no log")
rodados.clear(); abertos_at.clear()
cod = at.main(["--instalador", inst, "--sha256", "0" * 64, "--pid", "999999", "--programa", "C:/x/EasyServ.exe", "--log", log],
              executar=lambda c: rodados.append(c) or Res(), abrir=lambda c: abertos_at.append(c))
ok(cod == 3 and not rodados and not os.path.exists(inst) and avisos_at, "atualizador: SHA errado não instala")
ok(abertos_at, "e abre a versão de antes")

# ====================================================================
# 5. Sobre e licença
# ====================================================================
print("--- Sobre")
s = tela_sobre.TelaSobre(j); s.setWindowModality(Qt.ApplicationModal); s.show(); esperar(5)
t = s.texto_completo()
ok("© 2026 Pedro. Todos os direitos reservados." in t and f"Versão {versao.VERSAO}" in t, "direitos e versão")
for lib in ("PySide6", "openpyxl", "Pillow", "pywin32", "LGPL v3", "MIT", "PSF"):
    ok(lib in t, f"créditos: {lib}")
ok("Termos de uso" in t and "NÃO são documentos fiscais" in t, "aba Termos de uso com a LICENCA.txt")
ok(s.abas.count() == 3, "abas: notas, créditos, termos")
s.grab().save(os.path.join(saida, "sobre.png"))
s.abas.setCurrentIndex(1); esperar(2); s.grab().save(os.path.join(saida, "sobre_creditos.png")); s.done(0)
ok(any("1.2" == v for v, _d, _m in versao.NOTAS_DA_VERSAO) and versao.NOTAS_DA_VERSAO[0][0] == versao.VERSAO, "notas da versão atual no topo")

# ====================================================================
# 6. Modo tablet
# ====================================================================
print("--- modo tablet")
folha_normal = app.styleSheet()
j.usar_layout("Padrão"); esperar(5)
j.definir_modo_tablet(True); esperar(10)
ok(estilo.escala() == estilo.ESCALA_TABLET and j.modo_tablet and j.acao_tablet.isChecked(), "modo tablet ligado")
ok("font-size: 18px" in app.styleSheet() and "font-size: 14px" in folha_normal and app.styleSheet() != folha_normal, "letras maiores (14px -> 18px)")
ok(j.preferencias["layout_atual"] == "Touch" and j.teclado.grande, "usa o layout Touch")
ok(ler_json(preferencias.ARQUIVO_PREFERENCIAS)["modo_tablet"] is True, "lembra o modo tablet")
ok(QScroller.hasScroller(j.tabela.viewport()) or QScroller.grabbedGesture(j.tabela.viewport()) != 0, "rolagem por toque na tabela")
j.grab().save(os.path.join(saida, "tablet.png"))
n = len(teclados); j.entry_nome.setFocus(); esperar(3)
ok(len(teclados) == n + 1, "tocar no Nome abre o teclado do Windows")
j.entry_item.setFocus(); esperar(2)
com_dica = next(w for w in j.findChildren(QWidget) if w.toolTip() and w.isVisible() and w.window() is j)
app.sendEvent(com_dica, QMouseEvent(QEvent.MouseButtonPress, QPointF(2, 2), QPointF(2, 2), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
ok(j.lbl_status.text() == com_dica.toolTip(), f"dica aparece na barra ao tocar ({com_dica.toolTip()[:40]!r})")
j.definir_modo_tablet(False); esperar(10)
ok(estilo.escala() == 1.0 and app.styleSheet() == folha_normal and j.preferencias["layout_atual"] == "Padrão", "desligar volta tamanho e layout")
n = len(teclados); j.entry_nome.setFocus(); esperar(2); ok(len(teclados) == n, "fora do tablet não abre teclado")
# Tela de toque detectada
j.config.loja_confirmada = True  # (a janela de boas-vindas da 1.4 é testada no teste_v1_4)
toque.tem_tela_touch = lambda: True
j.preferencias["tablet_perguntado"] = False; resposta["v"] = QMessageBox.No; n = len(perguntas)
j.apos_abrir(None); ok(len(perguntas) == n + 1 and "toque" in perguntas[-1][1].lower() and not j.modo_tablet, "tela de toque: oferece o modo tablet")
j.apos_abrir(None); ok(len(perguntas) == n + 1, "pergunta só uma vez")
j.preferencias["tablet_perguntado"] = False; resposta["v"] = QMessageBox.Yes; j.apos_abrir(None); esperar(5)
ok(j.modo_tablet, "aceitou: liga o modo tablet")
j.definir_modo_tablet(False); esperar(5)

# ====================================================================
# Correção: tecla tirada de outra ação volta se mudar de ideia
# ====================================================================
print("--- tecla tomada volta")
teclas_antes = dict(j.atalhos)
t = tela_servicos.TelaServicos(j, j.atalhos, ao_salvar=j._servicos_salvos)
def achar(nome): return next(i for i, d_, _c in t.servicos() if d_["nome"] == nome)
t.arvore.setCurrentItem(achar("Consulta RioCard")); esperar()
original = t.dados(achar("Consulta RioCard"))["tecla"]
t._tecla_capturada("F6"); t._tecla_capturada("F6")
ok(t.dados(achar("Consulta RioCard"))["tecla"] == "F6" and t.teclas_fixas["pix"] == "", "F6 tirada do Pix")
t._tecla_capturada("Ctrl+9")
ok(t.teclas_fixas["pix"] == "F6", "mudou para Ctrl+9: F6 volta para o Pix")
t._tecla_capturada("F6"); t._tecla_capturada("F6"); t._definir_tecla("")
ok(t.teclas_fixas["pix"] == "F6", "Sem atalho: F6 volta para o Pix")
t._tecla_capturada("1"); t._tecla_capturada("1")
ok(t.dados(achar("Xerox"))["tecla"] == "", "tirou o 1 da Xerox")
t._tecla_capturada(original)
ok(t.dados(achar("Xerox"))["tecla"] == "1", "trocou de novo: o 1 volta para a Xerox")
t.novo_servico(); novo = t.arvore.currentItem(); t.campo_nome.setText("Teste"); t.campo_preco.setText("1")
t._tecla_capturada("F7"); t._tecla_capturada("F7")
ok(t.teclas_fixas["debito"] == "", "F7 tirada do Débito")
t.remover()
ok(t.teclas_fixas["debito"] == "F7", "removeu o serviço novo: F7 volta para o Débito")
t.arvore.setCurrentItem(achar("Consulta RioCard")); t._tecla_capturada("F6"); t._tecla_capturada("F6")
resposta["v"] = QMessageBox.Yes; t.reject()
ok(j.atalhos == teclas_antes and j.atalhos["pix"] == "F6", "Cancelar: nada muda, Pix continua com F6")

j.close()
print("\nFALHAS:", len(falhas))
