# -*- coding: utf-8 -*-
"""Quay Man Hinh - ung dung quay man hinh nhe cho Windows 10/11.

Chuc nang:
- Quay toan man hinh hoac mot vung chon bang chuot
- Thu tieng micro (ke ca micro iPhone qua WO Mic)
- Giu phim de lam noi bat con tro: vong tron / den roi / ca hai
- Hieu ung khi bam chuot
- Dem nguoc 3 giay, tam dung / tiep tuc, luu MP4
"""
import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from ctypes import wintypes
from tkinter import messagebox, ttk

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

APP_NAME = "Quay Màn Hình"
BASE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
FFMPEG = os.path.join(BASE, "ffmpeg.exe")
if not os.path.exists(FFMPEG):
    FFMPEG = shutil.which("ffmpeg") or FFMPEG
OUT_DIR = os.path.join(os.path.expanduser("~"), "Videos", "Quay man hinh")
CFG_FILE = os.path.join(os.environ.get("APPDATA", BASE), "QuayManHinh.json")
NOWIN = 0x08000000
KEY = "#ff00ff"  # mau nay se trong suot tren lop phu
NO_MIC = "Không thu tiếng"

HOTKEYS = {"Ctrl": 0x11, "Shift": 0x10, "F8": 0x77, "Chuột giữa": 0x04}
STYLES = ["Vòng tròn", "Đèn rọi", "Cả hai"]


# ---------------- Ham tien ich Windows ----------------
def virtual_screen():
    g = user32.GetSystemMetrics
    return g(76), g(77), g(78), g(79)  # x, y, rong, cao (tat ca man hinh)


def primary_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def hwnd_of(win):
    win.update_idletasks()
    return int(win.wm_frame(), 16)


def make_click_through(win):
    h = hwnd_of(win)
    style = user32.GetWindowLongW(h, -20)
    # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
    user32.SetWindowLongW(h, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)


def load_cfg():
    try:
        with open(CFG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(data):
    try:
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def list_mics():
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                           capture_output=True, creationflags=NOWIN, timeout=15)
        text = r.stderr.decode("utf-8", errors="ignore")
    except Exception:
        return []
    mics, section = [], None
    for line in text.splitlines():
        if "DirectShow video devices" in line:
            section = "video"
        elif "DirectShow audio devices" in line:
            section = "audio"
        if "Alternative name" in line:
            continue
        m = re.search(r'"([^"]+)"(?:\s*\((audio|video|none)\))?', line)
        if not m:
            continue
        kind = m.group(2) or section
        if kind == "audio" and m.group(1) not in mics:
            mics.append(m.group(1))
    return mics


