"""
versao.py - Nome, versão, direitos, créditos e notas da versão do programa
(aparecem na tela de abertura e em Ajuda › Sobre).

Ao lançar uma versão nova:
  1. aumente VERSAO (ex.: "1.3");
  2. coloque um bloco novo NO COMEÇO de NOTAS_DA_VERSAO contando o que mudou;
  3. gere o instalador (python ferramentas\\gerar_instalador.py) e publique no GitHub
     (passo a passo em ferramentas\\COMO_PUBLICAR.txt).
"""

NOME_PROGRAMA = "EasyServ"
VERSAO = "1.3.1"
AUTOR = "Pedro"
ANO = "2026"
COPYRIGHT = f"© {ANO} {AUTOR}. Todos os direitos reservados."

# Repositório PÚBLICO do GitHub onde as versões são publicadas, no formato
# "usuario/repositorio" (ex.: "pedro/easyserv"). Vazio = não procura atualizações.
# O programa só LÊ as versões publicadas: não existe senha nem token aqui dentro.
REPOSITORIO_GITHUB = "SrNomu/easyserv"

# Bibliotecas que vão dentro do programa: (nome, versão, licença, site).
BIBLIOTECAS = [
    ("Python", "3.13", "PSF License", "https://www.python.org/"),
    ("Qt 6 / PySide6 (Qt for Python)", "6.12", "LGPL v3", "https://www.qt.io/qt-for-python"),
    ("Shiboken6", "6.12", "LGPL v3", "https://www.qt.io/qt-for-python"),
    ("openpyxl", "3.1", "MIT", "https://openpyxl.readthedocs.io/"),
    ("et_xmlfile", "2.0", "MIT", "https://foss.heptapod.net/openpyxl/et_xmlfile"),
    ("Pillow", "12.2", "MIT-CMU (HPND)", "https://python-pillow.org/"),
    ("pywin32", "312", "PSF License", "https://github.com/mhammond/pywin32"),
    ("PyInstaller (bootloader)", "6.22", "GPL v2 com exceção para programas gerados",
     "https://pyinstaller.org/"),
    ("Inno Setup (instalador)", "6", "Licença Inno Setup (gratuita)", "https://jrsoftware.org/isinfo.php"),
]

