"""Create a small SYNTHETIC zip in the exact FAERS ASCII format, for testing the code only.
It is NOT real data - never use its numbers in a report or on a resume."""
import random
import sys
import zipfile
from pathlib import Path

random.seed(7)

DRUGS = {  # generic: (prod_ai as FDA writes it, messy spellings people type)
    "adalimumab": ("ADALIMUMAB", ["HUMIRA", "HUMIRA PEN", "HUMIRA (ADALIMUMAB)", "humira 40mg/0.4ml",
                                  "ADALIMUMAB", "HUMIRA 40 MG PREFILLED SYRINGE", "HUMIRA."]),
    "acetaminophen": ("ACETAMINOPHEN", ["TYLENOL", "TYLENOL EXTRA STRENGTH 500MG TABLETS", "ACETAMINOPHEN",
                                        "PARACETAMOL", "ACETAMINOPHEN 325 MG", "TYLENOL."]),
    "lisinopril": ("LISINOPRIL", ["LISINOPRIL", "LISINOPRIL 10MG", "LISINOPRIL TABS", "LISINIPRIL"]),
    "metformin": ("METFORMIN HYDROCHLORIDE", ["METFORMIN", "METFORMIN HCL", "METFORMIN HCL 500 MG ER",
                                              "METFORMIN HYDROCHLORIDE"]),
    "semaglutide": ("SEMAGLUTIDE", ["OZEMPIC", "OZEMPIC 1MG PEN", "SEMAGLUTIDE", "OZEMPIC (SEMAGLUTIDE)"]),
    "apixaban": ("APIXABAN", ["ELIQUIS", "ELIQUIS 5MG", "APIXABAN"]),
    "dupilumab": ("DUPILUMAB", ["DUPIXENT", "DUPIXENT 300MG/2ML", "DUPILUMAB"]),
    "ibuprofen": ("IBUPROFEN", ["ADVIL", "IBUPROFEN", "IBUPROFEN 200 MG", "MOTRIN IB"]),
    "simvastatin": ("SIMVASTATIN", ["ZOCOR", "SIMVASTATIN", "SIMVASTATIN 20MG"]),
    "acetaminophen / hydrocodone": ("ACETAMINOPHEN\\HYDROCODONE BITARTRATE",
                                    ["HYDROCODONE BITARTRATE\\ACETAMINOPHEN", "NORCO"]),
    "prednisone": ("PREDNISONE", ["PREDNISONE", "PREDNISONE 5 MG"]),
    "methotrexate": ("METHOTREXATE", ["METHOTREXATE", "METHOTREXATE SODIUM"]),
}
JUNK = ["UNKNOWN", "OTHER MEDICATIONS", "UNK", "XYZQ-11", "BLOOD PRESSURE PILL"]
WEIGHTS = [30, 18, 10, 9, 8, 7, 6, 5, 4, 3, 3, 2]
REACTIONS = ["Nausea", "Headache", "Fatigue", "Injection site pain", "Rash", "Dizziness", "Diarrhoea",
             "Drug ineffective", "Pneumonia", "Arthralgia", "Vomiting", "Pruritus", "Off label use"]

demo, drug, reac, outc = [], [], [], []
pid = 1000000
for case in range(1, 1501):
    versions = random.choices([1, 2, 3], weights=[75, 20, 5])[0]
    sex = random.choices(["F", "M", "UNK", ""], weights=[55, 35, 5, 5])[0]
    age, age_cod = random.choice([("", "")] * 3 + [(str(random.randint(1, 95)), "YR")] * 8 +
                                 [(str(random.randint(1, 11)), "MON"), ("6", "DEC"), ("250", "YR"), ("-3", "YR")])
    wt, wt_cod = random.choice([("", "")] * 5 + [(str(random.randint(45, 120)), "KG")] * 3 +
                               [(str(random.randint(100, 250)), "LBS"), ("900", "KG")])
    evt = random.choice(["", "2026", "202605", "20260611", "20260712", "20990101", "18000101", "2026-07"])
    ing = random.choices(list(DRUGS), weights=WEIGHTS)[0]
    for v in range(1, versions + 1):
        pid += 1
        fda_dt = f"202607{10 + v:02d}"
        demo.append([str(pid), str(case), str(v), "I" if v == 1 else "F", evt, "", "20260705", fda_dt,
                     "EXP", "", "", "", "", age, age_cod, "", sex, "Y", wt, wt_cod, "20260701", "",
                     random.choice(["MD", "CN", "CN", "PH", "OT", "LW", ""]),
                     random.choice(["US", "US", "US", "CA", "GB", "JP", ""]), "US"])
        prod_ai, spellings = DRUGS[ing]
        drug.append([str(pid), str(case), "1", "PS", random.choice(spellings), prod_ai, "1", "Oral",
                     "", "", "", "", "", "", "", "", "", "", "", ""])
        for seq in range(2, random.randint(2, 4)):
            if random.random() < 0.25:
                name, pai = random.choice(JUNK), ""
            else:
                other = random.choice(list(DRUGS))
                pai, sp = DRUGS[other]
                name = random.choice(sp)
            drug.append([str(pid), str(case), str(seq), random.choice(["C", "SS"]), name, pai, "1", "",
                         "", "", "", "", "", "", "", "", "", "", "", ""])
        for r in random.sample(REACTIONS, random.randint(1, 3)):
            reac.append([str(pid), str(case), r, ""])
        if random.random() < 0.4:
            outc.append([str(pid), str(case), random.choice(["HO", "HO", "OT", "DE", "LT"])])

H = {
    "DEMO": "primaryid$caseid$caseversion$i_f_code$event_dt$mfr_dt$init_fda_dt$fda_dt$rept_cod$auth_num$mfr_num$mfr_sndr$lit_ref$age$age_cod$age_grp$sex$e_sub$wt$wt_cod$rept_dt$to_mfr$occp_cod$reporter_country$occr_country",
    "DRUG": "primaryid$caseid$drug_seq$role_cod$drugname$prod_ai$val_vbm$route$dose_vbm$cum_dose_chr$cum_dose_unit$dechal$rechal$lot_num$exp_dt$nda_num$dose_amt$dose_unit$dose_form$dose_freq",
    "REAC": "primaryid$caseid$pt$drug_rec_act",
    "OUTC": "primaryid$caseid$outc_cod",
}
out = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/faers_ascii_test26q3.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for key, rows in (("DEMO", demo), ("DRUG", drug), ("REAC", reac), ("OUTC", outc)):
        lines = [H[key]] + ["$".join(r) for r in rows]
        if key == "DRUG":
            lines.insert(50, "$".join(["9999999", "1"] + ["x"] * 30))  # one malformed row
        z.writestr(f"ASCII/{key}26Q3.txt", "\r\n".join(lines) + "\r\n")
print(f"wrote {out}: {len(demo)} demo, {len(drug)} drug, {len(reac)} reac, {len(outc)} outc rows")
