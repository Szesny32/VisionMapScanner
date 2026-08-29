using System;
using UnityEngine;

[Serializable]
public class Config {
    private static Config instance;
    public static Config Instance {
        get {
            if (instance == null) {
                instance = Load() ?? new Config();
            }
            return instance;
        }
    }

    public string globalLogLevel = "Info";
    public string run_ros_tcp_endpoint_sh = "";
    public string run_stereo_processor_node_sh = "";

    [NonSerialized]
    private string global_run_ros_tcp_endpoint_sh = "";
    [NonSerialized]
    private string global_run_stereo_processor_node_sh = "";

    public string RunRosTcpEndpointSh => global_run_ros_tcp_endpoint_sh;
    public string RunStereoProcessorNodeSh => global_run_stereo_processor_node_sh;

    private static string GetConfigPath() {
        return FileManager.GetFullPath("config.json");
    }

    public static Config Load() {
        string filePath = GetConfigPath();
        string json = FileManager.LoadFileText(filePath);

        if (!string.IsNullOrEmpty(json)) {
            try {
                Config loadedConfig = JsonUtility.FromJson<Config>(json);
                loadedConfig.ResolvePaths();
                Debug.Log(string.Format(AppLabels.CONFIG_LOADED, filePath));
                return loadedConfig;
            }
            catch (Exception e) {
                Debug.LogError(string.Format(AppLabels.CONFIG_LOAD_ERROR, e.Message));
                return null;
            }
        }
        else {
            Config defaultConfig = new Config();
            defaultConfig.ResolvePaths();
            defaultConfig.Save();
            Debug.Log(string.Format(AppLabels.CONFIG_CREATED, filePath));
            return defaultConfig;
        }
    }

    private void ResolvePaths() {
        global_run_ros_tcp_endpoint_sh = string.IsNullOrEmpty(run_ros_tcp_endpoint_sh) ? "" : FileManager.GetFullPath(run_ros_tcp_endpoint_sh);
        global_run_stereo_processor_node_sh = string.IsNullOrEmpty(run_stereo_processor_node_sh) ? "" : FileManager.GetFullPath(run_stereo_processor_node_sh);
    }

    public void Save() {
        string filePath = GetConfigPath();
        string json = JsonUtility.ToJson(this, true);

        if (!FileManager.SaveFileText(filePath, json)) {
            Debug.LogError(string.Format(AppLabels.CONFIG_SAVE_ERROR, "File write failed"));
        }
    }

    public static void Reload() {
        instance = Load() ?? new Config();
    }
}