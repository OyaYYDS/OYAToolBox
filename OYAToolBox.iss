; Inno Setup 6 script for OYAToolBox
; Build target: dist\OYAToolBox
;
; 打包前请下载 WebView2 Evergreen 引导程序并放到项目根目录:
;   https://developer.microsoft.com/microsoft-edge/webview2/
;   (文件名: MicrosoftEdgeWebview2Setup.exe)

#define MyAppName "OYAToolBox"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "OYA"
#define MyAppExeName "OYAToolBox.exe"

[Setup]
AppId={{8F3EE22C-9A96-4B90-8E6F-6B8D0528A6D1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=dist
OutputBaseFilename=OYAToolBox-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=OYAToolBoxICO.ico

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
Source: "dist\OYAToolBox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; WebView2 Runtime 引导程序 (不存在时跳过, 见 [Run] 的 Check)
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 系统缺少 WebView2 Runtime 时静默安装
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "正在安装 WebView2 运行时..."; Check: not IsWebView2Installed
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2Installed: Boolean;
var
  Key: String;
begin
  Result := False;
  Key := 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  if RegKeyExists(HKLM, Key) then
    Result := True
  else
  if RegKeyExists(HKCU, Key) then
    Result := True;
end;
