"""
preferencias.py - Guarda preferências da tela (arquivo preferencias.json).

São coisas do jeito de usar o programa, que ele deve lembrar na próxima vez
que abrir: tamanho e posição da janela, onde está cada painel (e quais estão
abertos, inclusive o teclado), se o layout está travado, os layouts salvos
com nome, o modo claro/escuro, as cores e temas escolhidos e as teclas de
atalho.
Diferente do config.json, ninguém precisa editar este arquivo à mão.
"""

import copy
import json
import os

from config import pasta_base

ARQUIVO_PREFERENCIAS = os.path.join(pasta_base(), "preferencias.json")

PADRAO = {
    "geometria_janela": "",   # tamanho/posição da janela (texto em base64 gerado pelo Qt)
    "estado_paineis": "",     # posição de cada painel (texto em base64 gerado pelo Qt)
    "layout_travado": False,
    "layout_atual": "Padrão",  # último layout escolhido em Exibir › Layouts
    "teclado_grande": False,   # teclas grandes (layout "Touch")
    # Layouts salvos pela pessoa: {"nome": {"estado": "...base64...", "teclado_grande": False}}
    "layouts_salvos": {},
    "modo_cor": "sistema",     # "claro", "escuro" ou "sistema" (seguir o Windows)
    "cores": {},               # {"claro": {...}, "escuro": {...}}; vazio = cores de fábrica
    # Temas de cores salvos pela pessoa: {"nome": {"claro": {...}, "escuro": {...}}}
    "temas_salvos": {},
    # Layout que o "Restaurar layout padrão" usa: {"estado": "...", "teclado_grande": False}.
    # Vazio = o layout Padrão de fábrica.
    "layout_padrao": {},
    "atalhos": {},             # {"acao": "tecla"}; o que faltar usa a tecla de fábrica (atalhos.py)
    # Impressoras do Relatório do dia (pelo nome). Vazio = a padrão do Windows (A4)
    # ou a mesma das notinhas (resumo de 80mm).
    "impressora_relatorio": "",
    "impressora_resumo": "",
    "relatorio_paisagem": False,  # relatório A4 deitado (paisagem) em vez de em pé (retrato)
    # Modo tablet (Exibir › Modo tablet): tudo maior, layout Touch e teclado do Windows.
    "modo_tablet": False,
    "tablet_perguntado": False,     # já perguntou se quer ligar (tela de toque detectada)
    "layout_antes_tablet": "",      # layout para voltar quando desligar o modo tablet
}


def carregar():
    """Lê as preferências. Se o arquivo não existir ou estiver estragado, usa o padrão."""
    preferencias = copy.deepcopy(PADRAO)  # cópia de verdade (os {} de dentro não são compartilhados)
    try:
        with open(ARQUIVO_PREFERENCIAS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return preferencias
    for chave, valor_padrao in PADRAO.items():
        # Só aceita o valor do arquivo se for do mesmo tipo do padrão.
        if isinstance(dados, dict) and isinstance(dados.get(chave), type(valor_padrao)):
            preferencias[chave] = dados[chave]
    return preferencias


def salvar(preferencias):
    """Grava as preferências. Se não conseguir, não atrapalha o uso do programa."""
    try:
        with open(ARQUIVO_PREFERENCIAS, "w", encoding="utf-8") as arquivo:
            json.dump(preferencias, arquivo, ensure_ascii=False, indent=2)
    except OSError:
        pass
