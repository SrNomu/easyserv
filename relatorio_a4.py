"""
relatorio_a4.py - Desenha o Relatório do dia em folhas A4 (PDF, impressora e pré-visualização).

Por que desenhar "na mão" (com QPainter) e não com HTML: assim temos controle de
cada página:
  - cabeçalho em todas as páginas (loja, data, hora de emissão, "Página X de Y");
  - rodapé em todas: "Minha Loja - Relatório de DD/MM/AAAA - Página X de Y";
  - tabelas que continuam na página seguinte repetem o cabeçalho delas;
  - um atendimento nunca é cortado no meio (a linha inteira vai para a próxima página);
  - retrato ou paisagem: as colunas se espalham pela largura da folha.

Como funciona:
  1. montar_paginas() calcula onde cada coisa vai e guarda uma lista de páginas,
     cada uma com "ordens de desenho" (texto, linha, retângulo);
  2. pintar_pagina() executa as ordens de uma página (e escreve o "Página X de Y",
     que só dá para saber depois de montar tudo).

Unidade das medidas: 1/4 de ponto (72 pontos = 1 polegada). Ex.: fonte de 8pt = 32.
Assim o desenho é o mesmo em qualquer resolução (PDF, impressora ou tela).
"""

from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QPen,
)

import treino
from relatorio import TITULO_REPASSES, data_por_extenso, descrever_itens, formatar_porcento, recebido_e_troco
from utils import formatar_reais

U = 4                    # unidades por ponto
MARGEM_MM = 10           # margem da folha (todas as bordas)
FONTE = "Segoe UI"
TINTA = QColor("#1d1a1c")
CINZA = QColor("#5c5559")
LINHA_FRACA = QColor("#d9d3d6")
FUNDO_CARTAO = QColor("#f6f1f3")
COR_BARRA = QColor("#8c2f57")
VERMELHO = QColor("#b3261e")
ESPACO = 6 * U           # espaço padrão entre blocos
ALTURA_CABECALHO = 44 * U
ALTURA_RODAPE = 16 * U


def fonte(pontos, negrito=False):
    f = QFont(FONTE)
    f.setPixelSize(round(pontos * U))
    f.setBold(negrito)
    return f


@dataclass
class Pagina:
    ordens: list = field(default_factory=list)  # ("texto"|"linha"|"retangulo", ...)


class Montador:
    """Vai colocando os blocos de cima para baixo e abre página nova quando não cabe."""

    def __init__(self, largura, altura):
        self.largura, self.altura = largura, altura
        self.topo = ALTURA_CABECALHO + ESPACO          # onde começa o conteúdo
        self.limite = altura - ALTURA_RODAPE - ESPACO  # até onde vai o conteúdo
        self.paginas = [Pagina()]
        self.y = self.topo

    @property
    def pagina(self):
        return self.paginas[-1]

    def nova_pagina(self):
        self.paginas.append(Pagina())
        self.y = self.topo

    def cabe(self, altura):
        return self.y + altura <= self.limite

    def garantir(self, altura):
        """Se não couber no resto da página, vai para a próxima. True se mudou de página."""
        if not self.cabe(altura) and self.y > self.topo:
            self.nova_pagina()
            return True
        return False

    # --- ordens de desenho ---
    def texto(self, x, y, largura, altura, conteudo, f, cor=TINTA, alinhamento=Qt.AlignLeft):
        self.pagina.ordens.append(("texto", QRectF(x, y, largura, altura), alinhamento | Qt.TextWordWrap,
                                   f, cor, conteudo))

    def linha(self, x1, y1, x2, y2, cor=LINHA_FRACA, espessura=0.6):
        self.pagina.ordens.append(("linha", x1, y1, x2, y2, cor, espessura * U))

    def retangulo(self, x, y, largura, altura, cor):
        self.pagina.ordens.append(("retangulo", QRectF(x, y, largura, altura), cor))


def altura_texto(conteudo, f, largura):
    """Altura que o texto ocupa numa largura (quebrando as linhas)."""
    return QFontMetricsF(f).boundingRect(QRectF(0, 0, largura, 1e9), Qt.TextWordWrap, conteudo).height()


