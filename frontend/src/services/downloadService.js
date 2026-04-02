import { invoke } from "@tauri-apps/api/core";
import { BaseDirectory, mkdir, writeTextFile, writeFile, exists } from "@tauri-apps/plugin-fs";
import { save } from "@tauri-apps/plugin-dialog";

const FOLDER_NAME = "El Menestral datos";

// Check if we're running in Tauri
async function isTauri() {
  try {
    // Try to invoke a simple Tauri command to check if it works
    await invoke('get_desktop_path');
    return true;
  } catch (e) {
    console.log("Tauri not available:", e);
    return false;
  }
}

export async function ensureDownloadFolder() {
  console.log("ensureDownloadFolder called");
  
  const isTauriApp = await isTauri();
  console.log("isTauriApp:", isTauriApp);
  
  if (!isTauriApp) {
    console.warn("Not running in Tauri - using browser fallback");
    return false;
  }
  
  try {
    // Use Tauri command to create folder
    const folderPath = await invoke('create_download_folder', { folderName: FOLDER_NAME });
    console.log("Folder created at:", folderPath);
    return true;
  } catch (error) {
    console.error("Error creating download folder via Tauri:", error);
    
    // Try with plugin-fs as fallback
    try {
      await mkdir(FOLDER_NAME, { baseDir: BaseDirectory.Desktop, recursive: true });
      return true;
    } catch (e2) {
      console.error("Fallback also failed:", e2);
      return false;
    }
  }
}

export async function downloadPDFToFolder(filename, htmlContent) {
  console.log("downloadPDFToFolder called");
  
  const isTauriApp = await isTauri();
  
  if (!isTauriApp) {
    console.log("Not in Tauri - using browser fallback");
    return downloadPDFFallback(filename, htmlContent);
  }
  
  try {
    console.log("Starting PDF download, filename:", filename);
    
    // Ensure folder exists
    const folderExists = await ensureDownloadFolder();
    console.log("Folder exists result:", folderExists);
    
    if (!folderExists) {
      console.log("Using fallback - folder not available");
      return downloadPDFFallback(filename, htmlContent);
    }

    // Ask user where to save (default to the folder)
    console.log("Opening save dialog...");
    const filePath = await save({
      defaultPath: `${FOLDER_NAME}/${filename}`,
      filters: [{ name: "HTML", extensions: ["html"] }]
    });

    console.log("Save dialog returned:", filePath);

    if (!filePath) {
      return { success: false, cancelled: true };
    }

    // Write file using Tauri command
    const encoder = new TextEncoder();
    const content = encoder.encode(htmlContent);
    await invoke('save_file', { path: filePath, content: Array.from(content) });
    
    console.log("File written successfully to:", filePath);
    return { success: true, path: filePath };
  } catch (error) {
    console.error("Error downloading PDF:", error);
    alert("Error al descargar: " + error.message);
    return downloadPDFFallback(filename, htmlContent);
  }
}

// Fallback for browser/testing mode or when Tauri is not available
async function downloadPDFFallback(filename, htmlContent) {
  console.log("Using browser fallback download");
  const blob = new Blob([htmlContent], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  return { success: true, fallback: true };
}

export async function downloadFileFromBackend(url, filename) {
  console.log("downloadFileFromBackend called, url:", url);
  
  const isTauriApp = await isTauri();
  
  if (!isTauriApp) {
    console.log("Not in Tauri - using browser fallback");
    window.open("http://127.0.0.1:8000" + url, "_blank");
    return { success: true };
  }
  
  try {
    console.log("Starting Excel download");
    
    // Ensure folder exists
    const folderExists = await ensureDownloadFolder();
    console.log("Folder exists result:", folderExists);
    
    if (!folderExists) {
      console.log("Using browser fallback - folder not available");
      window.open("http://127.0.0.1:8000" + url, "_blank");
      return { success: true };
    }

    // Ask user where to save
    console.log("Opening save dialog for Excel...");
    const filePath = await save({
      defaultPath: `${FOLDER_NAME}/${filename}`,
      filters: [
        { name: "Excel", extensions: ["xlsx"] },
        { name: "All Files", extensions: ["*"] }
      ]
    });

    console.log("Save dialog returned:", filePath);

    if (!filePath) {
      return { success: false, cancelled: true };
    }

    // Download the file from backend and save to path
    console.log("Fetching from backend...");
    const response = await fetch("http://127.0.0.1:8000" + url, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    console.log("Response status:", response.status);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const blob = await response.blob();
    console.log("Blob size:", blob.size);
    
    const arrayBuffer = await blob.arrayBuffer();
    const uint8Array = new Uint8Array(arrayBuffer);
    
    // Write file using Tauri command
    console.log("Writing file to:", filePath);
    await invoke('save_file', { path: filePath, content: Array.from(uint8Array) });
    
    console.log("File written successfully!");
    return { success: true, path: filePath };
  } catch (error) {
    console.error("Error downloading file:", error);
    alert("Error al descargar: " + error.message);
    window.open("http://127.0.0.1:8000" + url, "_blank");
    return { success: true, fallback: true };
  }
}