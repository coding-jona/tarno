using System.Threading.Tasks;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Entscheidet, ob eine CodingAction sofort ausgeführt, nur vorgeschlagen oder
/// zur Bestätigung an die UI weitergegeben wird.
/// </summary>
public static class PermissionService
{
    /// <summary>
    /// Wertet eine Aktion basierend auf dem aktuellen ActionMode aus.
    /// Gibt true zurück, wenn die Aktion ausgeführt werden darf (Plan oder Auto),
    /// false wenn sie blockiert oder zur Genehmigung weitergeleitet werden muss.
    /// </summary>
    public static bool CanExecute(CodingAction action, ActionMode mode)
    {
        return mode switch
        {
            ActionMode.Plan => false,
            ActionMode.Manual => !action.RequiresApproval,
            ActionMode.Auto => true,
            _ => false
        };
    }

    /// <summary>
    /// Erzeugt eine Beschreibung, die im Plan-Modus oder Genehmigungs-Dialog angezeigt wird.</summary>
    public static string Describe(CodingAction action)
    {
        return $"{action.Type.ToUpperInvariant()} {action.Target}: {action.Description}";
    }
}
