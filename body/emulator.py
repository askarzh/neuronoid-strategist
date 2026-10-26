"""Эмулятор DOSBox Pure (libretro) внутри Python: кадры экрана, клавиатура, мышь, сохранения.

Одна копия эмулятора на процесс (ядро libretro хранит глобальное состояние; повторное
создание после close() зависает). Клавиши — `Key` (коды RETROK_*): `Key.A`..`Key.Z`,
`Key.Zero`..`Key.Nine`, `Key.RETURN`, `Key.SPACE`, `Key.ESCAPE`, стрелки `Key.LEFT` и т. д.
"""

from collections.abc import Iterable
from ctypes import byref
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from libretro import ArrayAudioDriver, ArrayVideoDriver, Session
from libretro.api.av import retro_system_av_info
from libretro.api.input import Key, MouseState

__all__ = ["DEFAULT_OPTIONS", "Key", "LibretroEmulator", "Mouse"]

# Фиксированная скорость CPU эмулятора — для воспроизводимости.
DEFAULT_OPTIONS: dict[str, str] = {"dosbox_pure_cycles": "4720"}

# Сколько кадров прогнать после unserialize, чтобы frame() показывал уже
# загруженное состояние (подобрано тестом со случайной историей и паузами).
LOAD_SETTLE_FRAMES = 2

_instance_created = False


@dataclass(frozen=True)
class Mouse:
    """Состояние мыши на каждый кадр шага: смещение и кнопки."""

    dx: int = 0
    dy: int = 0
    left: bool = False
    right: bool = False


class LibretroEmulator:
    def __init__(
        self,
        core: Path,
        game: Path,
        options: dict[str, str] | None = None,
        audio: bool = False,
    ):
        global _instance_created
        for path in (core, game):
            if not Path(path).is_file():
                raise FileNotFoundError(path)
        if _instance_created:
            raise RuntimeError(
                "one emulator per process (even after close): ядро libretro хранит глобальное состояние"
            )
        self._audio_enabled = audio
        self._mouse: MouseState | None = None
        self._held: set[Key] = set()
        self._video = ArrayVideoDriver()
        self._audio = ArrayAudioDriver()
        self._session = Session(
            core,
            game,
            video=self._video,
            audio=self._audio,
            input=self._inputs,
            options={**DEFAULT_OPTIONS, **(options or {})},
            perf=None,  # perf-драйвер libretro.py падает на retro_init
            log=None,
        )
        _instance_created = True
        self._session.__enter__()
        # Джойстики на портах не подключены (опрос их кнопок замедлял эмуляцию).
        for port in range(4):
            self._session.core.set_controller_port_device(port, 0)  # RETRO_DEVICE_NONE
        self._closed = False
        self.fps: float = float(self._session.core.get_system_av_info().timing.fps)
        # retro_get_system_av_info в DOSBox Pure ждёт, пока поток эмуляции
        # доделает кадр (TCM_FINISH_FRAME). Без этого retro_run возвращается
        # раньше, и мышь из следующего шага попадает в кадр в момент, зависящий
        # от времени хоста, — игра перестаёт быть детерминированной.
        self._av_info = retro_system_av_info()
        self._finish_frame = self._session.core._core.retro_get_system_av_info
        self._samples: list[np.ndarray] = []

    def _inputs(self):
        while True:
            yield self._mouse

    def _set_keys(self, keys: set[Key]) -> None:
        # libretro.py не шлёт клавиатурные события, зовём обработчик ядра сами
        kb = self._session.input.keyboard_callback
        for key in self._held - keys:
            kb(False, key, 0, 0)
        for key in keys - self._held:
            kb(True, key, key if 32 <= key < 127 else 0, 0)
        self._held = keys

    def step(self, keys: Iterable[Key] = (), frames: int = 1, mouse: Mouse | None = None) -> None:
        """Прогоняет `frames` кадров с нажатыми `keys` и мышью `mouse`; потом всё отпущено."""
        self._set_keys(set(keys))
        if mouse is not None:
            self._mouse = MouseState(x=mouse.dx, y=mouse.dy, left=mouse.left, right=mouse.right)
        for _ in range(frames):
            self._session.run()
            self._finish_frame(byref(self._av_info))
        self._mouse = None
        self._set_keys(set())
        self._drain_audio()

    def _drain_audio(self) -> None:
        buf = self._audio.buffer
        if self._audio_enabled and len(buf):
            self._samples.append(np.frombuffer(buf, dtype=np.int16).copy())
        del buf[:]

    def frame(self) -> np.ndarray:
        """Последний кадр: копия, uint8, (H, W, 3), RGB."""
        d = self._video._frame_dims
        raw = np.frombuffer(self._video._frame, dtype=np.uint8, count=d.length)
        raw = raw.reshape(d.height, d.pitch // 4, 4)
        return raw[:, : d.width, 2::-1].copy()  # XRGB8888 (BGRX в памяти) -> RGB

    def audio(self) -> np.ndarray:
        """Сэмплы int16 (N, 2), накопленные с прошлого вызова; пусто при audio=False."""
        if not self._samples:
            return np.zeros((0, 2), dtype=np.int16)
        out = np.concatenate(self._samples).reshape(-1, 2)
        self._samples.clear()
        return out

    def save_state(self) -> bytes:
        core = self._session.core
        buf = bytearray(core.serialize_size())
        if not core.serialize(buf):
            raise RuntimeError("ядро не смогло сохранить состояние")
        return bytes(buf)

    def load_state(self, state: bytes) -> None:
        """Восстанавливает состояние и прогоняет LOAD_SETTLE_FRAMES кадров.

        Ядро отдаёт картинку с задержкой, а буфер вывода не входит в savestate:
        без этих кадров frame() показал бы картинку до загрузки.
        """
        if not self._session.core.unserialize(state):
            raise RuntimeError("ядро не смогло загрузить состояние")
        self.step(frames=LOAD_SETTLE_FRAMES)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._session.__exit__(None, None, None)

    def __enter__(self) -> "LibretroEmulator":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
