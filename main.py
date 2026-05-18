import argparse
import sys

from ui.cli_app import run_cli


def _start_gui():
    try:
        from ui.gui_app import start_gui

        start_gui()
        return True
    except KeyboardInterrupt:
        print("\nExecucao interrompida pelo usuario.")
        return True
    except Exception as exc:
        print("Nao foi possivel iniciar a interface grafica.")
        print(f"Detalhes: {exc}")
        print("Dica: valide a instalacao do Tk/Tcl do Python ou rode em modo terminal com --cli.")
        return False


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="The Touchline")
    parser.add_argument("--gui", action="store_true", help="Forca abertura da interface grafica")
    parser.add_argument("--cli", action="store_true", help="Executa o jogo no terminal")
    parser.add_argument(
        "--fallback-cli",
        action="store_true",
        help="Se a GUI falhar, continua automaticamente no terminal",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])

    if args.cli:
        run_cli()
        return

    gui_ok = _start_gui()
    if gui_ok:
        return

    if args.fallback_cli:
        print("\nIniciando modo terminal por fallback...")
        run_cli()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExecucao interrompida pelo usuario.")
