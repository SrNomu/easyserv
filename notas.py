"""
notas.py - Monta as notinhas seguindo o layout escolhido em "Configurar notinhas".

A nota é feita em etapas:
  1. montar_linhas()      -> lista de linhas de texto, respeitando o layout
                             (o que aparece, alinhamento, caracteres por linha);
  2. renderizar_imagem()  -> desenha as linhas numa imagem, com logo e fonte
                             no tamanho escolhido (pré-visualização e impressão gráfica);
  3. gerar_nota()         -> salva a nota em .txt na pasta "notas/";
     imprimir_nota()      -> manda a nota para a impressora.

As notas ficam separadas por dia:
    notas/2026-11-01/atendimento_000012_loja.txt
"""

import os
import textwrap
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import impressao
import treino
from config import pasta_base
from layout_notas import COLUNAS_TEXTO, PAPEIS, caminho_logo
from utils import formatar_percentual, formatar_reais

PASTA_NOTAS = os.path.join(pasta_base(), "notas")
# Vai no rodapé de todas as notinhas e do resumo de fechamento (não dá para esconder).
AVISO_FISCAL = "NÃO É DOCUMENTO FISCAL"

# Resolução usada para desenhar a nota: 203 pontos por polegada (8 pontos por mm),
# que é a resolução das impressoras térmicas mais comuns.
DPI = 203

PASTA_FONTES = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
# Fontes "monoespaçadas" (todas as letras com a mesma largura), para as colunas
# de valores ficarem alinhadas. (normal, negrito) - usa a primeira que existir.
FONTES = [("consola.ttf", "consolab.ttf"), ("cour.ttf", "courbd.ttf")]


@lru_cache(maxsize=None)  # guarda as fontes já carregadas, para não ler o arquivo toda hora
def carregar_fonte(tamanho_px, negrito=False):
    for normal, em_negrito in FONTES:
        caminho = os.path.join(PASTA_FONTES, em_negrito if negrito else normal)
        if os.path.exists(caminho):
            return ImageFont.truetype(caminho, tamanho_px)
    return ImageFont.load_default(tamanho_px)


