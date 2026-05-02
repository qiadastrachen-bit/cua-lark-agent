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
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  }
"@

$HWND_TOPMOST = -1
$SWP_NOSIZE = 0x0001
$SWP_NOMOVE = 0x0002
$SW_SHOW = 9

$title = "Larker"
$hwnd = [Win32]::FindWindow($null, $title)

if ($hwnd -ne [IntPtr]::Zero) {
    $visible = [Win32]::IsWindowVisible($hwnd)
    $rect = New-Object Win32+RECT
    [Win32]::GetWindowRect($hwnd, [ref]$rect) | Out-Null

    # 先确保窗口可见（防止 Chrome --app 启动时最小化）
    if (-not $visible) {
        [Win32]::ShowWindow($hwnd, $SW_SHOW)
    }

    # 设置置顶
    $result = [Win32]::SetWindowPos($hwnd, $HWND_TOPMOST, 0, 0, 0, 0, $SWP_NOSIZE -bor $SWP_NOMOVE)
    if ($result) {
        Write-Output "Set always-on-top: $title (hwnd=$hwnd, visible=$visible, pos=($($rect.Left),$($rect.Top)))"
    } else {
        Write-Output "SetWindowPos failed for hwnd=$hwnd"
    }
} else {
    Write-Output "Window not found: $title"
    # 调试：列出所有 Chrome 窗口帮助排查
    Write-Output "Enumerating Chrome windows..."
    Get-Process chrome -ErrorAction SilentlyContinue | ForEach-Object {
        $mainTitle = $_.MainWindowTitle
        if ($mainTitle -and $mainTitle -ne "") {
            Write-Output "  Chrome window: '$mainTitle'"
        }
    } | Select-Object -First 10
}
