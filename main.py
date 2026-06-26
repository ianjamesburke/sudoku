#!/usr/bin/env python3
"""Sudoku — Easy, Medium, and Hard difficulties."""

from __future__ import annotations

import random

import plexi_sdk as sdk
from plexi_sdk import log, state
from plexi_sdk.effects import SetMouseTracking, SetState, SetStatus, SetTimer, SetTitle
from plexi_sdk.events import KeyEvent, MouseEvent, Resize, TimerFired
from plexi_sdk.ui import AppBar, Canvas, CanvasRect, CanvasText, Column, FooterKeys

TIMER_ID = 1
CLUES = {"easy": 46, "medium": 34, "hard": 26}
DIFFICULTIES = ["easy", "medium", "hard"]

C_BG = "#181825"
C_SURFACE = "#1e1e2e"
C_GRID = "#45475a"
C_BOX = "#cdd6f4"
C_GIVEN = "#cdd6f4"
C_USER = "#89b4fa"
C_ERROR = "#f38ba8"
C_SEL = "#45475a"
C_ROW = "#2a2a3d"
C_BOX_HL = "#2a2a40"
C_MUTED = "#6c7086"
C_ACCENT = "#cba6f7"
C_WIN = "#a6e3a1"
C_NOTE = "#585b70"

# ── Sudoku generation ──────────────────────────────────────────────────────

def _fill(grid, pos):
    if pos == 81:
        return True
    r, c = divmod(pos, 9)
    nums = list(range(1, 10))
    random.shuffle(nums)
    for n in nums:
        if _ok(grid, r, c, n):
            grid[r][c] = n
            if _fill(grid, pos + 1):
                return True
            grid[r][c] = 0
    return False

def _ok(grid, r, c, n):
    if n in grid[r]:
        return False
    for i in range(9):
        if grid[i][c] == n:
            return False
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            if grid[br + dr][bc + dc] == n:
                return False
    return True

def _new_game(difficulty):
    solution = [[0] * 9 for _ in range(9)]
    _fill(solution, 0)
    board = [row[:] for row in solution]
    given = [[True] * 9 for _ in range(9)]
    cells = list(range(81))
    random.shuffle(cells)
    to_remove = 81 - CLUES[difficulty]
    for pos in cells[:to_remove]:
        r, c = divmod(pos, 9)
        board[r][c] = 0
        given[r][c] = False
    return {
        "screen": "game",
        "difficulty": difficulty,
        "diff_idx": DIFFICULTIES.index(difficulty),
        "board": board,
        "solution": solution,
        "given": given,
        "sel_r": -1,
        "sel_c": -1,
        "errors": [[False] * 9 for _ in range(9)],
        "seconds": 0,
        "paused": False,
        "complete": False,
        "notes": [[[False] * 9 for _ in range(9)] for _ in range(9)],
        "notes_mode": False,
        "sel_num": 0,
    }

def _blank():
    return {
        "screen": "menu",
        "difficulty": "easy",
        "diff_idx": 0,
        "board": [[0] * 9 for _ in range(9)],
        "solution": [[0] * 9 for _ in range(9)],
        "given": [[False] * 9 for _ in range(9)],
        "sel_r": -1,
        "sel_c": -1,
        "errors": [[False] * 9 for _ in range(9)],
        "seconds": 0,
        "paused": False,
        "complete": False,
        "notes": [[[False] * 9 for _ in range(9)] for _ in range(9)],
        "notes_mode": False,
        "sel_num": 0,
    }

def _load():
    blank = _blank()
    d = {}
    for k, v in blank.items():
        d[k] = state.get(k, v)
    return d

# ── State helpers ──────────────────────────────────────────────────────────

def _errors(board, solution, given):
    out = [[False] * 9 for _ in range(9)]
    for r in range(9):
        for c in range(9):
            if not given[r][c] and board[r][c] != 0 and board[r][c] != solution[r][c]:
                out[r][c] = True
    return out

def _complete(board, given, solution):
    for r in range(9):
        for c in range(9):
            if board[r][c] != solution[r][c]:
                return False
    return True

