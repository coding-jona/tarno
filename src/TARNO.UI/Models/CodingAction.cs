using System;

namespace TARNO.UI.Models;

/// <summary>Eine einzelne vom Coding-Agenten vorgeschlagene oder ausgeführte
/// Aktion (lesen, schreiben, suchen, befehl).</summary>
public class CodingAction
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Type { get; set; } = string.Empty; // read, write, command, search
    public string Target { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public bool RequiresApproval { get; set; } = true;
}
