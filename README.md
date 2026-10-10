# project-melior
Hacktoberfest 2026 project 

## What is Melior

Melior is an assistive communication app for people with limited motor and speech abilities who can only move their head.

The user controls the app with head movements only. The app proposes what they probably want to say or need, and the user picks it. The chosen phrase is spoken out loud.

```
Webcam -> head tracking (MediaPipe Face Landmarker) -> gestures (move, dwell, nod, shake)
                                                          |
                          Gemma suggests 4-6 phrases / needs (JSON)
                                                          |
                                    user selects with the head   v
                                            ElevenLabs speaks it through the speakers
```

## Getting Started

To clone the repository, use one of the following commands:

**Using HTTPS:**
```bash
git clone https://github.com/jsfdez/project-melior.git
```

**Using SSH:**
```bash
git clone git@github.com:jsfdez/project-melior.git
```

### 🛠️ Setting Up the Sandbox

To ensure zero external dependencies and a fully isolated environment, this project uses a local Python virtual environment. **Do not install requirements globally.**

Run the provided setup script to initialize your sandbox:

```bash
chmod +x setup.sh
./setup.sh
```

### 🚀 Running the Project

To run any script within the project sandbox, use the `run.sh` utility. It automatically handles the virtual environment and updates dependencies if `requirements.txt` has changed.

```bash
chmod +x run.sh
./run.sh <path_to_script.py> [arguments...]
```

**Default Behavior:**
If no script is provided, it defaults to running `main.py`.

```bash
./run.sh
```
*(Runs main.py)*

```bash
./run.sh src/core/contracts.py
```
*(Runs the specific script)*

**📝 Debugging & Logs:**
All execution output (stdout and stderr) is automatically captured and saved to the `logs/` directory. If a command fails, check the latest `.log` file in that folder to diagnose the issue.

## 🛡️ Sandboxing & Isolation

This project is designed to run as a **self-contained sandbox**. 

* **Zero OOB Dependencies:** No system-level Python packages should be used. Everything required is listed in `requirements.txt` and installed within the local `venv/`.
* **Environment Isolation:** All sensitive configuration (API keys, endpoints) must be managed via a `.env` file, which is excluded from version control.
* **Predictable Environment:** By using the `setup.sh` script, every team member works in an identical, isolated environment, preventing "it works on my machine" issues.


## Use Claude Code

```bash
export ANTHROPIC_BASE_URL=https://bubbly-vermilion.netbird.apps.buildinmadrid.dev
export ANTHROPIC_API_KEY=none
claude --model=gemma-4-26b-a4b
```

## Application constraints

- Use Python
- Use Gemma-4-26b-a4b
- Use elevenlabs.io (mandatory)

## Application features

- Use webcam
- Use speakers
- Microphone: not in the MVP, possible future option

### How each one is used

| Feature | Used for |
|---|---|
| Webcam | Head tracking with MediaPipe Face Landmarker. Video is processed locally and never leaves the device |
| Microphone | Not used in the MVP. Future option: listen to the person talking to the user so Gemma can suggest replies |
| Speakers | Plays the phrase chosen by the user, generated with ElevenLabs |

### Interaction

Current implementation ("point and hold", head + long blink only):

| Gesture | Event | Action |
|---|---|---|
| Move the head slightly left / right / up / down and keep it there (~0.35 s) | `move` with `target_id` = `left`/`right`/`up`/`down` | Highlight that option |
| Keep the head still on it (~1.2 s) | `dwell` with the same `target_id` | Select it |
| Return to the center | (re-arms) | Ready for the next choice |
| Long blink (~0.6 s) | `back` | Go back / cancel |

Quick passes and jitter are ignored (direction must be stable before `move`, and the head can drift ~2.5° during the dwell). After a `dwell`, the head must return to the center before the next one. Short natural blinks are ignored.

Original ideas not implemented yet: nod = yes, shake = no.

Planned: One Euro filter and per-user ranges, because every user has a different range of movement.

## Vision & gestures (how to run)

