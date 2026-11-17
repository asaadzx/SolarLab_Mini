"""MicroPython boot hook: start the application without blocking the REPL."""

import sys  # Used to print the full traceback if the application crashes

try:
    import main  # main.py runs the forever loop (sensor, OLED, AP, webserver)
except Exception as e:  # e is the error raised while importing or starting main
    print('boot error:', e)  # Short error message for the serial console
    sys.print_exception(e)   # Full traceback makes hardware faults easier to debug
