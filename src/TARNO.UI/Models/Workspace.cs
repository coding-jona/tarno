using System;
using System.Collections.Generic;

namespace TARNO.UI.Models;

/// <summary>Repräsentiert einen Coding-Workspace mit Sandbox-Grenzen und
/// Include-/Exclude-Patterns.</summary>
public class Workspace
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Name { get; set; } = string.Empty;
    // Legacy single root path; kept for backward compatibility with older workspaces.
    public string RootPath { get; set; } = string.Empty;
    public List<WorkspaceFolder> Folders { get; set; } = new();
    public List<string> IncludePatterns { get; set; } = new() { "**/*" };
    public List<string> ExcludePatterns { get; set; } = new() { ".env", "*.secret", "bin/", "obj/", "node_modules/" };
    public string? LayoutState { get; set; }
    public string? LastSelectedChatId { get; set; }
    public List<string> ExpandedPaths { get; set; } = new();
}
