# train_intent_model.py
from pathlib import Path
import re
import pandas as pd
import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

EXCEL_PATH = DATA_DIR / "knowledge_base_grouped.xlsx"
MODEL_PATH = BASE_DIR / "intent_group_model.joblib"

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_ar(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[\u0617-\u061A\u064B-\u0652]", "", t)
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    t = t.replace("ى", "ي").replace("ة", "ه")
    t = t.replace("ؤ", "و").replace("ئ", "ي")
    t = re.sub(r"[^\w\s\u0600-\u06FF]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def main():
    if not EXCEL_PATH.exists():
        raise RuntimeError(f"Excel not found: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)

    for col in ["intent_group", "question"]:
        if col not in df.columns:
            raise RuntimeError("Excel must include columns: intent_group, question")

    for col in ["keywords", "variants"]:
        if col not in df.columns:
            df[col] = ""

    df = df.dropna(subset=["intent_group", "question"])
    df["intent_group"] = df["intent_group"].astype(str).map(norm)
    df["question"] = df["question"].astype(str).map(norm)
    df["keywords"] = df["keywords"].fillna("").astype(str).map(norm)
    df["variants"] = df["variants"].fillna("").astype(str).map(norm)

    df["text"] = df.apply(lambda r: f"{r['question']} | {r['keywords']} | {r['variants']}", axis=1)
    df["text"] = df["text"].map(normalize_ar)

    df = df[df["intent_group"].str.len() > 0]

    X = df["text"].tolist()
    y = df["intent_group"].tolist()

    clf = Pipeline(steps=[
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)),
        ("lr", LogisticRegression(max_iter=4000, solver="lbfgs"))
    ])

    clf.fit(X, y)
    joblib.dump(clf, MODEL_PATH)

    print(f"✅ Saved group model: {MODEL_PATH}")
    print("✅ Groups:", sorted(set(y)))

if __name__ == "__main__":
    main()