![App Icon](img/icon.png)

# S211 Converter

This graphical app allows the user to convert S211 MARC records between XML and CSV.

## Prerequisites

Create a virtual environment named `.venv` in the project root directory, activate it, and install the necessary packages listed in [requirements.txt](requirements.txt).

## Build

### Option A: Visual Studio Code

In Visual Studio Code, press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>B</kbd> to run the build task. Once the build task is complete, the application will be found in the `dist` directory.

### Option B: Terminal

Alternatively, the application can be built in the terminal by running the command:

```sh
pyinstaller --onefile --windowed --name="S211 Converter" --icon=img/icon.ico --add-data=img/icon.ico:. app.py
```

As with the Visual Studio Code method, the application will be found in the `dist` directory.