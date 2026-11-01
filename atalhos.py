"""
atalhos.py - As teclas de atalho do programa (editáveis em Ajuda › Atalhos do teclado).

Cada AÇÃO do programa tem um nome interno ("finalizar", "pix", "servico_1"...)
e uma tecla, guardada como texto no formato do Qt: "F12", "Esc", "Del", "1",
"Ctrl+1"... As teclas escolhidas ficam em preferencias.json; as que não
estiverem lá usam a tecla de fábrica (PADRAO).

Teclado de PDV: muitos têm teclas programáveis que mandam F13 a F24 ou
combinações com Ctrl/Alt. Qualquer uma delas pode virar atalho aqui.

Regra para não atrapalhar a digitação: quando o cursor está num campo de
texto, só funcionam os atalhos com F1 a F24, Esc ou com Ctrl/Alt. Números,
letras e Delete continuam sendo digitados no campo normalmente.

SERVIÇOS: cada serviço tem a sua ação, "servico:<id do serviço>" (o id fica no
config.json e nunca muda, mesmo renomeando ou mudando o serviço de lugar).
Serviço sem tecla escolhida pega a primeira tecla livre de 1 a 9 e 0, na ordem
da tela: com os 10 serviços de fábrica, fica 1 a 0 como sempre foi. Do 11º em
diante (ou se as teclas 1 a 0 já estiverem em uso), escolha a tecla em
Arquivo › Serviços e preços ou em Ajuda › Atalhos do teclado.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

# Teclas que os serviços recebem sozinhos, na ordem da tela.
TECLAS_SERVICOS = "1234567890"
PREFIXO_SERVICO = "servico:"

# (ação, descrição, tecla de fábrica) - nesta ordem aparecem na tela de atalhos.
# (as ações dos serviços não estão aqui: dependem dos serviços cadastrados)
ACOES = [
    ("nome", "Nome do cliente", "F2"),
    ("telefone", "Telefone do cliente", "F3"),
    ("recebido", "Valor recebido (dinheiro)", "F4"),
    ("dinheiro", "Pagamento: Dinheiro", "F5"),
    ("pix", "Pagamento: Pix", "F6"),
    ("debito", "Pagamento: Débito", "F7"),
    ("credito", "Pagamento: Crédito", "F8"),
    ("teclado", "Mostrar/esconder o teclado na tela", "F9"),
    ("relatorio", "Relatório do dia", "F10"),
    ("finalizar", "FINALIZAR atendimento", "F12"),
    ("remover", "Remover o item selecionado", "Del"),
    ("cancelar", "Cancelar atendimento (no campo do item: desistir do item)", "Esc"),
]
PADRAO = {acao: tecla for acao, _descricao, tecla in ACOES}
DESCRICOES = {acao: descricao for acao, descricao, _tecla in ACOES}
FORMA_DA_ACAO = {"dinheiro": "Dinheiro", "pix": "Pix", "debito": "Débito", "credito": "Crédito"}

# Teclas que não podem virar atalho: são usadas para andar pela tela e digitar.
PROIBIDAS = {Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Backspace, Qt.Key_Space}
# Teclas que são só "modificadoras" (sozinhas não formam um atalho).
MODIFICADORAS = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr, Qt.Key_CapsLock}


def acao_do_servico(id_servico):
    """Nome da ação de um serviço: 'servico:xerox'."""
    return PREFIXO_SERVICO + id_servico


def id_do_servico(acao):
    """'servico:xerox' -> 'xerox' (ou None se a ação não for de serviço)."""
    return acao[len(PREFIXO_SERVICO):] if acao.startswith(PREFIXO_SERVICO) else None


def _valida(tecla):
    """A tecla salva, já arrumada; "" = sem atalho; None = valor estragado (usa o de fábrica)."""
    if tecla == "":
        return ""
    if isinstance(tecla, str) and not QKeySequence(tecla).isEmpty():
        return normalizar(tecla)
    return None


def completar(salvos, ids_servicos=()):
    """
    Junta os atalhos salvos com os de fábrica e com os dos serviços.
    ids_servicos = ids dos serviços ATIVOS, na ordem da tela.
    Texto inválido volta para o de fábrica.
    """
    salvos = salvos if isinstance(salvos, dict) else {}
    atalhos = dict(PADRAO)
    for acao in PADRAO:
        tecla = _valida(salvos.get(acao))
        if tecla is not None:
            atalhos[acao] = tecla
    # Serviços com tecla escolhida pela pessoa. (Versão 1.0 guardava pela posição:
    # "servico_1" era o 1º serviço da tela; isso é aproveitado se ainda não houver o novo.)
    sem_tecla = []
    for posicao, id_servico in enumerate(ids_servicos):
        acao = acao_do_servico(id_servico)
        tecla = _valida(salvos.get(acao))
        if tecla is None:
            tecla = _valida(salvos.get(f"servico_{posicao + 1}"))
        if tecla is None:
            sem_tecla.append(acao)
        else:
            atalhos[acao] = tecla
    # Os outros pegam a primeira tecla livre de 1 a 0 (ou ficam sem atalho).
    usadas = set(atalhos.values())
    livres = [tecla for tecla in TECLAS_SERVICOS if tecla not in usadas]
    for acao in sem_tecla:
        atalhos[acao] = livres.pop(0) if livres else ""
    return atalhos


def normalizar(texto):
    """Escreve a tecla sempre do mesmo jeito (ex.: 'f5' -> 'F5', 'Delete' -> 'Del')."""
    return QKeySequence(texto).toString(QKeySequence.PortableText)


def tecla_do_evento(evento):
    """
    Transforma uma tecla apertada (QKeyEvent) no texto do atalho, ex.: 'F5', 'Ctrl+1'.
    Devolve "" para teclas que não servem de atalho (Enter, Tab, Shift sozinho...).
    """
    tecla = evento.key()
    if tecla in MODIFICADORAS or tecla in PROIBIDAS or tecla == Qt.Key_unknown:
        return ""
    # (o "1" do teclado numérico conta como o mesmo "1": o modificador Keypad é ignorado)
    mods = evento.modifiers()
    ctrl, alt, meta = (bool(mods & m) for m in (Qt.ControlModifier, Qt.AltModifier, Qt.MetaModifier))
    shift = bool(mods & Qt.ShiftModifier)
    # Shift junto com símbolo já muda o próprio símbolo ("!" e não "Shift+1").
    if evento.text() and evento.text().isprintable() and not (ctrl or alt or meta):
        if not (Qt.Key_F1 <= tecla <= Qt.Key_F35):
            shift = False
    valor = tecla
    for ativo, modificador in ((ctrl, Qt.ControlModifier), (alt, Qt.AltModifier),
                               (meta, Qt.MetaModifier), (shift, Qt.ShiftModifier)):
        if ativo:
            valor |= modificador.value
    return QKeySequence(valor).toString(QKeySequence.PortableText)


def eh_de_digitacao(texto):
    """
    True se a tecla é das que se digitam num campo (número, letra, Delete...).
    Esses atalhos não funcionam enquanto o cursor está num campo de texto.
    """
    if not texto:
        return False
    if any(parte in texto for parte in ("Ctrl+", "Alt+", "Meta+")):
        return False
    if texto == "Esc" or (texto.startswith("F") and texto[1:].isdigit()):
        return False
    return True


def texto_para_mostrar(texto):
    """Como a tecla aparece nos botões e rótulos (vazio vira 'sem atalho')."""
    return texto if texto else "sem atalho"