# ----------------------------------------------------------------------
# Blocos do relatório
# ----------------------------------------------------------------------

def _titulo_secao(m, titulo, continuacao=False, x=0, largura=None):
    f = fonte(10.5, True)
    altura = QFontMetricsF(f).height()
    m.texto(x, m.y, largura or m.largura, altura, titulo + ("  (continuação)" if continuacao else ""), f)
    m.y += altura + 2 * U


def _medir_tabela(colunas, linhas, largura):
    """Larguras das colunas e altura de cada linha (cabeçalho primeiro)."""
    soma = sum(peso for _titulo, peso, _alinhamento in colunas)
    larguras = [largura * peso / soma for _titulo, peso, _alinhamento in colunas]
    f, fc = fonte(8), fonte(7.5, True)
    respiro = 2.5 * U  # espaço em cima e embaixo do texto na linha

    def altura_linha(valores, fonte_linha):
        return max(altura_texto(str(v), fonte_linha, w - 6 * U) for v, w in zip(valores, larguras)) + 2 * respiro

    cabecalho = altura_linha([t for t, _p, _a in colunas], fc)
    return larguras, cabecalho, [altura_linha(linha, f) for linha in linhas], respiro


def _desenhar_linha(m, x, larguras, colunas, valores, altura, respiro, f, cor=TINTA, fundo=None):
    if fundo is not None:
        m.retangulo(x, m.y, sum(larguras), altura, fundo)
    posicao = x
    for valor, largura, (_titulo, _peso, alinhamento) in zip(valores, larguras, colunas):
        m.texto(posicao + 3 * U, m.y + respiro, largura - 6 * U, altura - 2 * respiro, str(valor), f, cor,
                alinhamento)
        posicao += largura
    m.y += altura
    m.linha(x, m.y, x + sum(larguras), m.y)


def tabela(m, titulo, colunas, linhas, rodape=None, x=0, largura=None):
    """
    Uma tabela que pode continuar em várias páginas: o cabeçalho se repete e
    nenhuma linha é cortada (a linha que não cabe vai inteira para a próxima página).
    colunas = [(título, peso da largura, alinhamento)]; rodape = linha de total (negrito).
    """
    largura = largura or m.largura
    todas = linhas + ([rodape] if rodape else [])
    larguras, altura_cab, alturas, respiro = _medir_tabela(colunas, todas, largura)
    altura_titulo = QFontMetricsF(fonte(10.5, True)).height() + 2 * U
    # O título nunca fica sozinho no pé da página: precisa caber com o cabeçalho e a 1ª linha.
    m.garantir(altura_titulo + altura_cab + (alturas[0] if alturas else 0))
    _titulo_secao(m, titulo, x=x, largura=largura)

    def cabecalho():
        _desenhar_linha(m, x, larguras, colunas, [t for t, _p, _a in colunas], altura_cab, respiro,
                        fonte(7.5, True), CINZA, FUNDO_CARTAO)

    cabecalho()
    for indice, (valores, altura) in enumerate(zip(todas, alturas)):
        if not m.cabe(altura):
            m.nova_pagina()
            _titulo_secao(m, titulo, continuacao=True, x=x, largura=largura)
            cabecalho()
        eh_total = rodape is not None and indice == len(todas) - 1
        _desenhar_linha(m, x, larguras, colunas, valores, altura, respiro, fonte(8, eh_total))
    m.y += ESPACO


def cartoes(m, itens):
    """Os números principais em cartões lado a lado: [(título, valor), ...]."""
    espaco = 6 * U
    largura = (m.largura - espaco * (len(itens) - 1)) / len(itens)
    ft, fv = fonte(7.5), fonte(14, True)
    altura = QFontMetricsF(ft).height() + QFontMetricsF(fv).height() + 12 * U
    m.garantir(altura)
    for i, (titulo, valor) in enumerate(itens):
        x = i * (largura + espaco)
        m.retangulo(x, m.y, largura, altura, FUNDO_CARTAO)
        m.texto(x + 6 * U, m.y + 5 * U, largura - 12 * U, QFontMetricsF(ft).height(), titulo, ft, CINZA)
        m.texto(x + 6 * U, m.y + 5 * U + QFontMetricsF(ft).height() + 2 * U, largura - 12 * U,
                QFontMetricsF(fv).height(), valor, fv)
    m.y += altura + ESPACO * 1.5


