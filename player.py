"""Игрок в DOS-Arkanoid: видит только экран (RGB-кадр), управляет клавиатурой и мышью.

Всё об игре выяснено наблюдением (см. LOG.md). Основное:
- старт: меню видеорежима (E = EGA), меню устройства (M = мышь), клик на заставке, клик пропускает историю;
- игровой экран 320x200: поле x 40..215, ракетка в строках 176..181, мяч 5x5;
- мышь: ракетка сдвигается на dx/4 пикселя, без ограничения скорости, отклик через ~3 кадра;
- левая кнопка запускает мяч с ракетки (и стреляет лазером);
- угол отскока задаётся смещением точки удара от центра ракетки (6 зон, используем 4 безопасные);
- кирпичи: обычные, серебряные (несколько ударов), золотые (неразрушимые);
- капсулы (+1000): липкая, три мяча, широкая ракетка, лазер, замедление.
Стратегия: ни одного мяча мимо; угол выбирается симуляцией полёта по максимуму «разбито / время»;
капсулы ловим, когда мяч далеко; с лазером стреляем по нижним кирпичам; при нескольких мячах следим
за тем, что раньше всех долетит до ракетки.
"""

import cv2
import numpy as np

from body import Key, Mouse

# --- геометрия игрового экрана (320x200) ---
FIELD_L, FIELD_R = 40, 217          # внутренность поля по x: [40, 217)
PADDLE_TOP = 176                    # верх ракетки
PAD_CENTER_MIN, PAD_CENTER_MAX = 52, 203
LAG = 3                             # кадров между командой мыши и её видимостью на экране
BALL_HIT_Y = 173                    # центр мяча по y в момент удара о ракетку
LAND_Y = 173.0                      # для прогноза точки касания по x
BALL_X_MIN, BALL_X_MAX = 42, 214    # крайние положения центра мяча по x (у стенок)

W = np.array([255, 255, 255], np.uint8)
S = np.array([170, 170, 170], np.uint8)


def in_game(f):
    """Игровой экран: серые стенки поля слева и справа."""
    if f.shape[0] != 200:
        return False
    return all((f[y, 34] == W).all() and (f[y, 218] == W).all() and (f[y, 33] == S).all() for y in (100, 150))


def find_paddle(f):
    """Центр ракетки по x (по белой полоске в строке 177) или None."""
    row = (f[177, FIELD_L:FIELD_R] == W).all(1)
    xs = np.flatnonzero(row)
    if len(xs) < 6:
        return None
    # ракетка — самая длинная непрерывная белая полоса
    splits = np.flatnonzero(np.diff(xs) > 1)
    runs = np.split(xs, splits + 1)
    run = max(runs, key=len)
    if len(run) < 6:
        return None
    return (run[0] + run[-1]) / 2 + FIELD_L


def has_laser(f, pad):
    """Лазерная ракетка: в строке 179 внутри корпуса красные полосы (у обычной — серый корпус)."""
    x = int(round(pad))
    return (f[179, x - 5] == (170, 0, 0)).all() and (f[179, x + 5] == (170, 0, 0)).all()


def paddle_half(f):
    """Полуширина ракетки: белая полоса + 5 пикселей с каждой стороны (красные концы)."""
    row = (f[177, FIELD_L:FIELD_R] == W).all(1)
    xs = np.flatnonzero(row)
    if len(xs) < 6:
        return None
    runs = np.split(xs, np.flatnonzero(np.diff(xs) > 1) + 1)
    return max(len(r) for r in runs) / 2 + 5


# мяч 5x5: '.' — не проверяем (углы бывают поверх кирпичей), остальное — точный цвет
BALL = [".sss.", "sWWsd", "sWssd", "sssdd", ".ddd."]
_COL = {"s": (170, 170, 170), "W": (255, 255, 255), "d": (85, 85, 85)}
_BALL_PIX = [(dy, dx, _COL[c]) for dy, row in enumerate(BALL) for dx, c in enumerate(row) if c != "."]


