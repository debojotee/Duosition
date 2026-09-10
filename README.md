# Duosition

Real-time macOS wallpaper viewer inspired by the foldable **Apple iPhone Duo** fold transition, reacting dynamically to your MacBook Pro's physical lid angle ($0^\circ \text{--} 180^\circ$).

---

## Inspiration

Inspired by the folding screen transition of the **iPhone Duo**, **Duosition** brings that fluid, physical fold aesthetic to the MacBook display. As you fold or tilt the laptop lid, the wallpaper transforms in real time to match the hinge motion:

* **Fold Skew & Vertical Drop**: Adapts to the physical angle with realistic perspective skew and trigonometric vertical height compensation ($1 - \sin\theta$).
* **Frosted Glass Blur**: A smooth optical blur pane glides across the screen as the fold angle changes.
* **Natural Edge Bleed**: The blurred edges bleed softly into the black canvas without harsh scissor cuts, while crisp areas stay razor-sharp.
* **Atmospheric Depth**: Subtle gradient depth trailing the fold line.
* **Pure Image**: 100% borderless, full-screen, zero text.

---

## Quick Start

### 1. Requirements
* macOS (Apple Silicon MacBook Pro / Air with lid angle sensor)
* Python 3.9+
* Install Pillow:
  ```bash
  pip install Pillow
  ```

### 2. Set Wallpaper
Drop your image into the `images/` folder and name it **`target.png`** (or `target.jpg`):
```bash
images/target.png
```

### 3. Run

**Interactive Slider Mode** (test the transition manually):
```bash
python3 image_viewer.py
```

**Live Sensor Mode** (reacts to your physical MacBook lid):
```bash
python3 main.py
```

---

## Configuration

Tweak top-level variables at the top of [`image_viewer.py`](image_viewer.py):

* **`TARGET_RESOLUTION`** (Line 40):
  * Set to `"native"`, `"1080p"`, `"720p"`, `"860p"`, or any custom pixel width.
* **`ENABLE_PAGE_VERTICAL_EXPANSION`** (Line 48):
  * `True`: Height expands upward based on $1 - \sin(\theta)$ as the screen tilts down.
  * `False`: Boundaries remain fixed at screen borders.
* **`SKEW_FACTOR`** (Line 58):
  * Controls the perspective taper intensity (default `0.25`).
* **Black Gradient**:
  * Inside `_apply_directional_gradient_blur()`: tweak `black_delay`, `darkness`, or set `darkness = 0.0` to turn it off.

---

## Project Files

* **`image_viewer.py`**: Full-screen viewer with perspective transform, blur pyramid, and slider.
* **`main.py`**: Real-time monitor querying the MacBook lid angle sensor.
* **`Hinge_angle.py`**: macOS IOKit driver reading the physical hinge sensor.
* **`images/target.png`**: Active wallpaper image.