def grafico_horas(m, por_hora):
    """Movimento por hora: uma barra por hora (altura = nº de atendimentos)."""
    titulo_altura = QFontMetricsF(fonte(10.5, True)).height() + 2 * U
    altura_grafico = 110 * U
    # Se sobrar um pouco menos de espaço na página, o gráfico encolhe em vez de pular de página.
    sobra = m.limite - m.y - titulo_altura - 12 * U
    if 75 * U <= sobra < altura_grafico:
        altura_grafico = sobra
    m.garantir(titulo_altura + altura_grafico)
    _titulo_secao(m, "Movimento por hora")
    if not por_hora:
        m.texto(0, m.y, m.largura, 14 * U, "Nenhum atendimento neste dia.", fonte(8), CINZA)
        m.y += 14 * U + ESPACO
        return
    # Mostra pelo menos das 8h às 18h (horário normal da loja), e mais se teve movimento fora disso.
    primeira, ultima = min(min(por_hora), 8), max(max(por_hora), 18)
    horas = list(range(primeira, ultima + 1))
    maior = max(qtd for qtd, _total in por_hora.values())
    fn, fp = fonte(7.5, True), fonte(7)
    altura_numero = QFontMetricsF(fn).height()
    altura_rotulos = QFontMetricsF(fp).height() * 2 + 2 * U
    area = altura_grafico - altura_numero - altura_rotulos - 4 * U  # altura máxima de uma barra
    base = m.y + altura_numero + 2 * U + area
    passo = m.largura / len(horas)
    largura_barra = passo * 0.62
    m.linha(0, base, m.largura, base, CINZA, 0.8)
    for i, hora in enumerate(horas):
        qtd, total = por_hora.get(hora, (0, None))
        x = i * passo + (passo - largura_barra) / 2
        if qtd:
            altura = max(area * qtd / maior, 1.5 * U)
            m.retangulo(x, base - altura, largura_barra, altura, COR_BARRA)
            m.texto(i * passo, base - altura - altura_numero - 1 * U, passo, altura_numero, str(qtd), fn,
                    TINTA, Qt.AlignHCenter)
        m.texto(i * passo, base + 2 * U, passo, QFontMetricsF(fp).height(), f"{hora:02d}h", fp, CINZA,
                Qt.AlignHCenter)
        if qtd:
            m.texto(i * passo, base + 2 * U + QFontMetricsF(fp).height(), passo, QFontMetricsF(fp).height(),
                    formatar_reais(total).replace("R$ ", ""), fp, CINZA, Qt.AlignHCenter)
    m.y += altura_grafico + ESPACO
    m.texto(0, m.y - ESPACO, m.largura, QFontMetricsF(fp).height(),
            "Barras: número de atendimentos em cada hora · embaixo: total da hora (R$)", fp, CINZA)
    m.y += QFontMetricsF(fp).height()


# ----------------------------------------------------------------------
# O relatório inteiro
# ----------------------------------------------------------------------

DIREITA, ESQUERDA, CENTRO = Qt.AlignRight, Qt.AlignLeft, Qt.AlignHCenter