def code(f):
    """Кадр -> одна целочисленная плоскость (по цвету EGA)."""
    return (f[..., 0].astype(np.int32) << 16) | (f[..., 1].astype(np.int32) << 8) | f[..., 2]


def find_balls(f, c=None):
    """Центры всех мячей [(x, y)] в поле."""
    c = code(f) if c is None else c
    reg = c[8:192, FIELD_L - 2:FIELD_R + 2]
    h, w = reg.shape
    ok = np.ones((h - 4, w - 4), bool)
    for dy, dx, col in _BALL_PIX:
        v = (col[0] << 16) | (col[1] << 8) | col[2]
        ok &= reg[dy:dy + h - 4, dx:dx + w - 4] == v
    ys, xs = np.nonzero(ok)
    return [(int(x) + FIELD_L - 2 + 2, int(y) + 8 + 2) for y, x in zip(ys, xs)]


def find_ball(f):
    b = find_balls(f)
    return b[0] if b else None


# цифры счёта: битовые маски 6x6 (белые пиксели), сняты с экрана при известном счёте
DIGITS = {0x7b3cf3cde: 0, 0x31c30c79e: 1, 0x7b30dec3f: 2, 0x7b3183cde: 3, 0x18e5a6fc6: 4,
          0xff0f83cde: 5, 0x7b0fb3cde: 6, 0xfc318630c: 7, 0x7b37b3cde: 8, 0x7b3cdf0de: 9}


def read_score(f):
    """Счёт с экрана (6 цифр справа от поля) или None."""
    if f.shape[0] != 200:
        return None
    v = 0
    for k in range(6):
        g = (f[63:69, 241 + 8 * k:247 + 8 * k] == 255).all(2).flatten()
        bits = int("".join("1" if b else "0" for b in g), 2)
        if bits not in DIGITS:
            return None
        v = v * 10 + DIGITS[bits]
    return v


def count_lives(f):
    """Число запасных ракеток (иконки внизу слева)."""
    row = f[194, FIELD_L:FIELD_R].any(1)
    return int(np.sum(row[1:] & ~row[:-1]) + row[0])


def blue_menu(f):
    """Текстовое меню на синем фоне (выбор видеорежима / устройства ввода)."""
    return f.shape == (400, 640, 3) and (f[::8, ::8] == [0, 0, 170]).all(2).mean() > 0.3


STALL_FRAMES = 2500                  # столько кадров без изменений = зацикливание
CAPSULE_SPEED = 1.0                 # пикс/кадр (измерено: y 82 -> 136 за 54 кадра)

# --- капсулы: «таблетки» 16x7, падают ~1 px/кадр строго по столбцам (левый край x = 40+16c) ---
CAPSULE_COLORS = {(0, 170, 0): "green", (170, 0, 0): "red", (170, 85, 0): "brown", (0, 170, 170): "cyan",
                  (85, 85, 255): "blue", (170, 0, 170): "magenta", (85, 85, 85): "gray"}


def find_capsules(f):
    """[(цвет, x центра, y низа)] — по краям таблетки: столбцы x0+1 и x0+14 одного цвета корпуса в 3 строках."""
    res = []
    for c in range(COLS):
        x0 = 40 + 16 * c
        a, b = f[8:186, x0 + 1], f[8:186, x0 + 14]
        same = (a == b).all(1)
        for col, name in CAPSULE_COLORS.items():
            m = same & (a == col).all(1)
            ys = np.flatnonzero(m[:-2] & m[1:-1] & m[2:])
            if len(ys):
                y = int(ys[-1]) + 8
                # корпус: строки сверху и снизу от середины; низ капсулы ~ на 3 строки ниже найденной тройки
                res.append((name, x0 + 7.5, y + 4))
    return res


# --- кирпичи: сетка 11 столбцов x 22 ряда, ячейка 16x8, кирпич 15x7 в (41+16c, 1+8r) ---
ROWS, COLS = 22, 11
EMPTY, NORMAL, SILVER, GOLD = 0, 1, 2, 3


