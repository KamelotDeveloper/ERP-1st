#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::Command;
use std::thread;
use std::time::Duration;

fn find_python() -> Option<PathBuf> {
    // First check PYTHON environment variable
    if let Ok(python_path) = env::var("PYTHON") {
        let p = PathBuf::from(&python_path);
        if p.exists() && Command::new(&p).arg("--version").output().is_ok() {
            return Some(p);
        }
    }

    // Try to find Python using where command on Windows (most reliable)
    if cfg!(target_os = "windows") {
        if let Ok(output) = Command::new("where").arg("python").output() {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout);
                if let Some(first_line) = path.lines().next() {
                    let p = PathBuf::from(first_line.trim());
                    if p.exists() {
                        return Some(p);
                    }
                }
            }
        }
    }

    // macOS: try python3
    if cfg!(target_os = "macos") {
        if Command::new("python3").arg("--version").output().is_ok() {
            return Some(PathBuf::from("python3"));
        }
    }

    // Then check common installation paths on Windows
    let possible_paths = [
        r"C:\Python314\python.exe",
        r"C:\Python313\python.exe",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Program Files\Python314\python.exe",
        r"C:\Program Files\Python313\python.exe",
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
        "python",
        "python3",
        "py",
    ];

    for path in possible_paths {
        if Command::new(path).arg("--version").output().is_ok() {
            return Some(PathBuf::from(path));
        }
    }

    None
}

