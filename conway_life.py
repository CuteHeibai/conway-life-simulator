import random
import tkinter as tk
from collections import defaultdict
from tkinter import filedialog, messagebox


APP_TITLE = "Conway Life Simulator"
MIN_CELL_SIZE = 1
MAX_CELL_SIZE = 80
DEFAULT_CELL_SIZE = 18
BASE_TICK_MS = 250
DEFAULT_SPEED_MULTIPLIER = 1
CYCLE_DETECTION_CELL_LIMIT = 20000
MAX_VISIBLE_DRAW_ITEMS = 12000
MAX_POPULATION_HISTORY = 5000
DEFAULT_RANDOM_COUNT = 300
DEFAULT_RANDOM_SPREAD = 30
MAX_RANDOM_COUNT = 50000
MAX_RANDOM_SPREAD = 100
GRID_COLOR = "#d8dee9"
LIVE_COLOR = "#1f7a4d"
LIVE_OUTLINE = "#0f5132"
BACKGROUND = "#f7f5ee"
PANEL_BG = "#ece7db"
TEXT_COLOR = "#202124"
RULES_TEXT = (
    "康威生命游戏规则：\n\n"
    "1. 每个格子只有两种状态：活细胞或空格。\n"
    "2. 活细胞周围少于 2 个活邻居时，下一代死亡。\n"
    "3. 活细胞周围有 2 或 3 个活邻居时，下一代继续存活。\n"
    "4. 活细胞周围多于 3 个活邻居时，下一代死亡。\n"
    "5. 空格周围正好有 3 个活邻居时，下一代变成活细胞。\n\n"
    "左键拖动画布，右键填充或擦除细胞，滚轮缩放。随机生成可自定义数量和离散程度。"
    "勾选“循环后暂停”时，检测到循环会提示并暂停。"
)


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
        self.seen_states = {}
        self.cycle_detection_paused = False
        self.render_limited = False
        self.population_history = []
        self.stats_window = None
        self.stats_canvas = None
        self.stats_text = tk.StringVar()

        self.random_count = tk.IntVar(value=DEFAULT_RANDOM_COUNT)
        self.random_spread = tk.IntVar(value=DEFAULT_RANDOM_SPREAD)
        self.speed_multiplier = tk.IntVar(value=DEFAULT_SPEED_MULTIPLIER)
        self.stop_on_cycle = tk.BooleanVar(value=True)
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
        toolbar.columnconfigure(16, weight=1)

        self.run_button = tk.Button(toolbar, text="开始", width=8, command=self.toggle_running)
        self.run_button.grid(row=0, column=0, padx=(0, 6))

        tk.Button(toolbar, text="单步", width=8, command=self.step_once).grid(row=0, column=1, padx=6)
        tk.Button(toolbar, text="清空", width=8, command=self.clear).grid(row=0, column=2, padx=6)
        tk.Button(toolbar, text="随机", width=8, command=self.randomize_visible).grid(row=0, column=3, padx=6)
        tk.Label(toolbar, text="数量", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=4, padx=(10, 4))
        tk.Spinbox(
            toolbar,
            from_=1,
            to=MAX_RANDOM_COUNT,
            width=8,
            increment=50,
            textvariable=self.random_count,
        ).grid(row=0, column=5, padx=4)

        tk.Label(toolbar, text="离散", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=6, padx=(10, 4))
        tk.Spinbox(
            toolbar,
            from_=1,
            to=MAX_RANDOM_SPREAD,
            width=5,
            textvariable=self.random_spread,
        ).grid(row=0, column=7, padx=4)

        tk.Button(toolbar, text="居中", width=8, command=self.center_view).grid(row=0, column=8, padx=6)
        tk.Button(toolbar, text="保存", width=8, command=self.save_pattern).grid(row=0, column=9, padx=6)
        tk.Button(toolbar, text="载入", width=8, command=self.load_pattern).grid(row=0, column=10, padx=6)
        tk.Button(toolbar, text="规则", width=8, command=self.show_rules).grid(row=0, column=11, padx=6)
        tk.Button(toolbar, text="统计", width=8, command=self.show_statistics).grid(row=0, column=12, padx=6)

        tk.Label(toolbar, text="倍速", bg=PANEL_BG, fg=TEXT_COLOR).grid(row=0, column=13, padx=(18, 4))
        multiplier = tk.Spinbox(toolbar, from_=1, to=200, width=6, textvariable=self.speed_multiplier)
        multiplier.grid(row=0, column=14, padx=4)

        tk.Checkbutton(
            toolbar,
            text="循环后暂停",
            variable=self.stop_on_cycle,
            bg=PANEL_BG,
            fg=TEXT_COLOR,
            activebackground=PANEL_BG,
            selectcolor=BACKGROUND,
        ).grid(row=0, column=15, padx=(14, 0))

        tk.Label(
            toolbar,
            text="左键拖动画布，右键绘制/擦除，随机可调数量和离散程度",
            bg=PANEL_BG,
            fg="#555",
        ).grid(row=0, column=16, padx=(18, 0), sticky="w")

        self.canvas = tk.Canvas(self.root, bg=BACKGROUND, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        status = tk.Label(self.root, textvariable=self.status_text, anchor="w", bg="#ded8ca", fg=TEXT_COLOR, padx=10, pady=5)
        status.grid(row=2, column=0, sticky="ew")

    def bind_events(self):
        self.canvas.bind("<Configure>", lambda event: self.redraw())
        self.canvas.bind("<Button-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.drag_pan)
        self.canvas.bind("<ButtonRelease-1>", self.stop_pan)
        self.canvas.bind("<Button-3>", self.start_paint)
        self.canvas.bind("<B3-Motion>", self.drag_paint)
        self.canvas.bind("<ButtonRelease-3>", self.stop_paint)
        self.canvas.bind("<MouseWheel>", self.zoom_with_wheel)
        self.root.bind("<space>", lambda event: self.toggle_running())
        self.root.bind("<Return>", lambda event: self.step_once())
        self.root.bind("<plus>", lambda event: self.zoom_at_center(1.2))
        self.root.bind("<minus>", lambda event: self.zoom_at_center(1 / 1.2))

    def center_view(self):
        self.offset_x = self.canvas.winfo_width() // 2
        self.offset_y = self.canvas.winfo_height() // 2
        self.redraw(full=True)

    def seed_glider(self):
        self.alive = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}
        self.generation = 0
        self.reset_history()

    def show_rules(self):
        messagebox.showinfo("生命游戏规则", RULES_TEXT)

    def reset_history(self, record_population=True):
        if len(self.alive) > CYCLE_DETECTION_CELL_LIMIT:
            self.seen_states = {}
            self.cycle_detection_paused = True
            if record_population:
                self.record_population()
            return

        shape, anchor = self.normalized_shape()
        self.seen_states = {shape: (self.generation, anchor)}
        self.cycle_detection_paused = False
        if record_population:
            self.record_population()

    def normalized_shape(self):
        if not self.alive:
            return frozenset(), (0, 0)

        min_x = min(cell_x for cell_x, _ in self.alive)
        min_y = min(cell_y for _, cell_y in self.alive)
        shape = frozenset((cell_x - min_x, cell_y - min_y) for cell_x, cell_y in self.alive)
        return shape, (min_x, min_y)

    def record_population(self):
        point = (self.generation, len(self.alive))
        if self.population_history and self.population_history[-1][0] == self.generation:
            self.population_history[-1] = point
        else:
            self.population_history.append(point)

        if len(self.population_history) > MAX_POPULATION_HISTORY:
            self.population_history = self.population_history[-MAX_POPULATION_HISTORY:]
        self.redraw_statistics()

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
        self.reset_history()
        self.redraw(full=False)

    def start_pan(self, event):
        self.pan_start = (event.x, event.y)
        self.view_start = (self.offset_x, self.offset_y)

    def drag_pan(self, event):
        if not self.pan_start or not self.view_start:
            return
        self.offset_x = self.view_start[0] + event.x - self.pan_start[0]
        self.offset_y = self.view_start[1] + event.y - self.pan_start[1]
        self.redraw(full=True)

    def stop_pan(self, event):
        self.pan_start = None
        self.view_start = None

    def zoom_with_wheel(self, event):
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        self.zoom_at(event.x, event.y, factor)

    def zoom_at_center(self, factor):
        self.zoom_at(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, factor)

    def zoom_at(self, screen_x, screen_y, factor):
        old_size = self.cell_size
        if factor > 1:
            new_size = max(old_size + 1, round(old_size * factor))
        else:
            new_size = min(old_size - 1, round(old_size * factor))
        new_size = max(MIN_CELL_SIZE, min(MAX_CELL_SIZE, new_size))
        if new_size == old_size:
            return

        world_x = (screen_x - self.offset_x) / old_size
        world_y = (screen_y - self.offset_y) / old_size
        self.cell_size = new_size
        self.offset_x = int(screen_x - world_x * new_size)
        self.offset_y = int(screen_y - world_y * new_size)
        self.redraw(full=True)

    def toggle_running(self):
        self.running = not self.running
        self.run_button.configure(text="暂停" if self.running else "开始")
        if self.running:
            self.run_loop()

    def run_loop(self):
        if not self.running:
            return

        cycle = self.advance_generation()
        self.redraw(full=False)
        if self.handle_cycle(cycle):
            return

        delay = max(1, BASE_TICK_MS // self.get_speed_multiplier())
        self.root.after(delay, self.run_loop)

    def step_once(self):
        cycle = self.advance_generation()
        self.redraw(full=False)
        self.handle_cycle(cycle)

    def get_speed_multiplier(self):
        try:
            return max(1, min(500, int(self.speed_multiplier.get())))
        except tk.TclError:
            return DEFAULT_SPEED_MULTIPLIER

    def advance_generation(self):
        alive = self.alive
        neighbor_counts = {}

        for cell_x, cell_y in alive:
            for dx, dy in NEIGHBOR_OFFSETS:
                neighbor = (cell_x + dx, cell_y + dy)
                neighbor_counts[neighbor] = neighbor_counts.get(neighbor, 0) + 1

        self.alive = {
            cell
            for cell, count in neighbor_counts.items()
            if count == 3 or (count == 2 and cell in alive)
        }
        self.generation += 1
        self.record_population()
        return self.detect_cycle()

    def detect_cycle(self):
        if len(self.alive) > CYCLE_DETECTION_CELL_LIMIT:
            self.cycle_detection_paused = True
            return None

        shape, anchor = self.normalized_shape()
        first_seen = self.seen_states.get(shape)
        if first_seen is not None:
            first_generation, first_anchor = first_seen
            movement_x = anchor[0] - first_anchor[0]
            movement_y = anchor[1] - first_anchor[1]
            return first_generation, self.generation - first_generation, movement_x, movement_y

        self.cycle_detection_paused = False
        self.seen_states[shape] = (self.generation, anchor)
        return None

    def handle_cycle(self, cycle):
        if cycle is None:
            return False

        first_seen, period, movement_x, movement_y = cycle
        action_text = "程序已暂停。" if self.stop_on_cycle.get() else "程序将继续运行。"
        if movement_x or movement_y:
            message = (
                f"检测到平移循环：第 {self.generation} 代与第 {first_seen} 代形状相同，"
                f"周期为 {period}，每周期平移 ({movement_x}, {movement_y})。{action_text}"
            )
        else:
            message = f"检测到循环：第 {self.generation} 代重复了第 {first_seen} 代，周期为 {period}。{action_text}"

        self.status_text.set(message)
        if not self.stop_on_cycle.get():
            return False

        self.running = False
        self.run_button.configure(text="开始")
        messagebox.showinfo("检测到循环", message)
        return True

    def clear(self):
        self.running = False
        self.run_button.configure(text="开始")
        self.alive.clear()
        self.generation = 0
        self.population_history = []
        self.stats_text.set("暂无数据")
        self.reset_history(record_population=False)
        self.redraw(full=False)
        self.redraw_statistics()

    def randomize_visible(self):
        count = self.clamp_int_var(self.random_count, DEFAULT_RANDOM_COUNT, 1, MAX_RANDOM_COUNT)
        spread = self.clamp_int_var(self.random_spread, DEFAULT_RANDOM_SPREAD, 1, MAX_RANDOM_SPREAD)
        center_x, center_y = self.screen_to_cell(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2)
        side = max(5, int((count ** 0.5) * (0.9 + spread / 8)) * 2 + 1)
        half_span = side // 2
        total_slots = side * side
        count = min(count, total_slots)

        self.alive.clear()
        for position in random.sample(range(total_slots), count):
            cell_x = center_x + (position % side) - half_span
            cell_y = center_y + (position // side) - half_span
            self.alive.add((cell_x, cell_y))
        self.generation = 0
        self.reset_history()
        self.redraw(full=False)

    def clamp_int_var(self, variable, default, minimum, maximum):
        try:
            value = int(variable.get())
        except (tk.TclError, ValueError):
            value = default
        value = max(minimum, min(maximum, value))
        variable.set(value)
        return value

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
        self.reset_history()
        self.redraw(full=False)

    def redraw(self, full=True):
        if full:
            self.canvas.delete("all")
            self.draw_grid()
        else:
            self.canvas.delete("cells")
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
            self.canvas.create_line(x, 0, x, height, fill=GRID_COLOR, tags="grid")
        for y in range(start_y, height, self.cell_size):
            self.canvas.create_line(0, y, width, y, fill=GRID_COLOR, tags="grid")

    def draw_cells(self):
        left, top, right, bottom = self.visible_bounds()
        pad = 1 if self.cell_size > 8 else 0
        visible_cells = [
            (cell_x, cell_y)
            for cell_x, cell_y in self.alive
            if left <= cell_x <= right and top <= cell_y <= bottom
        ]

        if len(visible_cells) > MAX_VISIBLE_DRAW_ITEMS:
            self.render_limited = True
            stride = (len(visible_cells) + MAX_VISIBLE_DRAW_ITEMS - 1) // MAX_VISIBLE_DRAW_ITEMS
            for cell_x, cell_y in visible_cells[::stride]:
                self.draw_cell(cell_x, cell_y, pad)
            return

        self.render_limited = False

        if self.cell_size <= 2:
            rows = defaultdict(list)
            for cell_x, cell_y in visible_cells:
                rows[cell_y].append(cell_x)

            for cell_y, row_cells in rows.items():
                row_cells.sort()
                segment_start = row_cells[0]
                previous = row_cells[0]
                for cell_x in row_cells[1:]:
                    if cell_x == previous + 1:
                        previous = cell_x
                        continue
                    self.draw_small_cell_segment(segment_start, previous, cell_y)
                    segment_start = cell_x
                    previous = cell_x
                self.draw_small_cell_segment(segment_start, previous, cell_y)
            return

        for cell_x, cell_y in visible_cells:
            self.draw_cell(cell_x, cell_y, pad)

    def draw_cell(self, cell_x, cell_y, pad):
        x, y = self.cell_to_screen(cell_x, cell_y)
        self.canvas.create_rectangle(
            x + pad,
            y + pad,
            x + self.cell_size - pad,
            y + self.cell_size - pad,
            fill=LIVE_COLOR,
            outline=LIVE_OUTLINE if self.cell_size >= 10 else LIVE_COLOR,
            tags="cells",
        )

    def draw_small_cell_segment(self, start_x, end_x, cell_y):
        x1, y1 = self.cell_to_screen(start_x, cell_y)
        x2, y2 = self.cell_to_screen(end_x + 1, cell_y)
        self.canvas.create_rectangle(x1, y1, x2, y2 + self.cell_size, fill=LIVE_COLOR, outline=LIVE_COLOR, tags="cells")

    def update_status(self):
        cycle_text = "    循环检测：暂停（活细胞过多）" if self.cycle_detection_paused else ""
        render_text = "    显示：采样" if self.render_limited else ""
        self.status_text.set(
            f"第 {self.generation} 代    活细胞：{len(self.alive)}    "
            f"缩放：{self.cell_size}px/格    倍速：{self.get_speed_multiplier()}x{cycle_text}{render_text}"
        )

    def show_statistics(self):
        if self.stats_window and self.stats_window.winfo_exists():
            self.stats_window.lift()
            self.redraw_statistics()
            return

        self.stats_window = tk.Toplevel(self.root)
        self.stats_window.title("活细胞趋势统计")
        self.stats_window.geometry("620x360")
        self.stats_window.minsize(420, 260)

        tk.Label(self.stats_window, textvariable=self.stats_text, anchor="w", padx=10, pady=6).pack(fill="x")
        self.stats_canvas = tk.Canvas(self.stats_window, bg="#ffffff", highlightthickness=0)
        self.stats_canvas.pack(fill="both", expand=True)
        self.stats_canvas.bind("<Configure>", lambda event: self.redraw_statistics())
        self.redraw_statistics()

    def redraw_statistics(self):
        if not self.stats_canvas or not self.stats_canvas.winfo_exists():
            return

        history = self.population_history[-800:]
        canvas = self.stats_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        padding = 38

        if not history:
            self.stats_text.set("暂无数据")
            return

        counts = [count for _, count in history]
        min_count = min(counts)
        max_count = max(counts)
        current_generation, current_count = history[-1]
        self.stats_text.set(
            f"当前第 {current_generation} 代，活细胞 {current_count}；"
            f"窗口内最小 {min_count}，最大 {max_count}"
        )

        canvas.create_line(padding, height - padding, width - padding, height - padding, fill="#999")
        canvas.create_line(padding, padding, padding, height - padding, fill="#999")

        if len(history) == 1:
            x = width // 2
            y = height // 2
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=LIVE_COLOR, outline=LIVE_COLOR)
            return

        span = max(1, max_count - min_count)
        x_step = (width - padding * 2) / (len(history) - 1)
        points = []
        for index, (_, count) in enumerate(history):
            x = padding + index * x_step
            y = height - padding - ((count - min_count) / span) * (height - padding * 2)
            points.extend((x, y))

        canvas.create_line(*points, fill=LIVE_COLOR, width=2, smooth=True)
        canvas.create_text(padding, padding - 18, anchor="w", text=f"max {max_count}", fill="#555")
        canvas.create_text(padding, height - padding + 18, anchor="w", text=f"min {min_count}", fill="#555")


def main():
    root = tk.Tk()
    app = LifeApp(root)
    root.after(300, app.show_rules)
    root.mainloop()


if __name__ == "__main__":
    main()
