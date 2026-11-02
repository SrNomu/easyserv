; EasyServ.iss - Script do instalador (Inno Setup 6.6 ou mais novo).
;
; Não precisa rodar este arquivo na mão: o ferramentas\gerar_instalador.py gera o
; programa, depois chama o Inno Setup assim:
;     ISCC.exe /DVersao=1.4.2 instalador\EasyServ.iss
; e o resultado sai em dist\EasyServ_Setup_1.4.2.exe.
;
; Visual: o mesmo da tela de abertura do programa (tela_abertura.py). Sempre escuro,
; com o degradê vinho no fundo de todas as telas, a logo grande, "EasyServ" com a
; versão em rosa embaixo e os direitos no rodapé. As imagens são geradas pelo
; ferramentas\gerar_icones.py (recursos\instalador_*.png).
;
; Onde fica cada coisa depois de instalado:
;   - programa: a pasta escolhida na instalação (padrão: %LOCALAPPDATA%\Programs\EasyServ,
;     sem precisar de administrador; dá para instalar para todos em Arquivos de Programas);
;   - dados (banco, configurações, layouts, temas, notas, relatórios, backups):
;     %APPDATA%\EasyServ. O instalador NUNCA escreve nessa pasta. O desinstalador
;     pergunta numa tela própria: "Manter seus dados" (o padrão) ou "Apagar tudo", e
;     antes de apagar oferece um backup na Área de Trabalho (EasyServ.exe --backup-para).

#if Ver < EncodeVer(6, 6, 0)
  #error O visual do instalador (modo escuro e fundo) precisa do Inno Setup 6.6 ou mais novo.
#endif

#ifndef Versao
  #define Versao "1.4.2"
#endif
#define Nome "EasyServ"
#define Exe "EasyServ.exe"
#define Direitos "© 2026 Pedro. Todos os direitos reservados."
#define Slogan "Atendimento e caixa para serviços"
; Cores da tela de abertura
#define CorFundo "#1b1719"
#define CorDestaque "#e891b6"
#define CorTextoFraco "#a99ba2"