# (versão, data, [o que mudou]) - a mais nova primeiro.
NOTAS_DA_VERSAO = [
    ("1.3.1", "novembro de 2026", [
        "Código-fonte publicado no GitHub (github.com/SrNomu/easyserv) como portfólio.",
        "O EasyServ passa a procurar atualizações nesse repositório ao abrir.",
        "Programa \"de fábrica\": o nome padrão da loja agora é \"Minha Loja\" (editável em "
        "Configurar notinhas). Quem já usa continua com os próprios dados e o próprio nome.",
        "Banco de dados novo se chama easyserv.db; o arquivo das versões anteriores continua sendo usado.",
        "Novos termos de uso (LICENCA.txt): código visível, todos os direitos reservados.",
    ]),
    ("1.3", "novembro de 2026", [
        "Nova tela de Preferências (Arquivo › Preferências), com as abas Atendimento, Privacidade e "
        "Aparência. A opção \"Guardar dados do cliente\" passou para lá.",
        "Nova opção \"Pedir o valor do boleto/recarga\" (desligada de fábrica): o funcionário digita o "
        "valor e o programa soma a taxa do serviço. Ex.: \"Valor do boleto: R$ 200,00 + Serviço: R$ 2,00 = "
        "Cobrar do cliente: R$ 202,00\".",
        "Com essa opção, a taxa da maquininha não é calculada sobre boletos e recargas, e o troco sai "
        "do valor cobrado (boleto + serviço).",
        "Notinhas e relatório mostram só as taxas de serviço; o valor do boleto/recarga fica guardado "
        "à parte no banco.",
        "Nova opção \"Mostrar repasses no relatório\": seção \"Repasses (não é faturamento)\" com o total "
        "de boletos e recargas por forma de pagamento, para conferir a gaveta (fora do total do dia).",
        "Serviços e preços: nova opção \"Cobra valor de terceiros (boleto/recarga)\" em cada serviço.",
    ]),
    ("1.2", "novembro de 2026", [
        "O programa agora se chama EasyServ, com logo e ícone novos.",
        "Tela de abertura: confere os arquivos do programa e o banco de dados e procura atualizações.",
        "Atualização automática pelo GitHub: mostra as novidades e só atualiza se você mandar "
        "(nunca no meio de um atendimento). Confere o arquivo baixado (SHA-256) e faz backup antes.",
        "Instalador (EasyServ_Setup) com atalhos na área de trabalho e no menu Iniciar.",
        "Os dados (banco, configurações, layouts, temas, notas, relatórios e backups) ficam em "
        "%APPDATA%\\EasyServ e não se perdem em atualizações. Os dados da versão antiga podem ser "
        "trazidos na primeira vez que o programa abre.",
        "Modo tablet (Exibir › Modo tablet): tudo maior, rolagem por toque, teclado do Windows "
        "no campo Nome e dicas na tela em vez de dicas de passar o mouse.",
        "Janela Sobre com direitos autorais e créditos das bibliotecas; arquivo LICENCA.txt.",
        "Serviços e preços: se uma tecla foi tirada de outra ação e você muda de ideia, ela volta "
        "para a ação de antes.",
    ]),
    ("1.1", "novembro de 2026", [
        "Tela \"Serviços e preços\": criar, renomear, remover e reordenar categorias e serviços "
        "(arrastando), com tecla de atalho e taxa da maquininha em cada serviço.",
        "Serviço removido fica \"desativado\": sai da tela, mas continua no histórico e nos relatórios.",
        "Mais de 10 serviços: as teclas de atalho dos serviços podem ser qualquer tecla.",
        "Janela \"Sobre\" com a versão e estas notas.",
        "Barra de título da janela com as cores do tema.",
        "\"NÃO É DOCUMENTO FISCAL\" no rodapé de todas as notinhas e do resumo de fechamento.",
        "Privacidade: nome e telefone do cliente não aparecem mais no relatório, no PDF, no Excel "
        "nem no resumo; na nota da loja vêm desmarcados.",
        "Nova opção \"Guardar dados do cliente\": não guardar, apagar depois de alguns dias "
        "(padrão: 30) ou guardar sempre.",
        "Relatório do dia: escolha da impressora da folha A4 e da impressora do resumo 80mm, "
        "com \"Imprimir teste\".",
        "Relatório A4 novo: cartões de resumo, ticket médio, por serviço (preço e %), por categoria, "
        "por forma de pagamento (taxa e %), movimento por hora, lista completa dos atendimentos, "
        "várias páginas com \"Página X de Y\", retrato ou paisagem e pré-visualização.",
        "O Excel do relatório ganhou as mesmas seções novas.",
    ]),
    ("1.0", "outubro de 2026", [
        "Calculadora de serviços com atendimento, troco e taxa da maquininha.",
        "Notinhas da loja e do cliente (impressora térmica ou comum), com editor de layout.",
        "Tela em painéis que podem ser arrastados, layouts prontos e salvos, teclado na tela.",
        "Modo claro, escuro ou seguindo o Windows, com temas de cores (prontos e salvos).",
        "Preços e taxas editáveis pela tela.",
        "Relatório do dia com PDF, Excel e fechamento de expediente.",
        "Modo treinamento, limpar dados com backup e atalhos do teclado editáveis.",
    ]),
]


def titulo():
    """Ex.: 'EasyServ 1.2'."""
    return f"{NOME_PROGRAMA} {VERSAO}"


def numero(texto):
    """'v1.10' ou '1.10' -> (1, 10), para comparar versões (1.10 é maior que 1.9)."""
    texto = str(texto).strip().lstrip("vV")
    partes = []
    for parte in texto.split("."):
        digitos = "".join(c for c in parte if c.isdigit())
        if not digitos:
            break
        partes.append(int(digitos))
    while len(partes) > 1 and partes[-1] == 0:
        partes.pop()  # 1.2.0 == 1.2
    return tuple(partes)
