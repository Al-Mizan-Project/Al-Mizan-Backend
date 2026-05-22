"""
Create realistic demo PDF documents and upload them to the Documents service.
Run via: Get-Content scripts\create_demo_docs.py | docker exec -i deploy-backend-1 python manage.py shell
"""
import hashlib
import uuid
from io import BytesIO
from fpdf import FPDF

from documents_service.models import Document
from documents_service.services.minio_client import MinioStorageService
from soumissions_app.models import Soumission


def make_pdf(title, body_lines, company="SARL TechnoPlus Algerie"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, title, ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Entreprise: {company}", ln=True)
    pdf.cell(0, 6, "Date: 10/05/2026", ln=True)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(6)

    # Body
    pdf.set_font("Helvetica", "", 10)
    for line in body_lines:
        pdf.cell(0, 5, line, ln=True)

    # Footer
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Document genere pour {company} - Confidentiel", ln=True)

    return pdf.output()


def upload_doc(pdf_bytes, filename, related_type, id_operateur):
    minio = MinioStorageService()
    unique_name = f"{uuid.uuid4()}.pdf"
    storage_url = f"{minio.bucket}/{unique_name}"
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    stream = BytesIO(pdf_bytes)
    minio.s3_client.upload_fileobj(stream, minio.bucket, unique_name)

    doc = Document.objects.create(
        related_type=related_type,
        id_operateur_economique=id_operateur,
        nom=filename,
        type_document="pdf",
        storage_url=storage_url,
        hash_sha256=sha,
        taille_fichier=len(pdf_bytes),
        is_encrypted=False,
    )
    return doc


# ── Operateur 1: Full document set (AO-2026-001, Soumission 1) ──

doc1 = upload_doc(
    make_pdf("REGISTRE DE COMMERCE", [
        "REGISTRE DE COMMERCE - Extrait",
        "",
        "Denomination: SARL TechnoPlus Algerie",
        "Numero d'inscription: 16/00-0123456B99",
        "Forme juridique: SARL",
        "Capital social: 10.000.000 DA",
        "Siege social: 45 Rue Didouche Mourad, Alger 16000",
        "Activite principale: Commerce de gros de materiel informatique",
        "Date d'inscription: 15/03/2018",
        "Gerant: M. Karim BENALI",
        "",
        "Le present extrait est delivre conformement aux dispositions",
        "du Code de Commerce, articles 19 et suivants.",
        "Delivre le: 02/01/2026",
    ]),
    "Registre_Commerce_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc1.id_document}: Registre de Commerce")

doc2 = upload_doc(
    make_pdf("CARTE FISCALE - NIF", [
        "REPUBLIQUE ALGERIENNE DEMOCRATIQUE ET POPULAIRE",
        "Ministere des Finances - Direction Generale des Impots",
        "",
        "CARTE D'IDENTIFICATION FISCALE",
        "",
        "NIF: 001916012345678",
        "Denomination: SARL TechnoPlus Algerie",
        "Adresse fiscale: 45 Rue Didouche Mourad, Alger",
        "Activite: Commerce de materiel informatique",
        "Regime fiscal: Reel",
        "Date de delivrance: 10/01/2026",
    ]),
    "Carte_Fiscale_NIF_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc2.id_document}: Carte Fiscale NIF")

doc3 = upload_doc(
    make_pdf("ATTESTATION CNAS CASNOS", [
        "CAISSE NATIONALE DES ASSURANCES SOCIALES",
        "DES TRAVAILLEURS SALARIES - CNAS",
        "",
        "ATTESTATION DE MISE A JOUR",
        "",
        "Societe: SARL TechnoPlus Algerie",
        "Numero employeur: 16-01-2345678-90",
        "Situation: REGULIERE",
        "Dernier trimestre acquitte: T1 2026",
        "Nombre de salaries declares: 45",
        "",
        "Delivree le: 05/04/2026",
    ]),
    "Attestation_CNAS_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc3.id_document}: Attestation CNAS")

doc4 = upload_doc(
    make_pdf("CERTIFICAT DE NON FAILLITE", [
        "TRIBUNAL DE COMMERCE D'ALGER",
        "",
        "CERTIFICAT DE NON-FAILLITE",
        "",
        "Le Greffe du Tribunal de Commerce certifie que:",
        "SARL TechnoPlus Algerie",
        "RC: 16/00-0123456B99",
        "",
        "N'a fait l'objet d'aucune procedure de:",
        "- Faillite",
        "- Reglement judiciaire",
        "- Liquidation judiciaire",
        "- Concordat preventif",
        "",
        "Delivre le: 01/04/2026",
    ]),
    "Certificat_Non_Faillite_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc4.id_document}: Certificat Non-Faillite")

doc5 = upload_doc(
    make_pdf("FICHE TECHNIQUE - OFFRE MATERIEL INFORMATIQUE", [
        "OFFRE TECHNIQUE",
        "Appel d'Offres: AO-2026-001",
        "",
        "1. ORDINATEURS PORTABLES (500 unites)",
        "   Marque: Dell Latitude 5540",
        "   Processeur: Intel Core i7-1365U",
        "   Memoire: 16 Go DDR5",
        "   Stockage: SSD 512 Go NVMe",
        "   Ecran: 15.6 pouces FHD IPS",
        "   Garantie: 3 ans sur site",
        "",
        "2. ACCESSOIRES",
        "   - Sacoche de transport (500)",
        "   - Souris sans fil (500)",
        "   - Station d'accueil USB-C (100)",
        "",
        "3. DELAI DE LIVRAISON: 60 jours",
    ]),
    "Offre_Technique_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc5.id_document}: Offre Technique")

doc6 = upload_doc(
    make_pdf("CERTIFICATS DE CONFORMITE EQUIPEMENTS", [
        "CERTIFICATS DE CONFORMITE",
        "",
        "Produit: Dell Latitude 5540",
        "Certifications:",
        "  - CE (Conformite Europeenne)",
        "  - ISO 9001:2015 (Qualite)",
        "  - ISO 14001:2015 (Environnement)",
        "  - RoHS Directive 2011/65/EU",
        "",
        "Organisme certificateur: SGS Algeria",
        "Date de certification: Mars 2026",
    ]),
    "Certificats_Conformite_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc6.id_document}: Certificats Conformite")

doc7 = upload_doc(
    make_pdf("PLAN DE LIVRAISON", [
        "PLAN DE LIVRAISON DETAILLE",
        "",
        "Phase 1 (J+0 a J+30):",
        "  - Commande aupres du fournisseur",
        "  - Reception au depot Alger",
        "  - Controle qualite lot 1 (250 unites)",
        "",
        "Phase 2 (J+30 a J+45):",
        "  - Livraison lot 1 au ministere",
        "  - Installation et configuration",
        "",
        "Phase 3 (J+45 a J+60):",
        "  - Livraison lot 2 (250 unites)",
        "  - Formation utilisateurs",
    ]),
    "Plan_Livraison_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc7.id_document}: Plan de Livraison")

doc8 = upload_doc(
    make_pdf("OFFRE FINANCIERE DETAILLEE", [
        "BORDEREAU DES PRIX UNITAIRES",
        "Appel d'Offres: AO-2026-001",
        "",
        "001 | Dell Latitude 5540       | 500 | 85.000 DA | 42.500.000 DA",
        "002 | Sacoche transport         | 500 |  1.500 DA |    750.000 DA",
        "003 | Souris sans fil           | 500 |    800 DA |    400.000 DA",
        "004 | Station accueil USB-C     | 100 |  8.500 DA |    850.000 DA",
        "005 | Formation                 |  10 | 50.000 DA |    500.000 DA",
        "",
        "TOTAL HT:  45.000.000 DA",
        "TVA 19%:    8.550.000 DA",
        "TOTAL TTC: 53.550.000 DA",
    ]),
    "Offre_Financiere_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc8.id_document}: Offre Financiere")

doc9 = upload_doc(
    make_pdf("BORDEREAU DES PRIX UNITAIRES", [
        "BORDEREAU DES PRIX UNITAIRES (BPU)",
        "",
        "N | Designation              | Unite | Prix Unit. HT",
        "1 | Ordinateur portable Dell | Unite | 85.000,00 DA",
        "2 | Sacoche transport        | Unite |  1.500,00 DA",
        "3 | Souris sans fil          | Unite |    800,00 DA",
        "4 | Station accueil USB-C    | Unite |  8.500,00 DA",
        "5 | Formation (par session)  | Seance| 50.000,00 DA",
    ]),
    "BPU_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc9.id_document}: BPU")

doc10 = upload_doc(
    make_pdf("GARANTIE BANCAIRE", [
        "BANQUE NATIONALE D'ALGERIE - BNA",
        "Agence Centrale Alger",
        "",
        "CAUTION DE SOUMISSION",
        "",
        "Beneficiaire: Ministere (AO-2026-001)",
        "Soumissionnaire: SARL TechnoPlus Algerie",
        "Montant de la caution: 900.000 DA",
        "(1% du montant de l'offre)",
        "",
        "La BNA s'engage irrevocablement a payer le montant",
        "ci-dessus sur premiere demande du beneficiaire.",
        "",
        "Validite: 120 jours a compter de la date de soumission",
        "Reference caution: BNA/CS/2026/04567",
    ]),
    "Garantie_Bancaire_TechnoPlus.pdf",
    "soumission", 1,
)
print(f"Doc {doc10.id_document}: Garantie Bancaire")


# ── Operateur 2: Incomplete docs (AO-2026-001, Soumission 2) ──
# Missing: CNAS, Certificat non-faillite, offre technique, plan de livraison

doc11 = upload_doc(
    make_pdf("REGISTRE DE COMMERCE", [
        "REGISTRE DE COMMERCE - Extrait",
        "Denomination: EURL InfoServices Oran",
        "Numero: 31/00-0987654A12",
        "Capital social: 5.000.000 DA",
        "Siege social: 12 Bd de l'ALN, Oran 31000",
    ], company="EURL InfoServices Oran"),
    "Registre_Commerce_InfoServices.pdf",
    "soumission", 2,
)
print(f"Doc {doc11.id_document}: RC Operateur 2")

doc12 = upload_doc(
    make_pdf("OFFRE FINANCIERE", [
        "OFFRE FINANCIERE SIMPLIFIEE",
        "Montant global HT: 52.000.000 DA",
        "TVA 19%: 9.880.000 DA",
        "Montant TTC: 61.880.000 DA",
    ], company="EURL InfoServices Oran"),
    "Offre_Financiere_InfoServices.pdf",
    "soumission", 2,
)
print(f"Doc {doc12.id_document}: Offre Financiere Operateur 2")


# ── Update soumission document_ids ──
s1 = Soumission.objects.get(id_soumission=1)
s1.document_ids = [doc1.id_document, doc2.id_document, doc3.id_document, doc4.id_document,
                   doc5.id_document, doc6.id_document, doc7.id_document,
                   doc8.id_document, doc9.id_document, doc10.id_document]
s1.conformite_statut = None
s1.conformite_rapport = None
s1.save()
print(f"\nSoumission 1: document_ids={s1.document_ids}")

s2 = Soumission.objects.get(id_soumission=2)
s2.document_ids = [doc11.id_document, doc12.id_document]
s2.conformite_statut = None
s2.conformite_rapport = None
s2.save()
print(f"Soumission 2: document_ids={s2.document_ids}")

print("\n=== ALL DOCUMENTS CREATED AND LINKED ===")