def _fmt(secs):
    m, s = divmod(int(secs), 60)
    return f"{m:02d}:{s:02d}"

# ── Grid layout ────────────────────────────────────────────────────────────

def _metrics():
    side = 130.0
    pad = 48.0
    cell = min((sdk.canvas_width - side - pad) / 9, (sdk.canvas_height - pad) / 9)
    ox = (sdk.canvas_width - side - cell * 9) / 2
    oy = (sdk.canvas_height - cell * 9) / 2
    return cell, ox, oy

def _hit(x, y):
    cell, ox, oy = _metrics()
    gx = x - ox
    gy = y - oy
    if gx < 0 or gx >= cell * 9 or gy < 0 or gy >= cell * 9:
        return -1, -1
    return max(0, min(8, int(gy / cell))), max(0, min(8, int(gx / cell)))

def _count_numbers(board):
    counts = [0] * 9
    for r in range(9):
        for c in range(9):
            v = board[r][c]
            if 1 <= v <= 9:
                counts[v - 1] += 1
    return counts

def _num_btn_layout(cell, ox, oy):
    gw = cell * 9
    px = ox + gw + 18.0
    py = oy + 8.0
    bw, bh = 26.0, 26.0
    gap = 4.0
    ny_start = py + 175.0
    positions = []
    for i in range(9):
        num = i + 1
        col = i % 3
        row = i // 3
        bx = px + col * (bw + gap)
        by = ny_start + row * (bh + gap)
        positions.append((num, bx, by, bw, bh))
    return positions

