using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
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
                var asm = Assembly.GetExecutingAssembly();
                string ver;
                using (var r = new StreamReader(asm.GetManifestResourceStream("version.txt"))) ver = r.ReadToEnd().Trim();
                var baseDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Plattenkiste");
                var dir = Path.Combine(baseDir, "runtime-" + ver);
                var pyw = Path.Combine(dir, "python", "pythonw.exe");
                if (!File.Exists(pyw)) Extract(asm, baseDir, dir);
                Cleanup(baseDir, dir);
                return PythonLauncher.Run(pyw, Path.Combine(dir, "app", "app.py"));
            }
            catch (Exception ex) { return PythonLauncher.Fail(ex); }
        }

        // ------------------------------------------------------------ Einmaliges Entpacken mit Fortschritt
        static void Extract(Assembly asm, string baseDir, string dir)
        {
            Directory.CreateDirectory(baseDir);
            var tmp = dir + ".tmp-" + Process.GetCurrentProcess().Id;
            Exception error = null;

            var form = new Form
            {
                FormBorderStyle = FormBorderStyle.None, StartPosition = FormStartPosition.CenterScreen,
                Size = new Size(420, 150), BackColor = Bg, ShowInTaskbar = true, Text = "Plattenkiste",
                Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath),
            };
            var title = new Label { Text = "Plattenkiste", Font = new Font("Georgia", 18f, FontStyle.Italic), ForeColor = Fg, AutoSize = true, Location = new Point(26, 22) };
            var sub = new Label { Text = "Wird beim ersten Start eingerichtet …", ForeColor = Muted, AutoSize = true, Location = new Point(28, 64), Font = new Font("Segoe UI", 9.5f) };
            int progress = 0;
            var bar = new Panel { Location = new Point(28, 102), Size = new Size(364, 6), BackColor = Track };
            bar.Paint += (o, e) =>
            {
                using (var b = new SolidBrush(Accent)) e.Graphics.FillRectangle(b, 0, 0, bar.Width * progress / 100, bar.Height);
            };
            form.Controls.AddRange(new Control[] { title, sub, bar });
            form.Paint += (o, e) => { using (var p = new Pen(Track)) e.Graphics.DrawRectangle(p, 0, 0, form.Width - 1, form.Height - 1); };

            var worker = new Thread(() =>
            {
                try
                {
                    if (Directory.Exists(tmp)) Directory.Delete(tmp, true);
                    using (var s = asm.GetManifestResourceStream("payload.zip"))
                    using (var zip = new ZipArchive(s, ZipArchiveMode.Read))
                    {
                        long total = zip.Entries.Sum(x => x.Length), done = 0;
                        foreach (var e in zip.Entries)
                        {
                            var dst = Path.GetFullPath(Path.Combine(tmp, e.FullName));
                            if (!dst.StartsWith(Path.GetFullPath(tmp), StringComparison.OrdinalIgnoreCase)) continue;
                            if (e.FullName.EndsWith("/")) { Directory.CreateDirectory(dst); continue; }
                            Directory.CreateDirectory(Path.GetDirectoryName(dst));
                            e.ExtractToFile(dst, true);
                            done += e.Length;
                            int pct = (int)(100 * done / Math.Max(1, total));
                            if (pct != progress) { progress = pct; form.BeginInvoke((Action)(() => bar.Invalidate())); }
                        }
                    }
                    if (Directory.Exists(dir)) Directory.Delete(dir, true);
                    Directory.Move(tmp, dir);
                }
                catch (Exception ex) { error = ex; }
                finally { form.BeginInvoke((Action)form.Close); }
            }) { IsBackground = true };
            form.Shown += (o, e) => worker.Start();
            Application.Run(form);
            if (error != null)
            {
                try { if (Directory.Exists(tmp)) Directory.Delete(tmp, true); } catch { }
                throw new Exception("Entpacken fehlgeschlagen: " + error.Message);
            }
        }

        // alte Versionen nach einem Update entfernen
        static void Cleanup(string baseDir, string keep)
        {
            try
            {
                foreach (var d in Directory.GetDirectories(baseDir, "runtime-*"))
                    if (!string.Equals(d, keep, StringComparison.OrdinalIgnoreCase))
                        try { Directory.Delete(d, true); } catch { }
            }
            catch { }
        }
    }
}
