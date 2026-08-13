using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using System;

namespace TARNO.UI.Dialogs;

/// <summary>
/// Zentrales Einstellungs-Dialog: buendelt die selten gebrauchten
/// Chat-Header-Toggles (Starkes Modell, Kontext-Effizienz, Agent-Pool), die
/// zuvor den Header ueberfuellt und im schmaleren Code-Workspace-Modus
/// abgeschnitten haben. Coding-Agent-Modus und Kamera-Toggle wurden bewusst
/// nicht migriert (Coding-Agent-Modus dupliziert die bereits neben der
/// Chat-Zeile vorhandene Autonomie-Modus-Auswahl, Kamera-Toggle ist
/// ueberfluessig, da Vision automatisch bei Kamera-Anfragen aktiviert wird).
/// </summary>
public sealed partial class ChatSettingsDialog : ContentDialog
{
    public MainViewModel ViewModel { get; }

    public ChatSettingsDialog(MainViewModel viewModel)
    {
        ViewModel = viewModel;
        this.InitializeComponent();
    }

    private void OnCategorySelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        // IsSelected="True" auf dem ersten ListViewItem loest SelectionChanged
        // bereits waehrend InitializeComponent() aus - zu diesem Zeitpunkt sind
        // die spaeter im Baum liegenden Panel-Felder noch nicht verbunden
        // (null), da WinUI Connect() in Dokumentreihenfolge aufruft. Ohne
        // diesen Guard wirft das eine NullReferenceException, die WinUI als
        // undurchsichtige "XAML parsing failed"-XamlParseException nach aussen
        // durchreicht (Connect()-Exceptions verlieren ihre Details). Live
        // bestaetigter Absturz beim ersten Oeffnen: der Guard prüfte bisher nur
        // ModelPanel, obwohl direkt danach auch ContextEfficiencyPanel und
        // AgentPoolPanel unbedingt angefasst werden - beide muessen ebenfalls
        // bereits verbunden sein.
        if (CategoryList.SelectedIndex < 0 || ModelPanel is null || ContextEfficiencyPanel is null || AgentPoolPanel is null)
        {
            return;
        }

        ModelPanel.Visibility = Visibility.Collapsed;
        ContextEfficiencyPanel.Visibility = Visibility.Collapsed;
        AgentPoolPanel.Visibility = Visibility.Collapsed;

        switch (CategoryList.SelectedIndex)
        {
            case 0:
                ModelPanel.Visibility = Visibility.Visible;
                break;
            case 1:
                ContextEfficiencyPanel.Visibility = Visibility.Visible;
                break;
            case 2:
                AgentPoolPanel.Visibility = Visibility.Visible;
                break;
        }
    }

    private async void OnHighTierToggleClick(object sender, RoutedEventArgs e)
    {
        var newState = !ViewModel.HighTierModelEnabled;
        InteractionLogger.Click("ChatSettingsDialog", $"HighTierToggle:{newState}");
        try
        {
            await ViewModel.SetHighTierModelAsync(newState);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Starkes-Modell-Umschaltung fehlgeschlagen: {ex.Message}");
        }
    }

    private async void OnContextEfficiencyToggleClick(object sender, RoutedEventArgs e)
    {
        var newState = !ViewModel.ContextEfficiencyEnabled;
        InteractionLogger.Click("ChatSettingsDialog", $"ContextEfficiencyToggle:{newState}");
        try
        {
            await ViewModel.SetContextEfficiencyAsync(newState);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("CHAT", $"Kontext-Effizienz-Umschaltung fehlgeschlagen: {ex.Message}");
        }
    }

}
