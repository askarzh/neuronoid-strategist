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


def find_ball(f):
    """Центр мяча (x, y) или None. Мяч: 5x5, вверху-слева белые пиксели 'WW' над 'W', обрамлены серым."""
    reg = f[8:190, FIELD_L:FIELD_R]
    w = (reg == W).all(2)
    s = (reg == S).all(2)
    # ядро мяча: W W в строке y, W в строке y+1 под левым, серый справа от него; s слева от обоих
    core = w[:-1, 1:-2] & w[:-1, 2:-1] & w[1:, 1:-2] & s[1:, 2:-1] & s[:-1, :-3] & s[1:, :-3]
    ys, xs = np.nonzero(core)
    if len(ys) == 0:
        return None
    # исключаем находки внутри кирпичей/стенок: над ядром должен быть серый верх мяча и чёрное вокруг
    best = None
    for y, x in zip(ys, xs):
        yy, xx = y + 8, x + FIELD_L  # координата ядра (левый W) в кадре = xx+1
        cx, cy = xx + 2, yy + 1
        if yy - 1 < 0:
            continue
        top = f[yy - 1, xx + 1:xx + 4]
        if not (top == S).all():
            continue
        corner = f[yy - 1, xx]
        if corner.any():
            continue
        best = (cx, cy)
        break
    return best


def blue_menu(f):
    """Текстовое меню на синем фоне (выбор видеорежима / устройства ввода)."""
    return f.shape == (400, 640, 3) and (f[::8, ::8] == [0, 0, 170]).all(2).mean() > 0.3


class Player:
    def __init__(self):
        self.t = 0
        self.phase = "boot"
        self.phase_t = 0
        self.snapshot = None
        self.pos = 128.0          # где, по нашим командам, должна быть ракетка
        self.hist = []            # история команд (для учёта задержки)
        self.ball_prev = None
        self.ball_vel = None
        self.still = 0
        self.mismatch = 0

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
            if blue_menu(f) and \
                    (f[60:140] != self.snapshot).any() and self.phase_t > 30:
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
            if f.shape[0] == 200 and in_game(f):
                self.phase = "game"
            else:
                return self.menus(f)
        if not in_game(f):
            return [], Mouse()
        return self.play(f)

    # --- игра ---
    def play(self, f):
        pad = find_paddle(f)
        ball = find_ball(f)
        # сверка: экран показывает позицию, заданную LAG кадров назад
        if pad is not None and len(self.hist) >= LAG:
            expected = self.hist[-LAG]
            if abs(pad - expected) > 1.0:
                self.mismatch += 1
                if self.mismatch >= 2:
                    self.pos += pad - expected
                    self.hist = [h + (pad - expected) for h in self.hist]
                    self.mismatch = 0
            else:
                self.mismatch = 0

        if ball is not None and self.ball_prev is not None:
            self.ball_vel = (ball[0] - self.ball_prev[0], ball[1] - self.ball_prev[1])
        self.ball_prev = ball

        target = self.pos
        click = False
        if ball is not None:
            target = self.choose_target(ball, self.ball_vel)
            # мяч лежит на ракетке — запустить
            if self.ball_vel == (0, 0) and ball[1] >= PADDLE_TOP - 6:
                self.still += 1
            else:
                self.still = 0
            click = self.still > 5 and self.still % 10 < 2

        target = min(max(target, PAD_CENTER_MIN), PAD_CENTER_MAX)
        dx = int(round((target - self.pos) * 4))
        self.pos += dx / 4
        self.hist.append(self.pos)
        if len(self.hist) > 20:
            self.hist.pop(0)
        return [], Mouse(dx=dx, left=click)

    def choose_target(self, ball, vel):
        x, y = ball
        if vel is None or vel[1] <= 0:
            return x
        vx, vy = vel
        # предсказание точки, где центр мяча окажется на высоте удара о ракетку
        hit_y = PADDLE_TOP - 3
        steps = (hit_y - y) / vy
        px = x + vx * steps
        lo, hi = FIELD_L + 2, FIELD_R - 3
        span = hi - lo
        # отражения от стенок
        u = (px - lo) % (2 * span)
        px = lo + (u if u <= span else 2 * span - u)
        return px
