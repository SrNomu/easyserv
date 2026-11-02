"""
relatorio.py - O Relatório do dia: as contas e os arquivos (PDF, Excel e resumo 80mm).

A tela fica em tela_relatorio.py; aqui só tem a parte que não depende da tela:
  montar_relatorio()  -> lê o banco e soma tudo do dia escolhido;
  linhas_resumo()     -> o resumo em linhas de texto, no formato da notinha;
  imprimir_resumo()   -> manda o resumo para a impressora de notinha (papel 80mm);
  exportar_pdf()      -> salva o relatório em PDF (folha A4, desenhado em relatorio_a4.py);
  exportar_excel()    -> salva o relatório em Excel (.xlsx), com os números como números.

Privacidade: o nome e o telefone do cliente NUNCA entram no relatório (nem na
tela, nem no PDF, no Excel ou no resumo).

Boletos e recargas: o relatório soma SÓ as taxas de serviço da loja. O valor dos
boletos/recargas (repasse) nunca entra no total do dia; com a opção "Mostrar
repasses no relatório" ligada, ele aparece numa seção separada, "Repasses (não é
faturamento)", por forma de pagamento, para ajudar a conferir a gaveta.

Os valores vêm do banco, que guarda o preço de cada atendimento no momento em que
ele foi feito: mudar um preço hoje não altera o relatório de dias anteriores.

Os relatórios salvos ficam na pasta "relatorios/", ao lado do programa:
    relatorios/relatorio_2026-11-01.pdf
(no modo treinamento: pasta "relatorios_treino/", e tudo sai marcado "TREINAMENTO").
"""

import copy
import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import banco
import impressao
import notas
import treino
from config import FORMAS_PAGAMENTO, pasta_base
from utils import arredondar, formatar_reais

PASTA_RELATORIOS = os.path.join(pasta_base(), "relatorios")
ZERO = Decimal("0")
DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                  "sexta-feira", "sábado", "domingo"]


@dataclass
class Relatorio:
    """Tudo o que o relatório de um dia mostra."""
    dia: object                                       # datetime.date
    atendimentos: list = field(default_factory=list)  # como vêm de banco.atendimentos_do_dia
    treino: bool = False  # feito no modo treinamento (sai marcado "TREINAMENTO - SEM VALOR")
    por_servico: list = field(default_factory=list)   # [(serviço, quantidade, valor), ...]
    por_forma: dict = field(default_factory=dict)     # forma -> (nº de atendimentos, total)
    subtotal: Decimal = ZERO                          # soma dos serviços (sem as taxas) = faturamento
    total_taxas: Decimal = ZERO                       # taxas da maquininha
    total: Decimal = ZERO                             # valor total do dia (serviços + taxas)
    total_itens: int = 0                              # soma das quantidades de todos os itens
    # Por serviço, com mais detalhe: [{"nome", "categoria", "quantidade", "preco" (None se
    # variou ou se é do tipo valor+taxa), "total", "percentual"}, ...]
    detalhe_servicos: list = field(default_factory=list)
    por_categoria: list = field(default_factory=list)  # [(categoria, itens, total, percentual), ...]
    taxa_por_forma: dict = field(default_factory=dict)  # forma -> taxa da maquininha cobrada
    por_hora: dict = field(default_factory=dict)        # hora (0 a 23) -> (atendimentos, total)
    mostrar_repasses: bool = False                      # mostra a seção "Repasses (não é faturamento)"
    repasse_por_forma: dict = field(default_factory=dict)  # forma -> (boletos/recargas, valor)
    total_repasses: Decimal = ZERO                      # nunca entra no total do dia

    @property
    def quantidade(self):
        return len(self.atendimentos)

    @property
    def ticket_medio(self):
        """Quanto cada atendimento deu, em média (total do dia / atendimentos)."""
        return arredondar(self.total / self.quantidade) if self.atendimentos else ZERO

    def percentual_da_forma(self, forma):
        """Quanto (%) do total do dia entrou por esta forma de pagamento."""
        return percentual(self.por_forma[forma][1], self.total)


def percentual(parte, todo):
    """Ex.: percentual(25, 200) -> Decimal('12.5'). Com todo = 0, dá 0."""
    if not todo:
        return ZERO
    return (Decimal(parte) * 100 / Decimal(todo)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def formatar_porcento(valor):
    """Decimal('12.5') -> '12,5%'."""
    return f"{valor:.1f}".replace(".", ",") + "%"


def data_por_extenso(dia):
    """Ex.: 'sábado, 01/11/2026'."""
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia.strftime('%d/%m/%Y')}"


