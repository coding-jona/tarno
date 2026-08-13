using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Navigation;
using TARNO.UI.Models;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Windows.Storage.Pickers;
using WinRT.Interop;

namespace TARNO.UI.Pages;

public sealed partial class WorkspacesPage : Page
{
    public MainViewModel ViewModel { get; private set; } = null!;

    private bool _updatingSelection;

    public WorkspacesPage()
    {
        // x:Bind wertet ViewModel.Workspaces bereits in InitializeComponent aus;
        // App.MainWindow ist zu diesem Zeitpunkt gesetzt und traegt dieselbe
        // Instanz. OnNavigatedTo ueberschreibt es trotzdem noch einmal sicher.
        if (App.MainWindow is MainWindow main)
        {
            ViewModel = main.ViewModel;
        }
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            ViewModel.PropertyChanged += OnViewModelPropertyChanged;
            Bindings.Update();
        }
        base.OnNavigatedTo(e);
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        if (ViewModel is not null)
        {
            ViewModel.PropertyChanged -= OnViewModelPropertyChanged;
        }
        base.OnNavigatedFrom(e);
    }

    private void OnViewModelPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(MainViewModel.Workspaces))
        {
            Bindings.Update();
        }
    }

    private void OnWorkspaceSelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_updatingSelection)
        {
            return;
        }
        if (WorkspaceListView.SelectedItem is Workspace workspace)
        {
            LoadWorkspaceIntoEditor(workspace);
        }
        else
        {
            ClearEditor();
        }
    }

    private void LoadWorkspaceIntoEditor(Workspace workspace)
    {
        NameTextBox.Text = workspace.Name;
        FolderListView.ItemsSource = workspace.Folders;
        FolderNameTextBox.Text = string.Empty;
        FolderPathTextBox.Text = string.Empty;
        IncludeTextBox.Text = string.Join(", ", workspace.IncludePatterns);
        ExcludeTextBox.Text = string.Join(", ", workspace.ExcludePatterns);
    }

    private void ClearEditor()
    {
        NameTextBox.Text = string.Empty;
        FolderListView.ItemsSource = null;
        FolderNameTextBox.Text = string.Empty;
        FolderPathTextBox.Text = string.Empty;
        IncludeTextBox.Text = string.Empty;
        ExcludeTextBox.Text = string.Empty;
    }

    private async void OnBrowseFolderClick(object sender, RoutedEventArgs e)
    {
        var picker = new FolderPicker();
        picker.SuggestedStartLocation = PickerLocationId.DocumentsLibrary;
        picker.FileTypeFilter.Add("*");

        var hwnd = WindowNative.GetWindowHandle(App.MainWindow);
        InitializeWithWindow.Initialize(picker, hwnd);

        var folder = await picker.PickSingleFolderAsync();
        if (folder is not null)
        {
            FolderPathTextBox.Text = folder.Path;
        }
    }

    private void OnAddFolderClick(object sender, RoutedEventArgs e)
    {
        if (WorkspaceListView.SelectedItem is not Workspace workspace)
        {
            return;
        }

        var name = FolderNameTextBox.Text.Trim();
        var path = FolderPathTextBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        workspace.Folders.Add(new WorkspaceFolder
        {
            Name = name,
            Path = path,
        });
        FolderNameTextBox.Text = string.Empty;
        FolderPathTextBox.Text = string.Empty;
        PersistWorkspaces();
        FolderListView.ItemsSource = workspace.Folders;
    }

    private void OnRemoveFolderClick(object sender, RoutedEventArgs e)
    {
        if (WorkspaceListView.SelectedItem is not Workspace workspace)
        {
            return;
        }
        if (FolderListView.SelectedItem is not WorkspaceFolder folder)
        {
            return;
        }

        workspace.Folders.Remove(folder);
        PersistWorkspaces();
        FolderListView.ItemsSource = workspace.Folders;
    }

    private void OnAddClick(object sender, RoutedEventArgs e)
    {
        var workspace = new Workspace
        {
            Name = "Neuer Workspace",
            RootPath = string.Empty,
            IncludePatterns = new List<string> { "**/*" },
            ExcludePatterns = new List<string> { ".env", "*.secret", "bin/", "obj/", "node_modules/" }
        };
        ViewModel.Workspaces.Add(workspace);
        PersistWorkspaces();
        SelectWorkspace(workspace);
    }

    private void OnRemoveClick(object sender, RoutedEventArgs e)
    {
        if (WorkspaceListView.SelectedItem is Workspace workspace)
        {
            ViewModel.Workspaces.Remove(workspace);
            PersistWorkspaces();
            ClearEditor();
        }
    }

    private void OnSaveClick(object sender, RoutedEventArgs e)
    {
        if (WorkspaceListView.SelectedItem is not Workspace workspace)
        {
            return;
        }

        workspace.Name = NameTextBox.Text;
        workspace.IncludePatterns = ParsePatterns(IncludeTextBox.Text);
        workspace.ExcludePatterns = ParsePatterns(ExcludeTextBox.Text);

        PersistWorkspaces();
        RefreshList();
    }

    private void PersistWorkspaces()
    {
        WorkspaceStore.Save(ViewModel.Workspaces.ToList());
    }

    private void RefreshList()
    {
        _updatingSelection = true;
        var selected = WorkspaceListView.SelectedItem;
        WorkspaceListView.ItemsSource = null;
        WorkspaceListView.ItemsSource = ViewModel.Workspaces;
        WorkspaceListView.SelectedItem = selected;
        _updatingSelection = false;
    }

    private void SelectWorkspace(Workspace workspace)
    {
        _updatingSelection = true;
        WorkspaceListView.SelectedItem = workspace;
        _updatingSelection = false;
        LoadWorkspaceIntoEditor(workspace);
    }

    private static List<string> ParsePatterns(string text)
    {
        return text
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(s => !string.IsNullOrWhiteSpace(s))
            .ToList();
    }
}
