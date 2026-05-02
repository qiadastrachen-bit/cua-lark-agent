# 设置 Larker Overlay 窗口为 Always on Top
# 通过窗口标题 "Larker" 匹配 Chrome --app 模式的窗口

Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter,
      int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  }
"@

$HWND_TOPMOST = -1
$SWP_NOSIZE = 0x0001
$SWP_NOMOVE = 0x0002

# Chrome --app 模式的窗口标题就是 HTML 的 <title>
# 我们的 title 是 "CUA Agent · Overlay"，但 Chrome --app 显示的是 <title> 内容
# 实际上是 "CUA Agent · Overlay"

$title = "Larker"
$hwnd = [Win32]::FindWindow($null, $title)

if ($hwnd -ne [IntPtr]::Zero) {
    [Win32]::SetWindowPos($hwnd, $HWND_TOPMOST, 0, 0, 0, 0, $SWP_NOSIZE -bor $SWP_NOMOVE)
    Write-Output "Set always-on-top: $title (hwnd=$hwnd)"
} else {
    Write-Output "Window not found: $title"
    Write-Output "Trying to find Chrome app windows..."
    Get-Process chrome | ForEach-Object {
        $mainWinTitle = $_.MainWindowTitle
        if ($mainWinTitle -and $mainWinTitle -ne "") {
            Write-Output "  Found: $mainWinTitle"
        }
    }
}
