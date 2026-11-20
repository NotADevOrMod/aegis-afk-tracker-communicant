using System.Diagnostics;
using Aegis.AfkWatch.Core;

namespace Aegis.AfkWatch.Ui;

/// <summary>Owns the tray icon (the only way to exit) and the status window.</summary>
internal sealed class TrayContext : ApplicationContext
{
    private readonly NotifyIcon _tray;
    private readonly StatusForm _form;

    public TrayContext(Session session, Settings settings)
    {
        _form = new StatusForm(session, settings);

        var menu = new ContextMenuStrip();
        menu.Items.Add("Show window", null, (_, _) => _form.Undismiss());
        menu.Items.Add("Open settings file", null, (_, _) =>
            Process.Start(new ProcessStartInfo(settings.FilePath) { UseShellExecute = true }));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => ExitThread());

        _tray = new NotifyIcon
        {
            Icon = SystemIcons.Shield,
            Text = "AEGIS AFK Watch",
            ContextMenuStrip = menu,
            Visible = true,
        };
    }

    protected override void ExitThreadCore()
    {
        _tray.Visible = false;
        _tray.Dispose();
        _form.Dispose();
        base.ExitThreadCore();
    }
}
