using System.Text.Json;

namespace Aegis.AfkWatch.Core;

/// <summary>User-editable settings, stored as JSON under %APPDATA%.</summary>
public sealed class Settings
{
    /// <summary>A server counts as BendersMC if its address contains any of these (case-insensitive).</summary>
    public List<string> ServerHostFragments { get; set; } = ["benders"];

    /// <summary>Names (from the "Sending you to ..." line) that count as the AFK server.</summary>
    public List<string> AfkServerNames { get; set; } = ["afk"];

    /// <summary>Idle seconds at which each warning level begins. The first entry is when warnings start.</summary>
    public List<int> WarningStepsSeconds { get; set; } = [120, 180, 300];

    /// <summary>Idle seconds before the AFK server turns the indicator blue.</summary>
    public int AfkServerAfterSeconds { get; set; } = 15;

    /// <summary>How long "Disconnected" stays up after a drop.</summary>
    public int DisconnectLingerSeconds { get; set; } = 600;

    /// <summary>
    /// How old the mod's last report may be before the game counts as gone. The mod refreshes it every
    /// second, so a few seconds of silence means it closed or crashed.
    /// </summary>
    public int BridgeStaleSeconds { get; set; } = 5;

    public bool WindowShowWhenActive { get; set; } = true;
    public bool WindowAlwaysOnTop { get; set; } = true;
    public double WindowOpacity { get; set; } = 0.92;
    public int WindowX { get; set; } = -1;
    public int WindowY { get; set; } = -1;
    public bool BeepOnWarning { get; set; } = false;

    private static readonly JsonSerializerOptions Json = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
    };

    public static string DefaultPath() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AegisAfkWatch", "settings.json");

    [System.Text.Json.Serialization.JsonIgnore] public string? LoadProblem { get; private set; }
    [System.Text.Json.Serialization.JsonIgnore] private string? StoredAt { get; set; }

    public static Settings Load(string path)
    {
        var s = new Settings();
        if (System.IO.File.Exists(path))
        {
            try
            {
                s = JsonSerializer.Deserialize<Settings>(System.IO.File.ReadAllText(path), Json) ?? new Settings();
            }
            catch (Exception e) when (e is IOException or JsonException)
            {
                // Leave the broken file untouched so it can be fixed by hand.
                s = new Settings { LoadProblem = $"Could not read settings, using defaults: {e.Message}", StoredAt = path };
                s.Normalize();
                return s;
            }
        }
        s.StoredAt = path;
        s.Normalize();
        s.Save();
        return s;
    }

    public void Save()
    {
        if (StoredAt is null) return;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(StoredAt)!);
            System.IO.File.WriteAllText(StoredAt, JsonSerializer.Serialize(this, Json));
        }
        catch (IOException)
        {
            // A settings file is a convenience; failing to write it must never affect anything else.
        }
    }

    [System.Text.Json.Serialization.JsonIgnore] public string FilePath => StoredAt ?? DefaultPath();

    public bool MatchesHost(string host) =>
        ServerHostFragments.Any(f => f.Length > 0 && host.Contains(f, StringComparison.OrdinalIgnoreCase));

    public bool IsAfkServer(string name) =>
        AfkServerNames.Any(n => string.Equals(n.Trim(), name.Trim(), StringComparison.OrdinalIgnoreCase));

    private void Normalize()
    {
        ServerHostFragments ??= ["benders"];
        AfkServerNames ??= ["afk"];
        WarningStepsSeconds = (WarningStepsSeconds ?? []).Where(v => v >= 10).Distinct().Order().ToList();
        if (WarningStepsSeconds.Count == 0) WarningStepsSeconds = [120, 180, 300];
        AfkServerAfterSeconds = Math.Max(5, AfkServerAfterSeconds);
        DisconnectLingerSeconds = Math.Max(30, DisconnectLingerSeconds);
        BridgeStaleSeconds = Math.Max(3, BridgeStaleSeconds);
        WindowOpacity = Math.Clamp(WindowOpacity, 0.3, 1.0);
    }
}
