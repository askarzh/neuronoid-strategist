"""Игрок в DOS-Arkanoid: видит только экран (RGB-кадр), управляет клавиатурой и мышью.

Всё об игре выяснено наблюдением (см. LOG.md). Основное:
- старт: меню видеорежима (E = EGA), меню устройства (M = мышь), клик на заставке, клик пропускает историю;
- игровой экран 320x200: поле x 40..215, ракетка в строках 176..181, мяч 5x5;
- мышь: ракетка сдвигается на dx/4 пикселя, без ограничения скорости, отклик через ~3 кадра;
- левая кнопка запускает мяч с ракетки.
"""

import numpy as np

from body import Key, Mouse

# --- геометрия игрового экрана (320x200) ---
FIELD_L, FIELD_R = 40, 217          # внутренность поля по x: [40, 217)
PADDLE_TOP = 176                    # верх ракетки
PAD_CENTER_MIN, PAD_CENTER_MAX = 52, 203
LAG = 3                             # кадров между командой мыши и её видимостью на экране
BALL_HIT_Y = 173                    # центр мяча по y в момент удара о ракетку
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


class Player:
    def __init__(self):
        self.t = 0
        self.phase = "boot"
        self.phase_t = 0
        self.snapshot = None
        self.moves = [0.0] * LAG    # сдвиги ракетки по последним командам, ещё не видимые на экране
        self.est = 128.0            # оценка текущей позиции ракетки (с учётом невидимых сдвигов)
        self.track = []             # история (x, y) отслеживаемого мяча без отскоков
        self.still = 0

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
        """Поставить ракетку в target (центр по x) с учётом невидимых ещё сдвигов."""
        target = min(max(target, PAD_CENTER_MIN), PAD_CENTER_MAX)
        dx = int(round((target - self.est) * 4))
        move = dx / 4
        self.est = min(max(self.est + move, PAD_CENTER_MIN), PAD_CENTER_MAX)
        self.moves = self.moves[1:] + [move]
        return [], Mouse(dx=dx, left=click)

    # --- игра ---
    def play(self, f):
        pad = find_paddle(f)
        if pad is not None:
            # экран показывает позицию до последних LAG команд
            self.est = min(max(pad + sum(self.moves), PAD_CENTER_MIN), PAD_CENTER_MAX)
        balls = find_balls(f)
        ball = self.pick_ball(balls)
        vel = self.update_track(ball)

        target, click = self.est, False
        if ball is not None:
            target = self.choose_target(ball, vel)
            # мяч лежит на ракетке — запустить
            if vel is not None and vel == (0.0, 0.0) and ball[1] >= PADDLE_TOP - 6:
                self.still += 1
            else:
                self.still = 0
            click = self.still > 5 and self.still % 10 < 2
        return self.command(target, click)

    def pick_ball(self, balls):
        if not balls:
            return None
        if self.track:
            lx, ly = self.track[-1]
            return min(balls, key=lambda b: abs(b[0] - lx) + abs(b[1] - ly))
        return max(balls, key=lambda b: b[1])

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
            return x
        return self.landing_x(x, y, vel)

    @staticmethod
    def landing_x(x, y, vel):
        """Где будет центр мяча на высоте удара о ракетку (с отражениями от боковых стенок)."""
        vx, vy = vel
        steps = (BALL_HIT_Y - y) / vy
        px = x + vx * steps
        lo, hi = BALL_X_MIN, BALL_X_MAX
        span = hi - lo
        u = (px - lo) % (2 * span)
        return lo + (u if u <= span else 2 * span - u)