TITULO_REPASSES = "Repasses (não é faturamento)"


def recebido_e_troco(atendimento):
    """
    O valor recebido e o troco para mostrar no relatório. Num atendimento com
    boleto/recarga eles incluem o valor do boleto, que não aparece: (None, None).
    """
    if atendimento.get("repasse"):
        return None, None
    return atendimento["valor_recebido"], atendimento["troco"]


def descrever_itens(atendimento):
    """Ex.: '3x Xerox, 2x Pagamento de boletos'."""
    return ", ".join(f"{item['quantidade']}x {item['servico']}" for item in atendimento["itens"])


def montar_relatorio(dia, ordem_servicos=(), categoria_de=None, ordem_categorias=(), mostrar_repasses=False):
    """
    Lê os atendimentos do dia e faz as somas.
    ordem_servicos: nomes dos serviços na ordem da tela (os que não estiverem
    nela, como um serviço removido, vão para o fim, em ordem alfabética).
    categoria_de: função nome do serviço -> categoria (Configuracao.categoria_de);
    o que ela não souber vai para "Outros". ordem_categorias: a ordem das categorias.
    mostrar_repasses: liga a seção "Repasses (não é faturamento)".
    """
    categoria_de = categoria_de or (lambda _nome: None)
    relatorio = Relatorio(dia=dia, atendimentos=banco.atendimentos_do_dia(dia), treino=treino.ativo())
    relatorio.por_forma = {forma: (0, ZERO) for forma in FORMAS_PAGAMENTO}
    relatorio.taxa_por_forma = {forma: ZERO for forma in FORMAS_PAGAMENTO}
    relatorio.mostrar_repasses = mostrar_repasses
    relatorio.repasse_por_forma = {forma: (0, ZERO) for forma in FORMAS_PAGAMENTO}
    servicos = {}  # nome -> {"quantidade", "total", "precos": set()}
    for atendimento in relatorio.atendimentos:
        forma = atendimento["forma_pagamento"]
        quantidade, total = relatorio.por_forma.get(forma, (0, ZERO))
        relatorio.por_forma[forma] = (quantidade + 1, total + atendimento["total"])
        relatorio.taxa_por_forma[forma] = relatorio.taxa_por_forma.get(forma, ZERO) + atendimento["taxa_valor"]
        relatorio.subtotal += atendimento["subtotal"]
        relatorio.total_taxas += atendimento["taxa_valor"]
        relatorio.total += atendimento["total"]
        hora = atendimento["data_hora"].hour
        qtd_hora, total_hora = relatorio.por_hora.get(hora, (0, ZERO))
        relatorio.por_hora[hora] = (qtd_hora + 1, total_hora + atendimento["total"])
        for item in atendimento["itens"]:
            if item.get("valor_terceiros"):  # boleto/recarga: só para a seção de repasses
                qtd_rep, valor_rep = relatorio.repasse_por_forma.get(forma, (0, ZERO))
                relatorio.repasse_por_forma[forma] = (qtd_rep + 1, valor_rep + item["valor_terceiros"])
                relatorio.total_repasses += item["valor_terceiros"]
            soma = servicos.setdefault(item["servico"], {"quantidade": 0, "total": ZERO, "precos": set()})
            soma["quantidade"] += item["quantidade"]
            soma["total"] += item["total"]
            # Preço unitário só faz sentido no tipo "unidade" (no "valor" cada um tem um valor).
            soma["precos"].add(item["valor_unitario"] if item["tipo"] == "unidade" else None)
            relatorio.total_itens += item["quantidade"]

    ordem = list(ordem_servicos)
    def posicao(nome):
        return (ordem.index(nome), "") if nome in ordem else (len(ordem), nome.lower())
    nomes = sorted(servicos, key=posicao)
    relatorio.por_servico = [(nome, servicos[nome]["quantidade"], servicos[nome]["total"]) for nome in nomes]
    categorias = {}  # categoria -> [itens, total]
    for nome in nomes:
        soma = servicos[nome]
        precos = soma["precos"]
        categoria = categoria_de(nome) or "Outros"
        relatorio.detalhe_servicos.append({
            "nome": nome,
            "categoria": categoria,
            "quantidade": soma["quantidade"],
            "preco": next(iter(precos)) if len(precos) == 1 else None,  # None = variou no dia
            "total": soma["total"],
            "percentual": percentual(soma["total"], relatorio.subtotal),
        })
        acumulado = categorias.setdefault(categoria, [0, ZERO])
        acumulado[0] += soma["quantidade"]
        acumulado[1] += soma["total"]
    ordem_cat = list(ordem_categorias)
    def posicao_categoria(nome):
        return (ordem_cat.index(nome), "") if nome in ordem_cat else (len(ordem_cat), nome.lower())
    relatorio.por_categoria = [(nome, itens, total, percentual(total, relatorio.subtotal))
                               for nome, (itens, total) in sorted(categorias.items(),
                                                                  key=lambda par: posicao_categoria(par[0]))]
    return relatorio