def montar_paginas(relatorio, largura, altura):
    """Calcula todas as páginas (largura e altura da área útil, em unidades)."""
    m = Montador(largura, altura)
    r = relatorio
    cartoes(m, [("Atendimentos", str(r.quantidade)), ("Total do dia", formatar_reais(r.total)),
                ("Ticket médio", formatar_reais(r.ticket_medio)),
                ("Taxas da maquininha", formatar_reais(r.total_taxas)), ("Total de itens", str(r.total_itens))])

    tabela(m, "Por serviço",
           [("Serviço", 30, ESQUERDA), ("Categoria", 20, ESQUERDA), ("Qtd", 7, DIREITA),
            ("Preço unit.", 11, DIREITA), ("Total", 12, DIREITA), ("% do faturamento", 12, DIREITA)],
           [(d["nome"], d["categoria"], d["quantidade"],
             formatar_reais(d["preco"]) if d["preco"] is not None else "vários", formatar_reais(d["total"]),
             formatar_porcento(d["percentual"])) for d in r.detalhe_servicos] or [("Nenhum serviço", "", "", "", "", "")],
           rodape=("Total", "", r.total_itens, "", formatar_reais(r.subtotal),
                   "100,0%" if r.subtotal else "0,0%"))

    # Categoria e forma de pagamento lado a lado (são tabelas pequenas).
    espaco = 10 * U
    meia = (m.largura - espaco) / 2
    colunas_cat = [("Categoria", 26, ESQUERDA), ("Itens", 9, DIREITA), ("Total", 14, DIREITA), ("%", 10, DIREITA)]
    linhas_cat = [(nome, itens, formatar_reais(total), formatar_porcento(pct))
                  for nome, itens, total, pct in r.por_categoria] or [("Nenhuma", "", "", "")]
    colunas_forma = [("Forma", 14, ESQUERDA), ("Atend.", 9, DIREITA), ("Total", 14, DIREITA),
                     ("Taxa cobrada", 13, DIREITA), ("% do total", 11, DIREITA)]
    linhas_forma = [(forma, qtd, formatar_reais(total), formatar_reais(r.taxa_por_forma.get(forma, 0)),
                     formatar_porcento(r.percentual_da_forma(forma))) for forma, (qtd, total) in r.por_forma.items()]
    alturas = []
    for colunas, linhas in ((colunas_cat, linhas_cat), (colunas_forma, linhas_forma)):
        _l, cab, linhas_alt, _r = _medir_tabela(colunas, linhas, meia)
        alturas.append(QFontMetricsF(fonte(10.5, True)).height() + 2 * U + cab + sum(linhas_alt))
    m.garantir(max(alturas))
    inicio = m.y
    tabela(m, "Por categoria", colunas_cat, linhas_cat, x=0, largura=meia)
    fim_esquerda = m.y
    m.y = inicio
    tabela(m, "Por forma de pagamento", colunas_forma, linhas_forma, x=meia + espaco, largura=meia)
    m.y = max(m.y, fim_esquerda)

    if r.mostrar_repasses:
        tabela(m, TITULO_REPASSES,
               [("Forma de pagamento", 30, ESQUERDA), ("Boletos/recargas", 14, DIREITA), ("Valor", 16, DIREITA)],
               [(forma, qtd, formatar_reais(valor)) for forma, (qtd, valor) in r.repasse_por_forma.items()],
               rodape=("Total (não entra no total do dia)", sum(q for q, _v in r.repasse_por_forma.values()),
                       formatar_reais(r.total_repasses)))

    grafico_horas(m, r.por_hora)

    def valor(v):
        return formatar_reais(v) if v is not None else "—"

    tabela(m, "Atendimentos do dia",
           [("Nº", 8, ESQUERDA), ("Hora", 6, ESQUERDA), ("Itens", 34, ESQUERDA), ("Subtotal", 10, DIREITA),
            ("Taxa", 8, DIREITA), ("Total", 10, DIREITA), ("Pagamento", 11, ESQUERDA),
            ("Recebido", 10, DIREITA), ("Troco", 8, DIREITA)],
           [(f"{a['numero']:06d}", a["data_hora"].strftime("%H:%M"), descrever_itens(a), valor(a["subtotal"]),
             valor(a["taxa_valor"]), valor(a["total"]), a["forma_pagamento"], *map(valor, recebido_e_troco(a)))
            for a in r.atendimentos] or [("", "", "Nenhum atendimento neste dia.", "", "", "", "",
                                                             "", "")],
           rodape=("", "", f"{r.quantidade} atendimento(s)", formatar_reais(r.subtotal),
                   formatar_reais(r.total_taxas), formatar_reais(r.total), "", "", ""))
    return m.paginas


