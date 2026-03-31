# Instalación de Rust para compilar la app de escritorio

## Windows

1. Descarga y ejecuta:
   https://win.rustup.rs/x86_64

2. Durante la instalación, elige las opciones por defecto:
   - Default toolchain: stable (1)
   - Path integration: Yes

3. Una vez instalado, reinicia tu terminal/VSCode

4. Verifica la instalación:
   ```
   rustc --version
   cargo --version
   ```

## Compilar la app

Una vez instalado Rust, ejecuta:

```bash
cd frontend
npm run tauri build
```

Esto generará un archivo `.exe` en:
`frontend/src-tauri/target/release/bundle/nsis/`

## Atajos de teclado en la app

- **F11**: Pantalla completa
- **Ctrl+R**: Recargar
- **F12**: Herramientas de desarrollo
