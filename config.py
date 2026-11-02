"""
config.py - Lê e grava o arquivo de configuração (config.json).

O config.json fica na pasta de dados (veja pasta_base). Nele estão o nome
da loja, os serviços com seus preços/taxas e as taxas da maquininha.
Para mudar um preço, basta editar o config.json (pelo Bloco de Notas, por
exemplo) e usar o menu "Arquivo > Recarregar configurações" no programa.

Se o config.json não existir, ele é criado automaticamente com os valores padrão.

Serviços com "cobra_taxa_maquininha": false (recargas e boletos) não entram na
conta da taxa da maquininha: o valor da recarga/boleto e a taxa dele são
cobrados à parte, direto na maquininha. A loja cobra só o preço do serviço.

Serviços com "valor_de_terceiros": true (Recarga RioCard, Recarga de celular,
Pagamento de boletos) cobram um valor que não é da loja. Com a opção
"Pedir o valor do boleto/recarga" ligada (Arquivo › Preferências › Atendimento),
o funcionário digita esse valor e o programa soma a taxa do serviço; o valor do
boleto/recarga só serve para o troco e fica guardado à parte no banco (nunca
entra no faturamento, nas notinhas nem nos totais do relatório).

Dados da loja ("loja": nome, endereço, telefone, CNPJ e logo): ficam SÓ aqui e
valem para o programa inteiro (título da janela, notinhas, relatórios e páginas de
teste). São preenchidos na janela de boas-vindas da primeira vez que o programa abre
("loja_confirmada" vira true) e mudam em Arquivo › Preferências › Loja.

Cada serviço tem também:
  "id"                -> um código que nunca muda (as teclas de atalho usam ele);
                         criado sozinho na primeira vez que o programa abre;
  "ativo"             -> false = serviço removido: some da tela, mas o nome dele
                         continua nos atendimentos antigos e nos relatórios;
  "nomes_anteriores"  -> nomes que o serviço já teve (para o relatório saber a
                         categoria de atendimentos feitos antes de renomear).
E "categorias" guarda a ordem das categorias (inclusive as ainda vazias).
A tela Arquivo › Serviços e preços cuida de tudo isso.
"""

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from decimal import Decimal


NOME_PASTA_DADOS = "EasyServ"
ARQUIVO_PORTATIL = "portatil.txt"


def pasta_programa():
    """
    A pasta onde o programa está instalado (a do .exe) ou, rodando pelo Python,
    a pasta do código. Aqui ficam só os arquivos do programa, nunca os dados.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def pasta_base():
    """
    A pasta dos DADOS: banco, config.json, preferências, layouts, temas, notas,
    relatórios e backups.
      - Programa instalado (.exe): %APPDATA%\\EasyServ. Assim não dá erro de permissão
        (a pasta do programa pode ser só de leitura) e uma atualização nunca mexe nos dados.
      - Com um arquivo "portatil.txt" ao lado do .exe: tudo ao lado do .exe (pendrive).
      - Rodando pelo Python (desenvolvimento): a pasta do código, como sempre foi.
      - A variável de ambiente EASYSERV_DADOS, se existir, manda em tudo (usada nos testes).
    """
    escolhida = os.environ.get("EASYSERV_DADOS")
    if not escolhida:
        programa = pasta_programa()
        if not getattr(sys, "frozen", False) or os.path.exists(os.path.join(programa, ARQUIVO_PORTATIL)):
            escolhida = programa
        else:
            appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
            escolhida = os.path.join(appdata, NOME_PASTA_DADOS)
    os.makedirs(escolhida, exist_ok=True)
    return escolhida


def recurso(nome):
    """
    Caminho de um arquivo que vem junto com o programa (logo, ícone, licença).
    No .exe do PyInstaller eles ficam na pasta interna do programa (sys._MEIPASS).
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    if nome.upper().endswith(".TXT"):
        return os.path.join(base, nome)  # LICENCA.txt e afins ficam na raiz
    return os.path.join(base, "recursos", nome)


