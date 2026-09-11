"""
Duosition (Fullscreen 3024x1964 Light Minimalist Architecture)
- When run directly (python3 image_viewer.py):
    Enables an interactive slider to test skew & dynamic blur with fluid motion.
- When run via main.py:
    Updates dynamically based on the hinge angle from the sensor.

Visual Behavior:
- Fullscreen Fit: Fills the entire display with zero borders.
- Pure Image Display: No text, no labels, only the pure aesthetic wallpaper.
- Fixed Top & Bottom: Vertical screen boundaries (y=0 and y=canvas_h) stay permanently fixed.
- Skewness: Preserved horizontal perspective trapezoid (1.0 - 0.25 * delta).
- Slow Black Gradient: Atmospheric black gradient descends from top to bottom (< 90°) or ascends from bottom to top (> 90°).
- Frosted Glass Pane: Blur glides down/up smoothly across the entire width.
- Soft Feathered Side Edges: Slanted trapezoid borders dissolve gently into black without hard lines.
- At 90°: Pristine, full-screen, unskewed, unblurred light wallpaper.

Closing window or pressing Ctrl+C exits cleanly.
"""

import os
import sys
import glob
import math
import tkinter as tk
from PIL import Image, ImageTk, ImageFilter, ImageChops

# ==============================================================================
# RESOLUTION CONFIGURATION
# ==============================================================================
# Set your desired resolution preset or pixel width:
#   "860p"   : ~1376x860 (Ultra-lightweight & fluid motion)
#   "720p"   : 1280x720  (Standard HD, 50-60 FPS)
#   "1080p"  : 1920x1080 (Full HD, crisp balance)
#   "1440p"  : 2560x1440 (2K Quad HD)
#   "4k"     : 3840x2160 (Ultra HD 4K)
#   "native" : 100% native screen pixels (no downscaling)
#   or any integer width: e.g. 860, 1080, 1280, 1920, 2560, 3024
# ==============================================================================
TARGET_RESOLUTION = "native"

# ==============================================================================
# PHYSICAL UPRIGHT PAGE PROJECTION (< 90°)
# ==============================================================================
# When True, the image height increases as the screen drops:
#   drop = canvas_h * (1.0 - sin(theta))
#   y_top = -drop, y_bottom = canvas_h (bottom anchored, height grows upward)
ENABLE_PAGE_VERTICAL_EXPANSION = True

# ==============================================================================
# SKEWNESS CONFIGURATION
# ==============================================================================
# Dynamic skew scaling following (1 - sin(theta)):
# Starts gentle at SKEW_MIN around 90°, accelerating to SKEW_MAX as the lid folds toward 0°.
#   SKEW_MIN = 0.25 : Subtle baseline perspective near upright typing angles
#   SKEW_MAX = 0.45 : Deep iPhone Duo fold perspective at sharp angles (try 0.45 - 0.55)
SKEW_MIN = 0.25
SKEW_MAX = 0.90
SKEW_FACTOR = SKEW_MAX  # Backward compatibility reference



def parse_resolution(val, canvas_w=None):
    """
    Parses a resolution setting into an integer pixel width.
    Supports presets ('860p', '720p', '1080p', '1440p', '2k', '4k', 'native')
    or raw integers (860, 1080, 1280, 1920, etc.).
    """
    if val is None or str(val).strip().lower() == "native":
        return canvas_w if canvas_w else 3024

    if isinstance(val, (int, float)):
        return int(val)

    s = str(val).strip().lower()
    presets = {
        "480p": 854,
        "720p": 1280,
        "hd": 1280,
        "860p": 1376,
        "1080p": 1920,
        "fhd": 1920,
        "1440p": 2560,
        "2k": 2560,
        "4k": 3840,
        "uhd": 3840,
        "native": canvas_w if canvas_w else 3024,
    }
    if s in presets:
        return presets[s]

    if s.endswith("p"):
        try:
            h = int(s[:-1])
            return int(h * 16.0 / 10.0)
        except ValueError:
            pass

    try:
        return int(s)
    except ValueError:
        return 1920


# Precomputed 256-point cosine lookup table for instant C-speed fades
COS_LUT = [int(255 * 0.5 * (1.0 + math.cos(math.pi * i / 255))) for i in range(256)]


