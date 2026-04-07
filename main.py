"""RetroSprite - Pixel Art Creator & Animator."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import RetroSpriteApp


def main():
    while True:
        try:
            app = RetroSpriteApp()
        except SystemExit:
            break
        restart = app.run()
        if not restart:
            break


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("export", "batch", "run", "info"):
        from src.cli import main as cli_main
        sys.exit(cli_main())
    else:
        main()