[Setup]
; O AppId identifica o programa para atualizar/desinstalar: NUNCA mude este número.
AppId={{4222878A-2751-46D4-AA7C-ED6DC9297A2F}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher=Pedro
AppCopyright={#Direitos}
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
; Sempre escuro (como a tela de abertura), com a barra de título também escura e sem as
; linhas horizontais entre as partes da janela.
WizardStyle=modern dark includetitlebar hidebevels
; O degradê da tela de abertura atrás de todas as telas (no desinstalador, que não tem
; imagem de fundo, vale a cor de fundo).
WizardBackImageFile=..\recursos\instalador_fundo_1x.png,..\recursos\instalador_fundo_2x.png
WizardBackColor={#CorFundo}
; Logo grande à esquerda (boas-vindas e final) e pequena no canto (outras telas), sem fundo.
WizardImageFile=..\recursos\instalador_lateral_1x.png,..\recursos\instalador_lateral_2x.png
WizardSmallImageFile=..\recursos\instalador_pequena_1x.png,..\recursos\instalador_pequena_2x.png
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

[LangOptions]
; "EasyServ" grande na tela de boas-vindas, como na tela de abertura.
WelcomeFontName=Segoe UI Semibold
WelcomeFontSize=28

[Messages]
; Textos das telas, revisados (a tradução padrão usa "pra" e frases longas).
pt.SetupWindowTitle=Instalar o %1
pt.UninstallAppFullTitle=Desinstalar o %1
pt.WelcomeLabel1=[name]
pt.WelcomeLabel2=Este assistente vai instalar o [name] no seu computador.%n%nSeus dados (atendimentos, configurações e notas) ficam guardados à parte e não são apagados nem alterados pela instalação.%n%nFeche o EasyServ antes de continuar.
pt.ClickNext=Clique em Avançar para continuar ou em Cancelar para sair.
pt.WizardLicense=Termos de uso
pt.LicenseLabel=Leia com atenção antes de continuar.
pt.LicenseLabel3=Leia os termos de uso abaixo. Para instalar, é preciso aceitá-los.
pt.LicenseAccepted=Eu &aceito os termos
pt.LicenseNotAccepted=Eu &não aceito os termos
pt.WizardSelectDir=Pasta do programa
pt.SelectDirDesc=Onde o [name] vai ser instalado?
pt.SelectDirLabel3=O [name] vai ser instalado nesta pasta.
pt.SelectDirBrowseLabel=Para continuar, clique em Avançar. Para escolher outra pasta, clique em Procurar.
pt.WizardSelectTasks=Atalhos
pt.SelectTasksDesc=Onde você quer os atalhos do [name]?
pt.SelectTasksLabel2=Escolha os atalhos e clique em Avançar.
pt.WizardReady=Pronto para instalar
pt.ReadyLabel1=Tudo pronto para instalar o [name] no seu computador.
pt.ReadyLabel2a=Clique em Instalar para começar, ou em Voltar para revisar alguma escolha.
pt.ReadyLabel2b=Clique em Instalar para começar.
pt.WizardPreparing=Preparando a instalação
pt.PreparingDesc=Preparando para instalar o [name] no seu computador.
pt.WizardInstalling=Instalando
pt.InstallingLabel=Aguarde enquanto o [name] é instalado no seu computador.
pt.FinishedHeadingLabel=Instalação concluída
pt.FinishedLabelNoIcons=O [name] foi instalado no seu computador.
pt.FinishedLabel=O [name] foi instalado no seu computador. Ele também pode ser aberto pelos atalhos criados.
pt.ClickFinish=Clique em Concluir para sair.
pt.ExitSetupTitle=Sair da instalação
pt.ExitSetupMessage=A instalação ainda não terminou. Se sair agora, o [name] não será instalado.%n%nVocê pode abrir o instalador de novo depois para terminar.%n%nSair da instalação?
pt.SetupAppRunningError=O %1 está aberto.%n%nFeche o programa e clique em OK para continuar, ou em Cancelar para sair.
pt.UninstallAppRunningError=O %1 está aberto.%n%nFeche o programa e clique em OK para continuar, ou em Cancelar para sair.
; Desinstalador
pt.ConfirmUninstall=Remover o %1 deste computador?%n%nOs seus dados (atendimentos e configurações) não são apagados sem você confirmar.
pt.WizardUninstalling=Removendo o programa
pt.UninstallStatusLabel=Aguarde enquanto o %1 é removido do seu computador.
pt.UninstalledAll=O %1 foi removido do seu computador.
pt.UninstalledMost=O %1 foi removido.%n%nAlguns arquivos não puderam ser apagados. Eles podem ser apagados à mão.
pt.UninstalledAndNeedsRestart=Para terminar de remover o %1, é preciso reiniciar o computador.%n%nReiniciar agora?
pt.PrivilegesRequiredOverrideTitle=Como instalar
pt.PrivilegesRequiredOverrideInstruction=Para quem instalar o EasyServ?
pt.PrivilegesRequiredOverrideText1=O %1 pode ser instalado para todos os usuários do computador (pede a senha de administrador) ou só para você.
pt.PrivilegesRequiredOverrideText2=O %1 pode ser instalado só para você ou para todos os usuários do computador (pede a senha de administrador).
pt.PrivilegesRequiredOverrideAllUsers=Para &todos os usuários
pt.PrivilegesRequiredOverrideAllUsersRecommended=Para &todos os usuários (recomendado)
pt.PrivilegesRequiredOverrideCurrentUser=Só para &mim
pt.PrivilegesRequiredOverrideCurrentUserRecommended=Só para &mim (recomendado)

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
Name: "{group}\Desinstalar {#Nome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Exe}"; Tasks: atalho_area_trabalho

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent

[Code]
const
  PBM_SETBARCOLOR = $0409;
  PBM_SETBKCOLOR = $2001;
  GWL_EXSTYLE = -20;
  WS_EX_CLIENTEDGE = $200;
  WS_EX_STATICEDGE = $20000;
  SWP_ATUALIZAR_BORDA = $27; // SWP_NOSIZE or SWP_NOMOVE or SWP_NOZORDER or SWP_FRAMECHANGED

// Tirar o tema do Windows da barra de progresso deixa trocar as cores dela.
function SetWindowTheme(Janela: HWND; App, Lista: String): Integer;
  external 'SetWindowTheme@uxtheme.dll stdcall';
function GetWindowLong(Janela: HWND; Indice: Integer): Integer;
  external 'GetWindowLongW@user32.dll stdcall';
function SetWindowLong(Janela: HWND; Indice, Valor: Integer): Integer;
  external 'SetWindowLongW@user32.dll stdcall';
function SetWindowPos(Janela, Depois: HWND; X, Y, L, A: Integer; Flags: Cardinal): Boolean;
  external 'SetWindowPos@user32.dll stdcall';

// Barra de progresso rosa sobre o trilho escuro, sem borda, como a da tela de abertura.
// As cores vão em BGR: $B691E8 = #e891b6 (destaque) e $312A3A = #3a2a31 (trilho).
procedure PintarBarra(Barra: TWinControl);
begin
  Barra.StyleElements := []; // sem isso o estilo escuro pinta a barra por cima (verde)
  SetWindowTheme(Barra.Handle, ' ', ' ');
  SetWindowLong(Barra.Handle, GWL_EXSTYLE,
    GetWindowLong(Barra.Handle, GWL_EXSTYLE) and not (WS_EX_CLIENTEDGE or WS_EX_STATICEDGE));
  SetWindowPos(Barra.Handle, 0, 0, 0, 0, 0, SWP_ATUALIZAR_BORDA);
  SendMessage(Barra.Handle, PBM_SETBARCOLOR, 0, $B691E8);
  SendMessage(Barra.Handle, PBM_SETBKCOLOR, 0, $312A3A);
end;

// Texto com cor própria (como na tela de abertura): o estilo escuro não troca a cor.
function CriarTexto(Pagina: TWinControl; Texto: String; Tamanho: Integer; Cor: String): TNewStaticText;
begin
  Result := TNewStaticText.Create(Pagina); // (no desinstalador não existe o WizardForm)
  Result.Parent := Pagina;
  Result.AutoSize := True;
  Result.Font.Size := Tamanho;
  Result.StyleElements := Result.StyleElements - [seFont];
  Result.Font.Color := StrToColor(Cor);
  Result.Caption := Texto;
end;

// Boas-vindas e tela final no visual da tela de abertura:
//   EasyServ (grande) / Versão x (rosa) / Atendimento e caixa para serviços / ... / © (rodapé)
procedure InitializeWizard;
var
  Nome, Texto, Titulo: TNewStaticText;
  Versao, Slogan, Direitos: TNewStaticText;
begin
  Nome := WizardForm.WelcomeLabel1;
  Texto := WizardForm.WelcomeLabel2;
  // Altura fixa de uma linha: AdjustLabelHeight deixava um vão grande antes da versão.
  Nome.Height := ScaleY(50);

  Versao := CriarTexto(WizardForm.WelcomePage, 'Versão {#Versao}', 13, '{#CorDestaque}');
  Versao.Left := Nome.Left + ScaleX(2);
  Versao.Top := Nome.Top + Nome.Height;
  Slogan := CriarTexto(WizardForm.WelcomePage, '{#Slogan}', 10, '{#CorTextoFraco}');
  Slogan.Left := Versao.Left;
  Slogan.Top := Versao.Top + Versao.Height + ScaleY(2);

  Texto.Top := Slogan.Top + Slogan.Height + ScaleY(28);
  Texto.Height := WizardForm.WelcomePage.ClientHeight - Texto.Top - ScaleY(40);

  Direitos := CriarTexto(WizardForm.WelcomePage, '{#Direitos}', 8, '{#CorTextoFraco}');
  Direitos.Left := Versao.Left;
  Direitos.Top := WizardForm.WelcomePage.ClientHeight - Direitos.Height - ScaleY(14);

  // Tela final: título menor que o "EasyServ" e os direitos no rodapé também.
  Titulo := WizardForm.FinishedHeadingLabel;
  Titulo.Font.Size := 20;
  Titulo.Height := ScaleY(38);
  WizardForm.FinishedLabel.Top := Titulo.Top + Titulo.Height + ScaleY(20);
  Direitos := CriarTexto(WizardForm.FinishedPage, '{#Direitos}', 8, '{#CorTextoFraco}');
  Direitos.Left := Titulo.Left + ScaleX(2);
  Direitos.Top := WizardForm.FinishedPage.ClientHeight - Direitos.Height - ScaleY(14);

  PintarBarra(WizardForm.ProgressGauge);
end;

// ----------------------------------------------------------------------------
// Desinstalador
// ----------------------------------------------------------------------------

var
  ApagarDados: Boolean;            // a pessoa escolheu "Apagar tudo" (o padrão é manter)
  OpcaoApagar: TNewRadioButton;
  OpcaoBackup: TNewCheckBox;

// Mesmo visual: barra rosa e os direitos no rodapé.
procedure InitializeUninstallProgressForm;
var
  Direitos: TNewStaticText;
begin
  PintarBarra(UninstallProgressForm.ProgressBar);
  Direitos := CriarTexto(UninstallProgressForm, '{#Direitos}', 8, '{#CorTextoFraco}');
  Direitos.Left := UninstallProgressForm.InnerNotebook.Left + ScaleX(2);
  Direitos.Top := UninstallProgressForm.CancelButton.Top +
                  (UninstallProgressForm.CancelButton.Height - Direitos.Height) div 2;
end;

// A pasta dos dados é a mesma que o programa usa (config.pasta_base): EASYSERV_DADOS,
// se existir (testes), senão %APPDATA%\EasyServ.
function PastaDosDados: String;
begin
  Result := GetEnv('EASYSERV_DADOS');
  if Result = '' then
    Result := ExpandConstant('{userappdata}\EasyServ');
end;

procedure OpcaoMudou(Sender: TObject);
begin
  OpcaoBackup.Enabled := OpcaoApagar.Checked;
end;

// Texto explicando cada opção, embaixo dela, na cor fraca da tela de abertura.
function Explicacao(Tela: TSetupForm; Texto: String; Topo: Integer): TNewStaticText;
begin
  Result := CriarTexto(Tela, Texto, 9, '{#CorTextoFraco}');
  Result.AutoSize := False;
  Result.WordWrap := True;
  Result.Left := ScaleX(118);
  Result.Width := Tela.ClientWidth - Result.Left - ScaleX(24);
  Result.Top := Topo;
  Result.Height := ScaleY(34);
end;

// Tela "O que fazer com os seus dados?": Manter (padrão) ou Apagar tudo (com backup antes).
// Devolve True se for para apagar; marca BackupAntes se a pessoa quer o backup.
function PerguntarDados(Pasta: String; var BackupAntes: Boolean): Boolean;
var
  Tela: TSetupForm;
  Logo: TBitmapImage;
  Titulo, Onde, Rodape: TNewStaticText;
  Manter: TNewRadioButton;
  Continuar: TNewButton;
  ArquivoLogo: String;
begin
  Tela := CreateCustomForm(ScaleX(560), ScaleY(400), False, True);
  try
    Tela.Caption := 'Desinstalar o {#Nome}';

    Logo := TBitmapImage.Create(Tela);
    Logo.Parent := Tela;
    Logo.SetBounds(ScaleX(24), ScaleY(24), ScaleX(72), ScaleY(72));
    Logo.Stretch := True;
    ArquivoLogo := ExpandConstant('{app}\_internal\recursos\easyserv.png');
    if FileExists(ArquivoLogo) then
      Logo.PngImage.LoadFromFile(ArquivoLogo);

    Titulo := CriarTexto(Tela, 'O que fazer com os seus dados?', 16, '#f1ecee');
    Titulo.Left := ScaleX(116);
    Titulo.Top := ScaleY(26);
    Onde := CriarTexto(Tela, 'O programa vai ser removido. Os dados ficam em:' + #13#10 + Pasta,
                       9, '{#CorTextoFraco}');
    Onde.Left := Titulo.Left + ScaleX(2);
    Onde.Top := Titulo.Top + Titulo.Height + ScaleY(6);

    Manter := TNewRadioButton.Create(Tela);
    Manter.Parent := Tela;
    Manter.Caption := 'Manter seus dados (atendimentos, configurações, backups)';
    Manter.Font.Style := [fsBold];
    Manter.SetBounds(ScaleX(116), ScaleY(124), Tela.ClientWidth - ScaleX(140), ScaleY(22));
    Manter.Checked := True;
    Manter.OnClick := @OpcaoMudou;
    Explicacao(Tela, 'Recomendado. Se instalar o EasyServ de novo, tudo continua como estava.',
               Manter.Top + ScaleY(24));

    OpcaoApagar := TNewRadioButton.Create(Tela);
    OpcaoApagar.Parent := Tela;
    OpcaoApagar.Caption := 'Apagar tudo';
    OpcaoApagar.Font.Style := [fsBold];
    OpcaoApagar.SetBounds(ScaleX(116), ScaleY(196), Tela.ClientWidth - ScaleX(140), ScaleY(22));
    OpcaoApagar.OnClick := @OpcaoMudou;
    Explicacao(Tela, 'Apaga atendimentos, configurações, notas, relatórios e os backups dessa pasta. ' +
               'Não tem volta.', OpcaoApagar.Top + ScaleY(24));

    OpcaoBackup := TNewCheckBox.Create(Tela);
    OpcaoBackup.Parent := Tela;
    OpcaoBackup.Caption := 'Fazer um backup antes de apagar, salvo na Área de Trabalho';
    OpcaoBackup.SetBounds(ScaleX(118), OpcaoApagar.Top + ScaleY(66), Tela.ClientWidth - ScaleX(142), ScaleY(22));
    OpcaoBackup.Checked := True;
    OpcaoBackup.Enabled := False;

    Continuar := TNewButton.Create(Tela);
    Continuar.Parent := Tela;
    Continuar.Caption := 'Continuar';
    Continuar.Width := Tela.CalculateButtonWidth([Continuar.Caption]);
    Continuar.Height := ScaleY(28);
    Continuar.Left := Tela.ClientWidth - Continuar.Width - ScaleX(20);
    Continuar.Top := Tela.ClientHeight - Continuar.Height - ScaleY(16);
    Continuar.ModalResult := mrOk;
    Continuar.Default := True;

    Rodape := CriarTexto(Tela, '{#Direitos}', 8, '{#CorTextoFraco}');
    Rodape.Left := ScaleX(24);
    Rodape.Top := Continuar.Top + (Continuar.Height - Rodape.Height) div 2;

    Tela.ActiveControl := Continuar;
    // Fechar no X conta como "Manter".
    Result := (Tela.ShowModal = mrOk) and OpcaoApagar.Checked;
    BackupAntes := OpcaoBackup.Checked;
  finally
    Tela.Free;
  end;
end;

// Backup com o próprio EasyServ (o mesmo .zip do menu Arquivo › Backup, que dá para
// restaurar depois). Precisa rodar ANTES de apagar os arquivos do programa.
function FazerBackup(var Arquivo: String): Boolean;
var
  Pasta: String;
  Codigo: Integer;
  Achado: TFindRec;
begin
  Pasta := ExpandConstant('{userdesktop}');
  Result := Exec(ExpandConstant('{app}\{#Exe}'), '--backup-para "' + Pasta + '"', ExpandConstant('{app}'),
                 SW_HIDE, ewWaitUntilTerminated, Codigo) and (Codigo = 0);
  // O nome tem a data e hora: o mais novo é o maior em ordem alfabética.
  Arquivo := '';
  if Result and FindFirst(Pasta + '\EasyServ_backup_*.zip', Achado) then
  try
    repeat
      if CompareText(Achado.Name, Arquivo) > 0 then
        Arquivo := Achado.Name;
    until not FindNext(Achado);
  finally
    FindClose(Achado);
  end;
  Result := Result and (Arquivo <> '');
end;

// Antes de remover: pergunta o que fazer com os dados (e faz o backup, se for o caso).
// Depois de remover: apaga a pasta dos dados, se a pessoa escolheu.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Pasta, Arquivo: String;
  BackupAntes: Boolean;
begin
  Pasta := PastaDosDados;
  if (CurUninstallStep = usUninstall) and DirExists(Pasta) and (not UninstallSilent) then
  begin
    ApagarDados := PerguntarDados(Pasta, BackupAntes);
    if ApagarDados and BackupAntes then
    begin
      if FazerBackup(Arquivo) then
        MsgBox('Backup feito e salvo na Área de Trabalho:' + #13#10 + Arquivo + #13#10#13#10 +
               'Para usar depois: no EasyServ, Arquivo › Backup › Restaurar backup...', mbInformation, MB_OK)
      else
      begin
        ApagarDados := False;
        MsgBox('Não foi possível fazer o backup.' + #13#10#13#10 +
               'Por segurança, os seus dados NÃO vão ser apagados. Eles continuam em:' + #13#10 + Pasta,
               mbError, MB_OK);
      end;
    end
    else if ApagarDados then
      ApagarDados := MsgBox('Apagar tudo SEM backup?' + #13#10#13#10 +
                            'Os atendimentos e configurações não vão poder ser recuperados.',
                            mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  end;
  if (CurUninstallStep = usPostUninstall) and ApagarDados then
    DelTree(Pasta, True, True, True);
end;
