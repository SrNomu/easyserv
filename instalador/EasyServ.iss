; EasyServ.iss - Script do instalador (Inno Setup 6).
;
; Não precisa rodar este arquivo na mão: o ferramentas\gerar_instalador.py gera o
; programa, depois chama o Inno Setup assim:
;     ISCC.exe /DVersao=1.2 instalador\EasyServ.iss
; e o resultado sai em dist\EasyServ_Setup_1.2.exe.
;
; Onde fica cada coisa depois de instalado:
;   - programa: a pasta escolhida na instalação (padrão: %LOCALAPPDATA%\Programs\EasyServ,
;     sem precisar de administrador; dá para instalar para todos em Arquivos de Programas);
;   - dados (banco, configurações, layouts, temas, notas, relatórios, backups):
;     %APPDATA%\EasyServ. O instalador NUNCA escreve nessa pasta. O desinstalador
;     pergunta se quer apagar ou manter (o padrão é manter).

#ifndef Versao
  #define Versao "1.2"
#endif
#define Nome "EasyServ"
#define Exe "EasyServ.exe"

[Setup]
; O AppId identifica o programa para atualizar/desinstalar: NUNCA mude este número.
AppId={{4222878A-2751-46D4-AA7C-ED6DC9297A2F}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=Pedro
AppCopyright=© 2026 Pedro. Todos os direitos reservados.
VersionInfoVersion={#Versao}
VersionInfoProductName={#Nome}
VersionInfoDescription=Instalador do {#Nome}
DefaultDirName={autopf}\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
UsePreviousAppDir=yes
LicenseFile=..\LICENCA.txt
OutputDir=..\dist
OutputBaseFilename=EasyServ_Setup_{#Versao}
SetupIconFile=..\recursos\easyserv.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nome}
WizardStyle=modern
WizardImageFile=..\recursos\instalador_lateral_1x.bmp,..\recursos\instalador_lateral_2x.bmp
WizardSmallImageFile=..\recursos\instalador_pequena_1x.bmp,..\recursos\instalador_pequena_2x.bmp
; Sem administrador por padrão (instala só para a pessoa); o instalador oferece
; "instalar para todos" (pede administrador) numa janelinha no começo.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/max
SolidCompression=yes
; O EasyServ aberto avisa o instalador por este "mutex" (main.py): ele pede para fechar.
AppMutex=EasyServMutex
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
pt.WelcomeLabel2=Este assistente vai instalar o [name/ver] no seu computador.%n%nSeus dados (atendimentos, configurações e notas) ficam guardados à parte e não são apagados nem alterados pela instalação.%n%nFeche o EasyServ antes de continuar.

[Tasks]
Name: "atalho_area_trabalho"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"

[InstallDelete]
; Numa atualização, remove os arquivos internos da versão anterior (os novos vêm completos).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; (inclui EasyServ.exe, EasyServAtualizador.exe, LICENCA.txt e manifesto.json)
Source: "..\dist\EasyServ\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar o {#Nome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Exe}"; Tasks: atalho_area_trabalho

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent

[Code]
// Desinstalar: pergunta se a pessoa quer apagar os dados também (o padrão é MANTER).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Pasta: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Pasta := ExpandConstant('{userappdata}\EasyServ');
    if DirExists(Pasta) and (not UninstallSilent) then
    begin
      if MsgBox('O EasyServ foi removido.' + #13#10#13#10 +
                'Quer APAGAR também os seus dados?' + #13#10 +
                '(atendimentos, configurações, layouts, temas, notas, relatórios e backups)' + #13#10#13#10 +
                Pasta + #13#10#13#10 +
                'Sim = apaga tudo, sem volta.' + #13#10 +
                'Não = mantém os dados (recomendado se for instalar de novo).',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Pasta, True, True, True);
    end;
  end;
end;
