using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace TARNO.UI.Models;

/// <summary>
/// Konfiguration des April-Fools-Modus (Aktivierung, Schwellen, Gummiband).
/// Wird aus Assets/AprilFools/april_fools_config.json geladen.
/// </summary>
public class AprilFoolsConfig
{
    [JsonPropertyName("autoEnableOnDate")]
    public string AutoEnableOnDate { get; set; } = "04-01";

    [JsonPropertyName("locale")]
    public string Locale { get; set; } = "de_april_fools";

    [JsonPropertyName("assetBasePath")]
    public string AssetBasePath { get; set; } = "Assets/AprilFools";

    [JsonPropertyName("stageThresholds")]
    public AprilFoolsStageThresholds StageThresholds { get; set; } = new();

    [JsonPropertyName("gummibandMsPerStep")]
    public int GummibandMsPerStep { get; set; } = 16;

    [JsonPropertyName("gummibandStepDip")]
    public double GummibandStepDip { get; set; } = 12.0;

    [JsonPropertyName("keyboardStressMaxMsBetweenEnters")]
    public int KeyboardStressMaxMsBetweenEnters { get; set; } = 600;

    [JsonPropertyName("keyboardStressMinRepeatedEnters")]
    public int KeyboardStressMinRepeatedEnters { get; set; } = 4;
}

public class AprilFoolsStageThresholds
{
    [JsonPropertyName("stage1ProximityDip")]
    public double Stage1ProximityDip { get; set; } = 30.0;

    [JsonPropertyName("stage2AfterEvades")]
    public int Stage2AfterEvades { get; set; } = 3;

    [JsonPropertyName("stage3AfterEvades")]
    public int Stage3AfterEvades { get; set; } = 6;

    [JsonPropertyName("fakeIconCount")]
    public int FakeIconCount { get; set; } = 5;
}
