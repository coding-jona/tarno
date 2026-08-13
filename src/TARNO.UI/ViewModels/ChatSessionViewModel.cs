using CommunityToolkit.Mvvm.ComponentModel;
using System;

namespace TARNO.UI.ViewModels;

public partial class ChatSessionViewModel : ObservableObject
{
    [ObservableProperty]
    private string _id = string.Empty;

    [ObservableProperty]
    private string _title = "Neuer Chat";

    [ObservableProperty]
    private DateTimeOffset _updatedAt = DateTimeOffset.Now;

    [ObservableProperty]
    private int _messageCount;

    [ObservableProperty]
    private string? _workspaceId;

    [ObservableProperty]
    private string _sidebarMode = "Chat";

    [ObservableProperty]
    private string? _provider;

    [ObservableProperty]
    private string? _model;

    public string Subtitle => $"{UpdatedAt:dd.MM. HH:mm} · {MessageCount} Nachrichten";

    public string ProviderModelLabel
    {
        get
        {
            if (string.IsNullOrWhiteSpace(Provider))
            {
                return string.Empty;
            }
            return string.IsNullOrWhiteSpace(Model) ? Provider : $"{Provider} › {Model}";
        }
    }
}
