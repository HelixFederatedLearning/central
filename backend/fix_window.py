# fix_window.py
import sys
import os

# Ensure backend folder is on PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import engine
from app.db.models import Setting
from sqlmodel import Session

with Session(engine) as session:
    st = session.get(Setting, 1)
    if st is None:
        print("No Setting row found — creating one...")
        st = Setting(id=1, window_minutes=1)
        session.add(st)
    else:
        print(f"Found existing window: {st.window_minutes} → Updating to 1")
        st.window_minutes = 1
        session.add(st)

    session.commit()
    print("✔ Window updated to 1 minute!")
