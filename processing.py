"""Small helpers to normalize and persist scraped data."""
import pandas as pd
import unicodedata


def normalize_name(name: str) -> str:
    if not name:
        return name
    # remove weird whitespace and normalize unicode
    s = unicodedata.normalize("NFKC", name)
    s = s.strip()
    s = " ".join(s.split())
    return s


def clean_trupp(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    if "name" in df.columns:
        df["name"] = df["name"].apply(normalize_name)
    return df


def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)