def solve_perspective_coeffs(src_coords, dst_coords):
    """
    Computes 8 projective transform coefficients mapping dst -> src
    using pure Python Gaussian elimination.
    """
    matrix = []
    for (sx, sy), (dx, dy) in zip(src_coords, dst_coords):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])

    A = [row[:] for row in matrix]
    B = []
    for sx, sy in src_coords:
        B.extend([sx, sy])

    n = 8
    for i in range(n):
        max_el = abs(A[i][i])
        max_row = i
        for k in range(i + 1, n):
            if abs(A[k][i]) > max_el:
                max_el = abs(A[k][i])
                max_row = k
        A[i], A[max_row] = A[max_row], A[i]
        B[i], B[max_row] = B[max_row], B[i]

        pivot = A[i][i]
        if abs(pivot) < 1e-9:
            pivot = 1e-9

        for k in range(i + 1, n):
            c = -A[k][i] / pivot
            for j in range(i, n):
                if i == j:
                    A[k][j] = 0
                else:
                    A[k][j] += c * A[i][j]
            B[k] += c * B[i]

    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = B[i] / (A[i][i] if abs(A[i][i]) > 1e-9 else 1e-9)
        for k in range(i - 1, -1, -1):
            B[k] -= A[k][i] * x[i]

    return x


def parse_angle(angle):
    """
    Extracts a float angle from raw inputs (float, int, or tuple).
    """
    if angle is None:
        return None
    if isinstance(angle, (tuple, list)):
        if len(angle) >= 2:
            val = angle[1]
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None
            return None
        elif len(angle) == 1:
            return parse_angle(angle[0])
    try:
        return float(angle)
    except (ValueError, TypeError):
        return None