def pintar_pagina(pintor, pagina, numero, total, relatorio, nome_loja, largura, altura, emitido):
    """Desenha uma página: cabeçalho, conteúdo e rodapé (com "Página X de Y")."""
    pintor.save()
    # Cabeçalho
    f_loja, f_normal, f_pequena = fonte(13, True), fonte(9), fonte(7.5)
    h_loja = QFontMetricsF(f_loja).height()
    pintor.setPen(TINTA)
    pintor.setFont(f_loja)
    pintor.drawText(QRectF(0, 0, largura * 0.65, h_loja), Qt.AlignLeft, nome_loja)
    pintor.setFont(f_normal)
    h_normal = QFontMetricsF(f_normal).height()
    pintor.drawText(QRectF(0, h_loja, largura * 0.65, h_normal), Qt.AlignLeft,
                    f"Relatório do dia · {data_por_extenso(relatorio.dia)}")
    pintor.setPen(CINZA)
    pintor.drawText(QRectF(largura * 0.5, 0, largura * 0.5, h_normal), Qt.AlignRight, f"Emitido em {emitido}")
    pintor.drawText(QRectF(largura * 0.5, h_normal, largura * 0.5, h_normal), Qt.AlignRight,
                    f"Página {numero} de {total}")
    if relatorio.treino:
        pintor.setPen(VERMELHO)
        pintor.setFont(fonte(9, True))
        pintor.drawText(QRectF(0, h_loja + h_normal, largura, h_normal), Qt.AlignLeft, treino.MARCA)
    pintor.setPen(QPen(TINTA, 0.8 * U))
    pintor.drawLine(0, round(ALTURA_CABECALHO - 4 * U), round(largura), round(ALTURA_CABECALHO - 4 * U))

    # Conteúdo
    for ordem in pagina.ordens:
        tipo = ordem[0]
        if tipo == "texto":
            _tipo, retangulo, alinhamento, f, cor, conteudo = ordem
            pintor.setFont(f)
            pintor.setPen(cor)
            pintor.drawText(retangulo, alinhamento, conteudo)
        elif tipo == "linha":
            _tipo, x1, y1, x2, y2, cor, espessura = ordem
            pintor.setPen(QPen(cor, espessura))
            pintor.drawLine(QRectF(x1, y1, 0, 0).topLeft(), QRectF(x2, y2, 0, 0).topLeft())
        elif tipo == "retangulo":
            _tipo, retangulo, cor = ordem
            pintor.fillRect(retangulo, cor)

    # Rodapé
    y = altura - ALTURA_RODAPE + 4 * U
    pintor.setPen(QPen(LINHA_FRACA, 0.6 * U))
    pintor.drawLine(0, round(y), round(largura), round(y))
    pintor.setFont(f_pequena)
    pintor.setPen(CINZA)
    pintor.drawText(QRectF(0, y + 2 * U, largura, ALTURA_RODAPE - 6 * U), Qt.AlignHCenter,
                    f"{nome_loja} - Relatório de {relatorio.dia.strftime('%d/%m/%Y')} - Página {numero} de {total}")
    pintor.restore()


def desenhar(dispositivo, relatorio, nome_loja):
    """
    Desenha o relatório inteiro num PDF (QPdfWriter) ou numa impressora (QPrinter),
    já configurados (papel, orientação e margens). Devolve o número de páginas.
    """
    escala = dispositivo.logicalDpiX() / (72 * U)
    largura, altura = dispositivo.width() / escala, dispositivo.height() / escala
    paginas = montar_paginas(relatorio, largura, altura)
    emitido = datetime.now().strftime("%d/%m/%Y %H:%M")
    pintor = QPainter(dispositivo)
    try:
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setRenderHint(QPainter.TextAntialiasing)
        pintor.scale(escala, escala)
        for numero, pagina in enumerate(paginas, start=1):
            if numero > 1:
                dispositivo.newPage()
            pintar_pagina(pintor, pagina, numero, len(paginas), relatorio, nome_loja, largura, altura, emitido)
    finally:
        pintor.end()
    return len(paginas)


def layout_da_pagina(paisagem):
    """Folha A4, retrato ou paisagem, com as margens do relatório."""
    return QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Landscape if paisagem else QPageLayout.Portrait,
                       QMarginsF(MARGEM_MM, MARGEM_MM, MARGEM_MM, MARGEM_MM), QPageLayout.Millimeter)


