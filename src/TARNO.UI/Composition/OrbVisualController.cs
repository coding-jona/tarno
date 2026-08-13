using System;
using System.Numerics;
using System.Threading.Tasks;
using Microsoft.UI.Composition;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Animation;
using Windows.UI;
using TARNO.UI.Services;

namespace TARNO.UI.Composition;

/// <summary>
/// Treibt den Voice-Orb (Glow/Rim/Core) rein über XAML-Composition-Visuals an
/// - kein WebView2, keine gehostete Sub-Fläche, daher auch keine Möglichkeit
/// für die WinUI-3-WebView2-Transparenzlücke (microsoft/microsoft-ui-xaml#6527),
/// die im Vorlauf dieser Änderung mehrfach pixelverifiziert an keiner der vier
/// versuchten Farb-Matching-Strategien (Property, XAML, CSS, ThemeDictionary)
/// vorbeikam. Folgt demselben Muster wie SpecularHighlightBehavior
/// (SpriteVisual + RadialGradientBrush über ElementCompositionPreview) statt
/// Win2D/Pixel-Shadern.
/// </summary>
public sealed class OrbVisualController
{
    private const float ErrorHoldSeconds = 1.8f;

    // Maximaler zusaetzlicher Skalierungs-Ausschlag der Ganzkoerper-Resonanz
    // bei voller (geformter) Amplitude 1.0 - 0.55 heisst der Orb waechst an
    // lauten Stellen bis auf 155% seiner Ruhegroesse, damit der Ausschlag
    // wirklich sichtbar "einschlaegt".
    private const float ResonanceAmplitude = 0.55f;
    private const float ResonanceRestScale = 1.0f;

    // Envelope-Follower (Attack/Release), damit der Orb ploppend auf
    // Wortanfaenge reagiert. 5ms Attack = hartes Hochschnellen, 35ms Release =
    // schnelles Absacken zwischen Silben, aber kein roboterhaftes Zucken.
    private const float AttackTimeMs = 5f;
    private const float ReleaseTimeMs = 35f;

    // Nichtlineares Response-Mapping (>1 staucht leise Stellen relativ
    // staerker als laute) - leise Passagen bleiben klein, laute Stellen
    // schlagen deutlich sichtbar ein.
    private const float ResponseCurveExponent = 2.0f;

    private readonly Compositor _compositor;
    private readonly SpriteVisual _glowVisual;
    private readonly CompositionRadialGradientBrush _glowBrush;
    private readonly SpriteVisual _coreVisual;
    private readonly CompositionRadialGradientBrush _coreBrush;
    private readonly Visual _rimVisual;
    private readonly ScaleTransform? _orbScaleTransform;
    private readonly DispatcherTimer _resonanceTimer;
    private float[]? _resonanceEnvelope;
    private double _resonanceDuration;
    private DateTime _resonanceStartedAt;
    private float _smoothedLevel;
    private int _resonanceTickCount;

    private string _currentState = "idle";
    private bool _errorLockActive;
    private bool _resonanceActive;