def medidas(modelo, modo_texto=False):
    """
    Devolve (largura da imagem em pixels, tamanho da fonte em pixels, caracteres por linha).

    Impressora gráfica: o tamanho da fonte escolhido define quantos caracteres cabem.
    Impressora de texto: o número de caracteres é fixo (depende do papel), então
    calculamos a fonte que faz a pré-visualização ficar igual ao que vai sair.
    """
    largura_px = round(PAPEIS[modelo["papel"]] / 25.4 * DPI)
    if modo_texto:
        colunas = COLUNAS_TEXTO[modelo["papel"]]
        largura_letra = carregar_fonte(100).getlength("M") / 100  # largura de 1 letra com fonte de 1px
        tamanho_px = int(largura_px / colunas / largura_letra)
    else:
        tamanho_px = round(modelo["tamanho_fonte"] * DPI / 72)  # 1 ponto = 1/72 de polegada
        colunas = int(largura_px // carregar_fonte(tamanho_px).getlength("M"))
    return largura_px, tamanho_px, max(colunas, 16)


def montar_linhas(modelo, numero, atendimento, itens, via, modo_texto=False):
    """
    Monta a nota como uma lista de linhas: [(texto, negrito), ...].
    'via' é "loja" ou "cliente".
    """
    _, _, colunas = medidas(modelo, modo_texto)
    mostrar = modelo["mostrar"]
    centralizar = modelo["alinhamento"] == "centro"
    linhas = []

    def texto(conteudo, negrito=False, alinhado=False):
        """Adiciona um texto, quebrando em várias linhas se for comprido.
        alinhado=True segue o alinhamento escolhido no layout (esquerda ou centro)."""
        for paragrafo in conteudo.split("\n"):
            for parte in textwrap.wrap(paragrafo, colunas) or [""]:
                if alinhado and centralizar:
                    parte = parte.center(colunas).rstrip()
                linhas.append((parte, negrito))

    def par(esquerda, direita, negrito=False):
        """Texto à esquerda e valor encostado à direita: 'TOTAL:        R$ 10,00'."""
        espacos = colunas - len(esquerda) - len(direita)
        if espacos < 1:  # não cabe numa linha: o valor vai para a linha de baixo
            texto(esquerda, negrito)
            linhas.append((direita.rjust(colunas), negrito))
        else:
            linhas.append((esquerda + " " * espacos + direita, negrito))

    def separador(caractere="-"):
        linhas.append((caractere * colunas, False))

    # --- Cabeçalho (dados da loja, cada um se estiver marcado para aparecer) ---
    def da_loja(chave, caixa):
        return modelo.get(chave, "").strip() if mostrar.get(caixa, True) else ""
    if da_loja("nome_loja", "loja_nome"):
        texto(da_loja("nome_loja", "loja_nome"), negrito=True, alinhado=True)
    if da_loja("endereco", "loja_endereco"):
        texto(da_loja("endereco", "loja_endereco"), alinhado=True)
    if da_loja("telefone", "loja_telefone"):
        texto(f"Tel.: {da_loja('telefone', 'loja_telefone')}", alinhado=True)
    if da_loja("cnpj", "loja_cnpj"):
        texto(f"CNPJ: {da_loja('cnpj', 'loja_cnpj')}", alinhado=True)
    separador("=")
    if treino.ativo():
        texto(f"*** {treino.MARCA} ***", negrito=True, alinhado=True)
    texto("VIA DA LOJA" if via == "loja" else "VIA DO CLIENTE", negrito=True, alinhado=True)

    if mostrar["numero"]:
        texto(f"Atendimento nº: {numero:06d}")
    if mostrar["data_hora"]:
        texto(f"Data/hora: {atendimento['data_hora'].strftime('%d/%m/%Y %H:%M:%S')}")
    if mostrar["cliente_nome"] and atendimento["cliente_nome"]:
        texto(f"Cliente: {atendimento['cliente_nome']}")
    if mostrar["telefone"] and atendimento["cliente_telefone"]:
        texto(f"Telefone: {atendimento['cliente_telefone']}")

    # --- Itens ---
    if mostrar["itens"] and itens:
        separador()
        for item in itens:
            if mostrar["quantidade"]:
                texto(item["servico"])
                if item["tipo"] == "unidade":
                    detalhe = f"  {item['quantidade']} x {formatar_reais(item['valor_unitario'])}"
                else:
                    detalhe = (f"  {formatar_reais(item['valor_digitado'])}"
                               f" + taxa {formatar_reais(item['taxa_servico'])}")
                par(detalhe, formatar_reais(item["total"]))
            else:
                par(item["servico"], formatar_reais(item["total"]))

    # --- Totais e pagamento ---
    separador()
    if mostrar["taxa"] and atendimento["taxa_valor"] > 0:
        par("Subtotal:", formatar_reais(atendimento["subtotal"]))
        par(f"Taxa maquininha ({formatar_percentual(atendimento['taxa_percentual'])}):",
            formatar_reais(atendimento["taxa_valor"]))
        base = atendimento.get("taxa_base")  # (atendimentos antigos não têm esta informação)
        if base is not None and base != atendimento["subtotal"]:
            # Com recarga/boleto a taxa não incide sobre tudo: mostra sobre quanto foi.
            texto(f"  sobre {formatar_reais(base)} (sem recarga/boleto)")
    par("TOTAL:", formatar_reais(atendimento["total"]), negrito=True)
    if mostrar["forma_pagamento"]:
        texto(f"Pagamento: {atendimento['forma_pagamento']}")
    # Com boleto/recarga (repasse), o valor recebido e o troco incluem o valor do boleto,
    # que nunca aparece na nota: por isso eles ficam de fora.
    if mostrar["troco"] and atendimento["valor_recebido"] is not None and not atendimento.get("repasse"):
        par("Valor recebido:", formatar_reais(atendimento["valor_recebido"]))
        par("Troco:", formatar_reais(atendimento["troco"]))

    # --- Rodapé ---
    separador("=")
    if modelo["rodape"].strip():
        texto(modelo["rodape"].strip(), alinhado=True)
    # Sempre, nas duas notas, sem opção de esconder: a nota não substitui a nota fiscal.
    texto(AVISO_FISCAL, negrito=True, alinhado=True)
    if treino.ativo():
        texto(f"*** {treino.MARCA} ***", negrito=True, alinhado=True)
    return linhas


def texto_da_nota(linhas):
    """Junta as linhas num texto só (para o .txt e para impressoras de texto)."""
    return "\n".join(conteudo for conteudo, _ in linhas) + "\n"


def _preparar_logo(modelo, largura_px):
    """Abre a logo, troca o fundo transparente por branco e ajusta o tamanho. None se não houver."""
    caminho = caminho_logo(modelo)
    if not caminho:
        return None
    try:
        with Image.open(caminho) as original:
            colorida = original.convert("RGBA")
    except OSError:
        return None  # arquivo corrompido ou não é imagem
    fundo = Image.new("RGBA", colorida.size, "white")
    logo = Image.alpha_composite(fundo, colorida).convert("L")  # "L" = tons de cinza
    largura = round(largura_px * modelo["tamanho_logo"] / 100)
    altura = max(1, round(logo.height * largura / logo.width))
    return logo.resize((largura, altura), Image.LANCZOS)


def renderizar_imagem(modelo, linhas, modo_texto=False):
    """Desenha a nota numa imagem em tons de cinza, do tamanho real do papel (a 203 DPI)."""
    largura_px, tamanho_px, _ = medidas(modelo, modo_texto)
    altura_linha = round(tamanho_px * 1.2)
    margem = altura_linha // 2
    # Impressora de texto não imprime logo nem negrito: a pré-visualização mostra isso.
    logo = None if modo_texto else _preparar_logo(modelo, largura_px)

    altura = margem * 2 + len(linhas) * altura_linha
    if logo:
        altura += logo.height + margem
    imagem = Image.new("L", (largura_px, altura), 255)  # 255 = branco

    y = margem
    if logo:
        x = (largura_px - logo.width) // 2 if modelo["alinhamento"] == "centro" else 0
        imagem.paste(logo, (x, y))
        y += logo.height + margem

    desenho = ImageDraw.Draw(imagem)
    for conteudo, negrito in linhas:
        fonte = carregar_fonte(tamanho_px, negrito and not modo_texto)
        desenho.text((0, y), conteudo, font=fonte, fill=0)  # 0 = preto
        y += altura_linha
    return imagem


def usa_modo_texto(layout):
    """True se a impressora configurada só imprime texto. Se não der para saber, False."""
    try:
        nome = impressao.escolher_impressora(layout["impressao"]["impressora"])
        return impressao.eh_impressora_texto(nome)
    except impressao.ErroImpressao:
        return False


def pasta_notas():
    """A pasta das notas: notas/ ou, no modo treinamento, notas_treino/."""
    return treino.PASTA_NOTAS_TREINO if treino.ativo() else PASTA_NOTAS


def caminho_da_nota(numero, data_hora, via="loja"):
    """Onde fica o .txt da nota: notas/AAAA-MM-DD/atendimento_000012_loja.txt."""
    pasta_do_dia = os.path.join(pasta_notas(), data_hora.strftime("%Y-%m-%d"))
    return os.path.join(pasta_do_dia, f"atendimento_{numero:06d}_{via}.txt")


def gerar_nota(layout, numero, atendimento, itens, via="loja", modo_texto=False):
    """Salva a nota em .txt e devolve o caminho completo do arquivo."""
    caminho = caminho_da_nota(numero, atendimento["data_hora"], via)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)  # cria a pasta do dia se não existir

    linhas = montar_linhas(layout[via], numero, atendimento, itens, via, modo_texto)
    # "utf-8-sig" grava os acentos de um jeito que o Bloco de Notas do Windows sempre entende.
    with open(caminho, "w", encoding="utf-8-sig") as arquivo:
        arquivo.write(texto_da_nota(linhas))
    return caminho


def imprimir_nota(layout, numero, atendimento, itens, via="loja"):
    """
    Imprime a nota na impressora configurada (ou na padrão do Windows).
    Lança impressao.ErroImpressao se algo der errado.
    """
    opcoes = layout["impressao"]
    impressora = impressao.escolher_impressora(opcoes["impressora"])
    modelo = layout[via]
    nome_documento = f"Atendimento {numero:06d} - {via}"

    if impressao.eh_impressora_texto(impressora):
        linhas = montar_linhas(modelo, numero, atendimento, itens, via, modo_texto=True)
        impressao.imprimir_texto(impressora, texto_da_nota(linhas), opcoes["tirar_acentos"], nome_documento)
    else:
        linhas = montar_linhas(modelo, numero, atendimento, itens, via)
        imagem = renderizar_imagem(modelo, linhas)
        impressao.imprimir_imagem(impressora, imagem, PAPEIS[modelo["papel"]], nome_documento)
