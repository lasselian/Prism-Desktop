# Prism Desktop

A modern, native Windows client for Home Assistant that lives in your system tray.

I built this because I wanted a faster, more elegant way to control my smart home without opening a browser tab. It features a sleek dashboard with fluid animations, drag-and-drop customization, and deep integration with Home Assistant entities.

![Main Interface](docs/images/dashboard-main.png)
*The main dashboard view showing light controls, climate widgets, and power sensors.*

## Features

- **System Tray Integration**: The app stays tucked away in your tray until you need it.
- **Morphing Controls**: Click and hold widgets to expand them into granular controls like dimmers or thermostats.
- **Drag & Drop Customization**: Rearrange your dashboard grid simply by dragging icons around.
- **Real-time Sync**: Uses Home Assistant's WebSocket API for instant state updates.
- **Customizable Appearance**: Choose from different border effects (like Rainbow or Aurora) and customize button colors.

## Installation

### Windows Installer
Download the latest `PrismDesktopSetup.exe` from the Releases page. This will install the app and optionally set it to start with Windows.

### Manual / Portable
You can also download the standalone `.exe` if you prefer not to install anything. Just run it, and it will create a configuration file in the same directory.

## Running from Source

If you want to modify the code or run it manually:

1. Clone this repository.
2. Install the dependencies:
   ```
   pip install PyQt6 requests websocket-client
   ```
3. Run the application:
   ```
   python main.py
   ```

## Configuration

Upon first launch, you will be asked for your Home Assistant URL and a Long-Lived Access Token. You can generate this token in your Home Assistant profile settings.

![Settings Menu](docs/images/settings-menu.png)
*The settings panel for configuring connection details and UI preferences.*

## Building

To build the executable yourself, run the included build script:

```
python build_exe.py
```

This will run PyInstaller and generate a single-file executable in the `dist` folder.
