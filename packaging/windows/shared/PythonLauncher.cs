using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace Plattenkiste
{
    // Gemeinsamer Teil beider Launcher: Python-App starten und Abstürze melden
    static class PythonLauncher
    {
        public static int Run(string pyw, string script)
        {
            var psi = new ProcessStartInfo(pyw, "-E -s -X utf8 \"" + script + "\"")
            {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true,
                WorkingDirectory = Path.GetDirectoryName(script),
                StandardErrorEncoding = Encoding.UTF8,
            };
            var err = new StringBuilder();
            using (var p = new Process { StartInfo = psi })
            {
                p.ErrorDataReceived += (o, e) => { if (e.Data != null) lock (err) err.AppendLine(e.Data); };
                p.Start();
                p.BeginErrorReadLine();
                p.WaitForExit();
                if (p.ExitCode != 0)
                {
                    string text;
                    lock (err) text = err.ToString();
                    var log = Path.Combine(Path.GetTempPath(), "plattenkiste-fehler.txt");
                    try { File.WriteAllText(log, text); } catch { }
                    var tail = text.Length > 1500 ? "…" + text.Substring(text.Length - 1500) : text;
                    MessageBox.Show("Plattenkiste wurde mit einem Fehler beendet.\n\n" + tail + "\n\nKompletter Bericht: " + log,
                        "Plattenkiste", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                return p.ExitCode;
            }
        }

        public static int Fail(Exception ex)
        {
            MessageBox.Show("Plattenkiste konnte nicht gestartet werden:\n\n" + ex.Message, "Plattenkiste",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
