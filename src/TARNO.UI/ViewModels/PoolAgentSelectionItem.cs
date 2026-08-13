using CommunityToolkit.Mvvm.ComponentModel;

namespace TARNO.UI.ViewModels;

/// <summary>Ein auswaehlbarer Eintrag im Agent-Pool-Auswahldialog: ein
/// Provider/Modell-Paar aus dem bestehenden ModelCatalog, plus ob es fuer
/// den aktuellen Pool-Lauf ausgewaehlt und/oder als Lead markiert ist.</summary>
public sealed partial class PoolAgentSelectionItem : ObservableObject
{
    public string Provider { get; init; } = string.Empty;
    public string Model { get; init; } = string.Empty;
    public string Label { get; init; } = string.Empty;

    [ObservableProperty]
    private bool _isSelected;

    [ObservableProperty]
    private bool _isLead;

    public string Slug => $"{Provider}:{Model}";
}
