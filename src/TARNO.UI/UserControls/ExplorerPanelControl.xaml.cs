using TARNO.UI.Models;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace TARNO.UI.UserControls;

/// <summary>
/// Explorer-Panel (Datei-Baum + Dateiinhalt-Vorschau), 1:1 aus
/// CodeWorkspacePage extrahiert (Multi-Screen-Plan Phase 1) - kann sowohl
/// inline im Hauptfenster (Einzelbildschirm, unveraendertes Verhalten) als
/// auch in einem eigenen ExplorerWindow auf einem zweiten Bildschirm
/// gehostet werden (Phase 3). AttachViewModel muss vor jeder Nutzung
/// aufgerufen werden (mirrort CodeWorkspacePage.OnNavigatedTo's bisheriges
/// ViewModel-Setzen).
/// </summary>
public sealed partial class ExplorerPanelControl : UserControl, IDraggablePanel
{
    public MainViewModel? ViewModel { get; private set; }

    /// <summary>Eindeutige Kennung dieses Panels für Drag-and-Drop.</summary>
    public string PanelId => "explorer";

    public string Title => "Explorer";

    /// <summary>Index des Fensters, in dem das Panel gerade liegt (0=Haupt, 1=Explorer-Fenster, ...).</summary>
    public int WindowIndex { get; set; }

    public FrameworkElement DragRoot => this;

    public FrameworkElement? Placeholder { get; set; }

    private sealed class FileNode
    {
        public string Name { get; }
        public string Path { get; }
        public bool IsDirectory { get; }
        public bool IsRoot { get; }
        public WorkspaceFolder? Folder { get; }
        public bool IsLoaded { get; set; }
        public string IconGlyph { get; }

        public FileNode(string name, string path, bool isDirectory, bool isRoot = false, WorkspaceFolder? folder = null)
        {
            Name = name;
            Path = path;
            IsDirectory = isDirectory;
            IsRoot = isRoot;
            Folder = folder;
            IconGlyph = isDirectory ? "" : ResolveFileGlyph(name);
        }

        private static string ResolveFileGlyph(string fileName)
        {
            return System.IO.Path.GetExtension(fileName).ToLowerInvariant() switch
            {
                ".cs" => "",
                ".py" => "",
                ".js" or ".ts" => "",
                ".xaml" or ".xml" => "",
                ".json" or ".yaml" or ".yml" => "",
                ".md" or ".txt" or ".rtf" => "",
                ".png" or ".jpg" or ".jpeg" or ".bmp" or ".svg" => "",
                ".exe" or ".dll" => "",
                _ => "",
            };
        }

        public override string ToString()
        {
            return IsRoot ? Name : $"{IconGlyph} {Name}";
        }
    }

    public ExplorerPanelControl()
    {
        this.InitializeComponent();
    }

    public void AttachViewModel(MainViewModel viewModel)
    {
        ViewModel = viewModel;
        LoadFiles();
    }

    public void LoadFiles()
    {
        ExplorerTree.RootNodes.Clear();
        FileContentView.Text = string.Empty;
        var workspace = ViewModel?.SelectedWorkspace;
        if (workspace is null || workspace.Folders.Count == 0)
        {
            return;
        }

        try
        {
            foreach (var folder in workspace.Folders)
            {
                if (string.IsNullOrWhiteSpace(folder.Path) || !Directory.Exists(folder.Path))
                {
                    continue;
                }
                var rootFile = new FileNode(folder.Name, folder.Path, true, true, folder);
                var rootNode = new TreeViewNode { Content = rootFile };
                AddPlaceholder(rootNode);
                ExplorerTree.RootNodes.Add(rootNode);
                TryRestoreExpanded(rootNode, rootFile);
            }
        }
        catch (Exception ex)
        {
            ExplorerTree.RootNodes.Add(new TreeViewNode { Content = $"[TARNO] Fehler beim Laden: {ex.Message}" });
        }
    }

    private void AddPlaceholder(TreeViewNode node)
    {
        node.Children.Add(new TreeViewNode { Content = new FileNode("...", "", true) });
    }

    private void TryRestoreExpanded(TreeViewNode node, FileNode dirNode)
    {
        if (!dirNode.IsDirectory)
        {
            return;
        }
        var workspace = ViewModel?.SelectedWorkspace;
        if (workspace is null || !workspace.ExpandedPaths.Contains(dirNode.Path))
        {
            return;
        }
        LoadDirectoryChildren(node, dirNode);
        try
        {
            node.IsExpanded = true;
            foreach (var child in node.Children)
            {
                if (child.Content is FileNode childFile && childFile.IsDirectory)
                {
                    TryRestoreExpanded(child, childFile);
                }
            }
        }
        catch
        {
            // Best-effort: IsExpanded-Setzer ist optional.
        }
    }

    private void LoadDirectoryChildren(TreeViewNode node, FileNode dirNode)
    {
        node.Children.Clear();
        try
        {
            var directories = Directory.EnumerateDirectories(dirNode.Path)
                .OrderBy(d => d)
                .Select(d => new FileNode(Path.GetFileName(d), d, true));
            var files = Directory.EnumerateFiles(dirNode.Path)
                .OrderBy(f => f)
                .Select(f => new FileNode(Path.GetFileName(f), f, false));

            foreach (var child in directories)
            {
                var childNode = new TreeViewNode { Content = child };
                AddPlaceholder(childNode);
                node.Children.Add(childNode);
            }
            foreach (var child in files)
            {
                node.Children.Add(new TreeViewNode { Content = child });
            }
            dirNode.IsLoaded = true;
        }
        catch (Exception ex)
        {
            node.Children.Add(new TreeViewNode { Content = $"[TARNO] Fehler: {ex.Message}" });
        }
    }

