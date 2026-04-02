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
            println!("Using PYTHON env: {}", python_path);
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
                        println!("Found Python via where: {:?}", p);
                        return Some(p);
                    }
                }
            }
        }
    }

    // Then check common installation paths on Windows
    let possible_paths = [
        "python",
        "python3",
        "py",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
        r"C:\Users\Giuliano\AppData\Local\Programs\Python\Python312\python.exe",
        r"C:\Users\Giuliano\AppData\Local\Programs\Python\Python311\python.exe",
    ];

    for path in possible_paths {
        if Command::new(path).arg("--version").output().is_ok() {
            return Some(PathBuf::from(path));
        }
    }

    None
}

fn main() {
    println!("El Menestral ERP Starting...");

    let current_exe = std::env::current_exe().unwrap_or_default();
    let exe_dir = current_exe.parent().unwrap_or(&current_exe);

    let possible_backend_paths = [
        exe_dir.join(r"_up_\_up_\backend"),
        exe_dir.join("backend"),
        exe_dir.join("resources").join("backend"),
        PathBuf::from("backend"),
    ];

    let mut backend_path = None;
    for path in &possible_backend_paths {
        let main_py = path.join("main.py");
        if main_py.exists() {
            println!("Found backend at: {:?}", main_py);
            backend_path = Some(path.clone());
            break;
        }
    }

    if let Some(bp) = backend_path {
        if let Some(python) = find_python() {
            println!("Using Python: {:?}", python);

            // Quick check if dependencies work
            let check = Command::new(&python)
                .arg("-c")
                .arg("import fastapi, sqlalchemy, uvicorn")
                .current_dir(&bp)
                .output();

            if check.is_err() || !check.as_ref().unwrap().status.success() {
                println!("Dependencies missing. Attempting to install...");

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

                println!("Install attempt complete.");
            }

            // Start uvicorn with system Python - HIDDEN WINDOW on Windows
            println!("Starting backend server (hidden)...");

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

            println!("Backend starting...");
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
