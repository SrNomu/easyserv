"""
toque.py - Coisas de tablet: saber se a tela é de toque e abrir o teclado virtual do Windows.

O teclado de toque do Windows (TabTip) é aberto pelo mesmo caminho que o próprio
Windows usa (a interface COM "ITipInvocation"). Se não der, cai para o teclado
na tela clássico (osk.exe). Tudo aqui falha em silêncio: no pior caso o teclado
não abre, mas o programa continua.
"""

import ctypes
import os
import subprocess
import uuid

from PySide6.QtGui import QInputDevice

TABTIP = os.path.join(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"),
                      "microsoft shared", "ink", "TabTip.exe")
# Interface do Windows que mostra/esconde o teclado de toque.
CLSID_UIHOSTNOLAUNCH = "{4CE576FA-83DC-4F88-951C-9D0782B4E376}"
IID_ITIPINVOCATION = "{37C994E7-432B-4834-A2F7-DCE1F13B834B}"


def tem_tela_touch():
    """True se o Windows informa uma tela sensível ao toque."""
    try:
        return any(dispositivo.type() == QInputDevice.DeviceType.TouchScreen
                   for dispositivo in QInputDevice.devices())
    except Exception:
        return False


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, texto):
        super().__init__()
        bruto = uuid.UUID(texto).bytes_le
        ctypes.memmove(ctypes.byref(self), bruto, 16)


def _teclado_visivel():
    """No Windows 10 dá para ver se a janela do teclado de toque está aparecendo."""
    janela = ctypes.windll.user32.FindWindowW("IPTip_Main_Window", None)
    if not janela:
        return False
    GWL_STYLE, WS_DISABLED = -16, 0x08000000
    estilo = ctypes.windll.user32.GetWindowLongW(janela, GWL_STYLE)
    return bool(ctypes.windll.user32.IsWindowVisible(janela)) and not estilo & WS_DISABLED


def _alternar_teclado_de_toque():
    """Chama ITipInvocation::Toggle (mostra o teclado de toque). True se deu certo."""
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    ponteiro = ctypes.c_void_p()
    CLSCTX_LOCAL_SERVER = 0x4
    resultado = ole32.CoCreateInstance(ctypes.byref(_GUID(CLSID_UIHOSTNOLAUNCH)), None, CLSCTX_LOCAL_SERVER,
                                       ctypes.byref(_GUID(IID_ITIPINVOCATION)), ctypes.byref(ponteiro))
    if resultado != 0 or not ponteiro:
        return False
    try:
        tabela = ctypes.cast(ponteiro, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        # Métodos: 0 QueryInterface, 1 AddRef, 2 Release, 3 Toggle(HWND)
        alternar = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(tabela[3])
        liberar = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(tabela[2])
        try:
            return alternar(ponteiro, ctypes.windll.user32.GetDesktopWindow()) == 0
        finally:
            liberar(ponteiro)
    except Exception:
        return False


def abrir_teclado_windows():
    """Mostra o teclado virtual do Windows. True se conseguiu pedir para abrir."""
    try:
        if _teclado_visivel():
            return True
        if os.path.exists(TABTIP) and not _processo_rodando("TabTip.exe"):
            os.startfile(TABTIP)  # inicia o serviço do teclado de toque (na 1ª vez já aparece)
            return True
        if _alternar_teclado_de_toque():
            return True
        subprocess.Popen(["osk.exe"], shell=True)  # teclado na tela clássico
        return True
    except Exception:
        return False


def _processo_rodando(nome):
    try:
        saida = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {nome}", "/NH"], capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=3).stdout
        return nome.lower() in saida.lower()
    except Exception:
        return False
