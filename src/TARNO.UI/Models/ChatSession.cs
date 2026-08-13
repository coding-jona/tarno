using System;
using System.Collections.Generic;

namespace TARNO.UI.Models;

/// <summary>
/// Persistierbare Chat-Sitzung mit allen Nachrichten.
/// </summary>
public class ChatSession
{
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Title { get; set; } = "Neuer Chat";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.Now;
    public string? WorkspaceId { get; set; }
    public string SidebarMode { get; set; } = "Chat";
    public string? Provider { get; set; }
    public string? Model { get; set; }
    public List<ChatMessageData> Messages { get; set; } = new();
}