# ---------------- Lop phu: noi bat chuot + hieu ung click ----------------
class Overlay:
    def __init__(self, root, app):
        self.root, self.app = root, app
        self.vx, self.vy, vw, vh = virtual_screen()
        geo = f"{vw}x{vh}+{self.vx}+{self.vy}"
        self.spot_win, self.spot = self._make(geo, 0.55)
        self.ring_win, self.ring = self._make(geo, 1.0)
        self.dim = self.spot.create_rectangle(0, 0, vw, vh, fill=KEY, outline="")
        self.hole = self.spot.create_oval(0, 0, 0, 0, fill=KEY, outline="")
        self.halo = self.ring.create_oval(0, 0, 0, 0, outline="#ff9500", width=3, state="hidden")
        self.circle = self.ring.create_oval(0, 0, 0, 0, outline="#ffd60a", width=6, state="hidden")
        self.spot_on = False
        self.ring_on = False
        self.buttons = {1: False, 2: False}
        self.ripples = []
        self.tick()

    def _make(self, geo, alpha):
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.geometry(geo)
        w.attributes("-topmost", True)
        w.attributes("-transparentcolor", KEY)
        w.attributes("-alpha", alpha)
        c = tk.Canvas(w, bg=KEY, highlightthickness=0)
        c.pack(fill="both", expand=True)
        make_click_through(w)
        return w, c

    def tick(self):
        try:
            self._update()
        finally:
            self.root.after(15, self.tick)

    def _update(self):
        x, y = cursor_pos()
        cx, cy = x - self.vx, y - self.vy
        on = key_down(HOTKEYS.get(self.app.hotkey.get(), 0x11))
        style = self.app.style.get()
        spot_on = on and style != "Vòng tròn"
        ring_on = on and style != "Đèn rọi"

        if spot_on != self.spot_on:
            self.spot.itemconfig(self.dim, fill="black" if spot_on else KEY)
            self.spot_on = spot_on
        if spot_on:
            r = 130
            self.spot.coords(self.hole, cx - r, cy - r, cx + r, cy + r)

        if ring_on != self.ring_on:
            st = "normal" if ring_on else "hidden"
            self.ring.itemconfig(self.circle, state=st)
            self.ring.itemconfig(self.halo, state=st)
            self.ring_on = ring_on
        if ring_on:
            self.ring.coords(self.circle, cx - 34, cy - 34, cx + 34, cy + 34)
            self.ring.coords(self.halo, cx - 42, cy - 42, cx + 42, cy + 42)

        if self.app.click_fx.get():
            for vk, color in ((1, "#ff3b30"), (2, "#0a84ff")):
                down = key_down(vk)
                if down and not self.buttons[vk]:
                    item = self.ring.create_oval(cx, cy, cx, cy, outline=color, width=5)
                    self.ripples.append([cx, cy, time.time(), item])
                self.buttons[vk] = down

        now = time.time()
        for rp in list(self.ripples):
            t = (now - rp[2]) / 0.45
            if t >= 1:
                self.ring.delete(rp[3])
                self.ripples.remove(rp)
            else:
                r = 8 + 40 * t
                self.ring.coords(rp[3], rp[0] - r, rp[1] - r, rp[0] + r, rp[1] + r)
                self.ring.itemconfig(rp[3], width=max(1, int(5 * (1 - t))))


# ---------------- Chon vung quay ----------------
def select_region(root, callback):
    vx, vy, vw, vh = virtual_screen()
    pw, ph = primary_size()
    w = tk.Toplevel(root)
    w.overrideredirect(True)
    w.geometry(f"{vw}x{vh}+{vx}+{vy}")
    w.attributes("-topmost", True)
    w.attributes("-alpha", 0.4)
    c = tk.Canvas(w, bg="black", cursor="cross", highlightthickness=0)
    c.pack(fill="both", expand=True)
    c.create_text(pw // 2 - vx, ph // 2 - vy, fill="white", font=("Segoe UI", 20, "bold"),
                  text="Kéo chuột để chọn vùng quay  •  Esc để hủy")
    st = {"start": None, "rect": None}

    def press(e):
        st["start"] = (e.x, e.y)
        st["rect"] = c.create_rectangle(e.x, e.y, e.x, e.y, outline="white", width=3)

    def drag(e):
        if st["rect"]:
            c.coords(st["rect"], *st["start"], e.x, e.y)

    def release(e):
        if not st["start"]:
            return
        x1, y1 = st["start"]
        left, top = min(x1, e.x), min(y1, e.y)
        width, height = abs(e.x - x1), abs(e.y - y1)
        w.destroy()
        if width < 40 or height < 40:
            callback(None)
        else:
            callback((left + vx, top + vy, width, height))

    def cancel(_e=None):
        w.destroy()
        callback(None)

    c.bind("<ButtonPress-1>", press)
    c.bind("<B1-Motion>", drag)
    c.bind("<ButtonRelease-1>", release)
    w.bind("<Escape>", cancel)
    w.focus_force()