ARQUIVO_CONFIG = os.path.join(pasta_base(), "config.json")

# Tipos de serviço:
#   "unidade" -> preço x quantidade (xerox, impressão, consulta, recargas, boletos...)
#   "valor"   -> o cliente informa um valor e soma-se a taxa (não é mais usado pelos
#                serviços de fábrica, mas continua funcionando se alguém configurar)
LOJA_PADRAO = {"nome": "Minha Loja", "endereco": "", "telefone": "", "cnpj": "", "logo": ""}
CAMPOS_LOJA = tuple(LOJA_PADRAO)

CONFIG_PADRAO = {
    "nome_loja": "Minha Loja",       # (cópia de loja["nome"], para versões antigas lerem)
    "loja": dict(LOJA_PADRAO),
    "loja_confirmada": False,        # False = mostra a janela "Dados da sua loja" ao abrir
    "servicos": [
        {"grupo": "Impressão e documentos", "nome": "Xerox", "tipo": "unidade", "preco": 0.50},
        {"grupo": "Impressão e documentos", "nome": "Xerox colorida", "tipo": "unidade", "preco": 1.50},
        {"grupo": "Impressão e documentos", "nome": "Impressão preto e branco", "tipo": "unidade", "preco": 1.50},
        {"grupo": "Impressão e documentos", "nome": "Impressão colorida", "tipo": "unidade", "preco": 2.50},
        {"grupo": "Impressão e documentos", "nome": "Criação de currículo", "tipo": "unidade", "preco": 5.00},
        {"grupo": "Impressão e documentos", "nome": "Digitalização de documentos", "tipo": "unidade", "preco": 3.00},
        {"grupo": "Consulta", "nome": "Consulta RioCard", "tipo": "unidade", "preco": 3.00},
        {"grupo": "RecargaPay", "nome": "Recarga RioCard", "tipo": "unidade", "preco": 1.00,
         "cobra_taxa_maquininha": False, "valor_de_terceiros": True},
        {"grupo": "RecargaPay", "nome": "Recarga de celular", "tipo": "unidade", "preco": 1.00,
         "cobra_taxa_maquininha": False, "valor_de_terceiros": True},
        {"grupo": "RecargaPay", "nome": "Pagamento de boletos", "tipo": "unidade", "preco": 2.00,
         "cobra_taxa_maquininha": False, "valor_de_terceiros": True},
    ],
    # Taxa da maquininha em porcentagem, por forma de pagamento.
    "taxas_maquininha": {"Débito": 5.0, "Crédito": 5.0},
    # Privacidade: o que fazer com o nome e o telefone do cliente (Arquivo › Preferências).
    "dados_cliente": {"guardar": "apagar", "dias": 30},
    # Opções do atendimento (Arquivo › Preferências › Atendimento).
    "atendimento": {"pedir_valor_terceiros": False, "mostrar_repasses": False},
    # Backup (Arquivo › Backup): pasta escolhida (vazio = backups/ na pasta de dados) e
    # se faz backup sozinho ao fechar o expediente (Preferências › Backup).
    "backup": {"pasta": "", "ao_fechar_expediente": False},
}

# Serviços de fábrica que cobram valor de terceiros. Vale para o config.json de versões
# antigas, que ainda não têm a chave "valor_de_terceiros".
IDS_VALOR_DE_TERCEIROS = ("recarga_riocard", "recarga_de_celular", "pagamento_de_boletos")

# Opções de "Guardar dados do cliente".
#   "nao"    -> nome e telefone só servem para imprimir a nota do cliente na hora (não vão pro banco);
#   "apagar" -> vão pro banco e são apagados depois de "dias" dias (quando o programa abre);
#   "sempre" -> ficam guardados.
GUARDAR_DADOS_CLIENTE = {
    "nao": "Não guardar",
    "apagar": "Apagar automaticamente depois de alguns dias",
    "sempre": "Guardar sempre",
}
DIAS_MINIMO, DIAS_MAXIMO = 1, 3650

# As formas de pagamento são fixas no código (a ordem é a dos botões na tela).
FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Débito", "Crédito"]


