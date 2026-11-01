"""
utils.py - Funções auxiliares usadas em vários lugares do programa.

Aqui ficam as funções que:
  - convertem o texto digitado pelo usuário em número (aceitando vírgula ou ponto);
  - formatam valores no padrão brasileiro (R$ 1.234,56);
  - aplicam a máscara de telefone (21) 99999-9999.

Usamos o tipo Decimal (e não float) para dinheiro. O float tem pequenos erros
de arredondamento (por exemplo, 0.1 + 0.2 dá 0.30000000000000004), e com
dinheiro isso não pode acontecer.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Um centavo. Usado para arredondar os valores para 2 casas decimais.
CENTAVO = Decimal("0.01")


def arredondar(valor):
    """Arredonda um Decimal para 2 casas (centavos), do jeito que aprendemos na escola."""
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def formatar_reais(valor):
    """Transforma um número em texto no formato brasileiro. Ex.: 1234.5 -> 'R$ 1.234,50'."""
    valor = arredondar(valor)
    sinal = "-" if valor < 0 else ""
    # O Python formata no padrão americano: "1,234.50".
    texto = f"{abs(valor):,.2f}"
    # Trocamos vírgula por ponto e ponto por vírgula (usando "_" como intermediário).
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sinal}R$ {texto}"


def formatar_percentual(valor):
    """Ex.: Decimal('5.0') -> '5%' e Decimal('2.5') -> '2,5%'."""
    # normalize() tira os zeros inúteis do final (5.0 vira 5).
    texto = format(Decimal(valor).normalize(), "f").replace(".", ",")
    return f"{texto}%"


def base_da_taxa(itens):
    """
    Soma dos itens sobre os quais a taxa da maquininha incide.
    Recargas e boletos ficam de fora (item["cobra_taxa_maquininha"] = False).
    """
    return sum((item["total"] for item in itens if item.get("cobra_taxa_maquininha", True)), Decimal("0"))


def converter_valor(texto, permitir_zero=False):
    """
    Converte o texto digitado em um Decimal positivo.

    Aceita: "10", "10,50", "10.50", "1.234,56", "R$ 5,00".
    Se o texto for inválido (vazio, negativo, zero ou com letras), lança
    ValueError com uma mensagem amigável, que a tela mostra para o usuário.
    permitir_zero=True aceita 0 (usado na taxa da maquininha).
    """
    original = texto
    texto = texto.strip().replace("R$", "").replace(" ", "")

    if not texto:
        raise ValueError("O valor não pode ficar vazio.")
    if texto.startswith("-"):
        raise ValueError("O valor não pode ser negativo.")

    if "," in texto and "." in texto:
        # Formato brasileiro com milhar: "1.234,56" -> "1234.56"
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        # Só vírgula: "10,50" -> "10.50"
        texto = texto.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        # Só pontos separando milhar: "1.234" -> "1234"
        texto = texto.replace(".", "")

    # Depois da conversão, só pode sobrar: dígitos, e opcionalmente ponto + 1 ou 2 dígitos.
    if not re.fullmatch(r"\d+(\.\d{1,2})?", texto):
        raise ValueError(f"'{original}' não é um valor válido.\nUse só números, por exemplo: 10,50")

    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"'{original}' não é um valor válido.")

    if valor < 0 or (valor == 0 and not permitir_zero):
        raise ValueError("O valor precisa ser maior que zero.")
    return valor


def converter_percentual(texto):
    """
    Converte a taxa digitada em porcentagem. Aceita "5", "5%", "2,5", "0".
    Lança ValueError se estiver vazia, negativa, com letras ou acima de 100.
    """
    texto = texto.strip().removesuffix("%").strip()
    if not texto:
        raise ValueError("A taxa não pode ficar vazia (use 0 para sem taxa).")
    try:
        valor = converter_valor(texto, permitir_zero=True)
    except ValueError:
        if texto.startswith("-"):
            raise ValueError("A taxa não pode ser negativa.")
        raise ValueError(f"'{texto}' não é uma taxa válida. Use só números, ex.: 5 ou 2,5")
    if valor > 100:
        raise ValueError("A taxa não pode passar de 100%.")
    return valor


def numero_para_campo(valor):
    """Mostra um número num campo de digitação, no jeito brasileiro: 0.5 -> '0,50'."""
    return f"{arredondar(valor):.2f}".replace(".", ",")


def converter_quantidade(texto):
    """Converte o texto em quantidade inteira e positiva (1, 2, 3...)."""
    texto = texto.strip()
    if not texto:
        raise ValueError("A quantidade não pode ficar vazia.")
    if not texto.isdigit():
        raise ValueError(f"'{texto}' não é uma quantidade válida.\nUse só números inteiros, por exemplo: 3")
    quantidade = int(texto)
    if quantidade <= 0:
        raise ValueError("A quantidade precisa ser maior que zero.")
    if quantidade > 9999:
        raise ValueError("Quantidade muito alta. Confira o valor digitado.")
    return quantidade


def so_digitos(texto):
    """Remove tudo o que não for número. Ex.: '(21) 99999-9999' -> '21999999999'."""
    return re.sub(r"\D", "", texto)


def formatar_telefone(texto):
    """
    Aplica a máscara de telefone enquanto a pessoa digita.
    Ex.: '2199999' -> '(21) 9999-9'   e   '21999999999' -> '(21) 99999-9999'.
    """
    d = so_digitos(texto)[:11]  # no máximo 11 dígitos (DDD + 9 dígitos)
    if not d:
        return ""
    if len(d) <= 2:
        return f"({d}"
    if len(d) <= 6:
        return f"({d[:2]}) {d[2:]}"
    if len(d) <= 10:
        # Telefone fixo: (21) 2222-3333
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    # Celular: (21) 99999-9999
    return f"({d[:2]}) {d[2:7]}-{d[7:]}"


def para_centavos(valor):
    """Decimal -> número inteiro de centavos (R$ 1,50 -> 150). É assim que guardamos no banco."""
    return int(arredondar(valor) * 100)


def de_centavos(centavos):
    """Número inteiro de centavos -> Decimal (150 -> 1.50)."""
    return Decimal(centavos) / 100
