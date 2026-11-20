using System.Drawing.Drawing2D;
using System.Drawing.Text;
using Aegis.AfkWatch.Core;

namespace Aegis.AfkWatch.Ui;

/// <summary>
/// Small borderless status window. Never takes focus, stays out of the taskbar and Alt-Tab, and is
/// purely a display: it does not talk to the game.
/// </summary>
internal sealed class StatusForm : Form
{
    private const int BaseWidth = 248;
    private const int BaseHeight = 86;
    private const int BaseMargin = 24;
    private const int BaseArc = 18;
    private const int RefreshMs = 100;

    private const int WsExNoActivate = 0x08000000;
    private const int WsExToolWindow = 0x00000080;

    private readonly Session _session;
    private readonly Settings _settings;
    private readonly float _scale;
    private readonly Font _titleFont;
    private readonly Font _headlineFont;
    private readonly Font _detailFont;

    private Indicator _view = Indicator.Inactive;
    private bool _dismissed;
    private long _dismissedAtConnect = -1;
    private int _lastSeverity;
    private Point? _dragOffset;

    public StatusForm(Session session, Settings settings)
    {
        _session = session;
        _settings = settings;
        _scale = DeviceDpi / 96f;

        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = settings.WindowAlwaysOnTop;
        Opacity = settings.WindowOpacity;
        DoubleBuffered = true;
        BackColor = Color.FromArgb(16, 20, 24);
        Size = new Size(S(BaseWidth), S(BaseHeight));
        using (GraphicsPath shape = RoundedRect(new Rectangle(0, 0, Width, Height), S(BaseArc)))
            Region = new Region(shape);
        Location = InitialLocation();

        _titleFont = new Font("Segoe UI", 10f * _scale, FontStyle.Bold, GraphicsUnit.Pixel);
        _headlineFont = new Font("Segoe UI", 20f * _scale, FontStyle.Bold, GraphicsUnit.Pixel);
        _detailFont = new Font("Segoe UI", 12f * _scale, FontStyle.Regular, GraphicsUnit.Pixel);

        ContextMenuStrip = BuildMenu();

        var timer = new System.Windows.Forms.Timer { Interval = RefreshMs };
        timer.Tick += (_, _) => UpdateIndicator();
        timer.Start();
    }

    /// <summary>Brings the window back after "Hide until next connection".</summary>
    public void Undismiss() => _dismissed = false;

    protected override bool ShowWithoutActivation => true;

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams cp = base.CreateParams;
            cp.ExStyle |= WsExNoActivate | WsExToolWindow;
            return cp;
        }
    }

    private int S(int value) => (int)Math.Round(value * _scale);

    private Point InitialLocation()
    {
        if (_settings.WindowX >= 0 && _settings.WindowY >= 0)
            return new Point(_settings.WindowX, _settings.WindowY);
        Rectangle area = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1920, 1080);
        return new Point(area.Right - S(BaseWidth) - S(BaseMargin), area.Top + S(BaseMargin));
    }

    private ContextMenuStrip BuildMenu()
    {
        var menu = new ContextMenuStrip();

        var onTop = new ToolStripMenuItem("Always on top") { Checked = _settings.WindowAlwaysOnTop, CheckOnClick = true };
        onTop.CheckedChanged += (_, _) =>
        {
            _settings.WindowAlwaysOnTop = onTop.Checked;
            TopMost = onTop.Checked;
            _settings.Save();
        };

        var hide = new ToolStripMenuItem("Hide until next connection");
        hide.Click += (_, _) =>
        {
            _dismissed = true;
            _dismissedAtConnect = _session.ConnectCount;
        };

        menu.Items.Add(onTop);
        menu.Items.Add(hide);
        return menu;
    }

    private void UpdateIndicator()
    {
        long now = Environment.TickCount64;
        _view = _session.Snapshot(now);

        if (_session.ConnectCount != _dismissedAtConnect) _dismissed = false;

        bool wanted = !_dismissed && _view.Mode switch
        {
            Mode.Inactive => false,
            Mode.Active => _settings.WindowShowWhenActive,
            _ => true,
        };

        int severity = _view.Mode == Mode.Warning ? _view.Severity : 0;
        if (_settings.BeepOnWarning && severity > _lastSeverity) System.Media.SystemSounds.Exclamation.Play();
        _lastSeverity = severity;

        if (Visible != wanted) Visible = wanted;
        if (wanted) Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

        Indicator v = _view;
        int rgb = Palette.Accent(v);
        int alpha = (int)Math.Round(255 * Palette.Pulse(v, Environment.TickCount64));
        Color accent = Color.FromArgb(alpha, (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);

        using GraphicsPath outline = RoundedRect(new Rectangle(0, 0, Width - 1, Height - 1), S(BaseArc));
        using var border = new Pen(accent, 2f * _scale);
        using var stripe = new SolidBrush(accent);
        using var titleBrush = new SolidBrush(Color.FromArgb(130, 140, 155));
        using var textBrush = new SolidBrush(Color.White);
        using var detailBrush = new SolidBrush(Color.FromArgb(184, 192, 204));

        g.SetClip(outline);
        g.FillRectangle(stripe, 0, 0, S(6), Height);
        g.ResetClip();
        g.DrawPath(border, outline);

        int left = S(20);
        g.DrawString("AEGIS  ·  AFK WATCH", _titleFont, titleBrush, left, S(10));
        g.DrawString(v.Headline, _headlineFont, textBrush, left, S(26));
        g.DrawString(v.Detail, _detailFont, detailBrush, left, S(58));
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Left) _dragOffset = e.Location;
        base.OnMouseDown(e);
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        if (_dragOffset is { } offset && e.Button == MouseButtons.Left)
            Location = new Point(Cursor.Position.X - offset.X, Cursor.Position.Y - offset.Y);
        base.OnMouseMove(e);
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        if (_dragOffset is not null)
        {
            _dragOffset = null;
            _settings.WindowX = Location.X;
            _settings.WindowY = Location.Y;
            _settings.Save();
        }
        base.OnMouseUp(e);
    }

    private static GraphicsPath RoundedRect(Rectangle r, int radius)
    {
        int d = radius * 2;
        var path = new GraphicsPath();
        path.AddArc(r.X, r.Y, d, d, 180, 90);
        path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _titleFont.Dispose();
            _headlineFont.Dispose();
            _detailFont.Dispose();
        }
        base.Dispose(disposing);
    }
}
