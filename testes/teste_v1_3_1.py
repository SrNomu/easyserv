"""Teste automático do EasyServ. Rode todos com: python testes/rodar_testes.py"""
import sys, os, re, json, glob, importlib, tempfile, shutil
pasta, saida = sys.argv[1], sys.argv[2]
os.makedirs(saida, exist_ok=True)
sys.path.insert(0, pasta); os.chdir(pasta)
# Este teste começa SEM config.json, para ver o programa "de fábrica".
for nome in ("config.json", "layout_notas.json", "preferencias.json"):
    if os.path.exists(nome): os.remove(nome)
import atualizacao
def sem_internet(*a, **k):
    raise AssertionError("teste tentou acessar a internet")
atualizacao.abrir_url = sem_internet
import config, layout_notas, banco, integridade, migracao, versao

falhas = []
def ok(c, m):
    print(("OK    " if c else "FALHA ") + m)
    if not c: falhas.append(m)

print("--- de fábrica")
c = config.carregar_config()
ok(c.nome_loja == "Minha Loja", f"nome padrão: {c.nome_loja}")
ok(json.load(open("config.json", encoding="utf-8"))["nome_loja"] == "Minha Loja", "config.json criado com Minha Loja")
ok(layout_notas.carregar_layout()["loja"]["nome_loja"] == "Minha Loja", "notinha de fábrica: Minha Loja")
codigo = "".join(open(f, encoding="utf-8").read() for f in glob.glob("*.py") + glob.glob("atualizador/*.py") + glob.glob("*.txt"))
sobra = [l.strip() for l in codigo.splitlines() if "maisbella" in l.lower()]
ok(all("maisbella.db" in l.lower() for l in sobra), f"MaisBella só no nome do banco antigo (compatibilidade): {sobra}")
ok("C:\\Users\\" not in codigo and not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", codigo), "sem caminho de usuário nem e-mail no código")

print("--- banco: nome novo e antigo")
ok(os.path.basename(banco.ARQUIVO_BANCO) == "easyserv.db", "instalação nova usa easyserv.db")
tmp = tempfile.mkdtemp(dir=saida)
open(os.path.join(tmp, "maisbella.db"), "w").close()
ok(os.path.basename(banco._escolher_arquivo_banco(tmp)) == "maisbella.db", "quem já usa continua no maisbella.db (sem renomear)")
open(os.path.join(tmp, "easyserv.db"), "w").close()
ok(os.path.basename(banco._escolher_arquivo_banco(tmp)) == "easyserv.db", "se existir o novo, usa o novo")
ok(migracao.tem_dados(tmp) and migracao._banco_em(tmp).endswith("easyserv.db"), "migração reconhece os dois nomes")
so_antigo = tempfile.mkdtemp(dir=saida); open(os.path.join(so_antigo, "maisbella.db"), "w").close()
ok(migracao.encontrar_dados_antigos([so_antigo]) == [so_antigo], "acha dados antigos com maisbella.db")
ok("easyserv.db" in integridade.BANCOS and "maisbella.db" in integridade.BANCOS, "integridade confere os dois")

print("--- versão e licença")
ok(versao.VERSAO == "1.3.1" and versao.REPOSITORIO_GITHUB == "SrNomu/easyserv", "1.3.1 com o repositório")
ok(versao.NOTAS_DA_VERSAO[0][0] == "1.3.1", "notas da 1.3.1 no topo")
lic = open("LICENCA.txt", encoding="utf-8").read()
ok("Todos os direitos reservados" in lic and "visualização" in lic and "autorização" in lic, "LICENCA: código visível, direitos reservados")
ok(atualizacao.ler_lancamento is not None, "ok")
print(f"\n{len(falhas)} falha(s)")
