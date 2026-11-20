namespace Aegis.AfkWatch.Core;

/// <summary>Accent colours as 0xRRGGBB, kept free of any UI library.</summary>
public static class Palette
{
    public const int Blue = 0x5AA9E6;     // calm: AFK in the AFK server
    public const int Orange = 0xE8833A;   // first warning
    public const int Red = 0xE5484D;      // second warning
    public const int DeepRed = 0xC62A2F;  // prolonged idle
    public const int Green = 0x6BCB8B;    // active
    public const int Slate = 0x9AA3B2;    // connection lost

    public static int Accent(Indicator v) => v.Mode switch
    {
        Mode.AfkServer => Blue,
        Mode.Warning => v.Severity switch { 1 => Orange, 2 => Red, _ => DeepRed },
        Mode.Active => Green,
        Mode.Disconnected => Slate,
        _ => 0,
    };

    /// <summary>0.7..1.0 pulse for the louder warning levels, steady 1.0 otherwise.</summary>
    public static double Pulse(Indicator v, long nowMs) =>
        v.Mode == Mode.Warning && v.Severity >= 2 ? 0.85 + 0.15 * Math.Sin(nowMs / 300.0) : 1.0;
}
