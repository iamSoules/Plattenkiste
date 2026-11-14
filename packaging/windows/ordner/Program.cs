using System;
using System.IO;
using System.Windows.Forms;

namespace Plattenkiste
{
    static class Program
    {
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
                return PythonLauncher.Run(pyw, script);
            }
            catch (Exception ex) { return PythonLauncher.Fail(ex); }
        }
    }
}