Code: `src/vision/head_tracker.py` (webcam -> `VisionFrame`), `src/interaction/gesture_engine.py` (`VisionFrame` -> `GestureEvent`), `demo_gestures.py` (live demo), `tests/test_gesture_engine.py`.

```bash
./setup.sh                                  # Linux/macOS; on Windows: python -m venv venv && venv\Scripts\pip install -r requirements.txt
python demo_gestures.py                     # Esc quits, R recalibrates the neutral pose
python -m unittest discover -s tests -t .   # tests (no camera needed)
```

Windows quick launch (from the repo folder): `.\venv\Scripts\python.exe demo_gestures.py`.
The demo needs the GUI build of OpenCV (`opencv-python`); `requirements.txt` lists `opencv-python-headless`, which has no window. `HeadTracker` and `GestureEngine` work with either. If the demo says `imshow` is missing: `pip uninstall -y opencv-python-headless && pip install opencv-python`.
Events: `move` (direction highlighted), `dwell` (held still ~1 s = select), `back` (long blink). Selecting by holding a direction matches `ArbolConversacion.md`; "Back" is the long blink instead of holding the center.

The first run downloads `models/face_landmarker.task` (~4 MB, git-ignored). Tested with Python 3.14 and `mediapipe` 1.1.0.

Usage from the main loop:

```python
from src.vision.head_tracker import HeadTracker
from src.interaction.gesture_engine import GestureEngine

engine = GestureEngine()
with HeadTracker() as tracker:
    while True:
        frame, vision_frame = tracker.read()      # vision_frame is None if no face is visible
        for event in engine.update(vision_frame):  # GestureEvent("move"|"dwell", "left"...) / ("back")
            ...
```

How it works:

- Head pose (yaw/pitch/roll in degrees) comes from the Face Landmarker facial transformation matrix; the blink score is the mean of the `eyeBlinkLeft`/`eyeBlinkRight` blendshapes.
- The neutral pose is learned from the first ~1.5 s (keep still, looking at the screen). Gestures are measured relative to it.
- Tunables are in `GestureConfig`: `yaw_deg`/`pitch_deg` (how far to move, lower = more sensitive), `stable_s` (time before highlighting), `dwell_s` (stillness to select), `still_deg`, blink threshold/duration, smoothing.
- If directions come out inverted on your camera, flip `yaw_sign` / `pitch_sign` (defaults are already flipped for a typical webcam).
- Timestamps passed to `detect_for_video` must always increase; `HeadTracker` guarantees it.

Known to verify with real users: angle thresholds and the long-blink duration.

## Architecture

- **Head tracking:** MediaPipe Face Landmarker (Python). Head pose from the facial transformation matrix, optional blendshapes (blink, jaw open) as alternative gestures.
- **Gestures:** a gesture engine separated from the UI that emits simple events (`move`, `dwell`, `nod`, `shake`), so it can be tested without Gemma or ElevenLabs.
- **LLM:** Gemma via the OpenAI-compatible endpoint below. It must answer with a short JSON list of options. It never speaks on behalf of the user without a selection.
- **Voice:** ElevenLabs text-to-speech (mandatory), with a cache for frequent phrases to cut latency and cost. The API key stays in an environment variable.
- **Fallback:** a small set of critical phrases (pain, help, emergency) prerecorded or spoken with a local TTS if the network or the LLM is down.

## To make LLM requests

```bash
curl https://bubbly-vermilion.netbird.apps.buildinmadrid.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.5",
    "messages": [
      { "role": "user", "content": "What is NetBird Agent Network?" }
    ]
  }'
```

Note: the model name in this example comes from the template. For Melior use `gemma-4-26b-a4b`.

## Configuration

Keep these out of the code (environment variables):

| Variable | Purpose |
|---|---|
| `LLM_BASE_URL` | Gemma endpoint (`https://bubbly-vermilion.netbird.apps.buildinmadrid.dev`) |
| `LLM_MODEL` | `gemma-4-26b-a4b` |
| `ELEVENLABS_API_KEY` | ElevenLabs key |
| `ELEVENLABS_VOICE_ID` | Voice to use |

## Privacy and safety

