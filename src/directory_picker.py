# Source - https://stackoverflow.com/a/49399213
# Posted by Siva Madugula, modified by community. See post Timeline for change history
# Retrieved 2026-06-24, License - CC BY-SA 3.0

from tkinter import filedialog, Tk


def pick_directory():
    root = Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory()
    with open(".env", "w") as f:
        f.write(f"CONFIG_DIR={folder_selected}")
