#!/usr/bin/env python3
import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


APPID_NAMES = {
    "400040": "ShareX",
    "431960": "Wallpaper Engine",
    "365670": "Blender",
    "280680": "Krita",
}


def app_label(appid: str) -> str:
    name = APPID_NAMES.get(appid, "")
    return f"{appid} — {name}" if name else appid


def extract_strings(line: str):
    return re.findall(r'"([^"]*)"', line)


def extract_key(line: str):
    values = extract_strings(line)
    return values[0] if values else None


def unescape_vdf(text: str) -> str:
    return text.replace('\\"', '"').replace('\\\\', '\\')


def escape_vdf(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"')


def line_indent(line: str) -> str:
    m = re.match(r'^(\s*)', line)
    return m.group(1) if m else ''


def find_block_end(lines, start_brace_index):
    depth = 0
    for i in range(start_brace_index, len(lines)):
        stripped = lines[i].strip()
        if stripped == '{':
            depth += 1
        elif stripped == '}':
            depth -= 1
            if depth == 0:
                return i
    return None


def parse_screenshots_vdf(vdf_path: Path):
    raw = vdf_path.read_text(encoding='utf-8', errors='ignore')
    lines = raw.splitlines(keepends=True)
    entries = []

    def parse_direct_pairs(open_brace_index, close_brace_index):
        data = {}
        depth = 0
        for n in range(open_brace_index + 1, close_brace_index):
            stripped = lines[n].strip()
            if stripped == '{':
                depth += 1
                continue
            if stripped == '}':
                depth = max(0, depth - 1)
                continue
            if depth != 0:
                continue
            vals = extract_strings(lines[n])
            if len(vals) >= 2:
                data[vals[0]] = unescape_vdf(vals[1])
        return data

    i = 0
    while i < len(lines):
        if not re.match(r'^\s*"\d+"\s*$', lines[i]):
            i += 1
            continue

        outer_key = extract_key(lines[i])
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or lines[j].strip() != '{':
            i += 1
            continue

        outer_end = find_block_end(lines, j)
        if outer_end is None:
            i += 1
            continue

        outer_data = parse_direct_pairs(j, outer_end)
        if 'filename' in outer_data:
            entries.append({
                'entry_key': outer_key,
                'start': j,
                'end': outer_end,
                'data': outer_data,
            })
            i = outer_end + 1
            continue

        k = j + 1
        while k < outer_end:
            if re.match(r'^\s*"\d+"\s*$', lines[k]):
                entry_key = extract_key(lines[k])
                m = k + 1
                while m < outer_end and not lines[m].strip():
                    m += 1
                if m < outer_end and lines[m].strip() == '{':
                    entry_end = find_block_end(lines, m)
                    if entry_end is not None and entry_end <= outer_end:
                        data = parse_direct_pairs(m, entry_end)
                        if 'filename' in data:
                            data.setdefault('gameid', outer_key)
                            entries.append({
                                'entry_key': entry_key,
                                'start': m,
                                'end': entry_end,
                                'data': data,
                            })
                        k = entry_end + 1
                        continue
            k += 1

        i = outer_end + 1

    return lines, entries


def make_backup(vdf_path: Path) -> Path:
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = vdf_path.with_name(f'{vdf_path.name}.{stamp}.bak')
    shutil.copy2(vdf_path, backup)
    return backup


def build_location_line(reference_line: str, value: str) -> str:
    indent = line_indent(reference_line)
    newline = '\r\n' if reference_line.endswith('\r\n') else '\n'
    return f'{indent}"location"\t\t"{escape_vdf(value)}"{newline}'


def update_location(lines, entry, location_text: str):
    start, end = entry['start'], entry['end']
    existing = None
    imported_index = None
    reference_index = None

    for i in range(start + 1, end):
        key = extract_key(lines[i])
        if key and key.lower() == 'location':
            existing = i
            break
        if '"imported"' in lines[i]:
            imported_index = i
        if reference_index is None and ('"filename"' in lines[i] or '"thumbnail"' in lines[i]):
            reference_index = i

    if existing is not None:
        lines[existing] = build_location_line(lines[existing], location_text)
    else:
        insert_after = imported_index if imported_index is not None else reference_index
        if insert_after is None:
            insert_after = start
        lines.insert(insert_after + 1, build_location_line(lines[insert_after], location_text))

    entry['data']['location'] = location_text


def resolve_asset(vdf_path: Path, rel_value: str | None):
    if not rel_value:
        return None
    rel = Path(rel_value.replace('/', '\\'))
    candidate = vdf_path.parent / 'remote' / rel
    if candidate.exists():
        return candidate
    candidate2 = vdf_path.parent / rel
    if candidate2.exists():
        return candidate2
    return candidate


def get_game_folder(vdf_path: Path, appid: str | None):
    if not vdf_path or not appid:
        return None
    folder = vdf_path.parent / 'remote' / appid / 'screenshots'
    if folder.exists():
        return folder
    return folder


def format_timestamp(ts: str | None):
    if not ts or not ts.isdigit():
        return ''
    try:
        return dt.datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ts


def score_vdf_candidate(path: Path):
    score = 0
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
        if '"431960"' in text:
            score += 50
        if 'Endfield' in text:
            score += 25
        score += text.count('"filename"') // 20
    except Exception:
        pass
    return score


def possible_steam_roots():
    roots = []
    env_candidates = [
        os.environ.get('PROGRAMFILES(X86)'),
        os.environ.get('PROGRAMFILES'),
        os.environ.get('LOCALAPPDATA'),
    ]

    for base in env_candidates:
        if not base:
            continue
        bp = Path(base)
        roots.extend([
            bp / 'Steam',
            bp / 'Valve' / 'Steam',
        ])

    roots.extend([
        Path(r'C:\Program Files (x86)\Steam'),
        Path(r'C:\Program Files\Steam'),
        Path.home() / 'AppData' / 'Local' / 'Steam',
    ])

    out = []
    seen = set()
    for p in roots:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def find_screenshots_vdf_candidates():
    found = []
    for root in possible_steam_roots():
        userdata = root / 'userdata'
        if not userdata.exists():
            continue
        try:
            for candidate in userdata.glob(r'*\760\screenshots.vdf'):
                if candidate.is_file():
                    found.append(candidate)
        except Exception:
            continue

    unique = []
    seen = set()
    for p in found:
        key = str(p.resolve()).lower() if p.exists() else str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda p: (-score_vdf_candidate(p), str(p).lower()))
    return unique


