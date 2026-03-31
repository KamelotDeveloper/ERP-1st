#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::Command;
use std::thread;
use std::time::Duration;

fn find_python() -> Option<PathBuf> {
    let possible_paths = [
        "python",
        "python3",
        "py",
        r"C:\Python312\python.exe",
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Program Files\Python312\python.exe",
        r"C:\Program Files\Python311\python.exe",
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

            println!("Backend starting...");
            thread::sleep(Duration::from_secs(4));
        } else {
            println!("Python not found. Please install Python 3.10+");
        }
    } else {
        println!("Backend not found in any location");
    }

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
