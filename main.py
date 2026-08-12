import sys

if __name__ == "__main__":
    try:
        from gui.main_window import main

        main()
    except Exception:
        # covers startup failures -- anything before the window even opens, which
        # report_callback_exception (in gui/main_window.py) can't catch since that
        # only handles errors from within the running event loop
        from app.errors import show_error_and_log

        show_error_and_log(*sys.exc_info())
        sys.exit(1)
