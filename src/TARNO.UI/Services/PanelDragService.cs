using System;
using System.Text.Json;
using System.Threading.Tasks;
using Windows.ApplicationModel.DataTransfer;
using Microsoft.UI.Xaml;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Zentrale Vermittlungsstelle für das Verschieben von Panels per Drag-and-Drop.
/// Phase 12 liefert das Grundgerüst: Payload-Erzeugung beim Start, Akzeptieren
/// beim Drop und ein Event, das spätere Phasen zum echten Umhängen nutzen.
/// </summary>
public static class PanelDragService
{
    public const string PayloadFormatName = "TARNO.PanelPayload";

    /// <summary>Wird gefeuert, sobald ein Panel irgendwo fallengelassen wurde.</summary>
    public static event EventHandler<PanelDropRequest>? PanelDropRequested;

    public static void SetDragPayload(DataPackage package, IDraggablePanel panel)
    {
        var payload = new PanelDragPayload
        {
            PanelId = panel.PanelId,
            SourceWindowIndex = panel.WindowIndex,
            Title = panel.Title,
        };
        string json = JsonSerializer.Serialize(payload);

        package.SetText(json);
        package.RequestedOperation = DataPackageOperation.Move;
    }

    public static async Task<PanelDragPayload?> TryParsePayloadAsync(DataPackageView dataView)
    {
        try
        {
            if (!dataView.Contains(StandardDataFormats.Text))
            {
                return null;
            }
            string json = await dataView.GetTextAsync();
            if (string.IsNullOrWhiteSpace(json))
            {
                return null;
            }
            return JsonSerializer.Deserialize<PanelDragPayload>(json);
        }
        catch
        {
            return null;
        }
    }

    public static void AcceptDrop(DragEventArgs e)
    {
        if (e.DataView.Contains(StandardDataFormats.Text))
        {
            e.AcceptedOperation = DataPackageOperation.Move;
            e.DragUIOverride.Caption = "Hier ablegen";
            e.DragUIOverride.IsCaptionVisible = true;
            e.DragUIOverride.IsGlyphVisible = true;
            e.DragUIOverride.IsContentVisible = true;
        }
    }

    public static async void HandleDropAsync(int targetWindowIndex, DragEventArgs e)
    {
        var payload = await TryParsePayloadAsync(e.DataView);
        if (payload is null)
        {
            return;
        }

        e.Handled = true;
        PanelDropRequested?.Invoke(null, new PanelDropRequest(payload, targetWindowIndex, e));
    }

    /// <summary>Payload, der im Drag-Paket serialisiert transportiert wird.</summary>
    public class PanelDragPayload
    {
        public string PanelId { get; set; } = string.Empty;
        public int SourceWindowIndex { get; set; }
        public string Title { get; set; } = string.Empty;
    }

    public class PanelDropRequest
    {
        public PanelDragPayload Payload { get; }
        public int TargetWindowIndex { get; }
        public DragEventArgs Args { get; }

        public PanelDropRequest(PanelDragPayload payload, int targetWindowIndex, DragEventArgs args)
        {
            Payload = payload;
            TargetWindowIndex = targetWindowIndex;
            Args = args;
        }
    }
}
