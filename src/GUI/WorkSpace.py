import tkinter as tk
from tkinter import ttk, scrolledtext
import math
import random
import os

class WorkSpace:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.colors = mediator.colors

        self.frame = ttk.Frame(parent)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # --- Tab 1: Code Editor (Multi-tab) ---
        self.editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_frame, text="Code Editor")

        # 編輯器頂部工具列
        self.editor_toolbar = tk.Frame(self.editor_frame, bg=self.colors['bg'], height=24)
        self.editor_toolbar.pack(side=tk.TOP, fill=tk.X)

        # 關閉按鈕
        self.btn_close_tab = tk.Button(
            self.editor_toolbar, text="×", font=("Arial", 12, "bold"),
            bg=self.colors['bg'], fg="#ff5555", bd=0,
            activebackground="#ff5555", activeforeground="white",
            command=self.close_current_file, cursor="hand2", width=3
        )
        self.btn_close_tab.pack(side=tk.RIGHT, padx=2)

        self.lbl_current_file = tk.Label(self.editor_toolbar, text="", bg=self.colors['bg'], fg="#888", font=("Consolas", 9))
        self.lbl_current_file.pack(side=tk.LEFT, padx=5)

        # 內部分頁
        self.editor_notebook = ttk.Notebook(self.editor_frame)
        self.editor_notebook.pack(fill=tk.BOTH, expand=True)
        self.editor_notebook.bind("<<NotebookTabChanged>>", self.on_editor_tab_change)

        self.opened_files_map = {} # frame -> file_path
        self.path_to_frame = {}    # file_path -> frame

        # --- Tab 2: Dependency Graph ---
        self.canvas = tk.Canvas(self.notebook, bg=self.colors['editor_bg'], highlightthickness=0)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self._hit_areas = []
        self.selected_node = None
        self._init_graph_menu()

        # --- Tab 2: Dependency Graph ---
        self.graph_frame = ttk.Frame(self.notebook) # 包裝 Canvas 和控制列
        self.notebook.add(self.graph_frame, text="Dependency Graph")

        # 控制列
        self.graph_toolbar = tk.Frame(self.graph_frame, bg=self.colors['bg'])
        self.graph_toolbar.pack(fill=tk.X, side=tk.TOP)

        self.view_mode = tk.StringVar(value="function")
        ttk.Radiobutton(self.graph_toolbar, text="Function View", value="function", variable=self.view_mode, command=self.draw_dependency_graph).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.graph_toolbar, text="Module View", value="module", variable=self.view_mode, command=self.draw_dependency_graph).pack(side=tk.LEFT, padx=5)

        self.canvas = tk.Canvas(self.graph_frame, bg=self.colors['editor_bg'], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def _init_graph_menu(self):
        self.graph_menu = tk.Menu(self.canvas, tearoff=0)
        self.graph_menu.add_command(label="Refine Module", command=self.on_graph_refine)
        self.graph_menu.add_command(label="Implement Function", command=self.on_graph_implement)

    # --- [修正] 對外 API 介面 ---

    def clear_all_editors(self):
        """[Fix] 給 MainWindow 呼叫，用來清空所有開啟的檔案"""
        for tab in self.editor_notebook.tabs():
            self.editor_notebook.forget(tab)
        self.opened_files_map.clear()
        self.path_to_frame.clear()
        # 重設預設頁
        self.open_file("Welcome", "Select a file from Project Explorer to edit.", None)

    def get_active_code(self):
        """[Fix] 給 IntelligencePanel 呼叫，獲取當前正在編輯的程式碼"""
        try:
            current_tab = self.editor_notebook.select()
            if not current_tab: return ""
            # current_tab 是一個 widget name (string)，我們需要找到對應的 widget instance
            # 在 ttk.Notebook 中，select() 回傳的是 identifier
            # 我們需要遍歷子元件找到 ScrolledText
            frame = self.editor_notebook.nametowidget(current_tab)
            for child in frame.winfo_children():
                if isinstance(child, scrolledtext.ScrolledText):
                    return child.get("1.0", tk.END).strip()
            return ""
        except Exception as e:
            print(f"Error getting active code: {e}")
            return ""

    # --- Editor Logic ---

    def on_editor_tab_change(self, event):
        try:
            current_tab = self.editor_notebook.select()
            # 這裡 current_tab 是 widget name
            # 我們存的 key 是 frame object，需要轉換或者直接用 name
            # 為了穩健，我們在此用 widget instance 比較
            target_widget = self.editor_notebook.nametowidget(current_tab)
            file_path = self.opened_files_map.get(target_widget)

            if file_path:
                self.lbl_current_file.config(text=file_path)
            else:
                self.lbl_current_file.config(text="(No File)")
        except:
            pass

    def close_current_file(self):
        try:
            current_tab = self.editor_notebook.select()
            if not current_tab: return
            target_widget = self.editor_notebook.nametowidget(current_tab)

            file_path = self.opened_files_map.pop(target_widget, None)
            if file_path and file_path in self.path_to_frame:
                del self.path_to_frame[file_path]

            self.editor_notebook.forget(current_tab)
        except Exception as e:
            print(f"Error closing tab: {e}")

    def open_file(self, title, content, file_path):
        if file_path and file_path in self.path_to_frame:
            self.editor_notebook.select(self.path_to_frame[file_path])
            return

        frame = ttk.Frame(self.editor_notebook)
        txt = scrolledtext.ScrolledText(
            frame, font=("Consolas", 11),
            bg=self.colors['editor_bg'], fg="#a9b7c6",
            insertbackground="white", selectbackground="#214283"
        )
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, content)

        self.editor_notebook.add(frame, text=title)
        self.editor_notebook.select(frame)

        if file_path:
            self.opened_files_map[frame] = file_path
            self.path_to_frame[file_path] = frame
        else:
            self.opened_files_map[frame] = title
            self.path_to_frame[title] = frame

    # --- Graph Logic (保持不變) ---
    def on_tab_change(self, event):
        selected_tab = self.notebook.index(self.notebook.select())
        if selected_tab == 1:
            self.draw_dependency_graph()

    # ... (其餘 Graph 相關程式碼 draw_dependency_graph, _generate_colors 等與上一版相同，請保留) ...
    # 為了簡潔，這裡省略重複的 Graph 代碼，請確保它們還在

    def _generate_colors(self, n):
        palette = ["#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b", "#ffb86c", "#ff5555", "#f1fa8c", "#6272a4", "#4a88c7", "#e06c75", "#98c379", "#61afef"]
        return [palette[i % len(palette)] for i in range(n)]

    def _get_contrast_color(self, hex_color):
        hex_color = hex_color.lstrip('#')
        try:
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            comp = (255 - rgb[0], 255 - rgb[1], 255 - rgb[2])
            return '#%02x%02x%02x' % comp
        except: return "white"

    def draw_module_view(self):
        self.canvas.delete("all")
        self._hit_areas = []

        nodes, edges = self.mediator.meta.get_module_dependencies()
        if not nodes:
            self.canvas.create_text(400, 300, text="No module data.", fill="#666")
            return

        # 取得當前控制面板的功能模式 (creation, static_eval...)
        current_data_mode = self.mediator.controls.current_mode.get()

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) / 3
        angle_step = 2 * math.pi / len(nodes)
        node_pos = {}

        # 1. 計算座標
        for i, node in enumerate(nodes):
            angle = i * angle_step
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            node_pos[node] = (x, y)

        # 2. [Fix 4] 畫線 (使用新的箭頭修正)
        node_r = 30 # 模組圓圈半徑
        for u, v in edges:
            if u in node_pos and v in node_pos:
                x1, y1 = node_pos[u]
                x2, y2 = node_pos[v]

                # 使用箭頭修正
                sx, sy, ex, ey = self._get_arrow_coords(x1, y1, x2, y2, radius=node_r + 5)

                self.canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, fill="#888", width=2)

        # 3. 畫節點
        for node, (x, y) in node_pos.items():
            # 顏色邏輯
            if current_data_mode == 'creation':
                color = "#4a88c7"
            else:
                color = self.mediator.meta.traffic_light.get_color('module', current_data_mode, node)

            self.canvas.create_oval(x-node_r, y-node_r, x+node_r, y+node_r, fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text=node, fill="white", font=("Arial", 10, "bold"))

    # [New API] 讓外部呼叫以自動更新編輯器內容
    def reload_active_file(self):
        try:
            current_tab = self.editor_notebook.select()
            if not current_tab: return
            target_widget = self.editor_notebook.nametowidget(current_tab)
            file_path = self.opened_files_map.get(target_widget)

            if file_path and os.path.exists(file_path):
                # 記住現在的捲動位置
                # scroll_pos = ... (ScrolledText 比較難精確還原，這裡先單純重載)
                with open(file_path, 'r', encoding='utf-8') as f:
                    new_content = f.read()

                # 找到 Text widget
                for child in target_widget.winfo_children():
                    if isinstance(child, scrolledtext.ScrolledText):
                        child.delete("1.0", tk.END)
                        child.insert(tk.END, new_content)
                        break
        except Exception as e:
            print(f"Auto-reload failed: {e}")

    def draw_dependency_graph(self):
        if self.view_mode.get() == "module":
            self.draw_module_view()
            return

        self.canvas.delete("all")
        self._hit_areas = [] # 格式: (tag_id, func, mod, spec_path)

        data = self.mediator.meta.get_function_distribution()
        if not data:
            self.canvas.create_text(400, 300, text="No function data.", fill="#666")
            return

        modules = list(data.keys())
        mod_colors = self._generate_colors(len(modules))
        mod_color_map = {mod: col for mod, col in zip(modules, mod_colors)}

        current_data_mode = self.mediator.controls.current_mode.get()
        is_creation_mode = (current_data_mode == "creation")

        # 佈局
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 100: width = 800
        if height < 100: height = 600

        center_x, center_y = width / 2, height / 2
        max_radius = min(width, height) / 2 - 80
        angle_per_mod = (2 * math.pi) / len(modules) if modules else 0

        node_pos_map = {} # { 'mod.func': (x, y) }
        nodes_to_draw = []

        # 1. 計算節點位置
        for i, mod in enumerate(modules):
            funcs = data[mod]
            start_angle = i * angle_per_mod
            base_color = mod_color_map.get(mod, "#888")

            for j, func in enumerate(funcs):
                # 為了穩定顯示，用 hash 固定位置
                random.seed(hash(mod + func))
                theta = start_angle + (angle_per_mod * 0.2) + (angle_per_mod * 0.6 * random.random())
                r = max_radius * (0.3 + 0.6 * random.random())
                x = center_x + r * math.cos(theta)
                y = center_y + r * math.sin(theta)

                full_name = f"{mod}.{func}"
                node_pos_map[full_name] = (x, y)
                # 容錯 key
                node_pos_map[func] = (x, y)

                if is_creation_mode:
                    color = base_color
                else:
                    color = self.mediator.meta.traffic_light.get_color('function', current_data_mode, func, parent_mod=mod)

                spec_path = self._get_spec_path(mod)
                nodes_to_draw.append({
                    'x': x, 'y': y, 'func': func, 'mod': mod,
                    'color': color, 'spec': spec_path, 'full': full_name
                })

        # 2. [Fix 1] 繪製依賴線條 (Spec + Static Analysis)
        # 收集所有邊 (src -> dst)
        edges = set()

        # A. 從 Spec (Phase 2)
        for node in nodes_to_draw:
            if node['spec'] and os.path.exists(node['spec']):
                try:
                    with open(node['spec'], 'r') as f: spec = json.load(f)
                    for f_spec in spec.get('functions', []):
                        if f_spec['name'] == node['func']:
                            for target in f_spec.get('required_calls', []):
                                edges.add((node['full'], target))
                except: pass

        # B. 從 Static Analysis (Phase 3 - 如果有實作)
        # 這裡需要 StructureAnalyzer 支援函式級依賴，如果尚未支援，至少我們有了 A 方案。
        # 假設 A 方案已經夠用 (因為我們修復了 required_calls)

        for src_name, tgt_name in edges:
            # 嘗試匹配座標
            start = node_pos_map.get(src_name)
            end = node_pos_map.get(tgt_name)

            # 嘗試模糊匹配
            if not end and "." not in tgt_name:
                # 可能是跨模組呼叫但沒寫模組名，遍歷所有節點找
                for k, v in node_pos_map.items():
                    if k.endswith(f".{tgt_name}"):
                        end = v
                        break

            if start and end:
                sx, sy, ex, ey = self._get_arrow_coords(start[0], start[1], end[0], end[1], radius=12)
                self.canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, fill="#888", width=1, dash=(2, 4))

        # 3. 繪製節點 (使用 tag 識別)
        node_r = 12
        for n in nodes_to_draw:
            x, y = n['x'], n['y']

            # 畫圓
            tag_id = f"node_{n['mod']}_{n['func']}"
            oval = self.canvas.create_oval(x-node_r, y-node_r, x+node_r, y+node_r,
                                           fill=n['color'], outline="#333", tags=(tag_id, "node"))

            # 畫文字
            self.canvas.create_text(x, y+18, text=n['func'], fill="#ccc", font=("Consolas", 8))

            # 儲存 hit area (這裡改存 tag_id 方便 lookup)
            self._hit_areas.append((tag_id, n['func'], n['mod'], n['spec']))

        if is_creation_mode:
            self._draw_legend(width, height, modules, mod_color_map)

    def _draw_legend(self, w, h, modules, color_map):
        legend_x = w - 200
        legend_y = h - (len(modules) * 20) - 20
        self.canvas.create_rectangle(legend_x - 10, legend_y - 10, w - 10, h - 10, fill="#222", outline="#444")
        self.canvas.create_text(legend_x, legend_y - 20, text="[ Module Legend ]", fill="white", anchor="nw")
        for i, mod in enumerate(modules):
            y = legend_y + i * 20
            self.canvas.create_rectangle(legend_x, y, legend_x+12, y+12, fill=color_map[mod], outline="")
            self.canvas.create_text(legend_x+20, y, text=mod, fill="#ccc", anchor="nw")

    # [Fix 2] 優化路徑搜尋，確保能找到 spec.json
    def _get_spec_path(self, mod_name):
        root = self.mediator.meta.workspace_root
        # 1. 直接在 root 下找
        p1 = os.path.join(root, mod_name, "spec.json")
        if os.path.exists(p1): return p1

        # 2. 在第一層子目錄找
        for d in os.listdir(root):
            d_path = os.path.join(root, d)
            if os.path.isdir(d_path):
                p2 = os.path.join(d_path, mod_name, "spec.json")
                if os.path.exists(p2): return p2
        return None

    # [Fix 2] 使用 Canvas 內建的 find_overlapping 確保點擊命中
    def on_canvas_click(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        # 搜尋點擊點附近 5px 的物件
        items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)

        current_mode = self.mediator.controls.current_mode.get()
        clicked_node = None

        for item_id in items:
            tags = self.canvas.gettags(item_id)
            if "node" in tags: # 確保點到的是節點圓圈
                # 反查資料
                for area in self._hit_areas:
                    # area: (tag_id, func, mod, spec_path)
                    if area[0] in tags:
                        clicked_node = area
                        break
            if clicked_node: break

        if clicked_node:
            tag_id, func, mod, spec_path = clicked_node
            self.selected_node = (func, mod)
            self.draw_dependency_graph() # 重繪選中框

            if current_mode == 'creation' and spec_path:
                self.mediator.controls.update_context_button('impl', (func, spec_path))
                self.graph_menu.post(event.x_root, event.y_root)
        else:
            if self.selected_node:
                self.selected_node = None
                self.draw_dependency_graph()
                if current_mode == 'creation':
                    self.mediator.controls.update_context_button('arch', None)
            try: self.graph_menu.unpost()
            except: pass

    def on_graph_refine(self):
        if not self.selected_node: return
        _, mod = self.selected_node
        self.mediator.run_async(lambda: self.mediator.meta.refine_module(mod, cancel_event=self.mediator._current_cancel_flag))

    def on_graph_implement(self):
        if not self.selected_node: return
        func, mod = self.selected_node
        # 簡易反推 spec path，實際應更嚴謹
        root = self.mediator.meta.workspace_root
        spec_path = None
        for d in os.listdir(root): # 檢查第一層子目錄
             potential = os.path.join(root, d, mod, "spec.json")
             if os.path.exists(potential): spec_path = potential; break
        if not spec_path: # 再試試直接在 root 下
             potential = os.path.join(root, mod, "spec.json")
             if os.path.exists(potential): spec_path = potential

        if spec_path:
            self.mediator.run_async(lambda: self.mediator.meta.implement_functions(spec_path, [func], cancel_event=self.mediator._current_cancel_flag))

    def _get_arrow_coords(self, x1, y1, x2, y2, radius=15):
        """
        [Fix 4] 計算箭頭的起點與終點，使其停留在圓周上，而非圓心。
        radius: 節點圓形的半徑 (需與繪圖時的 node_r 匹配，稍微大一點留白)
        """
        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx*dx + dy*dy)

        if dist == 0 or dist <= radius * 2:
            return x1, y1, x2, y2 # 重疊或太近，不調整

        # 單位向量
        ux = dx / dist
        uy = dy / dist

        # 起點往外推
        sx = x1 + ux * radius
        sy = y1 + uy * radius

        # 終點往回縮
        ex = x2 - ux * radius
        ey = y2 - uy * radius

        return sx, sy, ex, ey