    private void OnTreeItemInvoked(TreeView sender, TreeViewItemInvokedEventArgs e)
    {
        if (e.InvokedItem is not TreeViewNode node || node.Content is not FileNode fileNode || fileNode.IsDirectory)
        {
            return;
        }
        InteractionLogger.Click("CodeWorkspace", $"FileOpened:{fileNode.Name}");
        try
        {
            var text = File.ReadAllText(fileNode.Path);
            const int MaxLength = 200_000;
            if (text.Length > MaxLength)
            {
                text = text[..MaxLength] + "\n\n[... TARNO: Datei zu lang, gekürzt ...]";
            }
            FileContentView.Text = text;
        }
        catch (Exception ex)
        {
            FileContentView.Text = $"[TARNO] Fehler beim Lesen: {ex.Message}";
        }
    }

    private void OnTreeExpanding(TreeView sender, TreeViewExpandingEventArgs e)
    {
        if (e.Node.Content is not FileNode dirNode || !dirNode.IsDirectory || dirNode.IsLoaded)
        {
            return;
        }
        for (int i = e.Node.Children.Count - 1; i >= 0; i--)
        {
            if (e.Node.Children[i].Content is FileNode { Name: "..." })
            {
                e.Node.Children.RemoveAt(i);
            }
        }
        LoadDirectoryChildren(e.Node, dirNode);
        RecordExpanded(e.Node, true);
    }

    private void OnTreeCollapsed(TreeView sender, TreeViewCollapsedEventArgs e)
    {
        RecordExpanded(e.Node, false);
    }

    private void RecordExpanded(TreeViewNode node, bool expanded)
    {
        if (node.Content is not FileNode fileNode)
        {
            return;
        }
        var workspace = ViewModel?.SelectedWorkspace;
        if (workspace is null)
        {
            return;
        }
        if (expanded)
        {
            if (!workspace.ExpandedPaths.Contains(fileNode.Path))
            {
                workspace.ExpandedPaths.Add(fileNode.Path);
            }
        }
        else
        {
            workspace.ExpandedPaths.Remove(fileNode.Path);
        }
    }

    private async void OnAddFolderToWorkspaceClick(object sender, RoutedEventArgs e)
    {
        var workspace = ViewModel?.SelectedWorkspace;
        if (workspace is null)
        {
            return;
        }

        var picker = new FolderPicker();
        picker.SuggestedStartLocation = PickerLocationId.DocumentsLibrary;
        picker.FileTypeFilter.Add("*");

        var hwnd = WindowNative.GetWindowHandle(App.MainWindow);
        InitializeWithWindow.Initialize(picker, hwnd);

        var folder = await picker.PickSingleFolderAsync();
        if (folder is null)
        {
            return;
        }

        workspace.Folders.Add(new WorkspaceFolder
        {
            Name = folder.Name,
            Path = folder.Path,
        });
        PersistWorkspaceFolders(workspace);
        LoadFiles();
    }

    private void OnRemoveRootClick(object sender, RoutedEventArgs e)
    {
        var workspace = ViewModel?.SelectedWorkspace;
        if (workspace is null)
        {
            return;
        }

        if (ExplorerTree.SelectedNode?.Content is not FileNode { IsRoot: true, Folder: not null } fileNode)
        {
            return;
        }

        workspace.Folders.Remove(fileNode.Folder);
        PersistWorkspaceFolders(workspace);
        LoadFiles();
    }

    private void OnOpenInFileExplorerClick(object sender, RoutedEventArgs e)
    {
        if (ExplorerTree.SelectedNode?.Content is not FileNode fileNode)
        {
            return;
        }
        var path = fileNode.IsDirectory ? fileNode.Path : Path.GetDirectoryName(fileNode.Path);
        if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path))
        {
            return;
        }
        try
        {
            Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{path}\"") { UseShellExecute = true });
        }
        catch
        {
            // Best-effort: Explorer öffnen ist optional.
        }
    }

    private void OnCopyPathClick(object sender, RoutedEventArgs e)
    {
        if (ExplorerTree.SelectedNode?.Content is not FileNode fileNode)
        {
            return;
        }
        var package = new DataPackage();
        package.SetText(fileNode.Path);
        Clipboard.SetContent(package);
    }

    private void OnAddToContextClick(object sender, RoutedEventArgs e)
    {
        if (ExplorerTree.SelectedNode?.Content is not FileNode fileNode || fileNode.IsDirectory)
        {
            return;
        }
        if (ViewModel is null || ViewModel.SelectedContextFiles.Contains(fileNode.Path))
        {
            return;
        }
        ViewModel.SelectedContextFiles.Add(fileNode.Path);
    }

    private void PersistWorkspaceFolders(Workspace workspace)
    {
        try
        {
            WorkspaceStore.Save(ViewModel!.Workspaces.ToList());
        }
        catch
        {
            // Best-effort Persistierung.
        }
    }

    /// <summary>
    /// Wird vom Header-Border ausgelöst, wenn der Nutzer das Panel verschieben möchte.
    /// </summary>
    public async void OnPanelDragStarting(UIElement sender, DragStartingEventArgs e)
    {
        e.AllowedOperations = DataPackageOperation.Move;
        await DragVisualService.SetDragVisualAsync(e, this);
        PanelDragService.SetDragPayload(e.Data, this);
    }
}
