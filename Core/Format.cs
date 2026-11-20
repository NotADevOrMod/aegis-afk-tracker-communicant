namespace Aegis.AfkWatch.Core;

internal static class Format
{
    public static string Clock(long totalSeconds)
    {
        long s = Math.Max(0, totalSeconds);
        long h = s / 3600;
        long m = s % 3600 / 60;
        long sec = s % 60;
        return h > 0 ? $"{h}:{m:00}:{sec:00}" : $"{m}:{sec:00}";
    }
}
