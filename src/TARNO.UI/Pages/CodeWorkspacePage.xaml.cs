using TARNO.UI.Models;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using CommunityToolkit.WinUI.Controls;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Navigation;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Threading.Tasks;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace TARNO.UI.Pages;

public sealed partial class CodeWorkspacePage : Page
{
    public MainViewModel ViewModel { get; private set; } = null!;
    public TerminalService Terminal { get; private set; } = null!;
    public ObservableCollection<string> FileList { get; } = new();


    private readonly ObservableCollection<CommandPaletteItem> _paletteItems = new();
    private readonly IReadOnlyList<CommandPaletteItem> _allCommands = new List<CommandPaletteItem>
    {
        new("Frage an TARNO", "Startet eine neue Coding-Frage", "ask"),
        new("Coding-Aufgabe", "Startet eine editierende Coding-Aufgabe", "edit"),
        new("Build", "Build im Terminal starten", "build"),
        new("Tests", "Tests im Terminal ausführen", "test"),
        new("Git Status", "Git-Status im Terminal anzeigen", "git-status"),
        new("Kontext leeren", "Markierte Dateien aus dem Kontext entfernen", "clear-context"),
    };

    private sealed class CommandPaletteItem
    {
        public string Title { get; }
        public string Subtitle { get; }
        public string CommandId { get; }

