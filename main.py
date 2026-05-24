"""
main.py
───────
Project Eris – entry point.

This is the only file you need to run to start the application.
It sets the CustomTkinter appearance theme, then hands control to
the App class which builds all the windows and screens.

Run from the command line:   python main.py
Run from VS Code:            Press F5  (uses .vscode/launch.json)
"""

import customtkinter as ctk
from gui.app import App

if __name__ == "__main__":
    # Set the default visual theme before any widgets are created.
    # The user can toggle dark/light at runtime; this is just the startup default.
    # The saved preference in config.json overrides this inside App.__init__.
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    # Create and run the main application window.
    # mainloop() blocks here until the user closes the window.
    app = App()
    app.mainloop()
