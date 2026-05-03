# 设置 Larker Overlay 窗口为 Always on Top
# 通过进程窗口标题或 MainWindowHandle 匹配 Chrome --app 模式的窗口

Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter,
      int X, int Y, int cx, int cy, uint uFlags);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
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
$hwnd = [IntPtr]::Zero

# 方法1：通过 Get-Process 获取 MainWindowHandle（最可靠）
Write-Output "正在查找 Overlay 窗口..."
$chromeProcs = Get-Process chrome -ErrorAction SilentlyContinue

foreach ($proc in $chromeProcs) {
    $mainTitle = $proc.MainWindowTitle
    if ($mainTitle -and $mainTitle -ne "") {
        # 精确匹配 "Larker"（Chrome --app 模式正常时）
        if ($mainTitle -eq $title) {
            $hwnd = $proc.MainWindowHandle
            Write-Output "  ✓ 精确匹配: '$mainTitle' (PID=$($proc.Id), HWND=$hwnd)"
            break
        }
        # 匹配 localhost:8088（Chrome --app 未生效时的回退）
        if ($mainTitle -like "*8088*") {
            $hwnd = $proc.MainWindowHandle
            Write-Output "  ✓ 匹配端口: '$mainTitle' (PID=$($proc.Id), HWND=$hwnd)"
            break
        }
        # 匹配 "localhost"（另一种可能的标题）
        if ($mainTitle -like "*localhost*") {
            $hwnd = $proc.MainWindowHandle
            Write-Output "  ✓ 匹配 localhost: '$mainTitle' (PID=$($proc.Id), HWND=$hwnd)"
            break
        }
        # 记录所有 Chrome 窗口用于调试
        Write-Output "  ? Chrome 窗口: '$mainTitle' (PID=$($proc.Id), HWND=$($proc.MainWindowHandle))"
    }
}

# 方法2：枚举所有窗口标题（调试用，如果方法1失败）
if ($hwnd -eq [IntPtr]::Zero) {
    Write-Output "方法1失败，枚举所有 Chrome 窗口标题..."
    foreach ($proc in $chromeProcs) {
        $mainTitle = $proc.MainWindowTitle
        if ($mainTitle -and $mainTitle -ne "") {
            Write-Output "  Chrome 窗口: '$mainTitle' (PID=$($proc.Id), HWND=$($proc.MainWindowHandle))"
        }
    }
}

# 设置置顶
if ($hwnd -ne [IntPtr]::Zero) {
    $visible = [Win32]::IsWindowVisible($hwnd)
    $rect = New-Object Win32+RECT
    [Win32]::GetWindowRect($hwnd, [ref]$rect) | Out-Null

    # 先确保窗口可见
    if (-not $visible) {
        [Win32]::ShowWindow($hwnd, $SW_SHOW)
        Write-Output "  窗口已恢复显示（之前不可见）"
    }

    # 设置置顶
    $result = [Win32]::SetWindowPos($hwnd, [IntPtr]::new($HWND_TOPMOST), 0, 0, 0, 0, $SWP_NOSIZE -bor $SWP_NOMOVE)
    if ($result) {
        Write-Output "Set always-on-top: $title (hwnd=$hwnd, visible=$visible, pos=($($rect.Left),$($rect.Top)))"
    } else {
        $errCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
        Write-Output "SetWindowPos failed: hwnd=$hwnd, error=$errCode"
    }
} else {
    Write-Output "Window not found: $title"
    Write-Output "提示：请确认 Chrome --app 窗口已启动且标题为 '$title'"
}
