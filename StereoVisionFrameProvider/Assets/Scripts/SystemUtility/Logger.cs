using System;

public class Logger
{
    private string className;

    public Logger(string className) {
        this.className = className;
    }

    private string FormatLog(string logMessage) {
        //string time = DateTime.Now.ToString("HH:mm:ss");
        //return $"[{time}] [{className}] {logMessage}";
        return $"[{className}] {logMessage}";
    }

    public void Log(string logMessage) {
        if (LogLevel.Info >= GetCurrentLogLevel()) {
            UnityEngine.Debug.Log(FormatLog(logMessage));
        }
    }

    public void Warn(string logMessage) {
        if (LogLevel.Warning >= GetCurrentLogLevel()) {
            UnityEngine.Debug.LogWarning(FormatLog(logMessage));
        }
    }

    public void Error(string logMessage) {
        if (LogLevel.Error >= GetCurrentLogLevel()) {
            UnityEngine.Debug.LogError(FormatLog(logMessage));
        }
    }

    public void Debug(string logMessage) {
        if (LogLevel.Debug >= GetCurrentLogLevel()) {
            UnityEngine.Debug.Log(FormatLog(logMessage));
        }
    }
    private LogLevel GetCurrentLogLevel() {
        if (Enum.TryParse(Config.Instance.globalLogLevel, true, out LogLevel level)) {
            return level;
        }
        return LogLevel.Info;
    }
}