\# Tarno Mesh – FreeBSD Compatibility \& Development Guide



This guide outlines system dependencies, installation steps, build instructions, and cross-platform coding conventions to ensure \*\*Tarno Mesh\*\* runs seamlessly on FreeBSD while maintaining dual-compatibility with Windows.



\---



\## 🛠️ System Dependencies



Install required system packages, compilers, and C-libraries via FreeBSD's package manager `pkg`:



```bash

sudo pkg install python3 git portaudio pkgconf cmake



```



\---



\## 📦 Environment Setup \& Installation



1\. \*\*Clone the Repository:\*\*

```bash

git clone \[https://github.com/coding-jona/Tarno.git](https://github.com/coding-jona/Tarno.git)

cd Tarno



```





2\. \*\*Create and Activate Virtual Environment:\*\*

```bash

python3 -m venv .venv

source .venv/bin/activate



```





3\. \*\*Install Python Dependencies:\*\* (`requirements.txt` lives under `workspace/installer/`, two levels below the repo root)

```bash

pip install --upgrade pip setuptools wheel

pip install -r workspace/installer/requirements.txt



```







\---



\## 💻 Cross-Platform Guidelines (Windows \& FreeBSD)



To ensure code written by \*\*Dr-Deep\*\* (FreeBSD) and \*\*coding-jona\*\* (Windows) runs across both operating systems without manual modifications, adhere to these standards:



\### 1. Dynamic Paths (`pathlib` \& `platformdirs`)



Never hardcode `/` or `\\` path separators or fixed OS paths. Use `platformdirs` to resolve user directories on each platform automatically:



```python

from pathlib import Path

from platformdirs import user\_config\_dir, user\_data\_dir



\# FreeBSD: \~/.config/Tarno Mesh

\# Windows: C:\\Users\\<User>\\AppData\\Local\\Tarno AI\\Tarno Mesh

CONFIG\_DIR = Path(user\_config\_dir("Tarno Mesh", "Tarno AI"))

DATA\_DIR = Path(user\_data\_dir("Tarno Mesh", "Tarno AI"))



CONFIG\_DIR.mkdir(parents=True, exist\_ok=True)



```



\### 2. OS Platform Detection



FreeBSD returns platform strings like `freebsd13` or `freebsd14`. Always use `.startswith()`:



```python

import sys



IS\_FREEBSD = sys.platform.startswith("freebsd")

IS\_WINDOWS = sys.platform.startswith("win")

IS\_LINUX = sys.platform.startswith("linux")



```



\### 3. Pure Python File System Operations



Do not call system shell commands (`rmdir /s /q`, `rm -rf`, `del`). Use Python's built-in standard library tools:



\* \*\*Remove folders:\*\* `shutil.rmtree(path)`

\* \*\*Delete files:\*\* `path.unlink(missing\_ok=True)`

\* \*\*Create directories:\*\* `path.mkdir(parents=True, exist\_ok=True)`



\### 4. Audio Hardware Permissions (PortAudio / OSS)



Ensure your FreeBSD user account is added to the `audio` group to allow microphone capture and speaker playback:



```bash

sudo pw groupmod audio -m $USER



```



\---



\## 🚀 Running \& Packaging



\### Running the Backend



Start the application backend directly with Python:



```bash

python -m tarno\_backend



```



\### Building Portable Executables (PyInstaller)



PyInstaller is supported on FreeBSD to bundle standalone executables:



Run this from `workspace/installer/` (where this file and `Tarno Mesh.spec` live):

```bash

pip install pyinstaller

pyinstaller --noconfirm "Tarno Mesh.spec"



```



\*Note: Inno Setup (`setup.iss`) is Windows-specific for generating `.exe` installers. On FreeBSD, distribute the PyInstaller `workspace/installer/dist/Tarno Mesh/` output directly or package it via FreeBSD Ports / tarball.\*



```