        public CommandPaletteItem(string title, string subtitle, string commandId)
        {
            Title = title;
            Subtitle = subtitle;
            CommandId = commandId;
        }
    }

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
            IconGlyph = isDirectory ? "\uE8B7" : ResolveFileGlyph(name);
        }

        private static string ResolveFileGlyph(string fileName)
        {
            return System.IO.Path.GetExtension(fileName).ToLowerInvariant() switch
            {
                ".cs" => "\uE943",
                ".py" => "\uE943",
                ".js" or ".ts" => "\uE943",
                ".xaml" or ".xml" => "\uE7B5",
                ".json" or ".yaml" or ".yml" => "\uE7B5",
                ".md" or ".txt" or ".rtf" => "\uE7B5",
                ".png" or ".jpg" or ".jpeg" or ".bmp" or ".svg" => "\uE722",
                ".exe" or ".dll" => "\uE7F4",
                _ => "\uE7C3",
            };
        }

        public override string ToString()
        {
            return IsRoot ? Name : $"{IconGlyph} {Name}";
        }
    }

    private enum FocusPanel
    {
        Chat,
        Coding,
        Terminal,
    }

    private enum FocusAnchor
    {
        Left,
        Right,
        Top,
        Bottom,
    }

    // Verhindert, dass SelectionChanged auf den drei Layout-Combos waehrend
    // der programmatischen Wiederherstellung (OnNavigatedTo) jeweils sofort
    // ein - zu diesem Zeitpunkt unvollstaendiges - Layout anwendet. Selbes
    // Connect()-Timing-Muster wie beim ChatSettingsDialog-Absturz weiter
    // oben in dieser Session: Ereignisse koennen feuern, bevor alle drei
    // Combos gesetzt sind.
    private bool _restoringLayout;

    public CodeWorkspacePage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            Terminal = new TerminalService(DispatcherQueue.GetForCurrentThread());
            WorkspaceChatView.DataContext = ViewModel;
            Bindings.Update();
            LoadFiles();
            if (ViewModel.SelectedWorkspace is not null)
            {
                Terminal.Start(ViewModel.SelectedWorkspace);
            }
        }

        RestoreLayout(CodeLayoutPresetStore.Load("Stacked"));

        base.OnNavigatedTo(e);
    }

    private void OnEqualStackedClick(object sender, RoutedEventArgs e)
    {
        ApplyEqualLayout(horizontal: false);
        CodeLayoutPresetStore.Save("Stacked");
        InteractionLogger.Click("CodeWorkspace", "LayoutPreset:Stacked");
    }

    private void OnEqualSideBySideClick(object sender, RoutedEventArgs e)
    {
        ApplyEqualLayout(horizontal: true);
        CodeLayoutPresetStore.Save("SideBySide");
        InteractionLogger.Click("CodeWorkspace", "LayoutPreset:SideBySide");
    }

    private void OnFocusLayoutComboChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_restoringLayout || PrimaryPanelCombo is null || AnchorCombo is null || SecondaryOrderCombo is null)
        {
            return;
        }

        if (PrimaryPanelCombo.SelectedItem is not ComboBoxItem primaryItem
            || AnchorCombo.SelectedItem is not ComboBoxItem anchorItem
            || SecondaryOrderCombo.SelectedItem is not ComboBoxItem orderItem)
        {
            return;
        }

        var primary = Enum.Parse<FocusPanel>((string)primaryItem.Tag);
        var anchor = Enum.Parse<FocusAnchor>((string)anchorItem.Tag);
        bool swap = (string)orderItem.Tag == "Swapped";

        ApplyFocusLayout(primary, anchor, swap);
        CodeLayoutPresetStore.Save($"Focus:{primary}:{anchor}:{(swap ? 1 : 0)}");
        InteractionLogger.Click("CodeWorkspace", $"LayoutPreset:Focus:{primary}:{anchor}:{swap}");
    }

    /// <summary>
    /// Stellt eine gespeicherte Layout-Auswahl wieder her (oder den Standard,
    /// falls keine existiert oder das Format nicht (mehr) passt).
    /// </summary>
    private void RestoreLayout(string saved)
    {
        _restoringLayout = true;
        try
        {
            var parts = saved.Split(':');
            if (parts.Length == 4
                && parts[0] == "Focus"
                && Enum.TryParse<FocusPanel>(parts[1], out var primary)
                && Enum.TryParse<FocusAnchor>(parts[2], out var anchor)
                && int.TryParse(parts[3], out var swapFlag))
            {
                PrimaryPanelCombo.SelectedIndex = (int)primary;
                AnchorCombo.SelectedIndex = (int)anchor;
                SecondaryOrderCombo.SelectedIndex = swapFlag;
                ApplyFocusLayout(primary, anchor, swapFlag == 1);
                return;
            }

            PrimaryPanelCombo.SelectedIndex = 0;
            AnchorCombo.SelectedIndex = 0;
            SecondaryOrderCombo.SelectedIndex = 0;
            ApplyEqualLayout(horizontal: saved == "SideBySide");
        }
        finally
        {
            _restoringLayout = false;
        }
    }

    /// <summary>
    /// Baut RightGrid komplett neu auf: feste Zeilen/Spalten je Vorlage plus
    /// GridSplitter zum Verkleinern/Vergroessern. Ersetzt das vorherige
    /// SnapCanvas/Pegboard-Freiform-Drag-System (siehe PegboardDragService),
    /// das trotz mehrerer Fixes (Crash bei jedem Klick, Ueberlappung, im
    /// linken oberen Eck haengende Panels) nicht zuverlaessig funktionierte.
    /// Feste Positionen + native GridSplitter-Resize koennen weder
    /// abstuerzen noch ueberlappen - die Panels selbst (ChatPanelBorder/
    /// CodingPanelBorder/TerminalPanelBorder) bleiben dieselben Instanzen und
    /// werden nur zwischen Zeilen/Spalten umgehaengt, damit kein State
    /// (z. B. ChatView) verloren geht.
    ///
    /// Statt einzelner fest verdrahteter Presets (frueher 5 Stueck) deckt
    /// diese eine Funktion alle 3 (grosses Panel) x 4 (Position) x 2
    /// (Reihenfolge der anderen zwei) = 24 Kombinationen ab, plus die 2
    /// Gleichgross-Varianten (Stacked/SideBySide) ueber ApplyEqualLayout -
    /// macht "mindestens 20 Anpassungsmoeglichkeiten" wartbar statt 20
    /// beinahe-identische Switch-Faelle zu duplizieren.
    /// </summary>
    private void ApplyFocusLayout(FocusPanel primary, FocusAnchor anchor, bool swapSecondary)
    {
        RightGrid.RowDefinitions.Clear();
        RightGrid.ColumnDefinitions.Clear();
        RightGrid.Children.Clear();

        const int splitterThickness = 6;

        var others = Enum.GetValues<FocusPanel>().Where(p => p != primary).ToList();
        if (swapSecondary)
        {
            others.Reverse();
        }

        var primaryElement = PanelElement(primary);
        var secondary1 = PanelElement(others[0]);
        var secondary2 = PanelElement(others[1]);

        bool horizontal = anchor is FocusAnchor.Left or FocusAnchor.Right;

        if (horizontal)
        {
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(splitterThickness) });
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(splitterThickness) });
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            int primaryColumn = anchor == FocusAnchor.Left ? 0 : 2;
            int secondaryColumn = anchor == FocusAnchor.Left ? 2 : 0;

            AddChild(primaryElement, row: 0, column: primaryColumn, rowSpan: 3);
            AddSplitter(GridSplitter.GridResizeDirection.Columns, row: 0, column: 1, rowSpan: 3);
            AddChild(secondary1, row: 0, column: secondaryColumn);
            AddSplitter(GridSplitter.GridResizeDirection.Rows, row: 1, column: secondaryColumn);
            AddChild(secondary2, row: 2, column: secondaryColumn);
        }
        else
        {
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(2, GridUnitType.Star) });
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(splitterThickness) });
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(splitterThickness) });
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            int primaryRow = anchor == FocusAnchor.Top ? 0 : 2;
            int secondaryRow = anchor == FocusAnchor.Top ? 2 : 0;

            AddChild(primaryElement, row: primaryRow, column: 0, columnSpan: 3);
            AddSplitter(GridSplitter.GridResizeDirection.Rows, row: 1, column: 0, columnSpan: 3);
            AddChild(secondary1, row: secondaryRow, column: 0);
            AddSplitter(GridSplitter.GridResizeDirection.Columns, row: secondaryRow, column: 1);
            AddChild(secondary2, row: secondaryRow, column: 2);
        }
    }

    /// <summary>Alle drei Panels gleich gross - gestapelt oder nebeneinander.</summary>
    private void ApplyEqualLayout(bool horizontal)
    {
        RightGrid.RowDefinitions.Clear();
        RightGrid.ColumnDefinitions.Clear();
        RightGrid.Children.Clear();

        const int splitterThickness = 6;
        var panels = new[] { ChatPanelBorder, CodingPanelBorder, TerminalPanelBorder };

        if (horizontal)
        {
            for (int i = 0; i < panels.Length; i++)
            {
                if (i > 0)
                {
                    RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(splitterThickness) });
                    AddSplitter(GridSplitter.GridResizeDirection.Columns, row: 0, column: RightGrid.ColumnDefinitions.Count - 1);
                }
                RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                AddChild(panels[i], row: 0, column: RightGrid.ColumnDefinitions.Count - 1);
            }
            RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        }
        else
        {
            for (int i = 0; i < panels.Length; i++)
            {
                if (i > 0)
                {
                    RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(splitterThickness) });
                    AddSplitter(GridSplitter.GridResizeDirection.Rows, row: RightGrid.RowDefinitions.Count - 1, column: 0);
                }
                RightGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
                AddChild(panels[i], row: RightGrid.RowDefinitions.Count - 1, column: 0);
            }
            RightGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        }
    }

    private FrameworkElement PanelElement(FocusPanel panel) => panel switch
    {
        FocusPanel.Chat => ChatPanelBorder,
        FocusPanel.Coding => CodingPanelBorder,
        _ => TerminalPanelBorder,
    };

    private void AddChild(FrameworkElement element, int row, int column, int rowSpan = 1, int columnSpan = 1)
    {
        Grid.SetRow(element, row);
        Grid.SetColumn(element, column);
        Grid.SetRowSpan(element, rowSpan);
        Grid.SetColumnSpan(element, columnSpan);
        RightGrid.Children.Add(element);
    }

    private void AddSplitter(GridSplitter.GridResizeDirection direction, int row, int column, int rowSpan = 1, int columnSpan = 1)
    {
        var splitter = new GridSplitter
        {
            ResizeDirection = direction,
            ResizeBehavior = GridSplitter.GridResizeBehavior.BasedOnAlignment,
        };

        if (direction == GridSplitter.GridResizeDirection.Columns)
        {
            splitter.HorizontalAlignment = HorizontalAlignment.Stretch;
            splitter.VerticalAlignment = VerticalAlignment.Stretch;
        }
        else
        {
            splitter.HorizontalAlignment = HorizontalAlignment.Stretch;
            splitter.VerticalAlignment = VerticalAlignment.Stretch;
        }

        AddChild(splitter, row, column, rowSpan, columnSpan);
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        if (ViewModel?.SelectedWorkspace is not null)
        {
            try
            {
                WorkspaceStore.Save(ViewModel.Workspaces.ToList());
            }
            catch
            {
                // Best-effort Persistierung.
            }
        }
        Terminal?.Dispose();
        base.OnNavigatedFrom(e);
    }

    private void LoadFiles()
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

    private void OnClearContextFilesClick(object sender, RoutedEventArgs e)
    {
        ViewModel?.SelectedContextFiles.Clear();
    }

    private void PersistWorkspaceFolders(Workspace workspace)
    {
        try
        {
            WorkspaceStore.Save(ViewModel.Workspaces.ToList());
        }
        catch
        {
            // Best-effort Persistierung.
        }
    }

    private void OnTerminalInputKeyDown(object sender, Microsoft.UI.Xaml.Input.KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter)
        {
            SendTerminalCommand();
            e.Handled = true;
        }
    }

    private void SendTerminalCommand()
    {
        var command = TerminalInput.Text;
        if (string.IsNullOrWhiteSpace(command))
        {
            return;
        }
        Terminal.SendInput(command);
        TerminalInput.Text = string.Empty;
    }

    private void OnCodingInputKeyDown(object sender, Microsoft.UI.Xaml.Input.KeyRoutedEventArgs e)
    {
        if (e.Key == Windows.System.VirtualKey.Enter)
        {
            _ = SendCodingTaskAsync();
            e.Handled = true;
        }
    }

    private async Task SendCodingTaskAsync()
    {
        var prompt = CodingInput.Text;
        if (string.IsNullOrWhiteSpace(prompt) || ViewModel is null)
        {
            return;
        }
        await ViewModel.SendCodingTaskAsync(prompt, Array.Empty<string>(), ReadOnlyCheck.IsChecked ?? false);
        CodingInput.Text = string.Empty;
    }

    private void OnSendCodingTaskClick(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        _ = SendCodingTaskAsync();
    }

    private void OnCodingPanelToggleClick(object sender, Microsoft.UI.Xaml.RoutedEventArgs e)
    {
        bool expand = CodingContent.Visibility == Visibility.Collapsed;
        CodingContent.Visibility = expand ? Visibility.Visible : Visibility.Collapsed;
        CodingToggleButton.Content = expand ? "▼" : "▶";
    }

    private void FilterCommands(string filter)
    {
        _paletteItems.Clear();
        var query = filter.Trim().ToLowerInvariant();
        foreach (var item in _allCommands)
        {
            if (string.IsNullOrEmpty(query)
                || item.Title.Contains(filter, StringComparison.OrdinalIgnoreCase)
                || item.CommandId.Contains(query, StringComparison.OrdinalIgnoreCase))
            {
                _paletteItems.Add(item);
            }
        }
    }

    private void ExecuteCommand(string commandId)
    {
        if (ViewModel is null)
        {
            return;
        }
        switch (commandId)
        {
            case "ask":
            case "edit":
                CodingContent.Visibility = Visibility.Visible;
                CodingToggleButton.Content = "▼";
                _ = CodingInput.Focus(Microsoft.UI.Xaml.FocusState.Programmatic);
                break;
            case "build":
                Terminal.SendInput("dotnet build");
                break;
            case "test":
                Terminal.SendInput("dotnet test");
                break;
            case "git-status":
                Terminal.SendInput("git status");
                break;
            case "clear-context":
                ViewModel.SelectedContextFiles.Clear();
                break;
        }
    }

    private async void OnOpenCommandPaletteClick(object sender, RoutedEventArgs e)
    {
        await ShowCommandPaletteAsync();
    }

    private async void OnCommandPaletteAccelerator(KeyboardAccelerator sender, KeyboardAcceleratorInvokedEventArgs args)
    {
        args.Handled = true;
        await ShowCommandPaletteAsync();
    }

    private async Task ShowCommandPaletteAsync()
    {
        var input = new TextBox
        {
            PlaceholderText = "Befehl eingeben...",
            FontSize = 14,
        };
        var list = new ListBox
        {
            ItemsSource = _paletteItems,
            DisplayMemberPath = "Title",
            Height = 300,
            Margin = new Microsoft.UI.Xaml.Thickness(0, 12, 0, 0),
        };
        var panel = new StackPanel { Orientation = Orientation.Vertical };
        panel.Children.Add(input);
        panel.Children.Add(list);

        var dialog = new ContentDialog
        {
            Title = "Befehlspalette",
            Content = panel,
            PrimaryButtonText = "Ausführen",
            CloseButtonText = "Abbrechen",
            DefaultButton = ContentDialogButton.Primary,
            XamlRoot = XamlRoot,
        };

        input.TextChanged += (s, ev) =>
        {
            FilterCommands(input.Text);
            list.SelectedIndex = _paletteItems.Count > 0 ? 0 : -1;
        };
        input.KeyDown += (s, ev) =>
        {
            if (ev.Key == Windows.System.VirtualKey.Enter && list.SelectedItem is CommandPaletteItem item)
            {
                ExecuteCommand(item.CommandId);
                dialog.Hide();
                ev.Handled = true;
            }
            else if (ev.Key == Windows.System.VirtualKey.Escape)
            {
                dialog.Hide();
                ev.Handled = true;
            }
        };
        list.DoubleTapped += (s, ev) =>
        {
            if (list.SelectedItem is CommandPaletteItem item)
            {
                ExecuteCommand(item.CommandId);
                dialog.Hide();
            }
        };
        dialog.PrimaryButtonClick += (s, ev) =>
        {
            if (list.SelectedItem is CommandPaletteItem item)
            {
                ExecuteCommand(item.CommandId);
            }
        };

        FilterCommands(string.Empty);
        if (_paletteItems.Count > 0)
        {
            list.SelectedIndex = 0;
        }

        await dialog.ShowAsync();
    }
}
