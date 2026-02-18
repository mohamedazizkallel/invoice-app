import re
from datetime import datetime
import pandas as pd 
from decimal import Decimal
from builder import build_xml_from_dataframe


FORBIDDEN_PATTERN = re.compile(r"[;*&]|\b(OR|AND)\b", re.IGNORECASE)

REQUIRED_FIELDS = [
    "cert_ref",
    "date_paiement",
    "beneficiary_id",
    "beneficiary_name",
    "id_type_operation",
    "montant_ht",
    "montant_ttc",
    "montant_rs"
]

def validate_row(row, year, month):
    errors = []

    # 1. Check Required Fields
    for field in REQUIRED_FIELDS:
        if pd.isna(row.get(field)):
            errors.append(f"Missing field: {field}")

    # 2. Date Validation
    try:
        d = datetime.strptime(str(row["date_paiement"]), "%d/%m/%Y")
        if d.year != year or d.month != month:
            errors.append("DatePayement outside declaration period")
    except Exception:
        errors.append("Invalid DatePayement format (DD/MM/YYYY)")

    # 3. Security Pattern Check
    for k, v in row.items():
        if isinstance(v, str) and FORBIDDEN_PATTERN.search(v):
            errors.append(f"Forbidden characters in {k}")

    # 4. Financial & Calculation Validation
    try:
        # Convert to Decimal for precise calculation
        ht = Decimal(str(row.get("montant_ht", 0)))
        tva = Decimal(str(row.get("montant_tva", 0)))
        ttc = Decimal(str(row.get("montant_ttc", 0)))
        rs = Decimal(str(row.get("montant_rs", 0)))
        
        if ht < 0 or ttc < 0 or rs < 0:
            errors.append("Amounts must be >= 0")

        # Check: HT + TVA = TTC
        # Allowing a tiny margin for rounding (0.001) common in Tunisian Millimes
        if abs((ht + tva) - ttc) > Decimal('0.001'):
            errors.append(f"Calculation Error: HT ({ht}) + TVA ({tva}) != TTC ({ttc})")

        # Check: TTC - RS = Net (If you have a net field in your excel)
        if "montant_net_servi" in row:
            net = Decimal(str(row["montant_net_servi"]))
            if abs((ttc - rs) - net) > Decimal('0.001'):
                errors.append("Calculation Error: TTC - RS != Net")

    except Exception:
        errors.append("Financial fields must be numeric")

    return errors

def load_excel(path):
    cert_df = pd.read_excel(path, sheet_name="CERTIFICATS")
    header_df = pd.read_excel(path, sheet_name="DECLARATION_INFO")

    header = header_df.iloc[0].to_dict()

    REQUIRED_HEADER = [
        "declarant_type",
        "declarant_id",
        "declarant_category",
        "acte_depot",
        "annee_depot",
        "mois_depot"
    ]

    for f in REQUIRED_HEADER:
        if f not in header:
            raise RuntimeError(f"Missing declaration header field: {f}")

    # Inject header values into each row
    for k, v in header.items():
        cert_df[k] = v

    return cert_df

def split_valid_invalid_rows(df):
    valid_rows = []
    error_rows = []

    year = int(df.iloc[0]["annee_depot"])
    month = int(df.iloc[0]["mois_depot"])

    for idx, row in df.iterrows():
        errs = validate_row(row, year, month)

        if errs:
            error_rows.append({
                "excel_row": idx + 2,
                "cert_ref": row.get("cert_ref"),
                "errors": " | ".join(errs)
            })
        else:
            valid_rows.append(row)

    return pd.DataFrame(valid_rows), pd.DataFrame(error_rows)

df = load_excel("rs_declaration_template.xlsx")

valid_df, error_df = split_valid_invalid_rows(df)

if not error_df.empty:
    error_df.to_excel("errors.xlsx", index=False)

if valid_df.empty:
    raise RuntimeError("No valid rows to generate XML")

build_xml_from_dataframe(valid_df, "output.xml")