class ErroConfig(Exception):
    """Erro lançado quando o config.json está com algum problema."""


@dataclass
class Servico:
    """Um serviço da loja. O @dataclass cria o __init__ automaticamente pra gente."""
    nome: str
    grupo: str
    tipo: str            # "unidade" ou "valor"
    preco: Decimal       # usado quando tipo == "unidade"
    taxa: Decimal        # usado quando tipo == "valor"
    cobra_taxa_maquininha: bool = True  # False = a taxa do cartão não incide sobre este serviço
    id: str = ""                        # código fixo do serviço (ex.: "xerox")
    ativo: bool = True                  # False = removido (só aparece no histórico)
    nomes_anteriores: tuple = ()
    valor_de_terceiros: bool = False    # True = recarga/boleto: o valor digitado não é da loja

    @property
    def preco_do_servico(self):
        """O que a loja cobra pelo serviço (o preço, ou a taxa no tipo "valor")."""
        return self.preco if self.tipo == "unidade" else self.taxa

    def nome_do_valor(self):
        """Como chamar o valor de terceiros na tela: 'boleto', 'recarga' ou 'boleto/recarga'."""
        nome = self.nome.lower()
        if "boleto" in nome:
            return "boleto"
        if "recarga" in nome:
            return "recarga"
        return "boleto/recarga"


@dataclass
class Configuracao:
    """Todas as configurações do programa, já convertidas para os tipos certos."""
    nome_loja: str
    servicos: list          # só os ativos, na ordem da tela
    taxas_maquininha: dict  # ex.: {"Débito": Decimal("5"), "Crédito": Decimal("5")}
    # {"guardar": "nao" | "apagar" | "sempre", "dias": 30}
    dados_cliente: dict = None
    servicos_desativados: list = None   # os removidos (continuam valendo para o histórico)
    categorias: list = None             # nomes das categorias, na ordem
    # {"pedir_valor_terceiros": False, "mostrar_repasses": False}
    atendimento: dict = None
    loja: dict = None                   # {"nome", "endereco", "telefone", "cnpj", "logo"}
    loja_confirmada: bool = True        # False = ainda não passou pela janela de boas-vindas
    backup: dict = None                 # {"pasta": "", "ao_fechar_expediente": False}

    def pede_valor(self, servico):
        """True se, para este serviço, o funcionário digita o valor do boleto/recarga."""
        return bool(self.atendimento and self.atendimento["pedir_valor_terceiros"] and servico.valor_de_terceiros)

    def categoria_de(self, nome_servico):
        """A categoria de um serviço pelo nome (vale para desativados e nomes antigos). None se não achar."""
        for servico in self.servicos + self.servicos_desativados:
            if nome_servico == servico.nome or nome_servico in servico.nomes_anteriores:
                return servico.grupo
        return None


def salvar_config(dados):
    """Grava o dicionário de configuração no config.json (bem formatado e com acentos)."""
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def _para_decimal(valor, descricao):
    """Converte um número do JSON para Decimal, avisando se estiver errado."""
    try:
        numero = Decimal(str(valor))
    except Exception:
        raise ErroConfig(f"Valor inválido em {descricao}: {valor!r}")
    if not numero.is_finite() or numero < 0:
        raise ErroConfig(f"Valor inválido em {descricao}: {valor!r}")
    return numero


def _para_booleano(valor, nome, chave="cobra_taxa_maquininha"):
    """Confere se o valor do JSON é true ou false."""
    if not isinstance(valor, bool):
        raise ErroConfig(f"Em '{nome}', \"{chave}\" deve ser true ou false (sem aspas).")
    return valor


