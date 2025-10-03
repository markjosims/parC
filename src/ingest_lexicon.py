from src.constants import VERB_ROOTS_PATH
from src.database import engine, SessionLocal, Base
from tqdm import tqdm
import pandas as pd
from src.models import Lexeme
from sqlalchemy.orm import Session

def ingest_verbs(df: pd.DataFrame, db: Session):
    num_rows = len(df)
    for i, row in tqdm(df.iterrows(), total=num_rows):
        new_lexeme = Lexeme(
            root=row['verb_root'],
            part_of_speech='verb',
            gloss=row['root_sense'],
            lexical_info={"fv_class": row['root_fv']}
        )
        db.add(new_lexeme)
        db.flush()
    db.commit()
    print("Ingestion of verbs successful")

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print(f"Reading verb lexical data from {VERB_ROOTS_PATH}")
        df = pd.read_csv(VERB_ROOTS_PATH, keep_default_na=False)
        ingest_verbs(df, db)

    except Exception as e:
        print(f"Error occurred: {e}")
        print("Rolling back changes to database.")
    finally:
        db.close()

    return 0


if __name__ == '__main__':
    main()