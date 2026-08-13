using System;
using System.Linq;
using Windows.Security.Credentials;

namespace TARNO.UI.Services;

/// <summary>
/// Speichert den Tarno-Server-JWT sicher im Windows-Credential-Vault (wie
/// die bestehenden API-Keys im Windows Credential Manager - siehe Kommentar
/// in ApiKeysPage.xaml) statt in einer Klartextdatei. Getrennt vom
/// ApiKey-Speicher der KI-Provider, eigener Resource-Name.
/// </summary>
public static class MeshCredentialStore
{
    private const string ResourceName = "TarnoMesh.ServerAccessToken";

    public static void SaveToken(string email, string accessToken)
    {
        var vault = new PasswordVault();
        ClearInternal(vault);
        vault.Add(new PasswordCredential(ResourceName, email, accessToken));
    }

    public static (string Email, string AccessToken)? LoadToken()
    {
        var vault = new PasswordVault();
        try
        {
            var credential = vault.FindAllByResource(ResourceName).FirstOrDefault();
            if (credential is null)
            {
                return null;
            }
            credential.RetrievePassword();
            return (credential.UserName, credential.Password);
        }
        catch (Exception)
        {
            // FindAllByResource wirft, wenn nichts gefunden wurde - das ist
            // der Normalfall beim ersten Start, kein echter Fehler.
            return null;
        }
    }

    public static void Clear()
    {
        var vault = new PasswordVault();
        ClearInternal(vault);
    }

    private static void ClearInternal(PasswordVault vault)
    {
        try
        {
            foreach (var credential in vault.FindAllByResource(ResourceName).ToList())
            {
                vault.Remove(credential);
            }
        }
        catch (Exception)
        {
            // Nichts zu loeschen vorhanden - ignorieren.
        }
    }
}
