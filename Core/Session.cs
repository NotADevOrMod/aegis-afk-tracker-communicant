namespace Aegis.AfkWatch.Core;

/// <summary>
/// Pure state machine: knows nothing about Windows, files or the game. Fed with events, it answers
/// "what should the indicator show right now?". Times are monotonic milliseconds (Environment.TickCount64).
/// </summary>
public sealed class Session(Settings settings)
{
    private readonly object _gate = new();

    private bool _connected;
    private bool _onTarget;
    private bool _inAfkServer;
    private string _server = "";
    private long _lastActivity;
    private long _connectCount;

    private bool _dropped;
    private long _droppedAt;
    private long _idleAtDrop;

    /// <summary>A fresh connection was started (the game logged "Connecting to ...").</summary>
    public void OnConnect(string host, long now)
    {
        lock (_gate)
        {
            _connected = true;
            _onTarget = settings.MatchesHost(host);
            _dropped = false;
            _inAfkServer = false;
            _server = "";
            _lastActivity = now;
            _connectCount++;
        }
    }

    /// <summary>The network printed "Sending you to X now...".</summary>
    public void OnServerSwitch(string name, long now)
    {
        lock (_gate)
        {
            if (!_connected || !_onTarget) return;
            _server = name;
            _inAfkServer = settings.IsAfkServer(name);
            _lastActivity = now; // changing gamemode is something you just did
        }
    }

    /// <summary>The connection or the game process went away unexpectedly.</summary>
    public void OnDisconnect(long now)
    {
        lock (_gate)
        {
            if (_connected && _onTarget)
            {
                long idle = (now - _lastActivity) / 1000;
                if (idle >= settings.AfkServerAfterSeconds)
                {
                    _dropped = true;
                    _droppedAt = now;
                    _idleAtDrop = idle;
                }
                else
                {
                    _onTarget = false; // leaving while active is deliberate; not worth flagging
                }
            }
            _connected = false;
        }
    }

    /// <summary>The game closed normally, or was never running: forget everything quietly.</summary>
    public void OnGameClosed()
    {
        lock (_gate)
        {
            _connected = false;
            _onTarget = false;
            _dropped = false;
        }
    }

    public void OnActivity(long now)
    {
        lock (_gate)
        {
            if (_connected && _onTarget) _lastActivity = Math.Max(_lastActivity, now);
        }
    }

    /// <summary>
    /// Sets the time of the player's last action outright. The bridge mod is the authority on this, so
    /// it may move the value backwards (for example when the app starts while the player is already idle).
    /// </summary>
    public void SyncActivity(long at)
    {
        lock (_gate)
        {
            if (_connected && _onTarget) _lastActivity = at;
        }
    }

    /// <summary>Increments on every new connection; lets the window reset "hide for this session".</summary>
    public long ConnectCount
    {
        get { lock (_gate) return _connectCount; }
    }

    public Indicator Snapshot(long now)
    {
        lock (_gate)
        {
            if (!_onTarget) return Indicator.Inactive;

            if (!_connected)
            {
                bool fresh = _dropped && now - _droppedAt <= settings.DisconnectLingerSeconds * 1000L;
                return fresh ? new Indicator(Mode.Disconnected, 0, _idleAtDrop, _server) : Indicator.Inactive;
            }

            long idle = Math.Max(0, (now - _lastActivity) / 1000);
            if (_inAfkServer)
            {
                return idle >= settings.AfkServerAfterSeconds
                    ? new Indicator(Mode.AfkServer, 0, idle, _server)
                    : new Indicator(Mode.Active, 0, idle, _server);
            }

            int severity = settings.WarningStepsSeconds.Count(step => idle >= step);
            return severity > 0
                ? new Indicator(Mode.Warning, severity, idle, _server)
                : new Indicator(Mode.Active, 0, idle, _server);
        }
    }
}
