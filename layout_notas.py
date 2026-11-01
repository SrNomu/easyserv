"""
layout_notas.py - Lê e grava o layout das notinhas (arquivo layout_notas.json).

Existem dois modelos independentes: "loja" e "cliente". Cada modelo guarda:
  - textos do cabeçalho (nome, endereço, telefone, CNPJ) e do rodapé;
  - logo (se aparece, qual imagem e o tamanho);
  - quais informações aparecem (data/hora, número, cliente...);
  - tamanho da fonte, alinhamento e largura do papel.

Além dos modelos, há as opções de impressão (qual impressora usar),
que valem para as duas notas.

A tela que edita tudo isso fica em tela_notinhas.py.
"""

import copy
import json
import os
import shutil
from datetime import datetime

from config import ErroConfig, pasta_base

ARQUIVO_LAYOUT = os.path.join(pasta_base(), "layout_notas.json")
# As logos escolhidas são copiadas para esta pasta, para não se perderem
# se o arquivo original for apagado ou movido.
PASTA_IMAGENS = os.path.join(pasta_base(), "imagens")

MODELOS = {"loja": "Nota da loja", "cliente": "Nota do cliente"}

# Largura de papel -> largura útil de impressão em milímetros
# (a impressora não imprime até a borda, por isso é menor que o papel).
PAPEIS = {"58mm": 48, "80mm": 72, "A4": 190}

# Quantos caracteres cabem por linha em impressoras só de texto.
COLUNAS_TEXTO = {"58mm": 32, "80mm": 48, "A4": 80}

# Informações que podem ser mostradas ou escondidas: (chave, texto na tela).
CAMPOS = [
    ("data_hora", "Data/hora"),
    ("numero", "Nº do atendimento"),
    ("cliente_nome", "Nome do cliente"),
    ("telefone", "Telefone do cliente"),
    ("itens", "Itens"),
    ("quantidade", "Quantidade e detalhe"),
    ("forma_pagamento", "Forma de pagamento"),
    ("taxa", "Taxa da maquininha"),
    ("troco", "Valor recebido e troco"),
]

FONTE_MIN, FONTE_MAX = 6, 16
LOGO_MIN, LOGO_MAX = 20, 100


# Versão do formato do layout_notas.json. Na versão 2 o nome e o telefone do cliente
# passaram a vir desmarcados na nota da loja (privacidade): um arquivo antigo é
# ajustado uma vez ao abrir (a pessoa pode marcar de novo em Configurar notinhas).
VERSAO_LAYOUT_NOTAS = 2
CAMPOS_DO_CLIENTE = ("cliente_nome", "telefone")


def modelo_padrao(chave="cliente"):
    """
    Valores de fábrica de um modelo de nota ("loja" ou "cliente").
    Na nota da loja, nome e telefone do cliente vêm desmarcados: eles só
    aparecem na nota que fica com o próprio cliente.
    """
    modelo = {
        "nome_loja": "Minha Loja",
        "endereco": "",
        "telefone": "",
        "cnpj": "",
        "rodape": "Obrigado pela preferência!",
        "mostrar_logo": False,
        "logo": "",              # caminho da imagem, relativo à pasta do programa
        "tamanho_logo": 60,      # % da largura do papel
        "mostrar": {chave: True for chave, _ in CAMPOS},
        "tamanho_fonte": 9,      # em pontos (pt)
        "alinhamento": "centro", # "esquerda" ou "centro" (cabeçalho, logo e rodapé)
        "papel": "80mm",         # "58mm", "80mm" ou "A4"
    }
    if chave == "loja":
        for campo in CAMPOS_DO_CLIENTE:
            modelo["mostrar"][campo] = False
    return modelo


def impressao_padrao():
    return {
        "impressora": "",        # vazio = impressora padrão do Windows
        "tirar_acentos": False,  # para impressoras de texto que imprimem acentos errado
    }


def layout_padrao():
    return {
        "versao": VERSAO_LAYOUT_NOTAS,
        "loja": modelo_padrao("loja"),
        "cliente": modelo_padrao("cliente"),
        "impressao": impressao_padrao(),
    }