def read_bricks(f):
    """Сетка типов кирпичей по экрану."""
    g = np.zeros((ROWS, COLS), np.int8)
    for r in range(1, ROWS):
        y = 1 + 8 * r
        if y + 7 > PADDLE_TOP:
            break
        blk = f[y:y + 7, 41:41 + 16 * COLS].reshape(7, COLS, 16, 3)[:, :, :15]
        filled = (blk.sum(3) > 0).mean(axis=(0, 2)) >= 0.9
        for c in np.flatnonzero(filled):
            b = blk[:, c]
            if (b[0] == 255).all() and (b[:, 0] == 255).all():   # белая рамка сверху и слева
                fill = tuple(b[3, 7])
                g[r, c] = SILVER if fill == (170, 170, 170) else GOLD if fill == (255, 255, 85) else NORMAL
            else:
                g[r, c] = NORMAL
    return g


# направления отскока от ракетки по зонам смещения (мяч − центр ракетки): (смещение-цель, единичный вектор)
# Пологие зоны ([-12,-9] и [8,12]) не используем: пологий мяч на высокой скорости слишком легко
# упустить краем ракетки (3 потери из 3 в прогоне b5), а угол подлёта всегда равен углу отскока.
ZONES = [(-6.5, (-0.707, -0.707)), (-2.5, (-0.26, -0.97)), (1.5, (0.26, -0.97)), (5.5, (0.707, -0.707))]
BALL_Y_MIN = 10
R = 2.5  # полуразмер мяча


