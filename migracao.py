"""
migracao.py - Traz os dados da versão sem instalador para a pasta de dados nova.

Até a versão 1.1 o programa era um .exe solto, com os dados ao lado dele
(o banco, config.json, notas/...). A partir da 1.2 os dados ficam em
%APPDATA%\\EasyServ. Na primeira vez que o EasyServ abre com a pasta de dados
vazia, ele procura os dados antigos e oferece copiar tudo.

Os dados são COPIADOS (nunca movidos nem apagados): a pasta antiga fica como
estava, com um aviso .txt dizendo para onde os dados foram.
"""

import json
import os
import shutil
from datetime import datetime

from config import pasta_base, pasta_programa

# Tudo o que é dado da pessoa (o resto da pasta antiga é o programa velho).
BANCOS = ("easyserv.db", "maisbella.db")  # o nome novo e o das versões até a 1.3
ITENS = ("config.json", "preferencias.json", "layout_notas.json", *BANCOS, "treino.db",
         "notas", "notas_treino", "relatorios", "relatorios_treino", "backups", "imagens")
MARCA_PERGUNTADO = "migracao.json"   # na pasta de dados: "já perguntei, não pergunte de novo"
AVISO_NA_ORIGEM = "DADOS_COPIADOS_PARA_O_EASYSERV.txt"


def tem_dados(pasta):
    return any(os.path.exists(os.path.join(pasta, nome)) for nome in (*BANCOS, "config.json"))


def pastas_para_procurar():
    """Lugares comuns onde o .exe antigo costuma ficar (até um nível de subpasta)."""
    casa = os.path.expanduser("~")
    raizes = [pasta_programa()]
    for nome in ("Desktop", "Área de Trabalho", "Documents", "Documentos", "Downloads",
                 os.path.join("OneDrive", "Desktop"), os.path.join("OneDrive", "Área de Trabalho"),
                 os.path.join("OneDrive", "Documents"), os.path.join("OneDrive", "Documentos")):
        raizes.append(os.path.join(casa, nome))
    pastas = []
    for raiz in raizes:
        if not os.path.isdir(raiz):
            continue
        pastas.append(raiz)
        try:
            pastas += [entrada.path for entrada in os.scandir(raiz) if entrada.is_dir()]
        except OSError:
            pass
    return pastas


def encontrar_dados_antigos(pastas=None):
    """Pastas com dados antigos (a mais recente primeiro), sem contar a pasta de dados atual."""
    destino = os.path.normcase(os.path.abspath(pasta_base()))
    achadas = []
    for pasta in pastas if pastas is not None else pastas_para_procurar():
        if os.path.normcase(os.path.abspath(pasta)) != destino and tem_dados(pasta) \
                and _banco_em(pasta):
            achadas.append(pasta)
    unicas = list(dict.fromkeys(achadas))
    return sorted(unicas, key=lambda p: os.path.getmtime(_banco_em(p)), reverse=True)


def _banco_em(pasta):
    """O arquivo do banco que existe na pasta (nome novo ou antigo), ou None."""
    return next((os.path.join(pasta, nome) for nome in BANCOS if os.path.exists(os.path.join(pasta, nome))), None)


def precisa_oferecer():
    """True na primeira vez: pasta de dados ainda vazia e a pergunta ainda não foi feita."""
    base = pasta_base()
    return not tem_dados(base) and not os.path.exists(os.path.join(base, MARCA_PERGUNTADO))


def marcar_perguntado(resposta, origem=""):
    with open(os.path.join(pasta_base(), MARCA_PERGUNTADO), "w", encoding="utf-8") as arquivo:
        json.dump({"resposta": resposta, "origem": origem, "quando": datetime.now().isoformat(timespec="seconds")},
                  arquivo, ensure_ascii=False)


def guardar_dados_atuais():
    """
    Antes de importar por cima: MOVE os dados atuais para backups/antes_da_importacao_<data>/.
    Devolve a pasta onde ficaram.
    """
    base = pasta_base()
    guarda = os.path.join(base, "backups", f"antes_da_importacao_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")
    os.makedirs(guarda, exist_ok=True)
    for nome in ITENS:
        caminho = os.path.join(base, nome)
        if nome != "backups" and os.path.exists(caminho):
            shutil.move(caminho, os.path.join(guarda, nome))
    return guarda


def migrar(origem, destino=None):
    """Copia os dados de 'origem' para a pasta de dados. Devolve a lista do que foi copiado."""
    destino = destino or pasta_base()
    copiados = []
    for nome in ITENS:
        de, para = os.path.join(origem, nome), os.path.join(destino, nome)
        if os.path.isdir(de):
            shutil.copytree(de, para, dirs_exist_ok=True)
            copiados.append(nome)
        elif os.path.isfile(de) and not os.path.exists(para):
            shutil.copy2(de, para)  # copy2 mantém a data do arquivo
            copiados.append(nome)
    try:
        with open(os.path.join(origem, AVISO_NA_ORIGEM), "w", encoding="utf-8") as aviso:
            aviso.write(f"Em {datetime.now().strftime('%d/%m/%Y %H:%M')} estes dados foram copiados para:\n"
                        f"{destino}\n\nO EasyServ agora usa a pasta acima. Esta pasta pode ser guardada como "
                        "cópia de segurança ou apagada quando você tiver certeza de que está tudo certo.\n")
    except OSError:
        pass  # (pasta só de leitura: tudo bem, a cópia já foi feita)
    marcar_perguntado("migrou", origem)
    return copiados