def countdown(root, n, done):
    pw, ph = primary_size()
    w = tk.Toplevel(root)
    w.overrideredirect(True)
    w.attributes("-topmost", True)
    w.attributes("-alpha", 0.85)
    lbl = tk.Label(w, font=("Segoe UI", 72, "bold"), fg="white", bg="#1c1c1e", padx=60, pady=10)
    lbl.pack()

    def step(k):
        if k == 0:
            w.destroy()
            root.after(250, done)
            return
        lbl.config(text=str(k))
        w.update_idletasks()
        w.geometry(f"+{(pw - w.winfo_reqwidth()) // 2}+{(ph - w.winfo_reqheight()) // 2}")
        w.after(1000, step, k - 1)

    step(n)


# ---------------- Bo ghi hinh (ffmpeg) ----------------
class Recorder:
    def __init__(self, rect, mic):
        self.rect, self.mic = rect, mic
        self.tmp = tempfile.mkdtemp(prefix="qmh_")
        self.segs, self.proc, self.logf = [], None, None

    def start_segment(self):
        x, y, w, h = self.rect
        seg = os.path.join(self.tmp, f"part{len(self.segs):03d}.mkv")
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
               "-thread_queue_size", "512", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "1",
               "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop"]
        if self.mic:
            cmd += ["-thread_queue_size", "1024", "-f", "dshow", "-rtbufsize", "64M", "-i", f"audio={self.mic}"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
        if self.mic:
            cmd += ["-c:a", "aac", "-b:a", "160k"]
        cmd.append(seg)
        self.logf = open(seg + ".log", "w", encoding="utf-8", errors="ignore")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=self.logf, creationflags=NOWIN)
        self.segs.append(seg)

    def error_text(self):
        """Tra ve loi neu ffmpeg da tat bat thuong, nguoc lai None."""
        if self.proc and self.proc.poll() is not None:
            self.logf.close()
            try:
                with open(self.segs[-1] + ".log", encoding="utf-8", errors="ignore") as f:
                    return f.read()[-600:] or "ffmpeg đã dừng."
            except Exception:
                return "ffmpeg đã dừng."
        return None

    def stop_segment(self):
        if not self.proc:
            return
        try:
            self.proc.stdin.write(b"q")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
        self.proc = None
        try:
            self.logf.close()
        except Exception:
            pass

    def finish(self, out_path):
        self.stop_segment()
        segs = [s for s in self.segs if os.path.exists(s) and os.path.getsize(s) > 1000]
        if not segs:
            raise RuntimeError("Không có dữ liệu video nào được ghi.")
        lst = os.path.join(self.tmp, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for s in segs:
                f.write("file '%s'\n" % s.replace("\\", "/"))
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                            "-i", lst, "-c", "copy", "-movflags", "+faststart", out_path],
                           capture_output=True, creationflags=NOWIN)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", errors="ignore")[-600:])
        shutil.rmtree(self.tmp, ignore_errors=True)

    def discard(self):
        self.stop_segment()
        shutil.rmtree(self.tmp, ignore_errors=True)


