using System;
using System.IO;
using NAudio.Wave;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Spielt April-Fools-WAV-Dateien per NAudio ab.
/// Ignoriert fehlende Dateien lautlos, damit Tests ohne Assets nicht crashen.
/// </summary>
public static class AprilFoolsAudioService
{
    private static WaveOutEvent? _waveOut;
    private static AudioFileReader? _fileReader;
    private static string _basePath = string.Empty;

    /// <summary>
    /// Setzt den Basis-Pfad für alle Audio-Dateien (z. B. Assets/AprilFools).
    /// </summary>
    public static void Initialize(string basePath)
    {
        _basePath = basePath;
    }

    /// <summary>
    /// Spielt eine WAV-Datei anhand eines Locale-Schlüssels ab.
    /// </summary>
    public static void Play(string fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName))
        {
            return;
        }

        Stop();

        string path = Path.Combine(string.IsNullOrEmpty(_basePath) ? AppContext.BaseDirectory : _basePath, fileName);
        if (!File.Exists(path))
        {
            InteractionLogger.Warn("APRILFOOLS", $"Audio-Datei fehlt: {path}");
            return;
        }

        try
        {
            _fileReader = new AudioFileReader(path);
            _waveOut = new WaveOutEvent();
            _waveOut.Init(_fileReader);
            _waveOut.PlaybackStopped += OnPlaybackStopped;
            _waveOut.Play();
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Audio-Wiedergabe fehlgeschlagen: {ex.Message}");
            Cleanup();
        }
    }

    /// <summary>
    /// Bricht die aktuelle Wiedergabe ab und gibt Ressourcen frei.
    /// </summary>
    public static void Stop()
    {
        _waveOut?.Stop();
        Cleanup();
    }

    private static void OnPlaybackStopped(object? sender, StoppedEventArgs e)
    {
        Cleanup();
    }

    private static void Cleanup()
    {
        _waveOut?.Dispose();
        _waveOut = null;
        _fileReader?.Dispose();
        _fileReader = null;
    }
}
