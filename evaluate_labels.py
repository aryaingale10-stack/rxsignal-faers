"""Score the hand-labeled sample: accuracy per method, and Cohen's kappa between two reviewers.

1. Open output/manual_review_sample.csv in Excel / Google Sheets.
2. For each row, put Y or N in 'reviewer1_correct (Y/N)':
     - matched rows: Y if 'ingredient' is the right active ingredient for 'raw_name'
     - unresolved rows: Y if the name really is not a usable drug name (so leaving it
       unmatched was correct), N if it was a real drug the pipeline missed
3. (Optional) Ask a classmate to fill 'reviewer2_correct (Y/N)' without looking at yours.
4. Run:  python evaluate_labels.py
"""
import pandas as pd

from src.config import OUTPUT_DIR

R1, R2 = "reviewer1_correct (Y/N)", "reviewer2_correct (Y/N)"


def to_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper().map({"Y": True, "YES": True, "N": False, "NO": False})


def cohens_kappa(a: pd.Series, b: pd.Series) -> float:
    n = len(a)
    po = (a == b).mean()
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main():
    df = pd.read_csv(OUTPUT_DIR / "manual_review_sample.csv", dtype=str, keep_default_na=False)
    df["r1"] = to_bool(df[R1])
    labeled = df[df["r1"].notna()].copy()
    if labeled.empty:
        print(f"No labels yet. Fill in '{R1}' with Y/N first.")
        return
    labeled["r1"] = labeled["r1"].astype(bool)
    print(f"Labeled rows: {len(labeled)}\n")
    print("Accuracy by method (reviewer 1):")
    summary = labeled.groupby("method")["r1"].agg(["mean", "size"])
    for method, row in summary.iterrows():
        print(f"  {method:15s} {100 * row['mean']:5.1f}%  (n={int(row['size'])})")
    matched = labeled[labeled["method"] != "unresolved"]
    if len(matched):
        print(f"\nOverall accuracy of matched names: {100 * matched['r1'].mean():.1f}% (n={len(matched)})")

    df["r2"] = to_bool(df[R2])
    both = df[df["r1"].notna() & df["r2"].notna()]
    if len(both) >= 10:
        k = cohens_kappa(both["r1"].astype(bool), both["r2"].astype(bool))
        print(f"\nInter-rater agreement (Cohen's kappa): {k:.3f} on {len(both)} rows")
    summary.rename(columns={"mean": "accuracy", "size": "n"}).to_csv(OUTPUT_DIR / "manual_accuracy_by_method.csv")


if __name__ == "__main__":
    main()