def entry_status(data: dict):
    imported = data.get('imported', '').strip() == '1'
    published = bool(data.get('publishedfileid', '').strip())
    if published:
        return 'Published'
    if imported:
        return 'imported=1'
    return 'no import flag'


class CandidatePicker(tk.Toplevel):
    def __init__(self, master, candidates):
        super().__init__(master)
        self.title('Select screenshots.vdf')
        self.geometry('940x430')
        self.result = None
        self.candidates = candidates

        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text='Multiple screenshots.vdf files found. Please choose one:').pack(anchor='w', pady=(0, 8))

        columns = ('pfad', 'score')
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading('pfad', text='Pfad')
        self.tree.heading('score', text='Score')
        self.tree.column('pfad', width=790)
        self.tree.column('score', width=90, anchor='center')
        self.tree.pack(fill='both', expand=True)

        for idx, path in enumerate(candidates):
            self.tree.insert('', 'end', iid=str(idx), values=(str(path), score_vdf_candidate(path)))

        if candidates:
            self.tree.selection_set('0')

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(10, 0))
        ttk.Button(btns, text='Use selected', command=self.accept).pack(side='left')
        ttk.Button(btns, text='Cancel', command=self.cancel).pack(side='left', padx=8)

        self.tree.bind('<Double-1>', lambda e: self.accept())
        self.protocol('WM_DELETE_WINDOW', self.cancel)

    def accept(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.result = self.candidates[int(sel[0])]
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


class StartupChoice(tk.Toplevel):
    def __init__(self, master, appids, last_appid):
        super().__init__(master)
        self.title('Choose startup view')
        self.geometry('520x270')
        self.resizable(False, False)
        self.result = None
        self.appids = appids
        self.last_appid = last_appid

        self.transient(master)
        self.grab_set()

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill='both', expand=True)

        ttk.Label(
            frame,
            text='Welche AppID / welches Spiel soll nach dem Load zuerst angezeigt werden?'
        ).pack(anchor='w', pady=(0, 12))

        self.mode_var = tk.StringVar(value='first')
        ttk.Radiobutton(frame, text='First AppID in the list', variable=self.mode_var, value='first').pack(anchor='w', pady=3)

        state = 'normal' if last_appid and last_appid in appids else 'disabled'
        ttk.Radiobutton(
            frame,
            text=f'Last selection in this session ({app_label(last_appid)})' if last_appid else 'Last selection in this session',
            variable=self.mode_var,
            value='last',
            state=state
        ).pack(anchor='w', pady=3)

        ttk.Radiobutton(frame, text='Choose manually', variable=self.mode_var, value='manual').pack(anchor='w', pady=3)

        manual_row = ttk.Frame(frame)
        manual_row.pack(fill='x', pady=(10, 0))
        ttk.Label(manual_row, text='AppID').pack(side='left')

        self.manual_var = tk.StringVar(value=appids[0] if appids else '')
        self.manual_map = {app_label(a): a for a in appids}
        self.manual_display_var = tk.StringVar(value=app_label(appids[0]) if appids else '')

        self.box = ttk.Combobox(
            manual_row,
            textvariable=self.manual_display_var,
            state='readonly',
            values=list(self.manual_map.keys()),
            width=30
        )
        self.box.pack(side='left', padx=(8, 0))
        self.box.bind('<<ComboboxSelected>>', self.on_box_change)

        btns = ttk.Frame(frame)
        btns.pack(fill='x', pady=(18, 0))
        ttk.Button(btns, text='OK', command=self.accept).pack(side='left')
        ttk.Button(btns, text='Cancel', command=self.cancel).pack(side='left', padx=8)

        self.mode_var.trace_add('write', self.update_manual_state)
        self.update_manual_state()

        self.protocol('WM_DELETE_WINDOW', self.cancel)

    def update_manual_state(self, *args):
        if self.mode_var.get() == 'manual':
            self.box.configure(state='readonly')
        else:
            self.box.configure(state='disabled')

    def on_box_change(self, event=None):
        label = self.manual_display_var.get().strip()
        self.manual_var.set(self.manual_map.get(label, ''))

    def accept(self):
        mode = self.mode_var.get()
        if mode == 'first':
            self.result = ('first', None)
        elif mode == 'last':
            self.result = ('last', None)
        else:
            self.result = ('manual', self.manual_var.get().strip())
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Steam Screenshot Metadata Tool alpha 14')
        self.geometry('1560x920')
        self.minsize(1320, 820)

        self.vdf_path = None
        self.lines = []
        self.entries = []
        self.filtered_indices = []
        self.current_preview = None
        self.appids = []
        self.last_selected_appid = None
        self.appid_display_to_value = {}

        self._build_ui()
        self.after(250, self.auto_find_vdf)

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass

        top = ttk.Frame(self, padding=10)
        top.pack(fill='x')

        ttk.Label(top, text='screenshots.vdf').grid(row=0, column=0, sticky='w')
        self.vdf_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.vdf_var).grid(row=1, column=0, sticky='ew', padx=(0, 8))
        ttk.Button(top, text='Browse', command=self.pick_vdf).grid(row=1, column=1, sticky='ew')
        ttk.Button(top, text='Load', command=self.load_vdf).grid(row=1, column=2, sticky='ew', padx=(8, 0))
        ttk.Button(top, text='Auto-detect', command=self.auto_find_vdf).grid(row=1, column=3, sticky='ew', padx=(8, 0))
        top.columnconfigure(0, weight=1)

        filterbar = ttk.Frame(self, padding=(10, 0, 10, 6))
        filterbar.pack(fill='x')

        ttk.Label(filterbar, text='AppID / Game').pack(side='left')
        self.appid_var = tk.StringVar()
        self.appid_box = ttk.Combobox(filterbar, textvariable=self.appid_var, state='readonly', width=22)
        self.appid_box.pack(side='left', padx=(8, 12))
        self.appid_box.bind('<<ComboboxSelected>>', self.on_appid_changed)

        ttk.Button(filterbar, text='Startup view', command=self.apply_start_choice).pack(side='left', padx=(0, 10))

        self.only_published_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filterbar, text='Published only', variable=self.only_published_var, command=self.refresh_list).pack(side='left', padx=6)

        self.only_unpublished_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filterbar, text='Unpublished only', variable=self.only_unpublished_var, command=self.refresh_list).pack(side='left', padx=6)

        statsbar = ttk.Frame(self, padding=(10, 0, 10, 10))
        statsbar.pack(fill='x')

        self.stats_var = tk.StringVar(value='Status in current game: -')
        ttk.Label(statsbar, textvariable=self.stats_var).pack(anchor='w')

        main = ttk.Panedwindow(self, orient='horizontal')
        main.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=5)
        main.add(right, weight=2)

        columns = ('entry', 'game', 'status', 'filename', 'location', 'created')
        self.tree = ttk.Treeview(left, columns=columns, show='headings', height=22)
        self.tree.heading('entry', text='Entry')
        self.tree.heading('game', text='Game / AppID')
        self.tree.heading('status', text='Status')
        self.tree.heading('filename', text='Filename')
        self.tree.heading('location', text='Metadata')
        self.tree.heading('created', text='Created')

        self.tree.column('entry', width=60, anchor='center')
        self.tree.column('game', width=220)
        self.tree.column('status', width=120, anchor='center')
        self.tree.column('filename', width=320)
        self.tree.column('location', width=130)
        self.tree.column('created', width=150)

        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        self.tree.bind('<Double-1>', self.reveal_selected_file)

        self.tree.tag_configure('published', foreground='#8a5300', background='#fff1db')
        self.tree.tag_configure('imported', foreground='#1a537a', background='#eaf4fb')
        self.tree.tag_configure('local', foreground='#25543a', background='#eef8f1')

        sb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)

        info = ttk.LabelFrame(right, text='Preview & Metadata', padding=10)
        info.pack(fill='both', expand=True)

        badge_row = ttk.Frame(info)
        badge_row.pack(fill='x', pady=(0, 6))

        self.status_badge_var = tk.StringVar(value='Status: -')
        self.status_badge_label = tk.Label(
            badge_row,
            textvariable=self.status_badge_var,
            bg='#d9d9d9',
            fg='#202020',
            padx=10,
            pady=4,
            relief='groove',
            bd=1,
        )
        self.status_badge_label.pack(side='right')

        self.preview_frame = ttk.Frame(info, height=320)
        self.preview_frame.pack(fill='both', expand=True, pady=(0, 8))
        self.preview_frame.pack_propagate(False)
        self.preview_label = ttk.Label(self.preview_frame, text='No preview loaded', anchor='center')
        self.preview_label.pack(fill='both', expand=True)
        self.preview_frame.bind('<Configure>', self.on_preview_container_resize)
        self._current_preview_path = None

        self.selected_game_var = tk.StringVar(value='Selected game: -')
        ttk.Label(info, textvariable=self.selected_game_var).pack(anchor='w', pady=(6, 2))

        paths_frame = ttk.LabelFrame(info, text='Files', padding=5)
        paths_frame.pack(fill='x', pady=(2, 4))

        self.path_var = tk.StringVar()
        ttk.Label(paths_frame, text='Image path').pack(anchor='w', pady=(0, 2))
        ttk.Entry(paths_frame, textvariable=self.path_var, state='readonly').pack(fill='x')

        self.thumb_var = tk.StringVar()
        ttk.Label(paths_frame, text='Thumbnail path').pack(anchor='w', pady=(3, 0))
        ttk.Entry(paths_frame, textvariable=self.thumb_var, state='readonly').pack(fill='x')

        meta_frame = ttk.LabelFrame(info, text='Metadata fields', padding=5)
        meta_frame.pack(fill='x', pady=(0, 4))

        self.current_location_var = tk.StringVar()
        ttk.Label(meta_frame, text='Current metadata').pack(anchor='w', pady=(0, 1))
        ttk.Entry(meta_frame, textvariable=self.current_location_var, state='readonly').pack(fill='x')

        ttk.Label(meta_frame, text='New metadata').pack(anchor='w', pady=(3, 0))
        self.new_location_var = tk.StringVar()
        ttk.Entry(meta_frame, textvariable=self.new_location_var).pack(fill='x')

        wip_row = ttk.Frame(meta_frame)
        wip_row.pack(fill='x', pady=(4, 0))
        ttk.Button(wip_row, text='Workshop title (WIP)', command=self.wip_feature).pack(side='left', expand=True, fill='x')
        ttk.Button(wip_row, text='Tagged users (WIP)', command=self.wip_feature).pack(side='left', padx=6, expand=True, fill='x')

        self.info_var = tk.StringVar(value='Ready. Edit screenshot metadata in screenshots.vdf. Backups are optional and manual.')
        ttk.Label(info, textvariable=self.info_var, wraplength=285, justify='left').pack(anchor='w', pady=(2, 2))

        actions = ttk.Frame(info)
        actions.pack(fill='x', pady=(4, 0))
        ttk.Button(actions, text='Apply', command=self.apply_current).pack(side='left', expand=True, fill='x')
        ttk.Button(actions, text='Backup', command=self.create_backup_only).pack(side='left', padx=6, expand=True, fill='x')
        ttk.Button(actions, text='Reload', command=self.reload_selected).pack(side='left', padx=6, expand=True, fill='x')
        ttk.Button(actions, text='Reveal file', command=self.reveal_selected_file).pack(side='left', padx=6, expand=True, fill='x')

        footer = ttk.Frame(self, padding=(10, 0, 10, 10))
        footer.pack(fill='x')
        ttk.Label(
            footer,
            text='Metadata is edited directly in screenshots.vdf. Counters refer to the selected game.'
        ).pack(anchor='w')


    def _fit_start_window(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        req_w = max(self.winfo_reqwidth() + 24, 1280)
        req_h = max(self.winfo_reqheight() + 64, 860)
        width = min(req_w, max(1100, sw - 80))
        height = min(req_h, max(760, sh - 80))
        x = max((sw - width) // 2, 0)
        y = max((sh - height) // 2, 0)
        self.geometry(f'{width}x{height}+{x}+{y}')


    def create_backup_only(self):
        if not self.vdf_path:
            messagebox.showwarning('No VDF loaded', 'Load a screenshots.vdf file first.')
            return
        backup = backup_vdf(self.vdf_path) if make_backup else None
        self.info_var.set(f'Backup created: {backup.name}')

    def apply_current(self):
        self.save_current(make_backup=False)

    def wip_feature(self):
        messagebox.showinfo('Work in progress', 'This metadata field is planned for a later alpha build.')

    def auto_find_vdf(self):
        candidates = find_screenshots_vdf_candidates()
        if not candidates:
            self.info_var.set('No screenshots.vdf found automatically. Please browse manually.')
            return

        if len(candidates) == 1:
            self.vdf_var.set(str(candidates[0]))
            self.load_vdf()
            return

        picker = CandidatePicker(self, candidates)
        self.wait_window(picker)
        if picker.result:
            self.vdf_var.set(str(picker.result))
            self.load_vdf()
        else:
            self.info_var.set(f'{len(candidates)} candidates found, but nothing was selected.')

    def pick_vdf(self):
        path = filedialog.askopenfilename(
            title='Select screenshots.vdf',
            filetypes=[('VDF files', '*.vdf'), ('All files', '*.*')]
        )
        if path:
            self.vdf_var.set(path)
            self.load_vdf()

    def choose_start_appid(self):
        if not self.appids:
            return None
        dlg = StartupChoice(self, self.appids, self.last_selected_appid)
        self.wait_window(dlg)
        return dlg.result

    def apply_start_choice(self):
        choice = self.choose_start_appid()
        if choice is None:
            return

        mode, manual_value = choice
        if mode == 'first':
            selected = self.appids[0] if self.appids else ''
        elif mode == 'last' and self.last_selected_appid in self.appids:
            selected = self.last_selected_appid
        elif mode == 'manual' and manual_value in self.appids:
            selected = manual_value
        else:
            selected = self.appids[0] if self.appids else ''

        self.appid_var.set(app_label(selected) if selected else '')
        if selected:
            self.last_selected_appid = selected
        self.refresh_list()
        self.after(120, self._fit_start_window)

    def load_vdf(self):
        path_text = self.vdf_var.get().strip().strip('"')
        path = Path(path_text) if path_text else None
        if not path or not path.exists():
            messagebox.showerror('Error', 'Bitte eine gültige Select screenshots.vdf.')
            return

        try:
            self.lines, self.entries = parse_screenshots_vdf(path)
        except Exception as e:
            messagebox.showerror('Error', f'Could not load VDF:\n{e}')
            return

        self.vdf_path = path
        self.populate_appids()
        self.apply_default_appid()
        self.refresh_list()
        self.info_var.set(f'{len(self.entries)} Screenshot-Einträge geladen.')

    def populate_appids(self):
        appids = sorted({e['data'].get('gameid', '').strip() for e in self.entries if e['data'].get('gameid', '').strip()})
        self.appids = appids
        display_values = [app_label(a) for a in appids]
        self.appid_display_to_value = {app_label(a): a for a in appids}
        self.appid_box['values'] = display_values

    def apply_default_appid(self):
        if not self.appids:
            self.appid_var.set('')
            self.stats_var.set('Status in current game: -')
            return
        selected = self.appids[0]
        self.appid_var.set(app_label(selected))
        self.last_selected_appid = selected

    def selected_appid_value(self):
        text = self.appid_var.get().strip()
        return self.appid_display_to_value.get(text, text.split(' ')[0] if text else '')

    def update_stats_bar(self):
        selected_appid = self.selected_appid_value()
        if not selected_appid:
            self.stats_var.set('Status in current game: -')
            return

        counts = Counter()
        total = 0
        for entry in self.entries:
            data = entry['data']
            if data.get('gameid', '').strip() != selected_appid:
                continue
            counts[entry_status(data)] += 1
            total += 1

        self.stats_var.set(
            f'Status in {app_label(selected_appid)}: '
            f'no import flag {counts["no import flag"]} | '
            f'imported=1 {counts["imported=1"]} | '
            f'Published {counts["Published"]} | '
            f'Total {total}'
        )

    def on_appid_changed(self, event=None):
        value = self.selected_appid_value()
        if value:
            self.last_selected_appid = value
        self.refresh_list()

    def refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        selected_appid = self.selected_appid_value()
        query = ''
        only_published = self.only_published_var.get()
        only_unpublished = self.only_unpublished_var.get()
        self.filtered_indices = []

        self.update_stats_bar()

        matching_rows = []
        for idx, entry in enumerate(self.entries):
            data = entry['data']
            gameid = data.get('gameid', '').strip()
            if selected_appid and gameid != selected_appid:
                continue

            status = entry_status(data)
            location = data.get('location', '')
            published = bool(data.get('publishedfileid', '').strip())

            hay = ' '.join([
                entry['entry_key'],
                gameid,
                APPID_NAMES.get(gameid, ''),
                data.get('filename', ''),
                location,
                data.get('caption', ''),
                status,
            ]).lower()

            if query and query not in hay:
                continue
            if only_published and not published:
                continue
            if only_unpublished and published:
                continue

            matching_rows.append((idx, entry, status, location, gameid))

        self.filtered_indices = [idx for idx, *_ in matching_rows]

        for idx, entry, status, location, gameid in matching_rows:
            tag = 'local'
            if status == 'Published':
                tag = 'published'
            elif status == 'Imported':
                tag = 'imported'

            self.tree.insert(
                '',
                'end',
                iid=str(idx),
                values=(
                    entry['entry_key'],
                    app_label(gameid),
                    status,
                    entry['data'].get('filename', ''),
                    location,
                    format_timestamp(entry['data'].get('creation')),
                ),
                tags=(tag,)
            )

        if self.filtered_indices:
            first = str(self.filtered_indices[0])
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.see(first)
            self.on_select()
        else:
            self.clear_preview()

    def get_selected_entry(self):
        sel = self.tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        return self.entries[idx]

    def on_select(self, event=None):
        entry = self.get_selected_entry()
        if not entry or not self.vdf_path:
            return

        data = entry['data']
        gameid = data.get('gameid', '').strip()
        img_path = resolve_asset(self.vdf_path, data.get('filename'))
        thumb_path = resolve_asset(self.vdf_path, data.get('thumbnail'))
        game_folder = get_game_folder(self.vdf_path, gameid)
        status = entry_status(data)

        self.selected_game_var.set(f'Spiel: {app_label(gameid)}')
        self.path_var.set(str(img_path) if img_path else '')
        self.thumb_var.set(str(thumb_path) if thumb_path else '')
        self.current_location_var.set(data.get('location', ''))
        self.new_location_var.set(data.get('location', ''))

        extra = []
        if data.get('publishedfileid', '').strip():
            extra.append(f'publishedfileid={data.get("publishedfileid")}')
        if data.get('imported', '').strip():
            extra.append(f'imported={data.get("imported")}')
        if data.get('hscreenshot', '').strip():
            extra.append(f'hscreenshot={data.get("hscreenshot")}')

        status_text = f'Status: {status}'
        if extra:
            status_text += ' | ' + ' | '.join(extra[:3])
        self.set_status_badge(status_text, status)

        self.load_preview(img_path or thumb_path)

    def set_status_badge(self, text, status=None):
        palette = {
            'Published': ('#fff1db', '#8a5300'),
            'imported=1': ('#eaf4fb', '#1a537a'),
            'no import flag': ('#eef8f1', '#25543a'),
            None: ('#d9d9d9', '#202020'),
        }
        bg, fg = palette.get(status, palette[None])
        self.status_badge_var.set(text)
        self.status_badge_label.configure(bg=bg, fg=fg)

    def on_preview_container_resize(self, event=None):
        if self._current_preview_path:
            self.load_preview(self._current_preview_path)

    def clear_preview(self):
        self.preview_label.configure(image='', text='No preview loaded')
        self.current_preview = None
        self.selected_game_var.set('Selected game: -')
        self.set_status_badge('Status: -', None)
        self.path_var.set('')
        self.thumb_var.set('')
        self.current_location_var.set('')
        self.new_location_var.set('')

    def load_preview(self, img_path: Path | None):
        self._current_preview_path = img_path if img_path and img_path.exists() else None
        if not img_path or not img_path.exists():
            self.preview_label.configure(image='', text='No image file found')
            self.current_preview = None
            return

        if not PIL_AVAILABLE:
            self.preview_label.configure(image='', text='Pillow not installed. Preview disabled.')
            self.current_preview = None
            return

        try:
            img = Image.open(img_path)
            self.update_idletasks()
            frame_w = max(320, self.preview_frame.winfo_width())
            frame_h = max(240, self.preview_frame.winfo_height())
            max_w = max(300, frame_w - 8)
            max_h = max(220, frame_h - 8)
            img.thumbnail((max_w, max_h))
            photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo, text='')
            self.current_preview = photo
        except Exception as e:
            self.preview_label.configure(image='', text=f'Preview failed\n{e}')
            self.current_preview = None

    def save_current(self, make_backup=True):
        entry = self.get_selected_entry()
        if not entry or not self.vdf_path:
            messagebox.showwarning('Notice', 'No entry selected.')
            return

        new_location = self.new_location_var.get()
        try:
            backup = make_backup(self.vdf_path)
            update_location(self.lines, entry, new_location)
            self.vdf_path.write_text(''.join(self.lines), encoding='utf-8', errors='ignore')
            self.current_location_var.set(new_location)
            self.refresh_list()
            self.info_var.set(f'Saved. Backup created: {backup.name}')
        except Exception as e:
            messagebox.showerror('Error', f'Save failed:\n{e}')

    def reload_selected(self):
        current = self.get_selected_entry()
        current_key = current['entry_key'] if current else None
        current_appid = current['data'].get('gameid', '') if current else self.selected_appid_value()

        self.load_vdf()
        if current_appid and current_appid in self.appids:
            self.appid_var.set(app_label(current_appid))
            self.last_selected_appid = current_appid
            self.refresh_list()

        if current_key is None:
            return

        for idx, entry in enumerate(self.entries):
            if entry['entry_key'] == current_key and entry['data'].get('gameid', '') == current_appid:
                iid = str(idx)
                if self.tree.exists(iid):
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                    self.on_select()
                break

    def open_game_folder(self):
        folder_text = self.game_folder_var.get().strip()
        if not folder_text:
            return
        folder = Path(folder_text)
        if not folder.exists():
            messagebox.showwarning('Notice', f'Folder not found:\n{folder}')
            return

        try:
            if sys.platform.startswith('win'):
                os.startfile(str(folder))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(folder)], check=False)
            else:
                subprocess.run(['xdg-open', str(folder)], check=False)
        except Exception as e:
            messagebox.showerror('Error', f'Could not open folder:\n{e}')

    def reveal_selected_file(self, event=None):
        file_text = self.path_var.get().strip()
        if not file_text:
            return

        file_path = Path(file_text)
        if not file_path.exists():
            messagebox.showwarning('Notice', f'File not found:\n{file_path}')
            return

        try:
            if sys.platform.startswith('win'):
                subprocess.run(['explorer', '/select,', str(file_path)], check=False)
            elif sys.platform == 'darwin':
                subprocess.run(['open', '-R', str(file_path)], check=False)
            else:
                subprocess.run(['xdg-open', str(file_path.parent)], check=False)

            self.info_var.set(f'File revealed in file manager: {file_path.name}')
        except Exception as e:
            messagebox.showerror('Error', f'Could not reveal file in file manager:\n{e}')


if __name__ == '__main__':
    app = App()
    app.mainloop()