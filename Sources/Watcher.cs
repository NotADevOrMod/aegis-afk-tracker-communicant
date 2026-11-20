using Aegis.AfkWatch.Core;

namespace Aegis.AfkWatch.Sources;

/// <summary>
/// Polls the bridge file twice a second and translates what changed into <see cref="Session"/> events.
/// A report that stops refreshing means the game closed or crashed.
/// </summary>
public sealed class Watcher : IDisposable
{
    private const int PollMs = 500;

    private enum Link { Unknown, Fresh, Stale }

    private readonly Session _session;
    private readonly Settings _settings;
    private readonly BridgeReader _reader = new();
    private readonly object _gate = new();
    private System.Threading.Timer? _timer;

    private Link _link = Link.Unknown;
    private bool _wasConnected;
    private long _lastSession = -1;
    private string _lastServer = "";

    public Watcher(Session session, Settings settings)
    {
        _session = session;
        _settings = settings;
    }

    public void Start() => _timer = new System.Threading.Timer(_ => Poll(), null, 0, PollMs);

    private void Poll()
    {
        if (!Monitor.TryEnter(_gate)) return; // previous poll still running
        try
        {
            long nowTick = Environment.TickCount64;
            long nowEpoch = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();

            BridgeReport? report = _reader.Read();
            bool fresh = report is not null
                && nowEpoch - report.UpdatedAtMs <= _settings.BridgeStaleSeconds * 1000L;

            if (!fresh || report is null)
            {
                HandleStale(nowTick);
                return;
            }

            _link = Link.Fresh;
            HandleReport(report, nowTick, nowEpoch);
        }
        catch (Exception)
        {
            // A monitoring hiccup must never take the app down; the next poll starts clean.
        }
        finally
        {
            Monitor.Exit(_gate);
        }
    }

    private void HandleStale(long nowTick)
    {
        if (_link == Link.Stale) return; // already dealt with this gap
        _link = Link.Stale;

        if (_wasConnected)
            _session.OnDisconnect(nowTick); // heartbeat stopped mid-connection: a crash, kill or lost game
        else
            _session.OnGameClosed();        // nothing was happening; forget quietly
        _wasConnected = false;
        _lastServer = "";
    }

    private void HandleReport(BridgeReport r, long nowTick, long nowEpoch)
    {
        if (!r.Connected)
        {
            if (_wasConnected) _session.OnDisconnect(nowTick);
            _wasConnected = false;
            _lastServer = "";
            return;
        }

        if (!_wasConnected || r.Session != _lastSession)
        {
            _session.OnConnect(r.Host, nowTick);
            _lastSession = r.Session;
            _lastServer = "";
        }

        if (r.Server.Length > 0 && r.Server != _lastServer)
        {
            _session.OnServerSwitch(r.Server, nowTick);
            _lastServer = r.Server;
        }

        // The report is already a little old by the time we read it; account for that so idle time is exact.
        long reportAgeMs = Math.Max(0, nowEpoch - r.UpdatedAtMs);
        _session.SyncActivity(nowTick - reportAgeMs - r.IdleMs);

        _wasConnected = true;
    }

    public void Dispose() => _timer?.Dispose();
}
