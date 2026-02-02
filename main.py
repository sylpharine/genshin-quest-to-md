import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from genshhin_json_to_md.cli import main


if __name__ == "__main__":
    main()
