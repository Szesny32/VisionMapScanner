using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;

public class ShellManager
{
    Logger logger;
    
    private static ShellManager instance;
    public static ShellManager Instance {
        get {
            if (instance == null)
                instance = new ShellManager();
            return instance;
        }
    }

    private readonly List<Process> activeProcesses = new List<Process>();

    private ShellManager() { 
        logger = new Logger(GetType().Name);
    }

    public Process Execute(string scriptPath) {
        if (!File.Exists(scriptPath)) {
            logger.Error(string.Format(AppLabels.MISSING_SCRIPT_PATH, scriptPath));
            return null;
        }

        ProcessStartInfo startInfo = new ProcessStartInfo() {
            FileName = "/bin/bash",
            Arguments = scriptPath,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        try {
            Process process = Process.Start(startInfo);
            if (process != null) {
                lock (activeProcesses) {
                    activeProcesses.Add(process);
                }

                process.EnableRaisingEvents = true;
                process.Exited += (sender, e) => {
                    lock (activeProcesses) {
                        activeProcesses.Remove(process);
                    }
                    process.Dispose();
                };
                logger.Log(string.Format(AppLabels.STARTED_PROCESS, process.Id, scriptPath));
                return process;
            }
        }
        catch (Exception e) {
            logger.Error(AppLabels.INIT_PROCESS_FAILED + e.Message);
        }
        return null;
    }

    public void CloseProcess(Process process) {
        if (process == null) return;

        lock (activeProcesses) {
            if (activeProcesses.Contains(process)) {
                try {
                    if (!process.HasExited) {
                        int pid = process.Id;
                        logger.Log(string.Format(AppLabels.KILL_PROCESS_TREE, pid));
                        KillProcessTree(pid);
                    }
                }
                catch (Exception e) {
                    logger.Error(string.Format(AppLabels.KILL_PROCESS_ERROR, e.Message));
                }
                finally {
                    activeProcesses.Remove(process);
                    try { process.Dispose(); } catch { }
                }
            }
        }
    }

    private void KillProcessTree(int pid) {
        try {
            ProcessStartInfo psi = new ProcessStartInfo("pgrep", $"-P {pid}") {
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            
            using (Process pgrep = Process.Start(psi)) {
                pgrep.WaitForExit();
                string output = pgrep.StandardOutput.ReadToEnd();
                
                string[] children = output.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                foreach (string childStr in children) {
                    if (int.TryParse(childStr, out int childPid)) {
                        KillProcessTree(childPid);
                    }
                }
            }

            try {
                Process procToKill = Process.GetProcessById(pid);
                procToKill.Kill();
            } catch { } 
            
        } catch { }
    }

    public void CloseAllProcesses() {
        lock (activeProcesses) {
            var processesToClose = new List<Process>(activeProcesses);
            foreach (var process in processesToClose) {
                CloseProcess(process);
            }
            activeProcesses.Clear();
            logger.Log(AppLabels.CLOSED_ALL_PROCESSES);
        }
    }
}
