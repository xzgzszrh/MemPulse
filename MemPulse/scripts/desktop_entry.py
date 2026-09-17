from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from mempulse.desktop import main
if __name__ == '__main__':
    main()
