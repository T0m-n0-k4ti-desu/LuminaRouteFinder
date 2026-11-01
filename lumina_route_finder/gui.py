"""Desktop entry point and backwards-compatible public imports."""
from .ui.controller import Application, main
from .ui.presentation import describe_result, describe_filters
from .analysis import analyze_file

if __name__ == '__main__':
    main()