def criar_id(nome, existentes):
    """Um código para o serviço a partir do nome: 'Xerox colorida' -> 'xerox_colorida' (sem repetir)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_") or "servico"
    codigo, numero = base, 2
    while codigo in existentes:
        codigo, numero = f"{base}_{numero}", numero + 1
    return codigo


def _garantir_ids(dados):
    """Dá um id a cada serviço que ainda não tem (config.json de versão antiga). True se mudou algo."""
    servicos = [s for s in dados.get("servicos", []) if isinstance(s, dict)]
    usados = {s["id"] for s in servicos if isinstance(s.get("id"), str) and s["id"]}
    mudou = False
    for servico in servicos:
        if not isinstance(servico.get("id"), str) or not servico["id"]:
            servico["id"] = criar_id(str(servico.get("nome", "")), usados)
            usados.add(servico["id"])
            mudou = True
    return mudou


def carregar_config():
    """Lê o config.json e devolve um objeto Configuracao. Cria o arquivo se não existir."""
    if not os.path.exists(ARQUIVO_CONFIG):
        salvar_config(CONFIG_PADRAO)

    try:
        with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ErroConfig(
            f"O arquivo config.json tem um erro de digitação na linha {erro.lineno}.\n"
            "Confira vírgulas, aspas e chaves { }."
        )

    if not isinstance(dados, dict) or not isinstance(dados.get("servicos", []), list):
        raise ErroConfig("O config.json precisa ter a lista \"servicos\".")
    if _garantir_ids(dados) | _garantir_loja(dados):
        try:
            salvar_config(dados)  # grava os ids novos, para eles não mudarem mais
        except OSError:
            pass  # sem permissão: os ids valem só nesta vez (são os mesmos na próxima, pelo nome)

    servicos, desativados, ids = [], [], set()
    for i, s in enumerate(dados.get("servicos", []), start=1):
        if not isinstance(s, dict):
            raise ErroConfig(f"O serviço nº {i} do config.json está com o formato errado.")
        nome = s.get("nome")
        tipo = s.get("tipo")
        if not nome or tipo not in ("unidade", "valor"):
            raise ErroConfig(f"O serviço nº {i} do config.json precisa de 'nome' e 'tipo' (unidade ou valor).")
        if s["id"] in ids:
            raise ErroConfig(f"Dois serviços do config.json têm o mesmo id: {s['id']!r}.")
        ids.add(s["id"])
        anteriores = s.get("nomes_anteriores", [])
        servico = Servico(
            nome=nome,
            grupo=s.get("grupo") or "Outros",
            tipo=tipo,
            preco=_para_decimal(s.get("preco", 0), f"preço de '{nome}'"),
            taxa=_para_decimal(s.get("taxa", 0), f"taxa de '{nome}'"),
            cobra_taxa_maquininha=_para_booleano(s.get("cobra_taxa_maquininha", True), nome),
            id=s["id"],
            ativo=_para_booleano(s.get("ativo", True), nome, "ativo"),
            nomes_anteriores=tuple(n for n in anteriores if isinstance(n, str)) if isinstance(anteriores, list) else (),
            valor_de_terceiros=_para_booleano(s.get("valor_de_terceiros", s["id"] in IDS_VALOR_DE_TERCEIROS),
                                              nome, "valor_de_terceiros"),
        )
        (servicos if servico.ativo else desativados).append(servico)
    if not servicos:
        raise ErroConfig("Nenhum serviço ativo cadastrado no config.json.")

    # Ordem das categorias: a salva, mais as que aparecem nos serviços e não estão nela.
    categorias = [c for c in dados.get("categorias", []) if isinstance(c, str) and c.strip()]
    for servico in servicos + desativados:
        if servico.grupo not in categorias:
            categorias.append(servico.grupo)

    taxas = {}
    for forma, valor in dados.get("taxas_maquininha", {}).items():
        taxas[forma] = _para_decimal(valor, f"taxa da maquininha ({forma})")

    loja = conferir_loja(dados.get("loja"))
    return Configuracao(
        nome_loja=loja["nome"],
        servicos=servicos,
        taxas_maquininha=taxas,
        dados_cliente=_dados_cliente(dados.get("dados_cliente")),
        servicos_desativados=desativados,
        categorias=categorias,
        atendimento=_atendimento(dados.get("atendimento")),
        loja=loja,
        loja_confirmada=dados.get("loja_confirmada") is not False,
        backup=_backup(dados.get("backup")),
    )


def _dados_cliente(valor):
    """Confere a opção "Guardar dados do cliente". O que estiver errado volta para o padrão."""
    resultado = dict(CONFIG_PADRAO["dados_cliente"])
    if isinstance(valor, dict):
        if valor.get("guardar") in GUARDAR_DADOS_CLIENTE:
            resultado["guardar"] = valor["guardar"]
        dias = valor.get("dias")
        if isinstance(dias, int) and not isinstance(dias, bool):
            resultado["dias"] = min(max(dias, DIAS_MINIMO), DIAS_MAXIMO)
    return resultado


def _atendimento(valor):
    """Confere as opções do atendimento. O que estiver faltando ou errado fica desligado."""
    resultado = dict(CONFIG_PADRAO["atendimento"])
    if isinstance(valor, dict):
        for chave in resultado:
            if isinstance(valor.get(chave), bool):
                resultado[chave] = valor[chave]
    return resultado


def conferir_loja(valor):
    """Os dados da loja, conferidos (o que faltar ou estiver errado fica vazio)."""
    resultado = dict(LOJA_PADRAO)
    if isinstance(valor, dict):
        for chave in CAMPOS_LOJA:
            if isinstance(valor.get(chave), str):
                resultado[chave] = valor[chave].strip()
    if not resultado["nome"]:
        resultado["nome"] = LOJA_PADRAO["nome"]
    return resultado


def _garantir_loja(dados):
    """
    config.json de antes da 1.4 (sem "loja"): junta o nome que já estava configurado
    e o cabeçalho que estava no layout das notinhas, para a pessoa só confirmar na
    janela de boas-vindas. True se mudou algo (para gravar).
    """
    if isinstance(dados.get("loja"), dict):
        return False
    loja = dict(LOJA_PADRAO)
    if isinstance(dados.get("nome_loja"), str) and dados["nome_loja"].strip():
        loja["nome"] = dados["nome_loja"].strip()
    antigo = _cabecalho_do_layout_antigo()
    for chave_layout, chave in (("nome_loja", "nome"), ("endereco", "endereco"), ("telefone", "telefone"),
                                ("cnpj", "cnpj"), ("logo", "logo")):
        if antigo.get(chave_layout):
            loja[chave] = antigo[chave_layout]
    dados["loja"] = loja
    dados["loja_confirmada"] = False
    return True


def _cabecalho_do_layout_antigo():
    """O cabeçalho que o layout_notas.json guardava até a 1.3 (nota da loja; senão, a do cliente)."""
    try:
        with open(os.path.join(pasta_base(), "layout_notas.json"), "r", encoding="utf-8") as arquivo:
            layout = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}
    resultado = {}
    for via in ("cliente", "loja"):  # a da loja ganha (vem por último)
        modelo = layout.get(via) if isinstance(layout, dict) else None
        if isinstance(modelo, dict):
            for chave in ("nome_loja", "endereco", "telefone", "cnpj", "logo"):
                if isinstance(modelo.get(chave), str) and modelo[chave].strip():
                    resultado[chave] = modelo[chave].strip()
    return resultado


def salvar_loja(loja, confirmada=True):
    """Grava os dados da loja no config.json (o resto do arquivo não muda)."""
    with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    dados["loja"] = conferir_loja(loja)
    dados["nome_loja"] = dados["loja"]["nome"]
    dados["loja_confirmada"] = confirmada
    salvar_config(dados)


def _backup(valor):
    resultado = dict(CONFIG_PADRAO["backup"])
    if isinstance(valor, dict):
        if isinstance(valor.get("pasta"), str):
            resultado["pasta"] = valor["pasta"]
        if isinstance(valor.get("ao_fechar_expediente"), bool):
            resultado["ao_fechar_expediente"] = valor["ao_fechar_expediente"]
    return resultado


def atualizar_config(**chaves):
    """Grava só estas chaves no config.json (ex.: backup={...}); o resto continua igual."""
    with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    dados.update(chaves)
    salvar_config(dados)
