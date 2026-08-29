public static class AppLabels {
    // INFO
    public const string BASELINE_CALCULATED = "Calculated baseline between cameras: {0:F4} m";
    public const string STARTED_PROCESS = "Started process (ID: {0}): {1}";
    public const string KILL_PROCESS_TREE = "Closing entire process tree for PID: {0}";
    public const string CLOSED_ALL_PROCESSES = "Closed all .sh script processes along with their children.";
    public const string CONFIG_LOADED = "Loaded configuration from project directory: {0}";
    public const string CONFIG_CREATED = "Created default configuration file in project directory: {0}";

    // WARN
    public const string CAMERA_NOT_ASSIGNED = "One of the cameras is not assigned! Using default baseline.";
    
    // ERROR
    public const string MISSING_ROS_SCRIPTS_PATH = "Path to ROS scripts are empty!";
    public const string MISSING_SCRIPT_PATH = "Script file does not exist: {0}";
    public const string INIT_PROCESS_FAILED = "Error while starting process: {0}";
    public const string KILL_PROCESS_ERROR = "Error while closing process: {0}";
    public const string CONFIG_LOAD_ERROR = "Error reading config: {0}. Using default settings.";
    public const string CONFIG_SAVE_ERROR = "Error saving config: {0}";

    public const string FILE_READ_ERROR = "[FileManager] Error reading file {0}: {1}";
    public const string FILE_SAVE_ERROR = "[FileManager] Error saving file {0}: {1}";

}