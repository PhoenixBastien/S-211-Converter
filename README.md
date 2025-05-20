![App Icon](icon.ico)

# S211 Converter

This graphical app allows the user to convert S211 MARC records between XML and CSV.

## Setup

Before building the application, we need to create and activate a virtual environment named `.venv` in the project root directory and install the package dependencies.

### Option A: Visual Studio Code

In Visual Studio Code, press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd> to open the Command Palette, search for and select the **Python: Create Environment** command, and select the **Venv** environment type.

### Option B: PowerShell

From the project root directory, create and activate a virtual environment by running in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Then, install the package dependencies by running:

```powershell
pip install .
```

Alternatively, the package dependencies can be installed from a local flat directory called `wheels` containing archives by replacing the third line with:

```powershell
pip install --no-index --find-links=wheels .
```

## Build

Once the setup is complete, we can build the application.

### Option A: Visual Studio Code

In Visual Studio Code, press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>B</kbd> to run the build task. Once complete, the application will be found in the `dist` directory.

### Option B: PowerShell

From the project root directory, build the application by running in PowerShell:

```powershell
pyinstaller --onefile --windowed --name="S211 Converter" --icon=icon.ico --add-data=icon.ico:. app.py
```

The application will be found in the `dist` directory.