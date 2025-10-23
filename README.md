# Discord Rich Presence (Windows) — Privacy‑Aware

This Windows script updates your Discord status with **what you're doing** while allowing you to block out certain activities (think banking, budget, work files).   
It looks only at your **active window title**, masks anything that matches the sensitive words you input into the .py file, and then publishes a **friendly label** (e.g., `Working in Excel`, `Browsing example.com`, or `Working — details hidden`).

> **Privacy first:** The script never sends raw window titles to Discord — only the short label it derives locally.

---

## What you'll need

- **Windows 10/11**
- **Discord desktop app** (signed in and running)
- **Python 3.10+** (installed from python.org or the Microsoft Store)
- About **5–10 minutes**

---

## 1) Get the files

Download these into a folder (e.g., `C:\discord-presence`):

- `discord_presence.py` (the script)  
- `.env.example`  
- `pyproject.toml`  
- `.gitignore`

If you’re using GitHub, commit them to a new repo and clone locally.

---

## 2) Create a Discord Application (one‑time)

1. Open the **Discord Developer Portal** (Google it if you don’t know the link).
2. Click **New Application** → give it a name (e.g., _Presence Mask_).
3. On the left, open **Rich Presence** → (optional) **Art Assets** if you want custom icons later.
4. Copy the **Application ID** (sometimes called **Client ID**). You'll paste this into `.env` next.

> You **do not** need a bot or OAuth for local Rich Presence.

---

## 3) Set up your `.env`

1. Make a copy of `.env.example` named **`.env`** in the same folder.
2. Open `.env` and set:
   - `DISCORD_CLIENT_ID` → paste your Application (Client) ID
   - (Optional) `MASK_TERMS` → add your company names or sensitive words, comma‑separated  
     _Examples already included: `companyname, confidential, budget, invoice, payroll, student, medical, legal`_
   - (Optional) tweak `UPDATE_EVERY_SECS` and `CHECK_INTERVAL`

> `.env` is in `.gitignore` by default so you don't accidentally commit secrets.

---

## 4) Install Python dependencies

Open **PowerShell** in your project folder and run **one** of the following:

**Option A — Install via project metadata (recommended):**
```powershell
python -m pip install --upgrade pip
pip install .
```

**Option B — Install packages individually:**
```powershell
python -m pip install --upgrade pip
pip install pypresence psutil pygetwindow pywin32 python-dotenv
```

> If `pip` is not found, try `py -m pip` instead of `python -m pip`.

---

## 5) Run it

With Discord running, start the presence:

```powershell
python discord_presence.py --verbose
```
- Leave the window open; it will update every few seconds.
- Press **Ctrl+C** to stop.

You can also use the installed console script after `pip install .`:
```powershell
discord-presence --verbose
```

---

## What you'll see

- **Browsing example.com** when your active window is a browser tab titled with a domain.
- **Working in Excel** / **Coding in VS Code** for common apps.
- **Working — details hidden** if your active window title contains any **sensitive term** from `.env`.

> You can add more app labels or mappings inside `discord_presence.py` (`APP_MAP`), or customize mask terms in `.env`.

---

## Customize (optional)

- **Mask terms:** Edit `MASK_TERMS` in `.env`. Terms are **case‑insensitive** and matched anywhere in the active window title.
- **Update rate:** Change `UPDATE_EVERY_SECS` (default 15s). Be polite — don’t set extremely low values.
- **App/domain mapping:** Tweak `APP_MAP` in the script to change labels like “Working in Excel”.
- **Rich Presence icons:** In the Developer Portal → Rich Presence → **Art Assets**, upload images and use their keys in the script if you want.

---

## Troubleshooting

- **“This script currently supports Windows only.”**  
  It uses Windows APIs. macOS/Linux are out of scope for now.

- **It says `pywin32` / `pygetwindow` / `pypresence` missing.**  
  Re‑run the install step (Section 4). Make sure you used the **same Python** that runs the script.

- **Nothing updates / “Invalid pipe.”**  
  Make sure the **Discord app is open**. The script will **auto‑reconnect** if you close/reopen Discord.

- **Client ID error.**  
  Double‑check `DISCORD_CLIENT_ID` in `.env`. It must be your Application’s **numeric** ID.

- **It masks too much.**  
  Remove generic words (like `education` or `school`) from `MASK_TERMS`, or keep them if that’s what you prefer. You control it.

---

## Uninstall / Remove

- Stop the script with **Ctrl+C**.  
- Optionally remove the virtual environment (if you made one) and delete the folder/repo.

---

## License

MIT — do whatever you want, just don’t remove the copyright notice.
