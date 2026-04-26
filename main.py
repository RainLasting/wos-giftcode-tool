import os
import sys


def main():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    import tkinter as tk
    from gui import GiftCodeApp

    root = tk.Tk()
    app = GiftCodeApp(root, application_path)
    root.mainloop()


if __name__ == '__main__':
    main()