def simulate(grid, x, y, vx, vy, limit=400):
    """Полёт мяча от ракетки до первого разбитого кирпича (золото отражает) или до возвращения к ракетке.
    Возвращает (кадры, (ряд, столбец) или None, x возврата, vx возврата, мин. расстояние до разбиваемого кирпича)."""
    targets = np.argwhere((grid == NORMAL) | (grid == SILVER))
    tc = np.stack([41 + 16 * targets[:, 1] + 7, 1 + 8 * targets[:, 0] + 3], 1) if len(targets) else None

    def hit(px, py):
        c = int((px - 41 + R) // 16), int((px - 41 - R) // 16)
        r = int((py - 1 + R) // 8), int((py - 1 - R) // 8)
        for rr in {r[0], r[1]}:
            for cc in {c[0], c[1]}:
                if 0 <= rr < ROWS and 0 <= cc < COLS and grid[rr, cc]:
                    bx, by = 41 + 16 * cc, 1 + 8 * rr
                    if bx - R <= px < bx + 15 + R and by - R <= py < by + 7 + R:
                        return rr, cc
        return None
    mind = 1e9
    for t in range(1, limit):
        nx = x + vx
        h = hit(nx, y)
        if h:
            if grid[h] != GOLD:
                return t, h, x, vx, 0.0
            vx = -vx
        elif nx < BALL_X_MIN or nx > BALL_X_MAX:
            vx = -vx
        else:
            x = nx
        ny = y + vy
        h = hit(x, ny)
        if h:
            if grid[h] != GOLD:
                return t, h, x, vx, 0.0
            vy = -vy
        elif ny < BALL_Y_MIN:
            vy = -vy
        else:
            y = ny
        if tc is not None and t % 4 == 0:
            mind = min(mind, float(np.min(np.abs(tc[:, 0] - x) + np.abs(tc[:, 1] - y))))
        if y > BALL_HIT_Y:
            return t, None, x, vx, mind
    return limit, None, x, vx, mind


def simulate_rate(grid, x, y, vx, vy, limit=1500):
    """Полёт до возвращения к ракетке с разбиванием кирпичей (обычный — 1, удар по серебряному — 0.5, золото
    отражает). Возвращает (ценность разбитого, кадров полёта)."""
    g = grid.copy()
    value = 0.0

    def hit(px, py):
        c = int((px - 41 + R) // 16), int((px - 41 - R) // 16)
        r = int((py - 1 + R) // 8), int((py - 1 - R) // 8)
        for rr in {r[0], r[1]}:
            for cc in {c[0], c[1]}:
                if 0 <= rr < ROWS and 0 <= cc < COLS and g[rr, cc]:
                    bx, by = 41 + 16 * cc, 1 + 8 * rr
                    if bx - R <= px < bx + 15 + R and by - R <= py < by + 7 + R:
                        return rr, cc
        return None

    def smash(h):
        nonlocal value
        k = g[h]
        if k == NORMAL:
            value += 1.0
            g[h] = EMPTY
        elif k == SILVER:
            value += 0.5
    for t in range(1, limit):
        nx = x + vx
        h = hit(nx, y)
        if h:
            smash(h)
            vx = -vx
        elif nx < BALL_X_MIN or nx > BALL_X_MAX:
            vx = -vx
        else:
            x = nx
        ny = y + vy
        h = hit(x, ny)
        if h:
            smash(h)
            vy = -vy
        elif ny < BALL_Y_MIN:
            vy = -vy
        else:
            y = ny
        if y > BALL_HIT_Y:
            return value, t
    return value, limit


class Player:
    def __init__(self):
        self.t = 0
        self.phase = "boot"
        self.phase_t = 0
        self.snapshot = None
        self.lag = LAG
        self.pad_obs = []
        self.cmd_hist = []
        self.moves = [0.0] * 5  # сдвиги ракетки по последним командам, ещё не видимые на экране
        self.est = 128.0            # оценка текущей позиции ракетки (с учётом невидимых сдвигов)
        self.tracks = []            # треки всех мячей
        self.track = []             # история (x, y) отслеживаемого мяча без отскоков
        self.still = 0
        self.aim = None
        self.locked = None
        self.grid = None
        self.cycle = 0
        self.pad_half = 12.0      # полуширина ракетки (бывает расширенной)
        self.caps_prev = []
        self.shots = []
        self.progress_sig, self.progress_t = None, 0
        self.cnt_hist = []
        self.rng = 12345
        self.rest_prev = None
        self.avoid = set()        # цвета капсул, которые не ловим

    # --- меню до игры ---
    def menus(self, f):
        self.phase_t += 1
        if self.phase == "boot":
            if blue_menu(f):
                if self.phase_t > 30:
                    self.phase, self.phase_t = "video", 0
                    self.snapshot = f[60:140].copy()
                    return [Key.E], Mouse()
            else:
                self.phase_t = 0
            return [], Mouse()
        if self.phase == "video":
            # ждём смены текста меню (меню устройства ввода)
            if blue_menu(f) and (f[60:140] != self.snapshot).any() and self.phase_t > 30:
                self.phase, self.phase_t = "device", 0
                return [Key.M], Mouse()
            return [], Mouse()
        if self.phase == "device":
            # заставка: клик запускает историю, второй клик её пропускает
            if f.shape[0] == 200 and self.phase_t > 20 and self.phase_t % 40 < 3:
                return [], Mouse(left=True)
            return [], Mouse()
        return [], Mouse()

    def act(self, frame):
        self.t += 1
        f = frame
        if self.phase != "game":
            if f is not None and f.shape[0] == 200 and in_game(f):
                self.phase = "game"
            else:
                return self.menus(f) if f is not None else ([], Mouse())
        if not in_game(f):
            return self.command(self.est, False)
        return self.play(f)

    def command(self, target, click):
        self.last_target = target
        """Поставить ракетку в target (центр по x) с учётом невидимых ещё сдвигов.
        Пока недавний сдвиг не проявился на экране, мелкие поправки не шлём: задержка отклика
        игры немного плавает, и непрерывная обратная связь раскачивает ракетку."""
        lo, hi = self.pad_range()
        target = min(max(target, lo), hi)
        err = target - self.est
        # после хода ждём, пока он наверняка проявится (задержка 2..3 кадра и плавает), и лишь потом
        # поправляем; сразу — только большие переносы (новая цель)
        settling = any(m != 0 for m in self.moves[-4:])
        if abs(err) < 0.5 or (settling and abs(err) < 15):
            dx = 0
        else:
            dx = int(round(err * 4))
        move = dx / 4
        self.est = min(max(self.est + move, lo), hi)
        self.moves = self.moves[1:] + [move]
        self.cmd_hist = (self.cmd_hist + [self.est])[-24:]
        return [], Mouse(dx=dx, left=click)

    def estimate_lag(self):
        """Задержка (1..4 кадра), при которой видимые положения ракетки лучше всего совпадают с командами."""
        obs, cmd = self.pad_obs, self.cmd_hist
        n = min(len(obs), len(cmd))
        if n < 12:
            return self.lag
        best, be = self.lag, None
        for L in (1, 2, 3, 4):
            # obs[-1] — кадр после команды cmd[-1]; при задержке L он показывает cmd[-1-L]... (cmd[-L-1+1])
            e = 0.0; k = 0
            for i in range(1, n - L):
                o, c = obs[-i], cmd[-i - L]
                if o is not None:
                    e += min(abs(o - c), 30); k += 1
            if k >= 6:
                e /= k
                if be is None or e < be - 0.3 or (abs(e - be) <= 0.3 and L == self.lag):
                    best, be = L, e
        return best

    # --- игра ---
    def play(self, f):
        pad = find_paddle(f)
        if pad is not None:
            # экран показывает позицию до последних lag команд; lag обычно 3, но бывает 2 (раунд 33) —
            # оцениваем по тому, какая задержка лучше объясняет видимые положения ракетки
            self.pad_half = paddle_half(f) or self.pad_half
            self.pad_obs = (self.pad_obs + [pad])[-24:]
            self.lag = self.estimate_lag()
            lo, hi = self.pad_range()
            self.est = min(max(pad + sum(self.moves[len(self.moves) - self.lag:]), lo), hi)
        else:
            self.pad_obs = (self.pad_obs + [None])[-24:]
        if self.t % 10 == 0 or self.grid is None:
            self.grid = read_bricks(f)
            # застой: число разбиваемых кирпичей не уменьшается — траектория зациклилась. По счёту нельзя:
            # он растёт и без прогресса (сбитые враги, раунд 25). Враги, пролетая над клетками, на время
            # «стирают» кирпичи, поэтому берём максимум за последние 30 замеров (300 кадров).
            self.cnt_hist = (self.cnt_hist + [int(((self.grid == NORMAL) | (self.grid == SILVER)).sum())])[-30:]
            cnt = max(self.cnt_hist)
            if self.progress_sig is None or cnt != self.progress_sig:
                self.progress_sig, self.progress_t = cnt, self.t
        balls = find_balls(f)
        ball = self.pick_ball(balls)
        vel = self.update_track(ball)

        caps = self.update_capsules(f)
        laser = pad is not None and has_laser(f, pad)
        target, click = self.est, False
        if ball is not None:
            target = self.choose_target(ball, vel)
            free = self.free_time(ball, vel)
            cap = self.capsule_to_catch(caps, ball, vel)
            if cap is not None:
                target = cap
            elif laser and free:
                lt = self.laser_target()
                if lt is not None:
                    target = lt
            # мяч лежит на ракетке — не гнаться за ним, а запустить. Он едет вместе с ракеткой, но
            # с лишней задержкой ~2 кадра, поэтому признак покоя — неизменная высота, а не положение.
            if 171 <= ball[1] <= 174 and ball[1] == self.rest_prev:
                self.still += 1
            else:
                self.still = 0
            self.rest_prev = ball[1]
            if self.still >= 3:
                target = self.est
                click = self.still % 4 < 2
        if laser and self.t % 2 == 0:
            click = True                   # лазер: стреляем непрерывно
        shots = self.update_shots(f, balls)
        if shots:
            target = self.dodge(target, shots, ball, vel)
        return self.command(target, click)

    # --- снаряды босса (раунд 33): бело-серые осколки ~7x7, летят вниз по наклонной ---
    def update_shots(self, f, balls):
        reg = (f[60:176, FIELD_L:FIELD_R] == W).all(2)
        for bx, by in balls:                      # мячи не считаем
            y0, x0 = by - 3 - 60, bx - 3 - FIELD_L
            reg[max(y0, 0):max(y0 + 7, 0), max(x0, 0):max(x0 + 7, 0)] = False
        cur = []
        if reg.any():
            n, lab, st, cen = cv2.connectedComponentsWithStats(reg.astype(np.uint8))
            for i in range(1, n):
                if 4 <= st[i, 4] <= 64 and st[i, 2] <= 10 and st[i, 3] <= 10:
                    cur.append((cen[i][0] + FIELD_L, cen[i][1] + 60))
        tracks = []
        for c in cur:
            prev = [tr for tr in self.shots if 0 < c[1] - tr[-1][1] <= 6 and abs(c[0] - tr[-1][0]) <= 4]
            tracks.append((min(prev, key=lambda tr: abs(c[0] - tr[-1][0])) + [c])[-8:] if prev else [c])
        self.shots = tracks
        return [tr for tr in tracks if len(tr) >= 3]

    def shot_hits(self, shots, horizon):
        """[(кадров до строки ракетки, x)] для снарядов, которые долетят в пределах horizon кадров."""
        res = []
        for tr in shots:
            n = len(tr)
            vx = (tr[-1][0] - tr[0][0]) / (n - 1)
            vy = (tr[-1][1] - tr[0][1]) / (n - 1)
            if vy <= 0.3:
                continue
            T = (PADDLE_TOP - 3 - tr[-1][1]) / vy
            if -2 <= T <= horizon:
                res.append((T, tr[-1][0] + vx * max(T, 0)))
        return res

    def dodge(self, target, shots, ball, vel):
        """Сдвинуть цель так, чтобы снаряды не попали в ракетку; мяч при этом не упустить."""
        hits = self.shot_hits(shots, LAG + 14)
        if not hits:
            return target
        margin = self.pad_half + 12          # попадание засчитывается щедрее видимых контуров

        def safe(x):
            return all(abs(x - hx) >= margin for _, hx in hits)
        if safe(target):
            return target
        lo, hi = self.pad_range()
        cands = np.arange(lo, hi + 0.1, 1.0)
        # мяч на подлёте: ракетка должна остаться под ним (смещение не больше 10)
        if ball is not None and vel is not None and vel[1] > 0:
            steps = (BALL_HIT_Y - ball[1]) / vel[1]
            if steps < LAG + 16:
                land = self.locked if self.locked is not None else self.landing_x(ball[0], ball[1], vel)
                band = [c for c in cands if abs(c - land) <= 10 and safe(c)]
                if band:
                    return min(band, key=lambda c: abs(c - target))
                return target                     # некуда — мяч важнее
        ok = [c for c in cands if safe(c)]
        return min(ok, key=lambda c: abs(c - target)) if ok else target

    def free_time(self, ball, vel):
        """Мяч не долетит до ракетки раньше, чем мы успеем отойти и вернуться."""
        if vel is None or abs(vel[1]) < 0.3:
            return False
        return (BALL_HIT_Y - ball[1]) / abs(vel[1]) > 2 * LAG + 8

    def laser_target(self):
        """Центр ракетки, при котором лучи (центр ±8) попадут в нижние разбиваемые кирпичи двух столбцов."""
        if self.grid is None:
            return None
        val = []
        for c in range(COLS):
            col = self.grid[:, c]
            nz = np.flatnonzero(col)
            v = 0.0
            if len(nz):
                k = col[nz[-1]]
                v = 1.0 if k == NORMAL else 0.5 if k == SILVER else 0.0
            val.append(v)
        lo, hi = self.pad_range()
        best, bs = None, 0.0
        for c in range(COLS - 1):
            x = 56 + 16 * c
            if not lo <= x <= hi:
                continue
            s = val[c] + val[c + 1] - abs(x - self.est) / 1000
            if s > bs:
                best, bs = x, s
        return best

    def update_capsules(self, f):
        """Капсулы, подтверждённые движением вниз (тот же столбец, y вырос на 0..3 с прошлого кадра)."""
        cur = find_capsules(f)
        ok = [c for c in cur if any(p[1] == c[1] and 0 <= c[2] - p[2] <= 3 and p[0] == c[0] for p in self.caps_prev)]
        self.caps_prev = cur
        return ok

    def capsule_to_catch(self, caps, ball, vel):
        """Центр капсулы, под которую стоит встать сейчас, или None (мяч важнее)."""
        if not caps or vel is None:
            return None
        x, y = ball
        vy = vel[1]
        if abs(vy) < 0.3:
            return None
        # не раньше, чем через столько кадров мяч может оказаться у ракетки
        t_ball = (BALL_HIT_Y - y) / abs(vy)
        best = None
        for name, cx, cy in caps:
            if name in self.avoid:
                continue
            t_cap = (PADDLE_TOP - cy) / CAPSULE_SPEED
            if t_cap > LAG + 2 or t_cap < -5:
                continue                    # рано идти / уже пролетела
            if t_ball < t_cap + 2 * LAG + 6:
                continue                    # не успеем вернуться к мячу
            best = cx
        return best

    def pick_ball(self, balls):
        """Несколько мячей: ведём трек каждого, следим за тем, что раньше всех долетит до ракетки."""
        tracks, free = [], list(balls)
        for tr in self.tracks:
            if not free:
                break
            n = len(tr)
            v = ((tr[-1][0] - tr[0][0]) / (n - 1), (tr[-1][1] - tr[0][1]) / (n - 1)) if n >= 2 else (0, 0)
            px, py = tr[-1][0] + v[0], tr[-1][1] + v[1]
            b = min(free, key=lambda b: abs(b[0] - px) + abs(b[1] - py))
            if abs(b[0] - px) + abs(b[1] - py) <= 10:
                free.remove(b)
                tracks.append(self._extend(tr, b))
        tracks += [[b] for b in free]
        self.tracks = tracks
        if not tracks:
            return None

        def urgency(tr):
            n = len(tr)
            if n < 3:
                return 300.0
            vy = (tr[-1][1] - tr[0][1]) / (n - 1)
            y = tr[-1][1]
            return (BALL_HIT_Y - y) / vy if vy > 0.3 else 400.0 - y
        best = min(tracks, key=urgency)
        cur = next((tr for tr in tracks if self.track and len(tr) >= 2 and tr[-2] == self.track[-1]), None)
        if cur is not None and urgency(cur) <= urgency(best) + 6:
            best = cur
        elif cur is not best:
            self.aim = self.locked = None
        self.track = best[:-1]       # update_track допишет последнюю точку
        return best[-1]

    @staticmethod
    def _extend(tr, ball):
        if len(tr) >= 2:
            n = len(tr)
            vx = (tr[-1][0] - tr[0][0]) / (n - 1)
            vy = (tr[-1][1] - tr[0][1]) / (n - 1)
            if abs(ball[0] - tr[-1][0] - vx) > 2.5 or abs(ball[1] - tr[-1][1] - vy) > 2.5:
                tr = [tr[-1]]
        return (tr + [ball])[-12:]

    def update_track(self, ball):
        """Скорость мяча по прямолинейному участку траектории (сброс при отскоке)."""
        if ball is None:
            self.track = []
            return None
        tr = self.track
        if len(tr) >= 2:
            n = len(tr)
            vx = (tr[-1][0] - tr[0][0]) / (n - 1)
            vy = (tr[-1][1] - tr[0][1]) / (n - 1)
            px, py = tr[-1][0] + vx, tr[-1][1] + vy
            if abs(ball[0] - px) > 2.5 or abs(ball[1] - py) > 2.5:
                tr = [tr[-1]]
        elif len(tr) == 1 and (abs(ball[0] - tr[0][0]) > 8 or abs(ball[1] - tr[0][1]) > 8):
            tr = []
        tr = (tr + [ball])[-12:]
        self.track = tr
        if len(tr) < 2:
            return None
        n = len(tr)
        return ((tr[-1][0] - tr[0][0]) / (n - 1), (tr[-1][1] - tr[0][1]) / (n - 1))

    def choose_target(self, ball, vel):
        x, y = ball
        if vel is None or vel[1] <= 0:
            self.aim = self.locked = None
            return x
        steps = (BALL_HIT_Y - y) / vel[1]
        if steps <= LAG + 1 and self.locked is not None:
            return self.locked          # поздно что-то менять: команда не успеет
        land = self.landing_x(x, y, vel)
        if self.aim is None or y < 150:
            self.aim = self.choose_offset(land, vel)
        self.locked = land - self.aim
        return self.locked

    def choose_offset(self, land, vel):
        """Смещение точки удара, при котором мяч быстрее всего разобьёт кирпич.
        Поиск на два отскока от ракетки вперёд; если кирпич недостижим — минимальное сближение,
        при равенстве — чередование вариантов, чтобы не зацикливаться."""
        if self.grid is None:
            return 0.0
        speed = (vel[0] ** 2 + vel[1] ** 2) ** 0.5
        lo, hi = self.pad_range()
        if self.t - self.progress_t > STALL_FRAMES:
            # цикл: модель уверена, а на деле ничего не разбивается — пробуем углы вразнобой
            ok = [off for off, _ in ZONES if lo <= land - off <= hi]
            if ok:
                self.rng = (self.rng * 1103515245 + 12345) % (1 << 31)
                return ok[(self.rng >> 8) % len(ok)]
        # главный критерий: разбитое за полёт / время полёта (поощряет загнать мяч за стену кирпичей)
        rated = []
        for off, (ux, uy) in ZONES:
            if lo <= land - off <= hi:
                v, t = simulate_rate(self.grid, land, BALL_HIT_Y, ux * speed, uy * speed)
                if v > 0:
                    rated.append((v / (t + 20), off))
        if rated:
            return max(rated)[1]
        options = []
        for off, (ux, uy) in ZONES:
            if not lo <= land - off <= hi:
                continue
            t, h, bx, bvx, mind = simulate(self.grid, land, BALL_HIT_Y, ux * speed, uy * speed)
            if h is None:
                # второй отскок: мяч вернулся в точку bx, выбираем лучшее продолжение
                best2, mind2 = None, mind
                for off2, (ux2, uy2) in ZONES:
                    if not lo <= bx - off2 <= hi:
                        continue
                    t2, h2, _, _, md2 = simulate(self.grid, bx, BALL_HIT_Y, ux2 * speed, uy2 * speed, limit=300)
                    mind2 = min(mind2, md2)
                    if h2 is not None and (best2 is None or t2 < best2):
                        best2 = t2
                score = (1, t + best2, 0) if best2 is not None else (2, mind2, 0)
            else:
                score = (0, t, 0)
            options.append((score, off))
        if not options:
            return 0.0
        options.sort()
        if options[0][0][0] == 2:
            # ничего не достижимо — чередуем, иначе траектория повторяется вечно
            self.cycle += 1
            return options[self.cycle % len(options)][1]
        return options[0][1]

    def pad_range(self):
        hw = self.pad_half
        return FIELD_L + hw, FIELD_R - 1 - hw

    @staticmethod
    def landing_x(x, y, vel):
        """Где будет центр мяча в момент удара о ракетку (с отражениями от боковых стенок).
        Касание фактически происходит чуть ниже 173 (пологий мяч успевает сдвинуться ещё на кадр)."""
        vx, vy = vel
        steps = (LAND_Y - y) / vy
        px = x + vx * steps
        lo, hi = BALL_X_MIN, BALL_X_MAX
        span = hi - lo
        u = (px - lo) % (2 * span)
        return lo + (u if u <= span else 2 * span - u)
