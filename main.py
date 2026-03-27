from pathlib import Path

from app_config import AppConfig
from app_logger import AppLogger
from game.controller import GameStateController


def main() -> int:
    base_path = Path(__file__).resolve().parent
    AppConfig.init(base_path)
    AppLogger.configure(base_dir=base_path)
    log = AppLogger.get_logger("cli")
    log.info("Starting interactive chat application")

    try:
        controller = GameStateController(base_path)
        exit_code = controller.run()
        log.info("Application exited with code {}", exit_code)
        return exit_code
    except Exception:
        log.exception("Fatal error while running application")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