    public OrbVisualController(FrameworkElement rootElement, FrameworkElement glowHost, FrameworkElement coreHost, FrameworkElement rimElement)
    {
        _rimVisual = ElementCompositionPreview.GetElementVisual(rimElement);
        _compositor = _rimVisual.Compositor;

        // Ganzkoerper-Sprech-Resonanz treibt DIESEN XAML-RenderTransform (siehe
        // OrbRoot in ChatPage.xaml/VoicePage.xaml), NICHT Glow/Core direkt -
        // Glow und Core haben ihre EIGENEN, unabhaengigen Animationen (Farbe,
        // Opacity, Atmen) und duerfen dafuer nicht angefasst werden. Ein
        // RenderTransform auf dem Wurzel-Grid skaliert IMMER den kompletten
        // Sub-Baum (Glow+Ring+Glas+Core) als einen starren Koerper, unabhaengig
        // von allem, was innerhalb dessen weiter eigenstaendig animiert -
        // genau das gewuenschte "Resonanzkugel wie in Musikvideos"-Verhalten.
        _orbScaleTransform = rootElement.RenderTransform as ScaleTransform;
        if (_orbScaleTransform is null)
        {
            _orbScaleTransform = new ScaleTransform { ScaleX = 1.0, ScaleY = 1.0 };
            rootElement.RenderTransform = _orbScaleTransform;
            InteractionLogger.Info("ORB", "_orbScaleTransform war null/falscher Typ — neuer ScaleTransform erstellt und zugewiesen.");
        }

        // Treibt die Resonanz per direkter Property-Zuweisung auf jedem Tick,
        // NICHT ueber ein Storyboard/DoubleAnimationUsingKeyFrames - live
        // bestaetigt, dass ein Storyboard mit vielen dicht gepackten
        // Keyframes (mehrere hundert bei 90ms-Audioabtastung) auf diesem
        // Transform aus unklarem Grund nicht sichtbar rendert, waehrend eine
        // direkte Zuweisung UND ein einfacher 2-Keyframe-Storyboard-Test
        // beide zuverlaessig sichtbar waren. Ein Timer mit direkter
        // Zuweisung nutzt ausschliesslich den bestaetigt funktionierenden
        // Mechanismus.
        _resonanceTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(16) };
        _resonanceTimer.Tick += OnResonanceTick;

        // Glow: weicher, radialer Schein hinter dem Glas. Die Groesse des
        // Hosts IST die harte Obergrenze - anders als beim CSS-Ansatz kann
        // hier kein Wert "vergessen" werden und ueber den Rand hinausbluten,
        // der SpriteVisual kann seinen eigenen Host nicht ueberschreiten.
        _glowBrush = _compositor.CreateRadialGradientBrush();
        _glowBrush.MappingMode = CompositionMappingMode.Relative;
        _glowBrush.EllipseCenter = new Vector2(0.5f, 0.5f);
        _glowBrush.EllipseRadius = new Vector2(0.5f, 0.5f);
        _glowBrush.ColorStops.Insert(0, _compositor.CreateColorGradientStop(0.0f, Color.FromArgb(0x55, 0x67, 0xC9, 0xEC)));
        _glowBrush.ColorStops.Insert(1, _compositor.CreateColorGradientStop(1.0f, Color.FromArgb(0x00, 0x67, 0xC9, 0xEC)));
        _glowVisual = _compositor.CreateSpriteVisual();
        _glowVisual.Brush = _glowBrush;
        _glowVisual.Size = new Vector2((float)glowHost.ActualWidth, (float)glowHost.ActualHeight);
        _glowVisual.Opacity = 0.35f;
        _glowVisual.CenterPoint = new Vector3(_glowVisual.Size.X / 2, _glowVisual.Size.Y / 2, 0);
        ElementCompositionPreview.SetElementChildVisual(glowHost, _glowVisual);
        glowHost.SizeChanged += (_, a) =>
        {
            _glowVisual.Size = new Vector2((float)a.NewSize.Width, (float)a.NewSize.Height);
            _glowVisual.CenterPoint = new Vector3(_glowVisual.Size.X / 2, _glowVisual.Size.Y / 2, 0);
        };

        // Core: der eigentliche "Kern"-Schein, zustandsabhaengig eingefaerbt.
        _coreBrush = _compositor.CreateRadialGradientBrush();
        _coreBrush.MappingMode = CompositionMappingMode.Relative;
        _coreBrush.EllipseCenter = new Vector2(0.5f, 0.42f);
        _coreBrush.EllipseRadius = new Vector2(0.5f, 0.5f);
        _coreBrush.ColorStops.Insert(0, _compositor.CreateColorGradientStop(0.0f, Color.FromArgb(0xFF, 0x67, 0xC9, 0xEC)));
        _coreBrush.ColorStops.Insert(1, _compositor.CreateColorGradientStop(1.0f, Color.FromArgb(0x00, 0x67, 0xC9, 0xEC)));
        _coreVisual = _compositor.CreateSpriteVisual();
        _coreVisual.Brush = _coreBrush;
        _coreVisual.Size = new Vector2((float)coreHost.ActualWidth, (float)coreHost.ActualHeight);
        _coreVisual.Opacity = 0.4f;
        _coreVisual.CenterPoint = new Vector3(_coreVisual.Size.X / 2, _coreVisual.Size.Y / 2, 0);
        ElementCompositionPreview.SetElementChildVisual(coreHost, _coreVisual);
        coreHost.SizeChanged += (_, a) =>
        {
            _coreVisual.Size = new Vector2((float)a.NewSize.Width, (float)a.NewSize.Height);
            _coreVisual.CenterPoint = new Vector3(_coreVisual.Size.X / 2, _coreVisual.Size.Y / 2, 0);
        };

