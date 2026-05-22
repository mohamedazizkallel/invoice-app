from lxml import etree
from collections import defaultdict
from decimal import Decimal

# Helper to format to 3 decimal places (common for TND millimes)
def format_monetary(value):
    if value is None:
        return "0.000"
    # Quantize ensures exactly 3 decimal places for Tunisian Dinar
    return str(Decimal(str(value)).quantize(Decimal('0.000')))

def build_xml_from_dataframe(df, output_path):
    # Enforce one period per file
    if df["annee_depot"].nunique() != 1 or df["mois_depot"].nunique() != 1:
        raise RuntimeError("Multiple year/month detected")

    root = etree.Element("DeclarationsRS", VersionSchema="1.0")

    declarant = etree.SubElement(root, "Declarant")
    etree.SubElement(declarant, "TypeIdentifiant").text = str(df.iloc[0]["declarant_type"])
    etree.SubElement(declarant, "Identifiant").text = str(df.iloc[0]["declarant_id"])
    etree.SubElement(declarant, "CategorieContribuable").text = str(df.iloc[0]["declarant_category"])

    ref = etree.SubElement(root, "ReferenceDeclaration")
    etree.SubElement(ref, "ActeDepot").text = str(df.iloc[0]["acte_depot"])
    etree.SubElement(ref, "AnneeDepot").text = str(df.iloc[0]["annee_depot"])
    etree.SubElement(ref, "MoisDepot").text = f"{int(df.iloc[0]['mois_depot']):02d}"

    ajouter = etree.SubElement(root, "AjouterCertificats")

    for cert_ref, rows in df.groupby("cert_ref"):
        cert = etree.SubElement(ajouter, "Certificat")

        ben = etree.SubElement(cert, "Beneficiaire")
        id_tax = etree.SubElement(ben, "IdTaxpayer")
        mf = etree.SubElement(id_tax, "MatriculeFiscal")

        etree.SubElement(mf, "TypeIdentifiant").text = str(rows.iloc[0]["beneficiary_type"])
        etree.SubElement(mf, "Identifiant").text = str(rows.iloc[0]["beneficiary_id"])
        etree.SubElement(mf, "CategorieContribuable").text = str(rows.iloc[0]["beneficiary_category"])

        etree.SubElement(ben, "Resident").text = str(rows.iloc[0]["resident"])
        etree.SubElement(ben, "NometprenonOuRaisonsociale").text = rows.iloc[0]["beneficiary_name"]
        etree.SubElement(ben, "Adresse").text = str(rows.iloc[0]["beneficiary_address"])
        etree.SubElement(ben, "Activite").text = str(rows.iloc[0]["beneficiary_activity"])

        infos = etree.SubElement(ben, "InfosContact")
        etree.SubElement(infos, "AdresseMail").text = str(rows.iloc[0]["email"])
        etree.SubElement(infos, "NumTel").text = str(rows.iloc[0]["phone"])

        etree.SubElement(cert, "DatePayement").text = rows.iloc[0]["date_paiement"]
        etree.SubElement(cert, "Ref_certif_chez_declarant").text = str(cert_ref)

        ops = etree.SubElement(cert, "ListeOperations")
        totals = defaultdict(float)

        for _, r in rows.iterrows():
            op = etree.SubElement(
                ops, "Operation", IdTypeOperation=r["id_type_operation"]
            )

            etree.SubElement(op, "AnneeFacturation").text = str(r["annee_facturation"])
            etree.SubElement(op, "CNPC").text = str(r["CNPC"])
            etree.SubElement(op, "P_Charge").text = str(r["P_Charge"])
            etree.SubElement(op, "MontantHT").text = format_monetary(r["montant_ht"])
            etree.SubElement(op, "TauxRS").text = str(r["taux_rs"])
            etree.SubElement(op, "TauxTVA").text = str(r["taux_tva"])
            etree.SubElement(op, "MontantTVA").text = format_monetary(r["montant_tva"])
            etree.SubElement(op, "MontantTTC").text = format_monetary(r["montant_ttc"])
            etree.SubElement(op, "MontantRS").text = format_monetary(r["montant_rs"])
            etree.SubElement(op, "MontantNetServi").text = format_monetary(r["montant_net_servi"])

            totals["ht"] += r["montant_ht"]
            totals["tva"] += r["montant_tva"]
            totals["ttc"] += r["montant_ttc"]
            totals["rs"] += r["montant_rs"]
            totals["net"] += r["montant_net_servi"]

        total = etree.SubElement(cert, "TotalPayement")
        etree.SubElement(total, "TotalMontantHT").text = format_monetary(totals["ht"])
        etree.SubElement(total, "TotalMontantTVA").text = format_monetary(totals["tva"])
        etree.SubElement(total, "TotalMontantTTC").text = format_monetary(totals["ttc"])
        etree.SubElement(total, "TotalMontantRS").text = format_monetary(totals["rs"])
        etree.SubElement(total, "TotalMontantNetServi").text = format_monetary(totals["net"])

    etree.ElementTree(root).write(
        output_path,
        encoding="UTF-8",
        xml_declaration=True,
        standalone=True,
        pretty_print=True
    )
