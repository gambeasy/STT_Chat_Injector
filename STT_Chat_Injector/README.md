# 🎙️ Speech To Text Chat Injector

> **High-speed, offline speech-to-text push-to-talk chat injector with 100% Blizzard ToS and Warden anti-cheat compliance.**  
> Transcribe your voice locally on CPU via Faster-Whisper, format channel prefixes (`/say`, `/p`, `/g`), and inject text seamlessly using keyboard, mouse, or gamepad combos.

---

## 📖 Overview

**Speech To Text Chat Injector** is a modern accessibility and communication tool designed for PC gamers and desktop users. It enables fast, hands-free chat dictation for games like *World of Warcraft* without risking anti-cheat penalties or account bans.

Unlike risky automated macro spammers, **Speech To Text Chat Injector** strictly adheres to Blizzard's **1:1 hardware rule** (1 physical human input = 1 in-game action) by decoupling the speech workflow into three distinct, human-initiated steps.

```
+----------------------------------------------------------------------------------------------------+
|                               THE 3-STEP HUMAN ACCESSIBILITY WORKFLOW                               |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ACTION 1: PRESS (Key Down)] ──────────────────────────────► OPENS CHAT & STARTS RECORDING        |
|  User holds down hotkey, mouse side button, or trigger.       1:1 Hardware key remap (Enter).       |
|                                                                                                    |
|  [ACTION 2: RELEASE (Key Up)] ──────────────────────────────► TRANSCRIBES & PASTES INTO CARET       |
|  User releases the button. Whisper deciphers audio and        Standard OS clipboard paste (Ctrl+V). |
|  pastes formatted text into chat. Text sits awaiting review.   Zero automated Enter keystroke!      |
|                                                                                                    |
|  [ACTION 3: CLICK / TAP (Next Input)] ──────────────────────► SENDS MESSAGE & RESTORES CAMERA      |
|  User taps hotkey again, clicks, or hits physical Enter.      Distinct human action to post text.   |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## ✨ Key Features

- 🛡️ **100% Blizzard ToS & Warden Safe**: Operates via standard OS keyboard/mouse simulation and clipboard pasting (`Ctrl + V`). Does **not** hook game binaries, inject DLLs, read game memory, or automate multi-action gameplay loops.
- ⚡ **Local Faster-Whisper CPU Engine**: Powered by `faster-whisper` with CPU `int8` quantization. Runs completely offline on your computer—zero cloud API costs, no internet latency, and no GPU/CUDA driver headaches.
- 🎮 **Universal Peripheral & Multi-Button Combo Support**:
  - **Keyboards**: Any key (`F8`, `F9`, `Pause`, `NumPad`, etc.) or modifier combo (`Ctrl + F8`, `Shift + R`).
  - **Mouse**: Side thumb buttons (`Mouse 4`, `Mouse 5`, `Middle Click`).
  - **Gamepads**: Full support for Xbox and PlayStation controllers, including face buttons, bumpers (`LB` / `RB`), D-Pad directions, stick clicks, and analog triggers (`LT` / `RT`, `L2` / `R2`).
  - **Press-and-Hold Combo Capture**: Easily bind multi-button combos (`LB + RB`, `LT + A`). The app waits for all held buttons to be released before finalizing the combination.
- 🖥️ **Floating HUD Overlay**:
  - Compact status pill with dynamic color states: `STANDBY` (Gold), `REC [HOLD]` (Red), `DECIPHERING...` (Yellow), and `PASTED [TAP TO SEND]` (Bright Green).
  - Can be locked directly inside the game window's viewport or dragged freely anywhere on screen.
  - Double-click to expand a quick in-game settings menu to swap microphones or rebind keys on the fly.
- 💬 **Channel Prefixes & Suffixes**:
  - Configure bindings with slash commands (e.g. `/say `, `/p `, `/g `, `/ra `, `/1 `) and suffixes (e.g. ` [over]`).
  - Automatically handles message chunking for 255-character in-game chat box limits.
- 🎯 **Multi-Application Profiles & Auto-Detection**:
  - Dedicated profiles for *World of Warcraft (Retail, Classic, Beta)* or any other PC game/application.
  - Built-in process scanner and auto-detector to bind settings to target windows.
- 🎚️ **Live Audio VU Meter**: Real-time microphone input volume indicator directly in the settings view to confirm mic sensitivity.

---

## 🛠️ System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10, 3.11, 3.12, or 3.13
- **Hardware**: Any modern multi-core CPU (Intel Core i3/i5/i7/i9 or AMD Ryzen)
- **Microphone**: Any standard USB headset, desktop microphone, or webcam mic

---

## 🚀 Quickstart & Installation

### 1. Clone or Download the Repository
Download the application files into a directory of your choice:
```powershell
cd "Speech-to-text_wow_app"
```

### 2. Run the Application
Run `STT-CI.py` using Python:
```powershell
python STT-CI.py
```
> **Automatic Dependency Bootstrap**: On first launch, the app automatically checks for and installs any missing Python libraries (`faster-whisper`, `sounddevice`, `customtkinter`, `pynput`, `pyautogui`, `pyperclip`, `pygame`, `psutil`, `numpy`).

---

## 🎮 How to Use

1. **Select Your Microphone**:
   - In the main window or quick menu, choose your preferred microphone from the audio input dropdown.
   - Speak into your mic to verify input levels on the live VU meter.
2. **Configure Your Bindings**:
   - In the **Bindings** list, click **Bind** on any row.
   - Press and hold your desired button or combination (e.g. `F8`, `Mouse 4`, or `LB + RB`).
   - Release all buttons to set the binding.
3. **Set Channel Prefixes**:
   - Enter your desired in-game slash command (e.g. `/p ` for Party chat or `/s ` for Say).
4. **Dictate In-Game**:
   - **Step 1 (Hold to Talk)**: Press and hold your binding. The chat box opens and recording begins (`REC [HOLD]`).
   - **Step 2 (Release to Paste)**: Let go of the button when you finish speaking. Whisper deciphers your audio and pastes the text into the chat bar (`PASTED [TAP TO SEND]`).
   - **Step 3 (Tap to Send)**: Tap the binding again (or press physical `Enter` on your keyboard) to submit the message into the game.
   - **Cancel Anytime**: Press `Escape` at any point to cancel recording or discard pending text.

---

## 🛡️ Blizzard ToS & Anti-Cheat Compliance

For full technical, legal, and anti-cheat documentation, please consult the included guide:
📄 **[Blizzard ToS & Warden Anti-Cheat Guide](TOS_AND_WARDEN_GUIDE.md)**

### Why This Workflow is 100% Compliant:
1. **1:1 Physical Action Rule**: Blizzard mandates that 1 human hardware action = 1 in-game action ([Support Article 13074](https://us.battle.net/support/en/article/13074)). By requiring a physical press to open chat, a release to paste, and a second press to send, the app avoids prohibited multi-action automated macro loops.
2. **Standard OS Clipboard**: Pasting text into an open caret via `Ctrl + V` is standard operating system accessibility behavior. Faster-Whisper functions as an assistive virtual keyboard typing characters sequentially.
3. **No DLL Injection or Memory Tampering**: The app runs entirely in user-space as an external assistive utility. It does not read, modify, or inject into *World of Warcraft* client memory.

---

## ⚙️ Configuration (`config.json`)

Settings and profiles are automatically saved to `config.json`. Example structure:
```json
{
    "global_settings": {
        "device_index": 1,
        "model_size": "base",
        "compute_device": "cpu"
    },
    "active_profile": "World of Warcraft",
    "app_profiles": {
        "World of Warcraft": {
            "name": "World of Warcraft",
            "target_process": "Wow.exe, WowClassic.exe",
            "tos_safe_mode": {
                "enabled": true,
                "auto_open_chat": true
            },
            "bindings": [
                {
                    "binding_name": "Say",
                    "input_id": "pad_btn_4",
                    "display_name": "Xbox LB / PS L1",
                    "prefix": "/say",
                    "suffix": ""
                },
                {
                    "binding_name": "Party Combo",
                    "input_id": "pad_btn_4+pad_btn_5",
                    "display_name": "Xbox LB / PS L1 + Xbox RB / PS R1",
                    "prefix": "/p",
                    "suffix": ""
                }
            ]
        }
    }
}
```

---

## 📄 License & Disclaimer

This project is an independent open-source accessibility tool and is **not** affiliated with, endorsed by, or associated with Blizzard Entertainment, Inc. or Microsoft Corporation. *World of Warcraft* is a registered trademark of Blizzard Entertainment, Inc.

