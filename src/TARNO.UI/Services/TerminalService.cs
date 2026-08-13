using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using Microsoft.UI.Dispatching;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Startet einen Prozess innerhalb eines Workspace-Roots und leitet stdin/stdout/stderr
/// in eine ObservableCollection um.
/// </summary>
public sealed class TerminalService : INotifyPropertyChanged, IDisposable
{
    private Process? _process;
    private Workspace? _workspace;
    private readonly DispatcherQueue _dispatcher;

    public ObservableCollection<string> OutputLines { get; } = new();

    private bool _isRunning;
    public bool IsRunning
    {
        get => _isRunning;
        private set
        {
            if (_isRunning != value)
            {
                _isRunning = value;
                OnPropertyChanged();
            }
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    public TerminalService(DispatcherQueue dispatcher)
    {
        _dispatcher = dispatcher;
    }

    public void Start(Workspace workspace)
    {
        if (_process is not null)
        {
            Stop();
        }

        var primaryFolder = workspace.Folders.FirstOrDefault();
        if (primaryFolder is null || string.IsNullOrWhiteSpace(primaryFolder.Path) || !Directory.Exists(primaryFolder.Path))
        {
            OutputLines.Add("[TARNO] Workspace-Ordner nicht gefunden.");
            return;
        }

        _workspace = workspace;
        OutputLines.Clear();
        OutputLines.Add($"[TARNO] Terminal gestartet in: {primaryFolder.Path}");

        var psi = new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = "/Q /K PROMPT $P$G",
            WorkingDirectory = primaryFolder.Path,
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        _process = new Process { StartInfo = psi, EnableRaisingEvents = true };
        _process.OutputDataReceived += OnOutputDataReceived;
        _process.ErrorDataReceived += OnErrorDataReceived;
        _process.Exited += OnProcessExited;
        _process.Start();
        _process.BeginOutputReadLine();
        _process.BeginErrorReadLine();
        IsRunning = true;
    }

    public void SendInput(string command)
    {
        if (_process is null || _process.HasExited)
        {
            OutputLines.Add("[TARNO] Kein Terminal aktiv.");
            return;
        }

        _process.StandardInput.WriteLine(command);
    }

    public void Stop()
    {
        if (_process is not null && !_process.HasExited)
        {
            try
            {
                _process.Kill(entireProcessTree: true);
            }
            catch { }
        }
        _process?.Dispose();
        _process = null;
        IsRunning = false;
    }

    public void Dispose()
    {
        Stop();
    }

    private void OnOutputDataReceived(object sender, DataReceivedEventArgs e)
    {
        if (e.Data is not null)
        {
            _ = _dispatcher.TryEnqueue(() => OutputLines.Add(e.Data));
        }
    }

    private void OnErrorDataReceived(object sender, DataReceivedEventArgs e)
    {
        if (e.Data is not null)
        {
            _ = _dispatcher.TryEnqueue(() => OutputLines.Add(e.Data));
        }
    }

    private void OnProcessExited(object? sender, EventArgs e)
    {
        _ = _dispatcher.TryEnqueue(() =>
        {
            IsRunning = false;
            OutputLines.Add("[TARNO] Terminal beendet.");
        });
    }

    private void OnPropertyChanged([CallerMemberName] string propertyName = "")
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
