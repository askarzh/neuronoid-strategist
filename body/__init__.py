"""«Тело» исследователя: включить игру в эмуляторе, смотреть на экран, нажимать клавиши и двигать мышь."""

from pathlib import Path

from body.emulator import Key, LibretroEmulator, Mouse

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "games" / "arkanoid" / "DOS_arkanoid.zip"
CORE = ROOT / "cores" / "dosbox_pure_libretro.dll"

__all__ = ["Key", "LibretroEmulator", "Mouse", "power_on"]


def power_on(audio: bool = False) -> LibretroEmulator:
    """Включает компьютер с игрой: эмулятор стартует с самого начала, как после включения питания."""
    return LibretroEmulator(CORE, GAME, audio=audio)
