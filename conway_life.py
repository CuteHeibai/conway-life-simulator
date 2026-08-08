import random
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox


APP_TITLE = "Conway Life Simulator"
MIN_CELL_SIZE = 4
MAX_CELL_SIZE = 80
DEFAULT_CELL_SIZE = 18
DEFAULT_TICK_MS = 80
DEFAULT_GENERATIONS_PER_TICK = 1
GRID_COLOR = "#d8dee9"
LIVE_COLOR = "#1f7a4d"
LIVE_OUTLINE = "#0f5132"
BACKGROUND = "#f7f5ee"
PANEL_BG = "#ece7db"
TEXT_COLOR = "#202124"


NEIGHBOR_OFFSETS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


class LifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1180x760")
        self.root.minsize(860, 560)

        self.alive = set()
        self.generation = 0
        self.running = False
        self.cell_size = DEFAULT_CELL_SIZE
        self.offset_x = 0
        self.offset_y = 0
        self.paint_value = True
        self.last_painted_cell = None
        self.pan_start = None
        self.view_start = None

        self.gens_per_tick = tk.IntVar(value=DEFAULT_GENERATIONS_PER_TICK)
        self.tick_ms = tk.IntVar(value=DEFAULT_TICK_MS)
        self.status_text = tk.StringVar()

        self.build_ui()
        self.center_view()
        self.seed_glider()
        self.bind_events()
        self.redraw()

    def build_ui(self):
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = tk.Frame(self.root, bg=PANEL_BG, padx=10, pady=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(12, weight=1)

        self.run_button = tk.Button(toolbar, text="开始", width=8, command=self.toggle_running)
        self.run_button.grid(row=0, column=0, padx=(0, 6))

        tk.Button(toolbar, text="单步", width=8, command=self.step_once).grid(row=0, column=1, padx=6)
        tk.Button(toolbar, text="清空", width=8, command=self.clear).grid(row=0, column=2, padx=6)
        tk.Button(toolbar, text="随机", width=8, command=self.randomize_visible).grid(row=0, column=3, padx=6)
        tk.Button(toolbar, text="居中", width=8, command=self.center_view).grid(row=0, column=4, padx=6)
        tk.Button(toolbar, text="保存", width=8, command=self.save_pattern).grid(row=0, column=5, padx=6)
        tk.Button(toolbar, text="载入", width=8, command=self.load_pattern).grid(row=0, column=6, padx=6)

        tk.Label(toolbar, text="运算倍数", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=7, padx=(18, 4))
        multiplier = tk.Spinbox(toolbar, from_=1, to=1000, width=6, textvariable=self.gens_per_tick)
        multiplier.grid(row=0, column=8, padx=4)

        tk.Label(toolbar, text="间隔(ms)", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=9, padx=(14, 4))
        delay = tk.Spinbox(toolbar, from_=1, to=2000, increment=10, width=7, textvariable=self.tick_ms)
        delay.grid(row=0, column=10, padx=4)

        tk.Label(
            toolbar,
            text="左键画格，右键拖动画布，滚轮缩放",
            bg=PANEL_BG,
            fg="#555",
        ).grid(row=0, column=11, padx=(18, 0), sticky="w")

        self.canvas = tk.Canvas(self.root, bg=BACKGROUND, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        status = tk.Label(self.root, textvariable=self.status_text, anchor="w", bg="#ded8ca", fg=TEXT_COLOR, padx=10, pady=5)
        status.grid(row=2, column=0, sticky="ew")

    def bind_events(self):
        self.canvas.bind("<Configure>", lambda event: self.redraw())
        self.canvas.bind("<Button-1>", self.start_paint)
        self.canvas.bind("<B1-Motion>", self.drag_paint)
        self.canvas.bind("<ButtonRelease-1>", self.stop_paint)
        self.canvas.bind("<Button-3>", self.start_pan)
        self.canvas.bind("<B3-Motion>", self.drag_pan)
        self.canvas.bind("<MouseWheel>", self.zoom_with_wheel)
        self.root.bind("<space>", lambda event: self.toggle_running())
        self.root.bind("<Return>", lambda event: self.step_once())
        self.root.bind("<plus>", lambda event: self.zoom_at_center(1.2))
        self.root.bind("<minus>", lambda event: self.zoom_at_center(1 / 1.2))

    def center_view(self):
        self.offset_x = self.canvas.winfo_width() // 2
        self.offset_y = self.canvas.winfo_height() // 2
        self.redraw()

    def seed_glider(self):
        self.alive = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}
        self.generation = 0

    def screen_to_cell(self, x, y):
        cell_x = int((x - self.offset_x) // self.cell_size)
        cell_y = int((y - self.offset_y) // self.cell_size)
        return cell_x, cell_y

    def cell_to_screen(self, cell_x, cell_y):
        return (
            self.offset_x + cell_x * self.cell_size,
            self.offset_y + cell_y * self.cell_size,
        )

    def visible_bounds(self):
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        left = int((-self.offset_x) // self.cell_size) - 1
        top = int((-self.offset_y) // self.cell_size) - 1
        right = int((width - self.offset_x) // self.cell_size) + 2
        bottom = int((height - self.offset_y) // self.cell_size) + 2
        return left, top, right, bottom

    def start_paint(self, event):
        cell = self.screen_to_cell(event.x, event.y)
        self.paint_value = cell not in self.alive
        self.set_cell(cell, self.paint_value)
        self.last_painted_cell = cell

    def drag_paint(self, event):
        cell = self.screen_to_cell(event.x, event.y)
        if cell != self.last_painted_cell:
            self.set_cell(cell, self.paint_value)
            self.last_painted_cell = cell

    def stop_paint(self, event):
        self.last_painted_cell = None

    def set_cell(self, cell, alive):
        if alive:
            self.alive.add(cell)
        else:
            self.alive.discard(cell)
        self.redraw()

    def start_pan(self, event):
        self.pan_start = (event.x, event.y)
        self.view_start = (self.offset_x, self.offset_y)

    def drag_pan(self, event):
        if not self.pan_start or not self.view_start:
            return
        self.offset_x = self.view_start[0] + event.x - self.pan_start[0]
        self.offset_y = self.view_start[1] + event.y - self.pan_start[1]
        self.redraw()

    def zoom_with_wheel(self, event):
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        self.zoom_at(event.x, event.y, factor)

    def zoom_at_center(self, factor):
        self.zoom_at(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, factor)

    def zoom_at(self, screen_x, screen_y, factor):
        old_size = self.cell_size
        new_size = max(MIN_CELL_SIZE, min(MAX_CELL_SIZE, round(old_size * factor)))
        if new_size == old_size:
            return

        world_x = (screen_x - self.offset_x) / old_size
        world_y = (screen_y - self.offset_y) / old_size
        self.cell_size = new_size
        self.offset_x = int(screen_x - world_x * new_size)
        self.offset_y = int(screen_y - world_y * new_size)
        self.redraw()

    def toggle_running(self):
        self.running = not self.running
        self.run_button.configure(text="暂停" if self.running else "开始")
        if self.running:
            self.run_loop()

    def run_loop(self):
        if not self.running:
            return

        repeats = max(1, self.gens_per_tick.get())
        for _ in range(repeats):
            self.advance_generation()
        self.redraw()
        self.root.after(max(1, self.tick_ms.get()), self.run_loop)

    def step_once(self):
        self.advance_generation()
        self.redraw()

    def advance_generation(self):
        neighbor_counts = defaultdict(int)

        for cell_x, cell_y in self.alive:
            for dx, dy in NEIGHBOR_OFFSETS:
                neighbor_counts[(cell_x + dx, cell_y + dy)] += 1

        self.alive = {
            cell
            for cell, count in neighbor_counts.items()
            if count == 3 or (count == 2 and cell in self.alive)
        }
        self.generation += 1

    def clear(self):
        self.running = False
        self.run_button.configure(text="开始")
        self.alive.clear()
        self.generation = 0
        self.redraw()

    def randomize_visible(self):
        left, top, right, bottom = self.visible_bounds()
        self.alive.clear()
        for cell_x in range(left, right):
            for cell_y in range(top, bottom):
                if random.random() < 0.18:
                    self.alive.add((cell_x, cell_y))
        self.generation = 0
        self.redraw()

    def save_pattern(self):
        path = filedialog.asksaveasfilename(
            title="保存初始情况",
            defaultextension=".life",
            filetypes=(("Life pattern", "*.life"), ("Text file", "*.txt"), ("All files", "*.*")),
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8") as file:
            for cell_x, cell_y in sorted(self.alive):
                file.write(f"{cell_x},{cell_y}\n")

    def load_pattern(self):
        path = filedialog.askopenfilename(
            title="载入初始情况",
            filetypes=(("Life pattern", "*.life"), ("Text file", "*.txt"), ("All files", "*.*")),
        )
        if not path:
            return

        loaded = set()
        line_number = 0
        try:
            with open(path, "r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, 1):
                    text = line.strip()
                    if not text or text.startswith("#"):
                        continue
                    x_text, y_text = text.split(",", 1)
                    loaded.add((int(x_text), int(y_text)))
        except Exception as error:
            messagebox.showerror("载入失败", f"第 {line_number} 行附近无法读取：{error}")
            return

        self.running = False
        self.run_button.configure(text="开始")
        self.alive = loaded
        self.generation = 0
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        self.draw_grid()
        self.draw_cells()
        self.update_status()

    def draw_grid(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if self.cell_size < 8:
            return

        start_x = self.offset_x % self.cell_size
        start_y = self.offset_y % self.cell_size

        for x in range(start_x, width, self.cell_size):
            self.canvas.create_line(x, 0, x, height, fill=GRID_COLOR)
        for y in range(start_y, height, self.cell_size):
            self.canvas.create_line(0, y, width, y, fill=GRID_COLOR)

    def draw_cells(self):
        left, top, right, bottom = self.visible_bounds()
        pad = 1 if self.cell_size > 8 else 0

        for cell_x, cell_y in self.alive:
            if not (left <= cell_x <= right and top <= cell_y <= bottom):
                continue
            x, y = self.cell_to_screen(cell_x, cell_y)
            self.canvas.create_rectangle(
                x + pad,
                y + pad,
                x + self.cell_size - pad,
                y + self.cell_size - pad,
                fill=LIVE_COLOR,
                outline=LIVE_OUTLINE if self.cell_size >= 10 else LIVE_COLOR,
            )

    def update_status(self):
        self.status_text.set(
            f"第 {self.generation} 代    活细胞：{len(self.alive)}    "
            f"缩放：{self.cell_size}px/格    运算倍数：{self.gens_per_tick.get()} 代/帧"
        )


def main():
    root = tk.Tk()
    app = LifeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