        _rimVisual.CenterPoint = new Vector3((float)rimElement.ActualWidth / 2, (float)rimElement.ActualHeight / 2, 0);
        rimElement.SizeChanged += (_, a) =>
            _rimVisual.CenterPoint = new Vector3((float)a.NewSize.Width / 2, (float)a.NewSize.Height / 2, 0);

        StartAmbientAnimations();
    }

    private void StartAmbientAnimations()
    {
        // Core: sanftes Atmen, entspricht dem frueheren CSS "breathe 4s
        // ease-in-out infinite".
        var ease = _compositor.CreateCubicBezierEasingFunction(new Vector2(0.42f, 0f), new Vector2(0.58f, 1f));
        var scale = _compositor.CreateVector3KeyFrameAnimation();
        scale.InsertKeyFrame(0f, new Vector3(0.94f, 0.94f, 1f), ease);
        scale.InsertKeyFrame(0.5f, new Vector3(1.04f, 1.04f, 1f), ease);
        scale.InsertKeyFrame(1f, new Vector3(0.94f, 0.94f, 1f), ease);
        scale.Duration = TimeSpan.FromSeconds(4);
        scale.IterationBehavior = AnimationIterationBehavior.Forever;
        _coreVisual.StartAnimation(nameof(Visual.Scale), scale);

        StartRimRotation(6.0);
    }

    private void StartRimRotation(double periodSeconds)
    {
        var rotation = _compositor.CreateScalarKeyFrameAnimation();
        rotation.InsertKeyFrame(0f, 0f);
        rotation.InsertKeyFrame(1f, 360f);
        rotation.Duration = TimeSpan.FromSeconds(periodSeconds);
        rotation.IterationBehavior = AnimationIterationBehavior.Forever;
        _rimVisual.StartAnimation(nameof(Visual.RotationAngleInDegrees), rotation);
    }

    public void SetState(string state)
    {
        _currentState = state;
        if (_errorLockActive)
        {
            return;
        }

        if (state == "error")
        {
            _errorLockActive = true;
            ApplyState("error");
            _ = HoldErrorThenRevertAsync();
        }
        else
        {
            ApplyState(state);
        }
    }

    private async Task HoldErrorThenRevertAsync()
    {
        await Task.Delay(TimeSpan.FromSeconds(ErrorHoldSeconds));
        _errorLockActive = false;
        ApplyState(_currentState);
    }

    private void ApplyState(string state)
    {
        var (color, coreOpacity, glowOpacity, rimSpeedSeconds) = state switch
        {
            "listening" => (Color.FromArgb(0xFF, 0x14, 0xB8, 0xF0), 0.75f, 0.55f, 6.0),
            // Eigene Bernstein/Gold-Farbe fürs Denken - vorher wurde "listening"
            // wiederverwendet, was sich live als zu ähnlich zu Idle/Speaking
            // (beides Cyan/Türkis-Töne) herausstellte.
            "thinking" => (Color.FromArgb(0xFF, 0xF5, 0xB3, 0x42), 0.80f, 0.60f, 4.5),
            "processing" => (Color.FromArgb(0xFF, 0x9B, 0x7B, 0xFF), 0.80f, 0.60f, 2.2),
            "speaking" => (Color.FromArgb(0xFF, 0x10, 0xCF, 0xC2), 0.85f, 0.65f, 3.5),
            "error" => (Color.FromArgb(0xFF, 0xFF, 0x52, 0x52), 0.70f, 0.70f, 6.0),
            _ => (Color.FromArgb(0xFF, 0x67, 0xC9, 0xEC), 0.40f, 0.35f, 6.0),
        };

        AnimateColor(_coreBrush.ColorStops[0], color, TimeSpan.FromMilliseconds(700));
        AnimateColor(_glowBrush.ColorStops[0], Color.FromArgb(0x55, color.R, color.G, color.B), TimeSpan.FromMilliseconds(700));
        AnimateScalar(_coreVisual, nameof(Visual.Opacity), coreOpacity, TimeSpan.FromMilliseconds(300));
        AnimateScalar(_glowVisual, nameof(Visual.Opacity), glowOpacity, TimeSpan.FromMilliseconds(700));
        StartRimRotation(rimSpeedSeconds);

        // Verlaesst der Orb den "speaking"-Zustand, MUSS die Resonanz
        // sofort gestoppt werden - der self-listener-Sicherheitsnetz-Pfad
        // (siehe StopSpeechResonance): der reale VOICE_IDLE-Broadcast kann
        // vor Ablauf der vorab berechneten Envelope-Dauer eintreffen (z.B.
        // wenn pygames get_busy()-Sicherheits-Timeout vorzeitig abbricht),
        // und der Orb darf dann nicht in einer aufgeblasenen Groesse haengen
        // bleiben, sondern muss sofort zur Ruhegroesse zurueckkehren.
        if (state != "speaking")
        {
            StopSpeechResonance();
        }
    }

    /// <summary>Spielt die Ganzkoerper-"Lautsprecher/Bass"-Resonanz: skaliert
    /// den XAML-RenderTransform des gesamten OrbRoot-Grids (Glow+Ring+Glas+
    /// Core als EIN starrer Koerper) direkt aus der echten Amplituden-
    /// Huellkurve der gerade startenden TTS-Wiedergabe - keine prozedurale/
    /// rhythmische Fuellanimation, und Glow/Core werden dabei NICHT selbst
    /// angefasst (ihre eigenen Farb-/Opacity-/Atem-Animationen laufen
    /// unveraendert weiter). `durationSeconds` ist die ECHTE Abspieldauer,
    /// damit die Animation exakt so lange laeuft wie TARNO tatsaechlich
    /// spricht (von echtem Sprechbeginn bis -ende).</summary>
    public void PlaySpeechResonance(float[] envelope, double durationSeconds)
    {
        if (_orbScaleTransform is null)
        {
            InteractionLogger.Error("ORB", $"PlaySpeechResonance abgebrochen: _orbScaleTransform ist null (envelopeLength={envelope?.Length}, duration={durationSeconds})");
            return;
        }
        if (envelope is null || envelope.Length == 0 || durationSeconds <= 0)
        {
            InteractionLogger.Error("ORB", $"PlaySpeechResonance abgebrochen: ungueltige Daten (envelopeNull={envelope is null}, length={envelope?.Length}, duration={durationSeconds})");
            return;
        }

        _resonanceEnvelope = envelope;
        _resonanceDuration = durationSeconds;
        _resonanceStartedAt = DateTime.UtcNow;
        _resonanceActive = true;
        _smoothedLevel = 0f;
        _resonanceTickCount = 0;
        _resonanceTimer.Start();
        InteractionLogger.Info("ORB", $"PlaySpeechResonance gestartet: envelopeLength={envelope.Length}, duration={durationSeconds:F3}s, scaleTransformNull={_orbScaleTransform is null}");
    }

    private void OnResonanceTick(object? sender, object e)
    {
        if (_orbScaleTransform is null || _resonanceEnvelope is null || _resonanceEnvelope.Length == 0)
        {
            return;
        }

        double elapsed = (DateTime.UtcNow - _resonanceStartedAt).TotalSeconds;
        if (elapsed >= _resonanceDuration)
        {
            StopSpeechResonance();
            return;
        }

        // Linear zwischen den zwei naechsten Envelope-Samples interpolieren -
        // bei 12ms-Hop und 16ms-Tick sonst sichtbare Stufen statt fliessender
        // Bewegung.
        double progress = elapsed / _resonanceDuration * (_resonanceEnvelope.Length - 1);
        int index0 = Math.Clamp((int)progress, 0, _resonanceEnvelope.Length - 1);
        int index1 = Math.Clamp(index0 + 1, 0, _resonanceEnvelope.Length - 1);
        float frac = (float)(progress - index0);
        float raw = _resonanceEnvelope[index0] + (_resonanceEnvelope[index1] - _resonanceEnvelope[index0]) * frac;

        // Ein-Pol-Attack/Release-Envelope-Follower: schnelles Hochschnellen
        // auf Attacks, kontrolliertes (aber immer noch schnelles) Abklingen -
        // nicht der Rohwert direkt, sonst wirkt jede Aenderung "geschnitten"
        // statt wie ein plausibler Lautsprecher-Ausschlag.
        float tickMs = (float)_resonanceTimer.Interval.TotalMilliseconds;
        float timeConstantMs = raw > _smoothedLevel ? AttackTimeMs : ReleaseTimeMs;
        float coeff = 1f - MathF.Exp(-tickMs / timeConstantMs);
        _smoothedLevel += (raw - _smoothedLevel) * coeff;

        float shaped = MathF.Pow(Math.Clamp(_smoothedLevel, 0f, 1f), ResponseCurveExponent);
        double s = ResonanceRestScale + shaped * ResonanceAmplitude;
        _orbScaleTransform.ScaleX = s;
        _orbScaleTransform.ScaleY = s;

        _resonanceTickCount++;
        if (_resonanceTickCount == 1)
        {
            InteractionLogger.Info("ORB", $"ResonanceTick erster Tick: elapsed={elapsed:F3}, raw={raw:F3}, smoothed={_smoothedLevel:F3}, scale={s:F3}");
        }
    }

    /// <summary>Self-listener-Sicherheitsnetz: wird aufgerufen sobald der
    /// Orb den "speaking"-Zustand verlaesst (echter VOICE_IDLE/andere-Stage-
    /// Broadcast), unabhaengig davon ob die vorab berechnete Envelope-Dauer
    /// bereits abgelaufen ist - verhindert, dass der Orb sichtbar "haengen"
    /// bleibt, falls die echte Wiedergabe frueher endet als vorausberechnet.</summary>
    public void StopSpeechResonance()
    {
        if (!_resonanceActive)
        {
            return;
        }
        InteractionLogger.Info("ORB", $"StopSpeechResonance nach {_resonanceTickCount} Ticks");
        _resonanceActive = false;
        _resonanceTimer.Stop();
        _resonanceEnvelope = null;

        if (_orbScaleTransform is null)
        {
            return;
        }
        var back = new Storyboard();
        var backX = new DoubleAnimation { To = ResonanceRestScale, Duration = TimeSpan.FromMilliseconds(250) };
        var backY = new DoubleAnimation { To = ResonanceRestScale, Duration = TimeSpan.FromMilliseconds(250) };
        Storyboard.SetTarget(backX, _orbScaleTransform);
        Storyboard.SetTargetProperty(backX, nameof(ScaleTransform.ScaleX));
        Storyboard.SetTarget(backY, _orbScaleTransform);
        Storyboard.SetTargetProperty(backY, nameof(ScaleTransform.ScaleY));
        back.Children.Add(backX);
        back.Children.Add(backY);
        back.Begin();
    }

    private void AnimateColor(CompositionColorGradientStop stop, Color target, TimeSpan duration)
    {
        var anim = _compositor.CreateColorKeyFrameAnimation();
        anim.InsertKeyFrame(1f, target);
        anim.Duration = duration;
        stop.StartAnimation(nameof(CompositionColorGradientStop.Color), anim);
    }

    private void AnimateScalar(Visual visual, string property, float target, TimeSpan duration)
    {
        var anim = _compositor.CreateScalarKeyFrameAnimation();
        anim.InsertKeyFrame(1f, target);
        anim.Duration = duration;
        visual.StartAnimation(property, anim);
    }
}
