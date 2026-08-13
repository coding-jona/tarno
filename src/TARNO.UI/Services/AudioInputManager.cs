using NAudio.CoreAudioApi;
using System;
using System.Diagnostics;

namespace TARNO.UI.Services
{
    public class AudioInputManager
    {
        public WasapiCapture GetBestMicrophone(string configuredDeviceName)
        {
            var enumerator = new MMDeviceEnumerator();
            var captureDevices = enumerator.EnumerateAudioEndPoints(DataFlow.Capture, DeviceState.Active);

            if (captureDevices.Count == 0)
            {
                throw new Exception("Keine Audiogeräte auf diesem PC gefunden!");
            }

            // Falls "default" eingestellt oder das Feld leer ist, nehmen wir das WASAPI-Standardgerät.
            // Einzige Geräte-API für Auflistung, Standardgeräte-Ermittlung UND Aufnahme - kein
            // fragiler Cross-API-Namensabgleich mehr nötig (vormals WaveIn/MME vs. MMDeviceEnumerator/
            // WASAPI, ein dokumentiertes NAudio-Problem: beide APIs listen Geräte in unterschiedlicher
            // Reihenfolge, FriendlyName-Strings können sich zwischen Windows-Versionen unterscheiden).
            if (string.IsNullOrEmpty(configuredDeviceName) || configuredDeviceName.ToLower() == "default" || configuredDeviceName.ToLower() == "standard")
            {
                try
                {
                    var defaultDevice = enumerator.GetDefaultAudioEndpoint(DataFlow.Capture, Role.Console);
                    if (defaultDevice != null && defaultDevice.State == DeviceState.Active)
                    {
                        return CreateWasapiDevice(defaultDevice);
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"WASAPI Standardgerät-Ermittlung fehlgeschlagen: {ex.Message}. Weiche auf Fallback aus.");
                }
            }
            else
            {
                // Direkte WASAPI-Namenssuche gegen FriendlyName - keine MME-31-Zeichen-Kürzung mehr.
                foreach (var device in captureDevices)
                {
                    if (device.FriendlyName.IndexOf(configuredDeviceName, StringComparison.OrdinalIgnoreCase) >= 0 ||
                        configuredDeviceName.IndexOf(device.FriendlyName, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        return CreateWasapiDevice(device);
                    }
                }
            }

            // ULTIMATIVER FALLBACK: Wunschgerät offline oder WASAPI-Default nicht ermittelbar ->
            // Das erste aktive Capture-Gerät nehmen. Der Python-Backend AudioStream macht den
            // eigentlichen Open/Start-Test mit eigener Retry-Logik; die C#-Vorprüfung soll
            // nur sicherstellen, dass grundsätzlich ein Mikrofon existiert.
            foreach (var device in captureDevices)
            {
                try
                {
                    var testDevice = CreateWasapiDevice(device);
                    Debug.WriteLine($"Fallback: Nutze Gerät '{device.FriendlyName}'");
                    return testDevice;
                }
                catch
                {
                    continue; // Gerät lässt sich nicht instanziieren -> Nächstes probieren
                }
            }

            throw new Exception("Es wurden zwar Aufnahmegeräte gefunden, aber keines konnte initialisiert werden!");
        }

        private WasapiCapture CreateWasapiDevice(MMDevice device)
        {
            // Shared-Mode-WASAPI-Capture nutzt zwingend das native Mix-Format des Endpoints
            // (i.d.R. 44.1/48kHz, oft mehrkanalig) - anders als zuvor bei WaveInEvent kann kein
            // beliebiges Format (16kHz Mono) erzwungen werden. Für diesen reinen Preflight-Check
            // (öffnet das Gerät nur kurz zum Start/Stop-Test, verarbeitet keine Samples) ist das
            // unerheblich - die eigentliche 16kHz-Mono-Erfassung läuft vollständig im
            // Python-Backend (AudioStream).
            return new WasapiCapture(device);
        }
    }
}
