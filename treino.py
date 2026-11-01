"""
treino.py - Modo treinamento (menu Arquivo › Modo treinamento).

Serve para aprender a usar o programa (ou testar a impressora) sem mexer no
caixa de verdade. Com o modo ligado:
  - os atendimentos vão para outro banco, o treino.db (o banco de verdade não é tocado,
    então nada aparece no relatório real);
  - as notas saem marcadas "TREINAMENTO - SEM VALOR" e ficam na pasta notas_treino/;
  - o relatório do dia mostra só os atendimentos do treino (e sai marcado também).

Por segurança, o programa sempre abre com o modo treinamento DESLIGADO.
"""

import os

from config import pasta_base

ARQUIVO_BANCO_TREINO = os.path.join(pasta_base(), "treino.db")
PASTA_NOTAS_TREINO = os.path.join(pasta_base(), "notas_treino")
PASTA_RELATORIOS_TREINO = os.path.join(pasta_base(), "relatorios_treino")
MARCA = "TREINAMENTO - SEM VALOR"

_ativo = False


def ativo():
    """True enquanto o modo treinamento está ligado."""
    return _ativo


def ligar(sim):
    global _ativo
    _ativo = bool(sim)
