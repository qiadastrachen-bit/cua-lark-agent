# 设置 Larker Overlay 窗口为 Always on Top
# 通过进程窗口标题匹配 Chrome --app 模式的窗口

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool SetWindowPos(IntPtr h, IntPtr i, int x, int y, int cx, int cy, uint f);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", SetLastError=true)]
  public static extern bool GetWindowRect(IntPtr h, out RECT r);
}
[StructLayout(LayoutKind.Sequential)]
public struct RECT { public int L, T, R, B; }
'@

$HWND_TOPMOST = -1
$SWP_NOSIZE = 0x1
$SWP_NOMOVE = 0x2
$SW_SHOW = 9

$title = "Larker"
$hwnd = [IntPtr]::Zero

Write-Output "正在查找 Overlay 窗口 (title='$title')..."
$procs = Get-Process chrome -EA SilentlyContinue
foreach ($p in $procs) {
  $t = $p.MainWindowTitle
  if ($t -eq $title) {
    $hwnd = $p.MainWindowHandle
    Write-Output "  [精确] '$t' PID=$($p.Id) HWND=$hwnd"
    break
  }
}
if ($hwnd -eq [IntPtr]::Zero) {
  foreach ($p in $procs) {
    $t = $p.MainWindowTitle
    if ($t -and $t -ne "" -and ($t -like "*8088*" -or $t -like "*localhost*")) {
      $hwnd = $p.MainWindowHandle
      Write-Output "  [模糊] '$t' PID=$($p.Id) HWND=$hwnd"
      break
    }
  }
}
if ($hwnd -ne [IntPtr]::Zero) {
  $vis = [Win32]::IsWindowVisible($hwnd)
  $rect = New-Object RECT
  [Win32]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
  if (-not $vis) { [Win32]::ShowWindow($hwnd, $SW_SHOW) }
  $r = [Win32]::SetWindowPos($hwnd, [IntPtr]::new($HWND_TOPMOST), 0, 0, 0, 0, $SWP_NOSIZE -bor $SWP_NOMOVE)
  if ($r) {
    Write-Output "Set always-on-top: $title (hwnd=$hwnd, pos=($($rect.L),$($rect.T)))"
  } else {
    $err = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    Write-Output "SetWindowPos failed: hwnd=$hwnd, err=$err"
  }
} else {
  Write-Output "Window not found: $title"
}
