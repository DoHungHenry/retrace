# Getting started with retrace (plain-English guide)

retrace is a small app that runs **on your own computer** and lets you search
everything your AI coding tools (Claude Code, Codex, Cline) have done — plus any
folders you point it at. Nothing is uploaded anywhere.

You need to do this **once**. After that, it's one double-click.

---

## Step 1 — Get the files

1. Go to **https://github.com/DoHungHenry/retrace**
2. Click the green **`Code`** button → **Download ZIP**.
3. Double-click the downloaded ZIP to unzip it. You'll get a folder called `retrace`.

*(No need for “git” — the ZIP is fine.)*

---

## Step 2 — Make sure Python is installed

retrace runs on **Python 3**. Most Macs and PCs need it installed once.
Don't worry — the launcher in Step 3 will tell you if it's missing and how to fix it.

If you'd rather do it up front:

**Mac**
- Open the **Terminal** app (press `Cmd+Space`, type “Terminal”, Enter).
- Paste this and press Return:
  ```
  xcode-select --install
  ```
- Click **Install** in the popup and wait.

**Windows**
- Open **PowerShell** (Start menu → type “PowerShell”).
- Paste this and press Enter:
  ```
  winget install -e --id Python.Python.3.12
  ```
- Or download from https://www.python.org/downloads/ and **tick “Add python.exe to PATH”** during install.

---

## Step 3 — Start it

**Mac:** open the `retrace` folder and **double-click `start-retrace.command`**.
- First time only: macOS may say it's from an unidentified developer.
  **Right-click** the file → **Open** → **Open**. (You only do this once.)

**Windows:** open the `retrace` folder and **double-click `start-retrace.bat`**.

A small window opens, then retrace appears in your web browser automatically.
If it doesn't, open your browser and go to: **http://127.0.0.1:8787**

---

## Step 4 — Use it

- Type in the search box at the top — results appear instantly.
- Click any result to read the full conversation or file.
- Left side lists your **projects**; click one to search just that project.
- **Sources** (left, lower down): click **+** to add any folder on your computer
  (notes, documents, a project) so you can search inside it too.

To stop it: close the browser tab and the little window. It's not running in the
background after that.

---

## If something goes wrong

| Problem | Fix |
|---|---|
| “Python 3 not installed” message | Follow the instructions it prints (that's Step 2). |
| Mac won't open the launcher | Right-click `start-retrace.command` → **Open** → **Open**. |
| Browser didn't open | Go to **http://127.0.0.1:8787** manually. |
| “Address already in use” | It's already running — just open the link above. |
| Search feels slow | Optional: install **ripgrep** for speed (`brew install ripgrep` on Mac). It works without it too. |

---

## What retrace can and can't read

- **Reads (searches inside):** text files — `.txt`, `.md`, `.csv`, `.json`, code, etc.
- **Finds by name only:** Office/PDF files (`.docx`, `.xlsx`, `.pptx`, `.pdf`) — their
  *content* can't be searched, but you'll find them by **file name**.

Everything stays on your computer. retrace never sends your data anywhere.
