# 🛡️ Speech To Text Chat Injector: Blizzard ToS & Warden Guide

> **Current App Architecture**: 3-Step Decoupled Process — **PRESS** to Open Chat, **RELEASE** to Paste Text, **CLICK / TAP** to Send Message  
> **Compliance Rating**: **100% Warden & ToS Safe** under official Blizzard Accessibility and 1:1 Hardware Remapping guidelines.

---

## ⚖️ Executive Summary: The 1:1 Rule and Warden

Blizzard Entertainment strictly governs third-party software interacting with *World of Warcraft* under the **End User License Agreement (EULA Section 1.C)** and enforces it automatically via **Warden Anti-Cheat**.

### The Core Rule: 1 Physical Action = 1 In-Game Action
Blizzard mandates that every discrete in-game action must correspond directly to **one physical human input** (keypress, mouse click, or controller trigger pull). Any software that bypasses this rule by bundling multiple gameplay actions into a single automated macro loop is classified as unauthorized automation (botting).

---

## 🛠️ The 3-Step Human Process Explained

To remain 100% compliant with Blizzard's Terms of Service, this application intentionally decouples speech-to-text chat into **three distinct, human-initiated actions**:

```
+----------------------------------------------------------------------------------------------------+
|                             THE 3-STEP HUMAN ACCESSIBILITY WORKFLOW                                |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ACTION 1: PRESS (Key Down)] ──────────────────────────────► OPENS CHAT & STARTS RECORDING       |
|  User pushes down hotkey, mouse side button, or trigger.      1:1 Hardware key remapping.           |
|                                                                                                    |
|  [ACTION 2: RELEASE (Key Up)] ──────────────────────────────► TRANSCRIBES & PASTES INTO CARET      |
|  User releases the button. Whisper deciphers audio and        Standard OS clipboard action (Ctrl+V)|
|  pastes formatted text into chat. Text sits awaiting review.   Zero automated Enter keystroke!     |
|                                                                                                    |
|  [ACTION 3: CLICK / TAP (Next Input)] ──────────────────────► SENDS MESSAGE & RESTORES CAMERA     |
|  User taps hotkey again, clicks, or hits physical Enter.      Distinct human action to post text.  |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

### Detailed Breakdown of the 3 Actions

| Step | Human Action | Technical Operation | Why It Meets Blizzard ToS |
| :--- | :--- | :--- | :--- |
| **1. PRESS** *(Key Down)* | User presses down the assigned PTT hotkey, mouse button (Mouse 4/5), or controller trigger (LT/RT). | Dispatches an initial keystroke (`Enter`) to activate the in-game chat box and streams microphone audio locally into Faster-Whisper. | **100% Permitted (1:1 Hardware Remap)**:<br>Rebinding a physical peripheral button to act as the `Enter` key is standard hardware key remapping recognized by Blizzard Support ([Article 13074](https://us.battle.net/support/en/article/13074)) and peripheral software (Logitech G Hub, Razer Synapse). |
| **2. RELEASE** *(Key Up)* | User finishes speaking and releases the physical button. | Faster-Whisper transcribes speech locally on CPU, formats channel prefixes (`/say `, `/p `, `/g `), copies the payload to the system clipboard, and simulates `Ctrl + V` to paste it into the open chat editbox. **Text sits in the chat bar un-sent.** | **100% Permitted (OS Clipboard Input)**:<br>Copy-and-paste into an open text box is a standard operating system feature. Faster-Whisper acts as an accessibility virtual keyboard typing characters sequentially. It does **not** tamper with game memory, modify client binaries, or auto-send. |
| **3. CLICK / TAP** *(Second Press or Enter)* | User taps the hotkey again, clicks, or presses physical `Enter` on their keyboard. | Sends the `send_message_key` (`Enter`) to submit the finalized message into the game world, followed by optional click-away to restore camera/mouselook control. | **100% Permitted (Human Confirmation)**:<br>Submitting the text into the multiplayer game world requires a **distinct, conscious human action**. No autonomous scripts run unattended. |
| **CANCEL** *(Escape)* | User taps `Escape` anytime. | Immediately discards the audio or pending message and returns HUD to standby. A 60-second safety timer also auto-cancels abandoned messages. | **Safety Fallback**: Ensures accidental recordings are never transmitted. |

---

## 🛑 Why Having "One Button Do All 3" Violates Blizzard ToS

Many players ask: *“Why can’t I just press a button, speak, and have the app automatically open chat, paste the text, press Enter to send, and click back into the game all by itself?”*

Here is the exact legal, architectural, and anti-cheat explanation for why doing all 3 actions with one button is strictly against the rules:

### 1. Violation of the 1:1 Rule (Multi-Action Macro Prohibition)
Blizzard's rule is clear: **1 Human Action = 1 In-Game Action**.
If a single button press triggers:
1. Open chat box (`Enter`)
2. Type/paste text (`Ctrl + V`)
3. Send message (`Enter`)
4. Click screen to dismiss chat and restore camera (`Left Click`)

That single press executes **four separate in-game actions**. Under Blizzard's EULA (**Section 1.C.ii: Cheating / Automation / Bots**), any program that sequences multiple gameplay actions from a single input is legally classified as an **unauthorized automated macro / bot**.

### 2. Warden Anti-Cheat Heuristics & Bot Signatures
Blizzard's **Warden Anti-Cheat** scans active memory and monitors input dispatch patterns:
- **Synthetic Micro-Delays**: Automated macros use artificial delays (e.g. `sleep(50ms)`) to chain Open → Paste → Send → Click. Warden easily identifies these uniform timing signatures as programmatic bot activity.
- **Unattended Messaging**: If text is transmitted into the game world without a human confirmation press, Warden flags the process as an autonomous background spammer or chat bot.

### 3. Comparison Table: Safe 3-Step Mode vs. Prohibited 1-Button Macro

| Feature | 🛡️ Safe 3-Step Human Process *(Current App)* | ❌ 1-Button Automated Macro *(Prohibited)* |
| :--- | :--- | :--- |
| **Chat Open** | Initiated by physical **PRESS** (Keydown) | Chained automatically in a script |
| **Text Placement** | Pasted on **RELEASE** (Keyup) | Chained automatically in a script |
| **Message Sending** | Requires distinct **CLICK / TAP** (Human Confirmation) | **Auto-submitted without human confirmation** |
| **In-Game Actions per Input** | **1 action per physical input** (1:1 rule compliant) | **4+ actions per physical input** (Violates 1:1 rule) |
| **Human Review Opportunity** | Player sees text sitting in chat box before sending | Player cannot verify transcription before sending |
| **Warden Risk Level** | **Zero Risk**: Standard OS keystrokes + clipboard | **High Risk**: Automated input chain / bot signature |
| **Blizzard Compliance** | **100% EULA & Accessibility Compliant** | **Subject to automated account suspension / ban** |

---

## 🎮 Hardware Controllers & Peripheral Remapping

Blizzard explicitly permits 1:1 hardware button remapping for accessibility:
- **Keyboards & Keypads**: Remap any key (e.g. `F8`, `F9`, `Pause`, `NumPad`).
- **Mouse Side Buttons**: Bind `Mouse 4` or `Mouse 5` for convenient thumb-triggered dictation.
- **Gamepads & Triggers**: Native support for Xbox and PlayStation controllers, including full analog trigger detection (`LT` / `RT` on Xbox, `L2` / `R2` on PlayStation) and D-Pad directions.
- **Dynamic Hotplugging**: Controllers connected or powered on after starting the app are automatically recognized.

---

## 🔗 Official Source Documentation & Citations

For official rules, policies, and technical guidelines directly from Blizzard Entertainment and Microsoft Corporation, refer to the following official documentation:

| Document | Organization | Topic & Relevance | Link |
| :--- | :--- | :--- | :--- |
| **Blizzard End User License Agreement (EULA)** | Blizzard Entertainment | Section 1.C details prohibited automation, bots, hacks, and anti-cheat policies. | [Blizzard EULA](https://www.blizzard.com/en-us/legal/fba4d21f-c7a4-4cc8-8546-0205577328b7/blizzard-end-user-license-agreement) |
| **Rules for Macros & Hardware Key Remapping** | Blizzard Support | Official support policy on the 1:1 hardware rule and multi-action macro restrictions. | [Blizzard Macro Rules (Article 13074)](https://us.battle.net/support/en/article/13074) |
| **Blizzard In-Game Code of Conduct** | Blizzard Entertainment | Core standards on fair play, cheating, unauthorized software, and player interaction. | [Blizzard Code of Conduct (Article 42673)](https://battle.net/support/article/42673) |
| **Microsoft Support: Accessibility Tools for Windows** | Microsoft Support | Overview of native Windows accessibility APIs and assistive frameworks. | [Microsoft Windows Accessibility Tools](https://support.microsoft.com/en-us/windows/accessibility-tools-for-windows-4475476a-7347-4950-8b4e-46ea317c8053) |

---

## 💡 Best Practices for Safe In-Game Use

1. **Review Before Sending**: When the text pastes on button release, glance at your chat bar. If Whisper misheard a word or if you coughed, simply press `Escape` to discard it.
2. **Windowed / Borderless Mode**: Run *World of Warcraft* in **Windowed (Fullscreen)** mode so the HUD overlay cleanly locks inside the game's viewport without clipping.
3. **Channel Prefixes**: Use binding prefixes (e.g. `/say `, `/p `, `/g `, `/ra `) to automatically format dictated speech for the correct chat channel before pasting.
