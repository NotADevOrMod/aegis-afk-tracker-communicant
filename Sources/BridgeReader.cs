using System.Text.Json;

namespace Aegis.AfkWatch.Sources;

/// <summary>One reading published by the AEGIS AFK Bridge mod (protocol version 1).</summary>
internal sealed record BridgeReport(
    int V,
    long UpdatedAtMs,
    bool Connected,
    string Host,
    string Server,
    long IdleMs,
    long Session);

/// <summary>Reads %APPDATA%\AegisAfkWatch\bridge.json. Read-only; never locks the file against the mod.</summary>
internal sealed class BridgeReader
{
    private static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true };

    public static string DefaultPath() => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "AegisAfkWatch", "bridge.json");

    private readonly string _path = DefaultPath();

    /// <summary>The latest report, or null if the file is missing, mid-write, or not ours.</summary>
    public BridgeReport? Read()
    {
        try
        {
            // FileShare.Delete lets the mod replace the file while we have it open.
            using var stream = new FileStream(_path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            BridgeReport? report = JsonSerializer.Deserialize<BridgeReport>(stream, Json);
            return report is { V: 1 } ? report : null;
        }
        catch (Exception e) when (e is IOException or JsonException or UnauthorizedAccessException)
        {
            return null;
        }
    }
}
