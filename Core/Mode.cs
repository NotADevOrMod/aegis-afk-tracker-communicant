namespace Aegis.AfkWatch.Core;

/// <summary>What the indicator should currently communicate.</summary>
public enum Mode
{
    /// <summary>Not playing a tracked server; nothing to show.</summary>
    Inactive,
    /// <summary>On a tracked server and recently active.</summary>
    Active,
    /// <summary>Idle outside the AFK server. Escalates through <see cref="Indicator.Severity"/>.</summary>
    Warning,
    /// <summary>Idle inside the AFK server. Expected, so shown calmly.</summary>
    AfkServer,
    /// <summary>The connection or the game went away while the player was idle.</summary>
    Disconnected,
}