fn main() {
    let current_exe = std::env::current_exe().unwrap_or_default();
    let exe_dir = current_exe.parent().unwrap_or(&current_exe);

    // Get the resources directory for bundled apps
    let resources_dir = exe_dir.join("resources");

    // Search in multiple locations
    let possible_backend_paths = [
        // Same directory as exe
        exe_dir.to_path_buf(),
        // Resources folder (for bundled apps)
        resources_dir.join("backend"),
        // Bundle folder
        exe_dir.join("bundle").join("backend"),
        // One level up
        exe_dir.join("..").to_path_buf(),
        exe_dir.join("..").join("bundle").join("backend"),
        exe_dir.join("..").join("resources").join("backend"),
        // Two levels up
        exe_dir.join("..").join("..").to_path_buf(),
        exe_dir.join("..").join("..").join("bundle").join("backend"),
        exe_dir
            .join("..")
            .join("..")
            .join("resources")
            .join("backend"),
    ];

    let mut backend_exe = None;
    let mut backend_path = None;
    let mut python_backend = None;

    // First, look for the PyInstaller executable
    for path in &possible_backend_paths {
        let exe = path.join("ga-erp-backend.exe");
        println!("Checking for exe at: {:?}", exe);
        if exe.exists() {
            backend_exe = Some(exe.clone());
            backend_path = Some(path.clone());
            println!("Found backend exe at: {:?}", exe);
            break;
        }

        // Also check in subdirectory "backend"
        let exe_in_backend = path.join("backend").join("ga-erp-backend.exe");
        if exe_in_backend.exists() {
            backend_exe = Some(exe_in_backend.clone());
            backend_path = Some(path.join("backend"));
            println!("Found backend exe at: {:?}", exe_in_backend);
            break;
        }

        // Check for Python main.py in backend folder
        let py_main = path.join("main.py");
        if py_main.exists() {
            python_backend = Some(path.clone());
            println!("Found Python backend at: {:?}", py_main);
            break;
        }

        let py_in_backend = path.join("backend").join("main.py");
        if py_in_backend.exists() {
            python_backend = Some(path.join("backend"));
            println!("Found Python backend at: {:?}", py_in_backend);
            break;
        }
    }

    // Start backend (prefer exe, fallback to Python)
    if let Some(bp) = backend_path {
        // Try to use the PyInstaller executable first
        if let Some(be) = backend_exe {
            println!("Starting backend from executable: {:?}", be);

            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                const CREATE_NO_WINDOW: u32 = 0x08000000;

                let _result = Command::new(&be)
                    .creation_flags(CREATE_NO_WINDOW)
                    .current_dir(&bp)
                    .spawn();
            }

            #[cfg(not(target_os = "windows"))]
            {
                let _result = Command::new(&be).current_dir(&bp).spawn();
            }

            println!("Backend executable started");
            thread::sleep(Duration::from_secs(4));
        }
    } else if let Some(bp) = python_backend {
        // Fallback: use Python
        if let Some(python) = find_python() {
            println!("Using Python: {:?}", python);

            // Check if dependencies work
            let check = Command::new(&python)
                .arg("-c")
                .arg("import fastapi, sqlalchemy, uvicorn")
                .current_dir(&bp)
                .output();

            if check.is_err() || !check.as_ref().unwrap().status.success() {
                // Try pip install --user
                let _ = Command::new(&python)
                    .arg("-m")
                    .arg("pip")
                    .arg("install")
                    .arg("--user")
                    .arg("fastapi")
                    .arg("uvicorn")
                    .arg("sqlalchemy")
                    .arg("pydantic")
                    .arg("pydantic-settings")
                    .arg("python-dotenv")
                    .arg("slowapi")
                    .arg("passlib")
                    .arg("bcrypt")
                    .arg("alembic")
                    .arg("openpyxl")
                    .arg("httpx")
                    .arg("python-jose")
                    .arg("python-multipart")
                    .current_dir(&bp)
                    .output();
            }

            // Start uvicorn with system Python - HIDDEN WINDOW on Windows
            #[cfg(target_os = "windows")]
            {
                use std::os::windows::process::CommandExt;
                const CREATE_NO_WINDOW: u32 = 0x08000000;

                let _result = Command::new(&python)
                    .arg("-m")
                    .arg("uvicorn")
                    .arg("main:app")
                    .arg("--host")
                    .arg("127.0.0.1")
                    .arg("--port")
                    .arg("8000")
                    .creation_flags(CREATE_NO_WINDOW)
                    .current_dir(&bp)
                    .spawn();
            }

            #[cfg(not(target_os = "windows"))]
            {
                let _result = Command::new(&python)
                    .arg("-m")
                    .arg("uvicorn")
                    .arg("main:app")
                    .arg("--host")
                    .arg("127.0.0.1")
                    .arg("--port")
                    .arg("8000")
                    .current_dir(&bp)
                    .spawn();
            }

            println!("Backend Python started");
            thread::sleep(Duration::from_secs(4));
        } else {
            println!("Python not found. Please install Python 3.10+");
        }
    } else {
        println!("Backend not found in any location");
    }

    // Tauri commands for downloads
    #[tauri::command]
    fn get_desktop_path() -> Result<String, String> {
        if let Some(user_dirs) = directories::UserDirs::new() {
            if let Some(desktop) = user_dirs.desktop_dir() {
                return Ok(desktop.to_string_lossy().to_string());
            }
        }
        Err("Could not find desktop directory".to_string())
    }

    #[tauri::command]
    fn create_download_folder(folder_name: String) -> Result<String, String> {
        if let Some(user_dirs) = directories::UserDirs::new() {
            if let Some(desktop) = user_dirs.desktop_dir() {
                let folder_path = desktop.join(&folder_name);
                if !folder_path.exists() {
                    std::fs::create_dir_all(&folder_path)
                        .map_err(|e| format!("Failed to create folder: {}", e))?;
                }
                return Ok(folder_path.to_string_lossy().to_string());
            }
        }
        Err("Could not find desktop directory".to_string())
    }

    #[tauri::command]
    fn save_file(path: String, content: Vec<u8>) -> Result<(), String> {
        std::fs::write(&path, content).map_err(|e| format!("Failed to write file: {}", e))
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            get_desktop_path,
            create_download_folder,
            save_file
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