- Camera video is processed on the device only.
- Send the LLM and ElevenLabs only the minimum text needed. No personal or health data while the LLM endpoint is shared.
- Critical actions (emergency, alert) need a confirmation to avoid false positives.

## Open decisions

- [x] **UI in Python:** Decided on Pygame for a desktop-based interface.
- [x] **Web version:** Not a priority for the initial MVP.
- [x] **MVP level:** Microphone support is out of scope for the current MVP.
- [x] **Repo structure and how to run:** Documented in the Overview section.
- [ ] **First real user / therapist** to validate the interaction.
- [ ] **Languages:** Spanish first, English later?
- [ ] **Emergency fallback:** which phrases and which local voice?
- [ ] **Voice:** generic ElevenLabs voice or a cloned one (needs consent)?

## Team Roles & Implementation

To enable parallel development, the project is divided into four functional layers:

### 1. Vision & Signal Specialist (The "Eyes")
**Focus:** Capturing and stabilizing raw movement data.
*   **Tasks:** MediaPipe Face Landmarker implementation, head pose calculation, smoothing/filtering (One Euro filter), and user calibration.
*   **Stack:** OpenCV, MediaPipe, NumPy.

### 2. Interaction & Gesture Engineer (The "Brain")
**Focus:** Turning raw movement into meaningful intent.
*   **Tasks:** Gesture engine (move, dwell, nod, shake), application state machine, and gesture timing/dead-zone logic.
*   **Stack:** Python (asyncio/event loops).

### 3. Intelligence & Voice Integrator (The "Voice & Mind")
**Focus:** Managing the conversation and audio output.
*   **Tasks:** Gemma LLM integration, ElevenLabs TTS implementation, phrase caching, and emergency fallback logic.
*   **Stack:** `httpx`/`requests`, JSON, local caching.

### 4. Interface & UX Developer (The "Face")
**Focus:** Creating the visual environment for the user.
*   **Tasks:** UI implementation (Web or Desktop), visual gesture feedback, and suggestion board rendering.
*   **Stack:** FastAPI/NiceGUI (Web) or Pygame/Tkinter (Desktop).

## Roadmap

1. Prototype: webcam + smoothed cursor + dwell + 6 buttons + ElevenLabs speech (no Gemma).
2. Add Gemma suggestions through the endpoint above.
3. Future option: microphone input (speech-to-text) and replies to what the other person says.
4. Calibration, fallback mode and tests with a real user.

## Technical Component Overview

This section describes the core software components and their responsibilities.

### Vision & Signal Processing

*   **`HeadTracker` (`src/vision/head_tracker.py`)**: Uses MediaPipe Face Landmarker to capture webcam frames. It computes the facial transformation matrix to derive head pose (pitch, yaw, roll) and calculates a blink score from eye blendshapes.
*   **`VisionWorker` (`src/core/vision_worker.py`)**: A background `threading.Thread` that manages the `HeadTracker` lifecycle. It continuously reads from the camera and pushes `VisionFrame` objects (containing pose, blink, and the image) into a thread-safe `queue.Queue`.

### Interaction & Gestures

*   **`GestureEngine` (`src/interaction/gesture_engine.py`)**: Consumes `VisionFrame` data to detect semantic gestures. It uses Exponential Moving Average (EMA) smoothing for head pose and implements a state machine to trigger `move` (based on angle thresholds) and `back` (based on long-blink duration) events. It manages a "neutral pose" learned during an initial calibration period.

### User Interface

*   **`DesktopApp` (`src/interface/desktop_interface.py`)**: A Pygame-based graphical interface. It runs a main loop that:
    1.  Consumes the latest `VisionFrame` from the input queue (discarding older ones to minimize latency).
    2.  Updates the UI with the camera feed.
    3.  Processes detected `GestureEvent`s via the `GestureEngine`.
    4.  Displays status information and a log of recent events.

### Orchestration

*   **`main.py`**: The entry point of the application. It orchestrates the lifecycle of the `VisionWorker` thread and the `DesktopApp` main loop, ensuring a graceful shutdown of all components.
