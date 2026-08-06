"""Unified desktop entry point for interactive and command-line modes."""

import sys


CLI_COMMANDS = {"check", "status", "rotate", "ip", "stop", "start", "info", "config"}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--cli":
        args.pop(0)
        from app.cli import CLI
        return CLI().run(args)
    if args and (args[0] in CLI_COMMANDS or args[0] == "--version"):
        from app.cli import CLI
        return CLI().run(args)

    from app.shell import main as shell_main
    return shell_main()


if __name__ == "__main__":
    raise SystemExit(main())