class LidImageViewer:
    def __init__(
        self,
        image_folder="images",
        image_path=None,
        window_width=1000,
        window_height=650,
        show_slider=False,
        resolution=TARGET_RESOLUTION,
    ):
        self.image_folder = image_folder
        self.image_path = image_path
        self.window_width = window_width
        self.show_slider = show_slider
        self.window_height = window_height + (35 if show_slider else 0)
        self.resolution = resolution
        self.current_angle = 90.0
        self.is_running = True
        self.photo_tk = None
        self._last_w = self.window_width
        self._last_h = self.window_height
        self._canvas_img_id = None

        # Throttling / requestAnimationFrame job handle for fluid dragging
        self._render_job = None
        self._pending_angle = None
        self._is_dragging = False
        self._settle_job = None
        self._smooth_angle = None

        # Load source image (3024x1964 target.png)
        self.source_image = self._load_image()
        self._display_source = None
        self._blur_pyramid = {}
        self._cached_dims = (0, 0)
        self._cached_res = None

        # Initialize Tkinter Window with pure black background
        self.root = tk.Tk()
        self.root.title("Duosition")
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.minsize(400, 300)
        self.root.configure(bg="#000000")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Bottom manual slider (only in manual test mode, minimal without text)
        self.slider = None
        if self.show_slider:
            slider_frame = tk.Frame(self.root, bg="#000000")
            slider_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=2)

            self.angle_var = tk.DoubleVar(value=90.0)
            self.slider = tk.Scale(
                slider_frame,
                from_=10.0,
                to=170.0,
                resolution=0.5,
                orient=tk.HORIZONTAL,
                variable=self.angle_var,
                command=self._on_slider_change,
                bg="#000000",
                fg="#666666",
                activebackground="#ffffff",
                highlightthickness=0,
                troughcolor="#1a1a1a",
                showvalue=False,
                bd=0,
            )
            self.slider.pack(fill=tk.X, expand=True)

            self.slider.bind("<Button-1>", self._on_drag_start)
            self.slider.bind("<ButtonRelease-1>", self._on_drag_end)

        # Canvas for drawing full screen image (NO TEXT, PURE IMAGE)
        canvas_h = self.window_height - (35 if show_slider else 0)
        self.canvas = tk.Canvas(
            self.root,
            width=self.window_width,
            height=canvas_h,
            bg="#000000",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind resize event to dynamically rescale image on maximize or resize
        self.canvas.bind("<Configure>", self._on_resize)

        # Force initial layout calculation
        self.root.update_idletasks()

        # Initial render
        self.render(self.current_angle)
        self.root.update_idletasks()
        self.root.update()

    def _on_drag_start(self, event=None):
        self._is_dragging = True

    def _on_drag_end(self, event=None):
        self._is_dragging = False
        if self.is_running:
            self.render(self.current_angle, interactive=False)

    def _on_resize(self, event):
        """Called automatically when window is resized or maximized."""
        if abs(event.width - self._last_w) > 4 or abs(event.height - self._last_h) > 4:
            self._last_w = event.width
            self._last_h = event.height
            self.render(self.current_angle, interactive=False)

    def _on_slider_change(self, val):
        """
        Event-coalescing slider handler:
        Schedules next render as soon as idle, eliminating event queue lag.
        """
        self._pending_angle = float(val)
        if not self._render_job:
            self._render_job = self.root.after(1, self._process_pending_render)

    def _process_pending_render(self):
        self._render_job = None
        if self._pending_angle is not None and self.is_running:
            angle = self._pending_angle
            self._pending_angle = None
            self.render(angle, interactive=self._is_dragging)

    def _load_image(self):
        """
        Loads the image with the target name from the images folder.
        Simply name/rename your image 'target.png' in the 'images/' folder.
        """
        if self.image_path and os.path.exists(self.image_path):
            return Image.open(self.image_path).convert("RGB")

        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder, exist_ok=True)

        # Priority: target.png, target.jpg, target.jpeg, target.webp
        target_names = ["target.png", "target.jpg", "target.jpeg", "target.webp"]
        for name in target_names:
            path = os.path.join(self.image_folder, name)
            if os.path.exists(path):
                return Image.open(path).convert("RGB")

        # Fallback to any image in images/ folder
        valid_exts = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")
        for ext in valid_exts:
            matches = glob.glob(os.path.join(self.image_folder, ext))
            if matches:
                return Image.open(matches[0]).convert("RGB")

        # Default light minimalist background (3024x1964)
        return Image.new("RGB", (3024, 1964), color=(245, 243, 240))

    def close(self):
        """Closes the window and marks the viewer as stopped."""
        self.is_running = False
        if self._render_job:
            try:
                self.root.after_cancel(self._render_job)
            except Exception:
                pass
            self._render_job = None
        if self._settle_job:
            try:
                self.root.after_cancel(self._settle_job)
            except Exception:
                pass
            self._settle_job = None
        try:
            self.root.destroy()
        except Exception:
            pass

    def compute_destination_quad(self, angle_deg, canvas_w, canvas_h):
        """
        Calculates destination coordinates [TL, TR, BR, BL]:
        - Fullscreen: Fills the entire screen vertically from y=0 to y=canvas_h.
        - Top & Bottom vertical positions stay permanently fixed (top does not come down, bottom does not come up).
        - Horizontal skewness (1.0 - 0.25 * delta) active on width.
        """
        clamped_angle = max(5.0, min(175.0, angle_deg))

        base_w = canvas_w
        base_h = canvas_h
        xc = canvas_w / 2.0

        if clamped_angle <= 90.0:
            rad = math.radians(clamped_angle)
            t_drop = 1.0 - math.sin(rad)  # 0.0 at 90°, accelerates as lid closes

            if ENABLE_PAGE_VERTICAL_EXPANSION:
                # Upright Standing Page Projection:
                # As screen tilts forward, physical screen top drops by 1 - sin(theta).
                # Bottom stays anchored at screen bottom (y=canvas_h).
                # Height increases upward (y_top = -drop), with top cropped off-screen.
                drop = canvas_h * t_drop
                y_top = -drop
                y_bottom = canvas_h
            else:
                y_bottom = canvas_h
                y_top = 0

            # Angle decreased (< 90°):
            # Dynamic skewness linked to (1 - sin(theta)):
            # Starts at SKEW_MIN (0.25) near 90° and smoothly accelerates to SKEW_MAX (0.45-0.55) as screen folds
            current_skew = SKEW_MIN + (SKEW_MAX - SKEW_MIN) * t_drop
            top_w = base_w * max(0.18, 1.0 - current_skew * t_drop)
            bot_w = base_w
        else:
            # Angle increased (> 90°): only for < 90° vertical expansion
            y_bottom = canvas_h
            y_top = 0
            # Bottom width shrinks inward symmetrically
            rad = math.radians(clamped_angle)
            t_tilt = 1.0 - math.sin(rad)
            current_skew = SKEW_MIN + (SKEW_MAX - SKEW_MIN) * t_tilt
            bot_w = base_w * max(0.18, 1.0 - current_skew * t_tilt)
            top_w = base_w

        tl = (xc - top_w / 2.0, y_top)
        tr = (xc + top_w / 2.0, y_top)
        br = (xc + bot_w / 2.0, y_bottom)
        bl = (xc - bot_w / 2.0, y_bottom)

        return [tl, tr, br, bl]

    def _prepare_display_buffers(self, canvas_w, canvas_h):
        """
        Builds working display buffer and precomputed blur pyramid based on configured resolution.
        """
        target_w = parse_resolution(self.resolution, canvas_w)
        max_working_w = min(target_w, canvas_w) if canvas_w else target_w
        scale = max_working_w / max(1, self.source_image.width)
        scaled_w = max(10, int(self.source_image.width * scale))
        scaled_h = max(10, int(self.source_image.height * scale))

        self._display_source = self.source_image.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

        # Precompute heavy blur levels
        self._blur_pyramid = {}
        for r in (8, 18, 30, 45, 65, 85, 110):
            self._blur_pyramid[r] = self._display_source.filter(
                ImageFilter.BoxBlur(r)
            ).filter(ImageFilter.BoxBlur(max(3, r // 2)))

        self._cached_dims = (canvas_w, canvas_h)
        self._cached_res = self.resolution

    def _apply_directional_gradient_blur(self, angle_deg):
        """
        Frosted Glass Pane + Smooth Black Gradient + Localized Edge Feathering:
        - Starts seamlessly at 90°: blur starts first, black starts shortly after.
        - Blurred edge spreads wide; crisp edge narrows.
        - Localized side feathering: ONLY the blurred portion of the edges is feathered;
          the rest of the edges (ahead of the glass pane) are 100% crisp and sharp!
        """
        diff = abs(angle_deg - 90.0)
        if diff < 0.2:
            return self._display_source

        disp_w, disp_h = self._display_source.size
        delta = min(1.0, diff / 80.0)

        # 1. Blur lookup from precomputed pyramid
        target_r = max(8, int(delta * 110))
        closest_r = min(self._blur_pyramid.keys(), key=lambda k: abs(k - target_r))
        blurred = self._blur_pyramid[closest_r]

        # 2. Frosted glass pane leading edge progression
        pane_pos = min(1.0, delta * 1.25)
        softness = min(0.25, max(0.06, pane_pos * 0.6))

        mask_1d = bytearray(256)
        for i in range(256):
            y = i / 255.0
            if angle_deg > 90.0:
                y = 1.0 - y

            if y <= pane_pos - softness:
                # Fully behind the frosted glass pane: 100% blurred
                mask_1d[i] = 255
            elif y <= pane_pos:
                # Soft transition edge of the frosted pane (Hermite smoothstep)
                t = (pane_pos - y) / softness
                smooth = t * t * (3.0 - 2.0 * t)
                mask_1d[i] = int(255 * smooth)
            else:
                # Ahead of the glass pane: 100% crisp and sharp
                mask_1d[i] = 0

        glass_mask = Image.frombytes("L", (1, 256), bytes(mask_1d)).resize((disp_w, disp_h), Image.Resampling.BILINEAR)
        content_blended = Image.composite(blurred, self._display_source, glass_mask)

        # 3. Slow black gradient: starts shortly after blur starts, trailing closely behind the blur
        # -----------------------------------------------------------------------------------------
        # MANUAL TUNING GUIDE FOR BLACK GRADIENT:
        # - black_delay (default 0.012): Controls WHEN black starts (~1.0° after 90°). Smaller = starts earlier.
        # - darkness base (default 0.15): Initial darkness kick once delay is passed.
        # - darkness exponent (default 0.5): Darkness ramp shape. 0.5 = fast onset, 1.0 = linear.
        # - darkness scale (default 0.85): Max darkness factor (base 0.15 + 0.85 = 1.0 pure black).
        # - grad_depth factor (default 0.90): How deep into the screen black extends relative to the glass pane.
        # -----------------------------------------------------------------------------------------
        black_delay = 0.0000012  # ~1.0 degree delay
        dark_1d = bytearray(256)
        if delta > black_delay:
            t_black = (delta - black_delay) / (1.0 - black_delay)
            # Smoothly ramps up darkness so it has good presence early without a sudden pop
            #darkness = min(1.0, 0.15 + (t_black ** 0.5) * 0.85)
            darkness = 0.0
            grad_depth = min(1.0, max(0.04, pane_pos * 0.90))
            for i in range(256):
                y = i / 255.0
                if angle_deg > 90.0:
                    y = 1.0 - y
                if y < grad_depth:
                    p = y / grad_depth
                    lut_idx = int(255 * p)
                    dark_1d[i] = int(COS_LUT[lut_idx] * darkness)
                else:
                    dark_1d[i] = 0

        dark_mask = Image.frombytes("L", (1, 256), bytes(dark_1d)).resize((disp_w, disp_h), Image.Resampling.BILINEAR)

        # 4. Black atmospheric gradient:
        # Composites pure black from the top/bottom downwards without pinching or shrinking the side edges inward
        pure_black = Image.new("RGB", (disp_w, disp_h), color=(0, 0, 0))
        return Image.composite(pure_black, content_blended, dark_mask)

    def render(self, angle_deg, interactive=False):
        """Transforms and displays the image full-screen with zero borders and zero text."""
        if not self.is_running:
            return

        self.current_angle = angle_deg

        canvas_w = self.canvas.winfo_width()
        if canvas_w <= 10:
            canvas_w = self.window_width
        canvas_h = self.canvas.winfo_height()
        if canvas_h <= 10:
            canvas_h = self.window_height - (35 if self.show_slider else 0)

        # Refresh working buffer and blur pyramid if window dimensions or resolution changed
        target_dims = (canvas_w, canvas_h)
        if self._cached_dims != target_dims or self._cached_res != self.resolution or self._display_source is None:
            self._prepare_display_buffers(canvas_w, canvas_h)

        diff = abs(angle_deg - 90.0)
        dst_quad = self.compute_destination_quad(angle_deg, canvas_w, canvas_h)
        disp_w, disp_h = self._display_source.size

        try:
            if diff < 0.2:
                # FAST-PATH: Angle is 90° upright full screen (no perspective warp, zero blur)
                rendered_img = self._display_source.resize((canvas_w, canvas_h), Image.Resampling.BILINEAR)
                pos_x, pos_y = 0, 0
            else:
                # Directional gradient blur + slow black gradient
                processed = self._apply_directional_gradient_blur(angle_deg)

                # Resolution Pipeline based on self.resolution setting
                target_w = parse_resolution(self.resolution, canvas_w)
                if interactive and target_w > 1024:
                    max_render_w = 1024  # Fluid 50+ FPS responsiveness during active dragging
                else:
                    max_render_w = target_w

                render_scale = min(1.0, float(max_render_w) / max(1, canvas_w))
                rw = int(canvas_w * render_scale)
                rh = int(canvas_h * render_scale)

                delta = min(1.0, diff / 80.0)
                edge_r = max(2, int(delta * 22 * render_scale))
                edge_pad = edge_r + 4

                dst_quad = self.compute_destination_quad(angle_deg, rw, rh)
                xs = [p[0] for p in dst_quad]
                ys = [p[1] for p in dst_quad]
                bx0 = max(0, int(min(xs)) - edge_pad)
                by0 = max(0, int(min(ys)) - edge_pad)
                bx1 = min(rw, int(max(xs)) + 1 + edge_pad)
                by1 = min(rh, int(max(ys)) + 1 + edge_pad)
                rbw, rbh = max(10, bx1 - bx0), max(10, by1 - by0)

                dst_quad_bbox = [(x - bx0, y - by0) for x, y in dst_quad]
                src_quad = [(0, 0), (disp_w, 0), (disp_w, disp_h), (0, disp_h)]

                coeffs = solve_perspective_coeffs(src_quad, dst_quad_bbox)
                warped = processed.transform(
                    (rbw, rbh),
                    Image.Transform.PERSPECTIVE,
                    coeffs,
                    Image.Resampling.BILINEAR,
                )

                # Edge spread: Blurs the warped image boundary so the edge spreads naturally into the black canvas
                warped_blurred = warped.filter(ImageFilter.BoxBlur(edge_r))

                # Vertical glass pane transition mask
                pane_pos = min(1.0, delta * 1.25)
                softness = min(0.25, max(0.06, pane_pos * 0.6))
                mask_1d = bytearray(256)
                for i in range(256):
                    y = i / 255.0
                    if angle_deg > 90.0:
                        y = 1.0 - y
                    if y <= pane_pos - softness:
                        mask_1d[i] = 255
                    elif y <= pane_pos:
                        t = (pane_pos - y) / softness
                        mask_1d[i] = int(255 * t * t * (3.0 - 2.0 * t))
                    else:
                        mask_1d[i] = 0

                vert_mask = Image.frombytes("L", (1, 256), bytes(mask_1d)).resize((rbw, rbh), Image.Resampling.BILINEAR)

                # Composite: blurred edge spreads outward into the black canvas in blurred zone; crisp zone remains 100% sharp
                rendered_hd = Image.composite(warped_blurred, warped, vert_mask)

                if render_scale < 1.0:
                    final_bw = int(rbw / render_scale)
                    final_bh = int(rbh / render_scale)
                    resample_mode = Image.Resampling.NEAREST if interactive else Image.Resampling.BILINEAR
                    rendered_img = rendered_hd.resize((final_bw, final_bh), resample_mode)
                    pos_x = int(bx0 / render_scale)
                    pos_y = int(by0 / render_scale)
                else:
                    rendered_img = rendered_hd
                    pos_x, pos_y = bx0, by0

            self.photo_tk = ImageTk.PhotoImage(rendered_img)
            self.canvas.image = self.photo_tk

            if self._canvas_img_id is None:
                self._canvas_img_id = self.canvas.create_image(pos_x, pos_y, anchor=tk.NW, image=self.photo_tk)
            else:
                self.canvas.coords(self._canvas_img_id, pos_x, pos_y)
                self.canvas.itemconfig(self._canvas_img_id, image=self.photo_tk)

        except Exception as e:
            print(f"Render error: {e}")

    def set_resolution(self, resolution):
        """Allows dynamically changing resolution at runtime (e.g. '860p', '1080p', '4k', 'native')."""
        self.resolution = resolution
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w > 10 and canvas_h > 10:
            self._prepare_display_buffers(canvas_w, canvas_h)
            self.render(self.current_angle, interactive=False)

    def update(self, angle):
        """
        Updates the image with a new angle from main.py.
        Returns False if the window was closed.
        """
        if not self.is_running:
            return False

        angle_val = parse_angle(angle)
        if angle_val is not None:
            if self.slider is not None:
                self.angle_var.set(angle_val)

            # Smooth exponential interpolation to bridge discrete sensor steps
            if self._smooth_angle is None:
                self._smooth_angle = angle_val
            else:
                diff_a = angle_val - self._smooth_angle
                if abs(diff_a) > 0.05:
                    self._smooth_angle += diff_a * 0.75
                else:
                    self._smooth_angle = angle_val

            is_moving = abs(angle_val - self.current_angle) > 0.05
            self.render(self._smooth_angle, interactive=is_moving)

            if is_moving:
                if self._settle_job:
                    try:
                        self.root.after_cancel(self._settle_job)
                    except Exception:
                        pass
                self._settle_job = self.root.after(80, self._snap_settle_render)
        else:
            self.render(self.current_angle, interactive=False)

        try:
            self.root.update_idletasks()
            self.root.update()
            return self.is_running
        except (tk.TclError, Exception):
            self.is_running = False
            return False

    def _snap_settle_render(self):
        self._settle_job = None
        if self.is_running:
            self.render(self.current_angle, interactive=False)


if __name__ == "__main__":
    print("\nStarting Duosition (Fullscreen 3024x1964 Mode)...")
    print(" - Loads 'images/target.png' (or target.jpg)")
    print(" - Occupies 100% of the screen on fullscreen")
    print(" - Pure image render: no text or clutter")
    print(" - Drag slider at bottom to test skew, blur pane, & slow black gradient")
    print("Close the window or press Ctrl+C in terminal to exit.\n")

    viewer = LidImageViewer(image_folder="images", show_slider=True)
    try:
        viewer.root.mainloop()
    except KeyboardInterrupt:
        viewer.close()
