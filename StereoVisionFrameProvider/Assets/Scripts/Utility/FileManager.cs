using System.Diagnostics;
using System.IO;

public static class FileManager {

    public static string GetFullPath(string relativePath) {
        string rootDir = GetGitRootDirectory();
        return Path.Combine(rootDir, relativePath);
    }

    public static string LoadFileText(string filePath) {
        if (!File.Exists(filePath)) return null;
        try {
            return File.ReadAllText(filePath);
        }
        catch (System.Exception e) {
            UnityEngine.Debug.LogError(string.Format(AppLabels.FILE_READ_ERROR, filePath, e.Message));
            return null;
        }
    }

    public static bool SaveFileText(string filePath, string content) {
        try {
            File.WriteAllText(filePath, content);
            return true;
        }
        catch (System.Exception e) {
            UnityEngine.Debug.LogError(string.Format(AppLabels.FILE_SAVE_ERROR, filePath, e.Message));
            return false;
        }
    }

    private static string GetGitRootDirectory() {
        try {
            ProcessStartInfo startInfo = new ProcessStartInfo {
                FileName = "git",
                Arguments = "rev-parse --show-toplevel",
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using (Process process = Process.Start(startInfo)) {
                string output = process.StandardOutput.ReadToEnd().Trim();
                process.WaitForExit();

                if (!string.IsNullOrEmpty(output) && Directory.Exists(output)) {
                    return output;
                }
            }
        }
        catch (System.Exception) {
        }

        return Directory.GetCurrentDirectory();
    }
}