def _enter_number(d, num):
    sel_r = int(d.get("sel_r", -1))
    sel_c = int(d.get("sel_c", -1))
    # Always select this number for highlighting, even if no cell is active
    if sel_r < 0 or sel_c < 0:
        return [SetState({"sel_num": num})]
    given = d.get("given", [[True] * 9] * 9)
    if given[sel_r][sel_c]:
        return [SetState({"sel_num": num})]
    board = [list(row) for row in d.get("board", [[0] * 9] * 9)]
    solution = d.get("solution", [[0] * 9] * 9)
    notes = [[list(nc) for nc in row] for row in d.get("notes", [[[False]*9]*9]*9)]
    notes_mode = bool(d.get("notes_mode", False))
    if notes_mode:
        notes[sel_r][sel_c][num - 1] = not notes[sel_r][sel_c][num - 1]
        return [SetState({"notes": notes, "sel_num": num})]
    board[sel_r][sel_c] = num
    notes[sel_r][sel_c] = [False] * 9
    for i in range(9):
        notes[sel_r][i][num - 1] = False
        notes[i][sel_c][num - 1] = False
    br, bc = (sel_r // 3) * 3, (sel_c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            notes[br + dr][bc + dc][num - 1] = False
    errs = _errors(board, solution, given)
    done = _complete(board, given, solution)
    new_state = {"board": board, "errors": errs, "complete": done, "notes": notes, "sel_num": num}
    if done:
        new_state["screen"] = "win"
        secs = int(d.get("seconds", 0))
        return [SetState(new_state), SetStatus(f"Solved in {_fmt(secs)}!")]
    return [SetState(new_state)]

# ── Lifecycle ─────────────────────────────────────────────────────────────

def init(size, args):
    d = _load()
    missing = {k: v for k, v in _blank().items() if state.get(k) is None}
    effects = [
        SetTitle("Sudoku"),
        SetStatus("Choose difficulty"),
        SetMouseTracking(True),
        SetTimer(TIMER_ID, 1000, repeat=True),
    ]
    if missing:
        effects.append(SetState(missing))
    return effects

def update(event):
    d = _load()
    screen = str(d.get("screen", "menu"))

    if isinstance(event, TimerFired) and event.id == TIMER_ID:
        if screen == "game" and not d.get("paused") and not d.get("complete"):
            secs = int(d.get("seconds", 0)) + 1
            return [SetState({"seconds": secs}), SetStatus(_fmt(secs))]
        return []

    if isinstance(event, Resize):
        return []

    if isinstance(event, MouseEvent) and event.pressed:
        return _mouse(d, event.x, event.y)

    if isinstance(event, KeyEvent) and event.pressed:
        return _key(d, event)

    return []

# ── Input handlers ─────────────────────────────────────────────────────────

def _mouse(d, x, y):
    if str(d.get("screen")) != "game":
        return _menu_mouse(d, x, y)
    cell, ox, oy = _metrics()
    for num, bx, by, bw, bh in _num_btn_layout(cell, ox, oy):
        if bx <= x <= bx + bw and by <= y <= by + bh:
            return _enter_number(d, num)
    r, c = _hit(x, y)
    if r >= 0:
        board = d.get("board", [[0] * 9] * 9)
        return [SetState({"sel_r": r, "sel_c": c, "sel_num": board[r][c]})]
    return []

def _menu_mouse(d, x, y):
    # Three difficulty boxes drawn in view — calculate which was clicked
    w = sdk.canvas_width
    h = sdk.canvas_height
    bw, bh = 200.0, 60.0
    bx = (w - bw) / 2
    by_start = h / 2 - 80.0
    for i, diff in enumerate(DIFFICULTIES):
        by = by_start + i * 80.0
        if bx <= x <= bx + bw and by <= y <= by + bh:
            new = _new_game(diff)
            return [SetState(new), SetStatus(f"{diff.title()} — 00:00")]
    return []

def _key(d, event):
    key = event.key
    screen = str(d.get("screen", "menu"))

    if screen == "menu":
        idx = int(d.get("diff_idx", 0))
        if key in ("up", "k"):
            return [SetState({"diff_idx": (idx - 1) % 3})]
        if key in ("down", "j"):
            return [SetState({"diff_idx": (idx + 1) % 3})]
        if key in ("return", "space"):
            new = _new_game(DIFFICULTIES[idx])
            return [SetState(new), SetStatus(f"{DIFFICULTIES[idx].title()} — 00:00")]
        if key == "1":
            new = _new_game("easy")
            return [SetState(new), SetStatus("Easy — 00:00")]
        if key == "2":
            new = _new_game("medium")
            return [SetState(new), SetStatus("Medium — 00:00")]
        if key == "3":
            new = _new_game("hard")
            return [SetState(new), SetStatus("Hard — 00:00")]
        return []

    if screen in ("game", "win"):
        return _game_key(d, event)

    return []

def _game_key(d, event):
    key = event.key
    shift = event.modifiers.shift
    screen = str(d.get("screen", "game"))
    sel_r = int(d.get("sel_r", -1))
    sel_c = int(d.get("sel_c", -1))
    paused = bool(d.get("paused", False))
    notes_mode = bool(d.get("notes_mode", False))

    # Always-active keys
    if key == "m":
        blank = _blank()
        return [SetState(blank), SetStatus("Choose difficulty")]
    if key == "r":
        new = _new_game(str(d.get("difficulty", "easy")))
        return [SetState(new), SetStatus(f"{new['difficulty'].title()} — 00:00")]

    if screen == "win":
        if key in ("n", "m"):
            blank = _blank()
            return [SetState(blank), SetStatus("Choose difficulty")]
        return []

    if key == "p":
        return [SetState({"paused": not paused})]
    if key == "n":
        return [SetState({"notes_mode": not notes_mode})]

    if paused:
        return []

    # Navigation — shift+arrow jumps a full 3-cell box
    moves = {"up": (-1, 0), "k": (-1, 0), "down": (1, 0), "j": (1, 0),
              "left": (0, -1), "h": (0, -1), "right": (0, 1), "l": (0, 1)}
    if key in moves:
        dr, dc = moves[key]
        step = 3 if shift and key in ("up", "down", "left", "right") else 1
        nr = max(0, min(8, sel_r + dr * step)) if sel_r >= 0 else 0
        nc = max(0, min(8, sel_c + dc * step)) if sel_c >= 0 else 0
        if sel_r < 0:
            nr, nc = 4, 4
        return [SetState({"sel_r": nr, "sel_c": nc})]

    if sel_r < 0 or sel_c < 0:
        return []

    given = d.get("given", [[True] * 9] * 9)
    if given[sel_r][sel_c]:
        return []

    board = [list(row) for row in d.get("board", [[0] * 9] * 9)]
    solution = d.get("solution", [[0] * 9] * 9)
    notes = [[list(cell) for cell in row] for row in d.get("notes", [[[False]*9]*9]*9)]

    if key in ("backspace", "delete"):
        board[sel_r][sel_c] = 0
        return [SetState({"board": board, "errors": _errors(board, solution, given), "sel_num": 0})]

    if key in "123456789" and len(key) == 1:
        return _enter_number(d, int(key))

    return []

# ── View ───────────────────────────────────────────────────────────────────

def view():
    d = _load()
    screen = str(d.get("screen", "menu"))
    if screen == "menu":
        footer = FooterKeys([("↑↓", "select"), ("enter", "start"), ("1", "easy"), ("2", "medium"), ("3", "hard")])
    elif d.get("paused"):
        footer = FooterKeys([("p", "resume"), ("r", "restart"), ("m", "menu")])
    elif screen == "win":
        footer = FooterKeys([("r", "restart"), ("n", "new game"), ("m", "menu")])
    else:
        keys = [("1-9", "fill"), ("n", "notes"), ("p", "pause"), ("r", "restart"), ("m", "menu")]
        footer = FooterKeys(keys)
    return Column([
        AppBar("Sudoku"),
        Canvas(_draw(d), width=sdk.canvas_width, height=100.0, grow=True),
        footer,
    ], padding=0, gap=0, grow=True)

def _draw(d):
    if sdk.canvas_width <= 0 or sdk.canvas_height <= 0:
        return []
    screen = str(d.get("screen", "menu"))
    if screen == "menu":
        return _draw_menu(d)
    return _draw_game(d)

# ── Menu drawing ───────────────────────────────────────────────────────────

def _draw_menu(d):
    w = sdk.canvas_width
    h = sdk.canvas_height
    diff_idx = int(d.get("diff_idx", 0))
    cmds = []

    title_y = h / 2 - 160.0
    cmds.append(CanvasText(w / 2, title_y, "SUDOKU", size=36.0, color=C_BOX, bold=True, align="center_center"))
    cmds.append(CanvasText(w / 2, title_y + 40.0, "Choose your difficulty", size=13.0, color=C_MUTED, align="center_center"))

    bw, bh = 220.0, 64.0
    bx = (w - bw) / 2
    by_start = h / 2 - 80.0
    labels = [("Easy", f"{CLUES['easy']} clues"), ("Medium", f"{CLUES['medium']} clues"), ("Hard", f"{CLUES['hard']} clues")]
    colors_diff = ["#a6e3a1", "#f9e2af", "#f38ba8"]

    for i, (label, subtitle) in enumerate(labels):
        by = by_start + i * 80.0
        selected = i == diff_idx
        bg = "#313244" if selected else "#1e1e2e"
        border = colors_diff[i] if selected else "#45475a"
        cmds.append(CanvasRect(bx - 2, by - 2, bw + 4, bh + 4, border, radius=10.0))
        cmds.append(CanvasRect(bx, by, bw, bh, bg, radius=8.0))
        text_color = colors_diff[i] if selected else C_BOX
        cmds.append(CanvasText(bx + bw / 2, by + 22.0, label, size=17.0, color=text_color, bold=selected, align="center_center"))
        cmds.append(CanvasText(bx + bw / 2, by + 44.0, subtitle, size=11.0, color=C_MUTED, align="center_center"))

    return cmds

# ── Game drawing ───────────────────────────────────────────────────────────

def _draw_game(d):
    board = d.get("board", [[0] * 9] * 9)
    given = d.get("given", [[True] * 9] * 9)
    errors = d.get("errors", [[False] * 9] * 9)
    notes = d.get("notes", [[[False] * 9] * 9] * 9)
    sel_r = int(d.get("sel_r", -1))
    sel_c = int(d.get("sel_c", -1))
    paused = bool(d.get("paused", False))
    complete = bool(d.get("complete", False))
    screen = str(d.get("screen", "game"))
    notes_mode = bool(d.get("notes_mode", False))
    difficulty = str(d.get("difficulty", "easy"))
    seconds = int(d.get("seconds", 0))
    sel_num = int(d.get("sel_num", 0))

    cell, ox, oy = _metrics()
    gw = cell * 9
    gh = cell * 9
    cmds = []

    # Grid shadow/bg
    cmds.append(CanvasRect(ox - 3, oy - 3, gw + 6, gh + 6, "#11111b", radius=6.0))
    cmds.append(CanvasRect(ox, oy, gw, gh, C_BG, radius=4.0))

    # Highlight row, col, box of selected cell
    if sel_r >= 0 and sel_c >= 0 and not paused and screen == "game":
        cmds.append(CanvasRect(ox, oy + sel_r * cell, gw, cell, C_ROW))
        cmds.append(CanvasRect(ox + sel_c * cell, oy, cell, gh, C_ROW))
        br, bc = (sel_r // 3) * 3, (sel_c // 3) * 3
        cmds.append(CanvasRect(ox + bc * cell, oy + br * cell, cell * 3, cell * 3, C_BOX_HL))

    # Same-number highlight (driven by sel_num — set by clicking a cell or a number button)
    if sel_num != 0 and not paused:
        for r in range(9):
            for c in range(9):
                if board[r][c] == sel_num and not (r == sel_r and c == sel_c):
                    cmds.append(CanvasRect(ox + c * cell + 2, oy + r * cell + 2, cell - 4, cell - 4, "#3d3a52", radius=3.0))

    # Selected cell highlight
    if sel_r >= 0 and sel_c >= 0 and not paused and screen == "game":
        cmds.append(CanvasRect(ox + sel_c * cell + 1, oy + sel_r * cell + 1, cell - 2, cell - 2, C_SEL, radius=3.0))

    # Cell content
    if not paused:
        for r in range(9):
            for c in range(9):
                cx = ox + c * cell + cell / 2
                cy = oy + r * cell + cell / 2
                val = board[r][c]
                if val != 0:
                    if given[r][c]:
                        col, bold = C_GIVEN, True
                    elif errors[r][c]:
                        col, bold = C_ERROR, False
                    elif complete:
                        col, bold = C_WIN, False
                    else:
                        col, bold = C_USER, False
                    cmds.append(CanvasText(cx, cy, str(val), size=cell * 0.52, color=col, bold=bold, align="center_center"))
                else:
                    # Pencil marks
                    cell_notes = notes[r][c]
                    mini = cell / 3.2
                    for ni in range(9):
                        if cell_notes[ni]:
                            nr2, nc2 = divmod(ni, 3)
                            nx = ox + c * cell + nc2 * (cell / 3) + cell / 6
                            ny = oy + r * cell + nr2 * (cell / 3) + cell / 6
                            cmds.append(CanvasText(nx, ny, str(ni + 1), size=max(7.0, mini * 0.6), color=C_NOTE, align="center_center"))

    # Grid lines
    for i in range(10):
        box_line = i % 3 == 0
        lw = 2.0 if box_line else 0.5
        col = C_BOX if box_line else C_GRID
        cmds.append(CanvasRect(ox, oy + i * cell - lw / 2, gw, lw, col))
        cmds.append(CanvasRect(ox + i * cell - lw / 2, oy, lw, gh, col))

    # Box outline drawn on top of grid lines
    if sel_r >= 0 and sel_c >= 0 and not paused and screen == "game":
        br, bc = (sel_r // 3) * 3, (sel_c // 3) * 3
        bx0 = ox + bc * cell
        by0 = oy + br * cell
        bs = cell * 3
        lw = 2.0
        c_bord = "#7c7a9a"
        cmds.append(CanvasRect(bx0 - lw, by0 - lw, bs + lw * 2, lw, c_bord))  # top
        cmds.append(CanvasRect(bx0 - lw, by0 + bs, bs + lw * 2, lw, c_bord))  # bottom
        cmds.append(CanvasRect(bx0 - lw, by0 - lw, lw, bs + lw * 2, c_bord))  # left
        cmds.append(CanvasRect(bx0 + bs, by0 - lw, lw, bs + lw * 2, c_bord))  # right

    # Side panel
    px = ox + gw + 18.0
    py = oy + 8.0

    diff_colors = {"easy": "#a6e3a1", "medium": "#f9e2af", "hard": "#f38ba8"}
    d_color = diff_colors.get(difficulty, C_ACCENT)

    cmds += [
        CanvasText(px, py, "DIFFICULTY", size=9.0, color=C_MUTED),
        CanvasText(px, py + 15.0, difficulty.upper(), size=15.0, color=d_color, bold=True),
        CanvasText(px, py + 50.0, "TIME", size=9.0, color=C_MUTED),
        CanvasText(px, py + 65.0, _fmt(seconds), size=20.0, color=C_BOX, bold=True),
    ]

    if notes_mode:
        cmds.append(CanvasRect(px - 4, py + 100.0, 90.0, 22.0, "#2a2a1a", radius=4.0))
        cmds.append(CanvasText(px + 41.0, py + 111.0, "NOTES ON", size=10.0, color="#f9e2af", bold=True, align="center_center"))

    # Clues remaining hint
    filled = sum(1 for r in range(9) for c in range(9) if not given[r][c] and board[r][c] != 0)
    blanks = sum(1 for r in range(9) for c in range(9) if not given[r][c])
    if blanks > 0:
        cmds += [
            CanvasText(px, py + 135.0, "PROGRESS", size=9.0, color=C_MUTED),
            CanvasText(px, py + 150.0, f"{filled}/{blanks}", size=13.0, color=C_USER),
        ]

    # Number buttons 1-9
    counts = _count_numbers(board)
    cmds.append(CanvasText(px, py + 167.0, "NUMBERS", size=9.0, color=C_MUTED))
    for num, bx, by, bw, bh in _num_btn_layout(cell, ox, oy):
        done_num = counts[num - 1] >= 9
        is_sel = num == sel_num and sel_num != 0
        if done_num:
            bg = "#1a1a2a"
            text_col = "#3a3a50"
            border = "#2a2a3a"
        elif is_sel:
            bg = "#3d3a52"
            text_col = C_ACCENT
            border = C_ACCENT
        else:
            bg = "#252535"
            text_col = C_BOX
            border = C_GRID
        cmds.append(CanvasRect(bx - 1, by - 1, bw + 2, bh + 2, border, radius=5.0))
        cmds.append(CanvasRect(bx, by, bw, bh, bg, radius=4.0))
        cmds.append(CanvasText(bx + bw / 2, by + bh / 2, str(num), size=13.0, color=text_col, bold=not done_num, align="center_center"))

    # Overlay: paused
    cxg = ox + gw / 2
    cyg = oy + gh / 2
    if paused:
        cmds += [
            CanvasRect(cxg - 90, cyg - 32, 180, 64, "#000000ee", radius=8.0),
            CanvasText(cxg, cyg, "PAUSED", size=22.0, color="#f9e2af", bold=True, align="center_center"),
        ]

    # Overlay: win
    if screen == "win":
        cmds += [
            CanvasRect(cxg - 120, cyg - 50, 240, 100, "#000000ee", radius=10.0),
            CanvasText(cxg, cyg - 18, "PUZZLE SOLVED!", size=20.0, color=C_WIN, bold=True, align="center_center"),
            CanvasText(cxg, cyg + 12, _fmt(seconds), size=16.0, color=C_BOX, align="center_center"),
            CanvasText(cxg, cyg + 34, "press R for new game", size=11.0, color=C_MUTED, align="center_center"),
        ]

    return cmds
