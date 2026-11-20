using Aegis.AfkWatch.Core;
using Aegis.AfkWatch.Sources;
using Aegis.AfkWatch.Ui;

namespace Aegis.AfkWatch;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        using var single = new Mutex(initiallyOwned: true, "Aegis.AfkWatch.SingleInstance", out bool first);
        if (!first) return;

        ApplicationConfiguration.Initialize();

        Settings settings = Settings.Load(Settings.DefaultPath());
        if (settings.LoadProblem is not null)
            MessageBox.Show(settings.LoadProblem, "AEGIS AFK Watch", MessageBoxButtons.OK, MessageBoxIcon.Warning);

        var session = new Session(settings);
        using var watcher = new Watcher(session, settings);
        watcher.Start();

        Application.Run(new TrayContext(session, settings));
    }
}