def _completar(dados, padrao):
    """
    Junta o que veio do arquivo com os valores padrão.
    Se faltar alguma chave (ex.: arquivo de uma versão antiga) ou o tipo
    estiver errado, usa o valor padrão. Assim o programa nunca quebra por isso.
    """
    resultado = {}
    for chave, valor_padrao in padrao.items():
        valor = dados.get(chave, valor_padrao) if isinstance(dados, dict) else valor_padrao
        if isinstance(valor_padrao, dict):
            resultado[chave] = _completar(valor, valor_padrao)
        elif isinstance(valor_padrao, bool):
            resultado[chave] = valor if isinstance(valor, bool) else valor_padrao
        elif isinstance(valor_padrao, int):
            resultado[chave] = valor if isinstance(valor, int) and not isinstance(valor, bool) else valor_padrao
        else:
            resultado[chave] = valor if isinstance(valor, str) else valor_padrao
    return resultado


def _validar_modelo(modelo):
    """Corrige valores fora do permitido."""
    padrao = modelo_padrao()
    if modelo["papel"] not in PAPEIS:
        modelo["papel"] = padrao["papel"]
    if modelo["alinhamento"] not in ("esquerda", "centro"):
        modelo["alinhamento"] = padrao["alinhamento"]
    modelo["tamanho_fonte"] = min(max(modelo["tamanho_fonte"], FONTE_MIN), FONTE_MAX)
    modelo["tamanho_logo"] = min(max(modelo["tamanho_logo"], LOGO_MIN), LOGO_MAX)
    return modelo


def carregar_layout():
    """Lê o layout_notas.json (cria com os valores padrão se não existir)."""
    if not os.path.exists(ARQUIVO_LAYOUT):
        salvar_layout(layout_padrao())
        return layout_padrao()
    try:
        with open(ARQUIVO_LAYOUT, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ErroConfig(
            f"O arquivo layout_notas.json tem um erro na linha {erro.lineno}.\n"
            "Corrija o arquivo ou apague-o para voltar ao padrão."
        )
    layout = _completar(dados, layout_padrao())
    for chave in MODELOS:
        _validar_modelo(layout[chave])
    versao = dados.get("versao", 1) if isinstance(dados, dict) else 1
    if not isinstance(versao, int) or versao < 2:
        # Arquivo de antes da versão 2: tira os dados do cliente da nota da loja (uma vez só).
        for campo in CAMPOS_DO_CLIENTE:
            layout["loja"]["mostrar"][campo] = False
        layout["versao"] = VERSAO_LAYOUT_NOTAS
        try:
            salvar_layout(layout)
        except OSError:
            pass  # sem permissão para gravar: vale só nesta vez, sem atrapalhar
    return layout


def salvar_layout(layout):
    with open(ARQUIVO_LAYOUT, "w", encoding="utf-8") as arquivo:
        json.dump(layout, arquivo, ensure_ascii=False, indent=2)


def copiar(dados):
    """Cópia independente do layout ou de um modelo (mudar a cópia não muda o original)."""
    return copy.deepcopy(dados)


def caminho_logo(modelo):
    """Caminho completo da logo do modelo, ou None se não houver logo/arquivo."""
    if not modelo["mostrar_logo"] or not modelo["logo"]:
        return None
    caminho = os.path.join(pasta_base(), modelo["logo"])
    return caminho if os.path.exists(caminho) else None


def guardar_logo(caminho_origem, chave_modelo):
    """
    Copia a imagem escolhida para a pasta "imagens/" do programa
    e devolve o caminho relativo (é ele que fica salvo no layout).
    """
    os.makedirs(PASTA_IMAGENS, exist_ok=True)
    extensao = os.path.splitext(caminho_origem)[1].lower()
    # A data/hora no nome evita sobrescrever a logo atual antes de você clicar em "Salvar".
    nome = f"logo_{chave_modelo}_{datetime.now():%Y%m%d_%H%M%S}{extensao}"
    shutil.copyfile(caminho_origem, os.path.join(PASTA_IMAGENS, nome))
    return os.path.join("imagens", nome)
