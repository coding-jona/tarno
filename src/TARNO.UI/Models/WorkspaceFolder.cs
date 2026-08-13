using System;

namespace TARNO.UI.Models;

/// <summary>Repräsentiert einen einzelnen Root-Ordner innerhalb eines Workspaces.</summary>
public class WorkspaceFolder
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Name { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public string DisplayText => string.IsNullOrWhiteSpace(Name) ? Path : $"{Name} ({Path})";
    public override string ToString() => DisplayText;
}
