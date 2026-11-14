using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace Plattenkiste
{
    static class Program
    {
        static readonly Color Bg = Color.FromArgb(0x15, 0x13, 0x0F), Fg = Color.FromArgb(0xF0, 0xE8, 0xD8),
                              Muted = Color.FromArgb(0x9C, 0x92, 0x7F), Accent = Color.FromArgb(0xE9, 0xA2, 0x3B),
                              Track = Color.FromArgb(0x38, 0x32, 0x28);

        [STAThread]
        static int Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            try
            {
                // Alles liegt im Ordner "runtime" direkt neben der EXE – nichts wird installiert oder entpackt
                var dir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "runtime");
                var pyw = Path.Combine(dir, "python", "pythonw.exe");
                var script = Path.Combine(dir, "app", "app.py");
                if (!File.Exists(pyw) || !File.Exists(script))
                    throw new Exception("Der Ordner \"runtime\" fehlt oder ist unvollständig.\n" +
                                        "Bitte den kompletten Plattenkiste-Ordner entpacken und die EXE darin starten.");
                return Launch(pyw, script);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Plattenkiste konnte nicht gestartet werden:\n\n" + ex.Message, "Plattenkiste", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 1;
            }
        }

        // ------------------------------------------------------------ App starten, Absturz melden
        static int Launch(string pyw, string script)
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
    }
}
