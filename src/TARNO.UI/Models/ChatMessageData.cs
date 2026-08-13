using System;

namespace TARNO.UI.Models;

/// <summary>
/// Persistierbare Rohdaten einer Chat-Nachricht (kein UI-Image-Source).
/// </summary>
public class ChatMessageData
{
    public string Role { get; set; } = "user";
    public string Text { get; set; } = string.Empty;
    public DateTimeOffset Timestamp { get; set; } = DateTimeOffset.Now;
    public string? ImageCaption { get; set; }
}