def salvar_pdf(relatorio, nome_loja, caminho, paisagem=False):
    escritor = QPdfWriter(caminho)
    escritor.setResolution(600)
    escritor.setPageLayout(layout_da_pagina(paisagem))
    escritor.setTitle(f"Relatório do dia {relatorio.dia.strftime('%d/%m/%Y')}")
    escritor.setCreator(nome_loja)
    return desenhar(escritor, relatorio, nome_loja)


def imagens(relatorio, nome_loja, paisagem=False, dpi=96):
    """As páginas como imagens (folha inteira, com margem branca). Usado em testes e prints."""
    medida = layout_da_pagina(paisagem).fullRectPoints()
    escala = dpi / (72 * U)
    margem = MARGEM_MM / 25.4 * 72 * U
    largura, altura = medida.width() * U - 2 * margem, medida.height() * U - 2 * margem
    paginas = montar_paginas(relatorio, largura, altura)
    emitido = datetime.now().strftime("%d/%m/%Y %H:%M")
    resultado = []
    for numero, pagina in enumerate(paginas, start=1):
        imagem = QImage(round(medida.width() * dpi / 72), round(medida.height() * dpi / 72), QImage.Format_RGB32)
        imagem.fill(QColor("white"))
        pintor = QPainter(imagem)
        pintor.setRenderHint(QPainter.Antialiasing)
        pintor.setRenderHint(QPainter.TextAntialiasing)
        pintor.scale(escala, escala)
        pintor.translate(margem, margem)
        pintar_pagina(pintor, pagina, numero, len(paginas), relatorio, nome_loja, largura, altura, emitido)
        pintor.end()
        resultado.append(imagem)
    return resultado


# ----------------------------------------------------------------------
# Impressora comum (A4)
# ----------------------------------------------------------------------

def criar_impressora(nome_impressora, paisagem=False):
    """
    Um QPrinter apontando para a impressora escolhida (pelo nome), em A4.
    Só escolhe a impressora para este trabalho: a impressora padrão do Windows não muda.
    """
    from PySide6.QtPrintSupport import QPrinter

    impressora = QPrinter(QPrinter.HighResolution)
    if nome_impressora:
        impressora.setPrinterName(nome_impressora)
    impressora.setPageLayout(layout_da_pagina(paisagem))
    impressora.setFullPage(False)
    return impressora


def imprimir(relatorio, nome_loja, nome_impressora, paisagem=False):
    """Manda o relatório para a impressora A4. Devolve o número de páginas."""
    impressora = criar_impressora(nome_impressora, paisagem)
    impressora.setDocName(f"Relatório do dia {relatorio.dia.strftime('%d/%m/%Y')}")
    if not impressora.isValid():
        raise RuntimeError(f'Não foi possível usar a impressora "{nome_impressora}".')
    return desenhar(impressora, relatorio, nome_loja)


def imprimir_teste(nome_impressora, nome_loja, paisagem=False):
    """Uma folha de teste: confere se a impressora A4 está funcionando e se as margens estão boas."""
    impressora = criar_impressora(nome_impressora, paisagem)
    impressora.setDocName("Teste do relatório")
    if not impressora.isValid():
        raise RuntimeError(f'Não foi possível usar a impressora "{nome_impressora}".')
    escala = impressora.logicalDpiX() / (72 * U)
    largura, altura = impressora.width() / escala, impressora.height() / escala
    pintor = QPainter(impressora)
    try:
        pintor.scale(escala, escala)
        pintor.setPen(QPen(TINTA, 1 * U))
        pintor.drawRect(QRectF(0, 0, largura, altura))
        pintor.setFont(fonte(16, True))
        pintor.drawText(QRectF(0, altura * 0.35, largura, 30 * U), Qt.AlignHCenter, nome_loja)
        pintor.setFont(fonte(11))
        pintor.drawText(QRectF(0, altura * 0.35 + 34 * U, largura, 60 * U), Qt.AlignHCenter | Qt.TextWordWrap,
                        f"Teste de impressão do relatório A4\n{nome_impressora}\n"
                        f"{datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
                        "Se o quadrado em volta da folha aparece inteiro, as margens estão certas.")
    finally:
        pintor.end()
