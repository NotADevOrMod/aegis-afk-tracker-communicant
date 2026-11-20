namespace Aegis.AfkWatch.Core;

/// <summary>Immutable snapshot of what to display.</summary>
/// <param name="Seconds">Idle seconds; for <see cref="Mode.Disconnected"/>, the idle time when it dropped.</param>
public sealed record Indicator(Mode Mode, int Severity, long Seconds, string Server)
{
    public static readonly Indicator Inactive = new(Mode.Inactive, 0, 0, "");

    public string Headline => Mode switch
    {
        Mode.Active => "Active",
        Mode.Warning => Severity switch
        {
            1 => $"Idle · {Format.Clock(Seconds)}",
            2 => $"AFK warning · {Format.Clock(Seconds)}",
            _ => $"Still idle · {Format.Clock(Seconds)}",
        },
        Mode.AfkServer => $"AFK · {Format.Clock(Seconds)}",
        Mode.Disconnected => "Disconnected",
        _ => "",
    };

    public string Detail => Mode switch
    {
        Mode.Active => $"Idle {Format.Clock(Seconds)}",
        Mode.Warning => Severity switch
        {
            1 => "Not in the AFK server",
            2 => "Move, or head to the AFK server",
            _ => "Idle for a while: join the AFK server",
        },
        Mode.AfkServer => Server.Length == 0 ? "In the AFK server" : $"In {Server}",
        Mode.Disconnected => $"Lost while idle · {Format.Clock(Seconds)}",
        _ => "",
    };
}
