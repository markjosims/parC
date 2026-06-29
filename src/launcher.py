import os
import sys
import dotenv
import uvicorn

dotenv.load_dotenv()

if not os.environ.get("CONFIG_DIR"):
    from tkinter import filedialog, Tk

    def pick_directory():
        root = Tk()
        root.withdraw()
        folder_selected = filedialog.askdirectory()
        with open(".env", "w") as f:
            f.write(f"CONFIG_DIR={folder_selected}")

    pick_directory()
    dotenv.load_dotenv()

if not os.environ.get("CONFIG_DIR"):
    sys.exit("No config directory selected.")

uvicorn.run("src.api:app", host="127.0.0.1", port=8000, reload=True)
