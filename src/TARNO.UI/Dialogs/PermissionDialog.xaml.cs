using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using System;

namespace TARNO.UI.Dialogs;

/// <summary>
/// Confirmation dialog for a MEDIUM/HIGH-risk command the backend wants to run
/// (CommandEngine/PermissionService, round-tripped over gRPC - see
/// TarnoGrpcBridge.request_permission_sync in the Python backend).
/// HIGH-risk requests additionally require typing the safety phrase the
/// backend sent before the confirm button is enabled; the backend never
/// treats a HIGH-risk approval as persistent regardless of the checkbox.
/// </summary>
public sealed partial class PermissionDialog : ContentDialog
{
    private readonly string _requiredSafetyPhrase;

    public bool Persistent => PersistentCheckBox.IsChecked == true;

    public PermissionDialog(string permission, string target, string riskLevel, string safetyPhrase)
    {
        this.InitializeComponent();
        _requiredSafetyPhrase = safetyPhrase ?? string.Empty;

        TargetText.Text = target;
        ConfigureRiskBadge(riskLevel);

        bool isHighRisk = !string.IsNullOrEmpty(_requiredSafetyPhrase);
        if (isHighRisk)
        {
            SafetyPhrasePanel.Visibility = Visibility.Visible;
            SafetyPhraseHint.Text = $"Zum Bestätigen exakt eingeben: \"{_requiredSafetyPhrase}\"";
            PersistentCheckBox.Visibility = Visibility.Collapsed; // backend never persists HIGH-risk approvals
            IsPrimaryButtonEnabled = false;
        }
    }

    private static readonly SolidColorBrush WhiteBrush = new(Windows.UI.Color.FromArgb(255, 255, 255, 255));

    private void ConfigureRiskBadge(string riskLevel)
    {
        var (bg, fg, label) = riskLevel switch
        {
            "high" => ("ErrorSubtleBrush", (SolidColorBrush)Application.Current.Resources["ErrorBrush"], "HOHES RISIKO"),
            "medium" => ("WarningBrush", WhiteBrush, "MITTLERES RISIKO"),
            _ => ("SuccessBrush", WhiteBrush, "NIEDRIGES RISIKO"),
        };
        RiskBadge.Background = (SolidColorBrush)Application.Current.Resources[bg];
        RiskBadgeText.Foreground = fg;
        RiskBadgeText.Text = label;
    }

    private void OnSafetyPhraseChanged(object sender, TextChangedEventArgs e)
    {
        IsPrimaryButtonEnabled = string.Equals(SafetyPhraseBox.Text, _requiredSafetyPhrase, StringComparison.Ordinal);
    }
}