# ---------------- Giao dien chinh ----------------
class App:
    def __init__(self):
        self.root = root = tk.Tk()
        root.title(APP_NAME)
        root.resizable(False, False)
        root.attributes("-topmost", True)
        try:
            root.tk.call("tk", "scaling", user32.GetDpiForSystem() / 72.0)
        except Exception:
            pass
        cfg = load_cfg()
        self.region = tk.StringVar(value=cfg.get("region", "full"))
        self.mic = tk.StringVar(value=cfg.get("mic", NO_MIC))
        self.hotkey = tk.StringVar(value=cfg.get("hotkey", "Ctrl"))
        self.style = tk.StringVar(value=cfg.get("style", "Vòng tròn"))
        self.click_fx = tk.BooleanVar(value=cfg.get("click_fx", True))
        self.count3 = tk.BooleanVar(value=cfg.get("count3", True))
        self.hide_bar = tk.BooleanVar(value=cfg.get("hide_bar", True))
        self.state = "idle"
        self.rec = None
        self.elapsed = 0.0
        self.t_start = 0.0
        self._build()
        self.overlay = Overlay(root, self)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(200, self.apply_hide)
        root.after(300, self.refresh_mics)
        root.after(500, self.tick)
        if not os.path.exists(FFMPEG):
            messagebox.showerror(APP_NAME, "Thiếu file ffmpeg.exe.\nHãy giải nén đầy đủ file ZIP rồi chạy lại.")

    def _build(self):
        st = ttk.Style()
        try:
            st.theme_use("vista")
        except Exception:
            pass
        st.configure("TButton", font=("Segoe UI", 10), padding=4)
        st.configure("Rec.TButton", font=("Segoe UI", 10, "bold"))
        f = ttk.Frame(self.root, padding=10)
        f.pack()

        top = ttk.Frame(f)
        top.grid(row=0, column=0, columnspan=4, sticky="we", pady=(0, 8))
        self.btn_rec = ttk.Button(top, text="⏺  Quay", style="Rec.TButton", command=self.on_record)
        self.btn_pause = ttk.Button(top, text="⏸  Tạm dừng", command=self.on_pause, state="disabled")
        self.btn_stop = ttk.Button(top, text="⏹  Dừng & Lưu", command=self.on_stop, state="disabled")
        self.btn_dir = ttk.Button(top, text="📁  Thư mục video", command=self.open_folder)
        for i, b in enumerate((self.btn_rec, self.btn_pause, self.btn_stop, self.btn_dir)):
            b.grid(row=0, column=i, padx=2)
        self.lbl_time = tk.Label(top, text="00:00", font=("Consolas", 14, "bold"), fg="#888")
        self.lbl_time.grid(row=0, column=4, padx=(10, 0))

        ttk.Label(f, text="Vùng quay:").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(f, text="Toàn màn hình", variable=self.region, value="full").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(f, text="Chọn vùng bằng chuột", variable=self.region, value="area").grid(
            row=1, column=2, columnspan=2, sticky="w")

        ttk.Label(f, text="Micro:").grid(row=2, column=0, sticky="w", pady=4)
        self.cb_mic = ttk.Combobox(f, textvariable=self.mic, state="readonly", width=38)
        self.cb_mic.grid(row=2, column=1, columnspan=2, sticky="we", pady=4)
        ttk.Button(f, text="↻ Tìm lại", command=self.refresh_mics).grid(row=2, column=3, padx=(4, 0))

        ttk.Label(f, text="Nổi bật chuột:").grid(row=3, column=0, sticky="w")
        hk = ttk.Frame(f)
        hk.grid(row=3, column=1, columnspan=3, sticky="w")
        ttk.Label(hk, text="giữ phím").pack(side="left")
        ttk.Combobox(hk, textvariable=self.hotkey, values=list(HOTKEYS), state="readonly", width=11).pack(
            side="left", padx=4)
        ttk.Label(hk, text="kiểu").pack(side="left")
        ttk.Combobox(hk, textvariable=self.style, values=STYLES, state="readonly", width=10).pack(
            side="left", padx=4)

        opt = ttk.Frame(f)
        opt.grid(row=4, column=0, columnspan=4, sticky="w", pady=(6, 0))
        ttk.Checkbutton(opt, text="Hiệu ứng khi bấm chuột", variable=self.click_fx).pack(side="left")
        ttk.Checkbutton(opt, text="Đếm ngược 3 giây", variable=self.count3).pack(side="left", padx=10)
        ttk.Checkbutton(opt, text="Ẩn bảng này khỏi video", variable=self.hide_bar,
                        command=self.apply_hide).pack(side="left")

    # ----- tien ich -----
    def apply_hide(self):
        try:
            user32.SetWindowDisplayAffinity(hwnd_of(self.root), 0x11 if self.hide_bar.get() else 0)
        except Exception:
            pass

    def refresh_mics(self):
        self.root.config(cursor="watch")
        self.root.update()
        mics = list_mics()
        self.root.config(cursor="")
        self.cb_mic["values"] = [NO_MIC] + mics
        if self.mic.get() not in mics:
            self.mic.set(mics[0] if mics else NO_MIC)

    def save(self):
        save_cfg({"region": self.region.get(), "mic": self.mic.get(), "hotkey": self.hotkey.get(),
                  "style": self.style.get(), "click_fx": self.click_fx.get(), "count3": self.count3.get(),
                  "hide_bar": self.hide_bar.get()})

    def open_folder(self, select=None):
        os.makedirs(OUT_DIR, exist_ok=True)
        if select:
            subprocess.Popen(["explorer", "/select,", select])
        else:
            os.startfile(OUT_DIR)

    def set_buttons(self):
        idle = self.state == "idle"
        self.btn_rec.config(state="normal" if idle else "disabled")
        self.btn_pause.config(state="disabled" if idle else "normal",
                              text="▶  Tiếp tục" if self.state == "pause" else "⏸  Tạm dừng")
        self.btn_stop.config(state="disabled" if idle else "normal")
        self.lbl_time.config(fg={"idle": "#888", "rec": "#e0245e", "pause": "#ff9500"}[self.state])

    # ----- quay -----
    def on_record(self):
        if self.state != "idle":
            return
        self.save()
        if self.region.get() == "area":
            select_region(self.root, self._got_rect)
        else:
            w, h = primary_size()
            self._got_rect((0, 0, w, h))

    def _got_rect(self, rect):
        if not rect:
            return
        x, y, w, h = rect
        rect = (x, y, w - w % 2, h - h % 2)  # video can kich thuoc chan
        self.btn_rec.config(state="disabled")
        if self.count3.get():
            countdown(self.root, 3, lambda: self._start(rect))
        else:
            self._start(rect)

    def _start(self, rect):
        os.makedirs(OUT_DIR, exist_ok=True)
        mic = self.mic.get()
        self.rec = Recorder(rect, None if mic == NO_MIC else mic)
        try:
            self.rec.start_segment()
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Không bắt đầu quay được:\n{e}")
            self.rec = None
            self.set_buttons()
            return
        self.state, self.elapsed, self.t_start = "rec", 0.0, time.time()
        self.set_buttons()

    def on_pause(self):
        if self.state == "rec":
            self.rec.stop_segment()
            self.elapsed += time.time() - self.t_start
            self.state = "pause"
        elif self.state == "pause":
            self.rec.start_segment()
            self.t_start = time.time()
            self.state = "rec"
        self.set_buttons()

    def on_stop(self):
        if self.state == "idle":
            return
        out = os.path.join(OUT_DIR, datetime.datetime.now().strftime("Video_%Y-%m-%d_%H-%M-%S.mp4"))
        self.root.config(cursor="watch")
        self.lbl_time.config(text="Đang lưu…")
        self.root.update()
        try:
            self.rec.finish(out)
            ok = True
        except Exception as e:
            ok = False
            messagebox.showerror(APP_NAME, f"Lưu video bị lỗi:\n{e}")
        self.root.config(cursor="")
        self.rec, self.state = None, "idle"
        self.set_buttons()
        self.lbl_time.config(text="00:00")
        if ok and messagebox.askyesno(APP_NAME, f"Đã lưu video:\n{out}\n\nMở thư mục chứa video?"):
            self.open_folder(out)

    def tick(self):
        if self.state == "rec" and self.rec:
            err = self.rec.error_text()
            if err:
                self.rec.discard()
                self.rec, self.state = None, "idle"
                self.set_buttons()
                hint = "\n\nGợi ý: thử chọn micro khác hoặc chọn 'Không thu tiếng'." if self.mic.get() != NO_MIC else ""
                messagebox.showerror(APP_NAME, f"Quay bị dừng do lỗi:\n{err}{hint}")
        if self.state != "idle":
            sec = int(self.elapsed + (time.time() - self.t_start if self.state == "rec" else 0))
            self.lbl_time.config(text=f"{sec // 60:02d}:{sec % 60:02d}")
        self.root.after(500, self.tick)

    def on_close(self):
        if self.state != "idle":
            if not messagebox.askyesno(APP_NAME, "Đang quay. Dừng và lưu video rồi thoát?"):
                return
            self.on_stop()
        self.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
