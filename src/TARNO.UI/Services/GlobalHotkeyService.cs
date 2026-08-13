using System;
using System.Runtime.InteropServices;

namespace TARNO.UI.Services;

/// <summary>
/// Registers a system-wide hotkey (works even when TARNO is not the
/// foreground window) by subclassing the given window's WndProc to
/// intercept WM_HOTKEY - Block 5, Phase 46 ("physischer Kill-Switch").
///
/// WinUI 3 doesn't expose WM_HOTKEY through any public event/API, unlike
/// WPF's HwndSource - this is the standard low-level workaround: replace
/// GWLP_WNDPROC with a custom delegate that handles WM_HOTKEY itself and
/// forwards everything else to the original WndProc via CallWindowProc, so
/// none of WinUI's own window handling breaks.
/// </summary>
public sealed class GlobalHotkeyService : IDisposable
{
    private const int WM_HOTKEY = 0x0312;
    private const int GWLP_WNDPROC = -4;

    [Flags]
    private enum Modifiers : uint
    {
        Alt = 0x0001,
        Control = 0x0002,
        Shift = 0x0004,
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    [DllImport("user32.dll")]
    private static extern IntPtr CallWindowProc(IntPtr lpPrevWndFunc, IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")]
    private static extern IntPtr SetWindowLongPtr64(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongW")]
    private static extern IntPtr SetWindowLong32(IntPtr hWnd, int nIndex, IntPtr dwNewLong);

    private delegate IntPtr WndProcDelegate(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    private readonly IntPtr _hwnd;
    private readonly int _hotkeyId;
    private readonly WndProcDelegate _newWndProcDelegate;
    private IntPtr _newWndProcPtr;
    private IntPtr _originalWndProc;
    private bool _registered;

    /// <summary>Fired on the same thread as the window message loop when the hotkey fires.</summary>
    public event Action? HotkeyPressed;

    /// <param name="hwnd">Window handle to subclass (see WinRT.Interop.WindowNative.GetWindowHandle).</param>
    /// <param name="virtualKeyCode">Windows virtual-key code, e.g. 0x4B for 'K'.</param>
    public GlobalHotkeyService(IntPtr hwnd, uint virtualKeyCode, bool ctrl = true, bool alt = true, bool shift = false)
    {
        _hwnd = hwnd;
        _hotkeyId = GetHashCode() & 0x0000FFFF; // RegisterHotKey ids must be in [0, 0xBFFF] range-safe

        uint modifiers = 0;
        if (ctrl) modifiers |= (uint)Modifiers.Control;
        if (alt) modifiers |= (uint)Modifiers.Alt;
        if (shift) modifiers |= (uint)Modifiers.Shift;

        _newWndProcDelegate = WndProc;
        _newWndProcPtr = Marshal.GetFunctionPointerForDelegate(_newWndProcDelegate);
        _originalWndProc = SetWindowLongPtr(_hwnd, GWLP_WNDPROC, _newWndProcPtr);

        _registered = RegisterHotKey(_hwnd, _hotkeyId, modifiers, virtualKeyCode);
    }

    private IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg == WM_HOTKEY && wParam.ToInt32() == _hotkeyId)
        {
            HotkeyPressed?.Invoke();
        }
        return CallWindowProc(_originalWndProc, hWnd, msg, wParam, lParam);
    }

    private static IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr newProc)
    {
        return Environment.Is64BitProcess
            ? SetWindowLongPtr64(hWnd, nIndex, newProc)
            : SetWindowLong32(hWnd, nIndex, newProc);
    }

    public void Dispose()
    {
        if (_registered)
        {
            UnregisterHotKey(_hwnd, _hotkeyId);
            _registered = false;
        }
        if (_originalWndProc != IntPtr.Zero)
        {
            SetWindowLongPtr(_hwnd, GWLP_WNDPROC, _originalWndProc);
            _originalWndProc = IntPtr.Zero;
        }
    }
}