def caminho_padrao(dia, extensao):
    """Onde o relatório do dia é salvo: relatorios/relatorio_AAAA-MM-DD.<extensao>."""
    return os.path.join(pasta_relatorios(), f"relatorio_{dia.strftime('%Y-%m-%d')}.{extensao}")


def pasta_relatorios():
    """relatorios/ ou, no modo treinamento, relatorios_treino/."""
    return treino.PASTA_RELATORIOS_TREINO if treino.ativo() else PASTA_RELATORIOS


# ----------------------------------------------------------------------
# Resumo no formato da notinha (80mm)
# ----------------------------------------------------------------------

def linhas_resumo(relatorio, nome_loja, colunas):
    """O resumo do dia em linhas [(texto, negrito)], com 'colunas' caracteres por linha."""
    linhas = []

    def texto(conteudo, negrito=False, centro=False):
        for parte in textwrap.wrap(conteudo, colunas) or [""]:
            linhas.append((parte.center(colunas).rstrip() if centro else parte, negrito))

    def par(esquerda, direita, negrito=False):
        espacos = colunas - len(esquerda) - len(direita)
        if espacos < 1:  # não cabe numa linha: o valor vai para a linha de baixo
            texto(esquerda, negrito)
            linhas.append((direita.rjust(colunas), negrito))
        else:
            linhas.append((esquerda + " " * espacos + direita, negrito))

    def titulo(nome):
        linhas.append(("-" * colunas, False))
        texto(nome, negrito=True)

    if nome_loja.strip():
        texto(nome_loja.strip(), negrito=True, centro=True)
    texto("RELATÓRIO DO DIA", negrito=True, centro=True)
    if relatorio.treino:
        texto(f"*** {treino.MARCA} ***", negrito=True, centro=True)
    linhas.append(("=" * colunas, False))
    texto(f"Dia: {data_por_extenso(relatorio.dia)}")
    texto(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    par("Atendimentos:", str(relatorio.quantidade))

    titulo("POR SERVIÇO")
    if not relatorio.por_servico:
        texto("(nenhum)")
    for nome, quantidade, valor in relatorio.por_servico:
        texto(nome)
        par(f"  {quantidade} un.", formatar_reais(valor))

    titulo("POR FORMA DE PAGAMENTO")
    for forma, (quantidade, total) in relatorio.por_forma.items():
        par(f"{forma} ({quantidade})", formatar_reais(total))

    linhas.append(("-" * colunas, False))
    par("Serviços:", formatar_reais(relatorio.subtotal))
    par("Taxas maquininha:", formatar_reais(relatorio.total_taxas))
    par("TOTAL DO DIA:", formatar_reais(relatorio.total), negrito=True)
    if relatorio.mostrar_repasses:
        titulo(TITULO_REPASSES.upper())
        texto("Boletos e recargas recebidos. Não entram no total do dia.")
        for forma, (quantidade, valor) in relatorio.repasse_por_forma.items():
            par(f"{forma} ({quantidade})", formatar_reais(valor))
        par("Total de repasses:", formatar_reais(relatorio.total_repasses))
    linhas.append(("=" * colunas, False))
    texto(notas.AVISO_FISCAL, negrito=True, centro=True)
    return linhas


def modelo_resumo(layout, papel="80mm"):
    """O modelo da nota da loja (fonte, alinhamento, logo), no papel do resumo (80mm)."""
    modelo = copy.deepcopy(layout["loja"])
    modelo["papel"] = papel
    return modelo


def imprimir_resumo(layout, relatorio, nome_loja, impressora=""):
    """
    Imprime o resumo (papel 80mm). impressora = nome da impressora escolhida no
    Relatório do dia; vazio = a mesma das notinhas (a de Configurar notinhas).
    Lança impressao.ErroImpressao se algo der errado. Devolve o nome da impressora.
    """
    return _imprimir_80mm(layout, impressora, lambda colunas: linhas_resumo(relatorio, nome_loja, colunas),
                          f"Relatório do dia {relatorio.dia.strftime('%d/%m/%Y')}")


def imprimir_teste_resumo(layout, nome_loja, impressora=""):
    """Um papelzinho de teste na impressora do resumo (80mm). Devolve o nome da impressora."""
    def linhas(colunas):
        resultado = [(parte.center(colunas).rstrip(), True)
                     for parte in (nome_loja.strip(), "TESTE DO RESUMO") if parte]
        resultado.append(("=" * colunas, False))
        resultado += [(parte, False) for parte in textwrap.wrap(
            f"Impressora do resumo de fechamento. {datetime.now().strftime('%d/%m/%Y %H:%M')}", colunas)]
        resultado.append(("-" * colunas, False))
        resultado.append((notas.AVISO_FISCAL.center(colunas).rstrip(), True))
        return resultado
    return _imprimir_80mm(layout, impressora, linhas, "Teste do resumo")


def _imprimir_80mm(layout, impressora, gerar_linhas, nome_documento):
    """
    Imprime o resumo: papel 80mm, texto puro ou imagem, conforme o tipo da impressora.
    Se for a MESMA impressora das notinhas, segue o que está em Configurar notinhas:
    o modo (ESC/POS direto ou driver do Windows), os caracteres por linha e o papel de
    58mm (a impressora de 58mm não tem largura para as 48 letras do papel de 80mm).
    """
    opcoes = layout["impressao"]
    try:
        das_notinhas = impressao.escolher_impressora(opcoes["impressora"])
    except impressao.ErroImpressao:
        if not impressora:
            raise
        das_notinhas = ""  # (sem impressora padrão no Windows, mas o resumo tem a dele)
    impressora = impressora or das_notinhas
    mesma = impressora == das_notinhas
    papel = "58mm" if mesma and layout["loja"]["papel"] == "58mm" else "80mm"
    modelo = modelo_resumo(layout, papel)
    if not mesma:
        # Outra impressora: o modo e a largura de Configurar notinhas não valem para ela.
        layout = {**layout, "impressao": {**opcoes, "modo": impressao.MODO_WINDOWS, "colunas": 0}}

    def linhas(modo_texto):
        return gerar_linhas(notas.colunas_texto(layout, modelo) if modo_texto else notas.medidas(modelo)[2])
    notas.imprimir_linhas(layout, impressora, modelo, linhas, nome_documento)
    return impressora


# ----------------------------------------------------------------------
# PDF (o desenho da folha A4 fica em relatorio_a4.py)
# ----------------------------------------------------------------------

def exportar_pdf(relatorio, nome_loja, caminho, paisagem=False):
    """Salva o relatório em PDF (A4, várias páginas). Precisa do QApplication já criado."""
    import relatorio_a4  # (usa o Qt: importado só aqui)
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    relatorio_a4.salvar_pdf(relatorio, nome_loja, caminho, paisagem)
    return caminho


# ----------------------------------------------------------------------
# Excel
# ----------------------------------------------------------------------

def exportar_excel(relatorio, nome_loja, caminho):
    """
    Salva o relatório em Excel: aba "Resumo" (com todas as seções) e aba
    "Atendimentos" (um atendimento por linha). Sem nome nem telefone de cliente.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    reais = '"R$" #,##0.00'  # formato de dinheiro nas células (o Excel usa vírgula no Brasil)
    porcento = '0.0%'
    negrito = Font(bold=True)
    planilha = Workbook()

    resumo = planilha.active
    resumo.title = "Resumo"
    resumo.append([nome_loja])
    resumo.append(["Relatório do dia", data_por_extenso(relatorio.dia)])
    resumo["A2"].font = Font(bold=True, size=14)
    if relatorio.treino:
        resumo["C2"] = treino.MARCA
        resumo["C2"].font = Font(bold=True, size=14, color="B3261E")
    resumo.append(["Emitido em", datetime.now().strftime("%d/%m/%Y %H:%M")])
    resumo.append([])
    for rotulo, valor in (("Atendimentos", relatorio.quantidade), ("Total de itens", relatorio.total_itens),
                          ("Serviços (faturamento)", relatorio.subtotal),
                          ("Taxas da maquininha", relatorio.total_taxas),
                          ("Ticket médio", relatorio.ticket_medio), ("Total do dia", relatorio.total)):
        resumo.append([rotulo, float(valor) if isinstance(valor, Decimal) else valor])
        if isinstance(valor, Decimal):
            resumo.cell(resumo.max_row, 2).number_format = reais
    resumo.cell(resumo.max_row, 1).font = negrito
    resumo.cell(resumo.max_row, 2).font = negrito

    def bloco(titulo, cabecalho, linhas, formatos):
        """Uma tabela no Resumo. formatos = {nº da coluna (1, 2...): formato}."""
        resumo.append([])
        resumo.append([titulo])
        resumo.cell(resumo.max_row, 1).font = Font(bold=True, size=12)
        resumo.append(cabecalho)
        for coluna in range(1, len(cabecalho) + 1):
            resumo.cell(resumo.max_row, coluna).font = negrito
        for linha in linhas:
            resumo.append(list(linha))
            for coluna, formato in formatos.items():
                resumo.cell(resumo.max_row, coluna).number_format = formato

    def fracao(valor):
        return float(valor) / 100  # 12,5 -> 0,125 (o Excel mostra 12,5%)

    bloco("Por serviço", ["Serviço", "Categoria", "Quantidade", "Preço unitário", "Total", "% do faturamento"],
          [(d["nome"], d["categoria"], d["quantidade"], float(d["preco"]) if d["preco"] is not None else "vários",
            float(d["total"]), fracao(d["percentual"])) for d in relatorio.detalhe_servicos],
          {4: reais, 5: reais, 6: porcento})
    bloco("Por categoria", ["Categoria", "Itens", "Total", "% do faturamento"],
          [(nome, itens, float(total), fracao(pct)) for nome, itens, total, pct in relatorio.por_categoria],
          {3: reais, 4: porcento})
    bloco("Por forma de pagamento", ["Forma", "Atendimentos", "Total", "Taxa cobrada", "% do total"],
          [(forma, qtd, float(total), float(relatorio.taxa_por_forma.get(forma, ZERO)),
            fracao(relatorio.percentual_da_forma(forma))) for forma, (qtd, total) in relatorio.por_forma.items()],
          {3: reais, 4: reais, 5: porcento})
    if relatorio.mostrar_repasses:
        bloco(TITULO_REPASSES, ["Forma", "Boletos/recargas", "Valor"],
              [(forma, qtd, float(valor)) for forma, (qtd, valor) in relatorio.repasse_por_forma.items()]
              + [("Total (não entra no total do dia)", sum(q for q, _v in relatorio.repasse_por_forma.values()),
                  float(relatorio.total_repasses))],
              {3: reais})
        resumo.cell(resumo.max_row, 1).font = negrito
    bloco("Movimento por hora", ["Hora", "Atendimentos", "Total"],
          [(f"{hora:02d}h", qtd, float(total)) for hora, (qtd, total) in sorted(relatorio.por_hora.items())],
          {3: reais})
    for letra, largura in zip("ABCDEF", (30, 24, 16, 15, 14, 17)):
        resumo.column_dimensions[letra].width = largura

    lista = planilha.create_sheet("Atendimentos")
    cabecalho = ["Nº", "Hora", "Itens", "Subtotal", "Taxa", "Total", "Pagamento", "Valor recebido", "Troco"]
    lista.append(cabecalho)
    for coluna in range(1, len(cabecalho) + 1):
        lista.cell(1, coluna).font = negrito
        lista.cell(1, coluna).alignment = Alignment(wrap_text=True)

    def numero(valor):
        return float(valor) if valor is not None else None

    for atendimento in relatorio.atendimentos:
        recebido, troco = recebido_e_troco(atendimento)
        lista.append([
            atendimento["numero"], atendimento["data_hora"].strftime("%H:%M"), descrever_itens(atendimento),
            numero(atendimento["subtotal"]), numero(atendimento["taxa_valor"]), numero(atendimento["total"]),
            atendimento["forma_pagamento"], numero(recebido), numero(troco),
        ])
        for coluna in (4, 5, 6, 8, 9):
            lista.cell(lista.max_row, coluna).number_format = reais
        lista.cell(lista.max_row, 3).alignment = Alignment(wrap_text=True, vertical="top")
    for letra, largura in zip("ABCDEFGHI", (9, 8, 46, 12, 10, 12, 12, 15, 11)):
        lista.column_dimensions[letra].width = largura
    lista.freeze_panes = "A2"  # o cabeçalho fica parado ao rolar

    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    planilha.save(caminho)
    return caminho
