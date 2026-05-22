"""
Seed ONLY the 4 soumission documents for the demo:
  1. Offre technique
  2. Offre financiere
  3. Declaration a souscrire
  4. Declaration de probite

Run: Get-Content scripts\seed_demo_soumission.py | docker exec -i deploy-backend-1 python manage.py shell
"""
import hashlib
import uuid
from io import BytesIO
from fpdf import FPDF

from documents_service.models import Document
from documents_service.services.minio_client import MinioStorageService
from soumissions_app.models import Soumission
from appels_service.models import AppelOffres


def make_pdf(title, body_lines, company="SARL TechnoPlus Algerie"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, title, ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Entreprise: {company}", ln=True)
    pdf.cell(0, 6, "Date: 10/05/2026", ln=True)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    for line in body_lines:
        pdf.cell(0, 5, line, ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Document genere pour {company} - Confidentiel", ln=True)
    return pdf.output()


def upload_doc(pdf_bytes, filename, id_operateur):
    minio = MinioStorageService()
    unique_name = f"{uuid.uuid4()}.pdf"
    storage_url = f"{minio.bucket}/{unique_name}"
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    stream = BytesIO(pdf_bytes)
    minio.s3_client.upload_fileobj(stream, minio.bucket, unique_name)
    doc = Document.objects.create(
        related_type="soumission",
        id_operateur_economique=id_operateur,
        nom=filename,
        type_document="pdf",
        storage_url=storage_url,
        hash_sha256=sha,
        taille_fichier=len(pdf_bytes),
        is_encrypted=False,
    )
    return doc


# ── Nettoyage ──
Document.objects.all().delete()
print("Documents precedents supprimes.")

# ── Mise a jour AO: required_docs = les 4 docs de soumission ──
try:
    ao = AppelOffres.objects.get(id_appel_offres=1)
    ao.required_docs_admin = []
    ao.required_docs_tech = ["Offre technique"]
    ao.required_docs_fin = ["Offre financiere"]
    ao.save()
    print(f"AO {ao.reference} mis a jour: required_docs = Offre technique, Offre financiere")
except AppelOffres.DoesNotExist:
    print("ERREUR: AppelOffres id=1 non trouve. Executez seed_demo.py d'abord.")


# ══════════════════════════════════════════════════════════════════════
# OPERATEUR 1 — Dossier COMPLET (4/4 documents) → attendu: CONFORME
# ══════════════════════════════════════════════════════════════════════

doc1 = upload_doc(
    make_pdf("OFFRE TECHNIQUE", [
        "OFFRE TECHNIQUE",
        "Appel d'Offres: AO-2026-001",
        "Fourniture de materiel informatique",
        "",
        "1. PRESENTATION DE L'ENTREPRISE",
        "   SARL TechnoPlus Algerie, creee en 2018",
        "   Specialisee en materiel informatique",
        "   45 employes, CA annuel: 120M DA",
        "",
        "2. PROPOSITION TECHNIQUE",
        "   2.1 Ordinateurs portables (500 unites)",
        "       Marque: Dell Latitude 5540",
        "       Processeur: Intel Core i7-1365U, 10 coeurs",
        "       Memoire: 16 Go DDR5",
        "       Stockage: SSD 512 Go NVMe",
        "       Ecran: 15.6 pouces FHD IPS",
        "       Systeme: Windows 11 Pro",
        "       Garantie: 3 ans sur site",
        "",
        "3. METHODOLOGIE DE LIVRAISON",
        "   Phase 1: 250 unites sous 30 jours",
        "   Phase 2: 250 unites sous 60 jours",
        "   Installation et configuration incluses",
        "",
        "4. SERVICE APRES-VENTE",
        "   Support technique 24/7",
        "   Intervention sur site sous 48h",
        "   Stock de pieces de rechange",
    ]),
    "Offre_Technique_TechnoPlus.pdf", 1,
)
print(f"Doc {doc1.id_document}: Offre Technique (Op. 1)")

doc2 = upload_doc(
    make_pdf("OFFRE FINANCIERE", [
        "OFFRE FINANCIERE",
        "Bordereau des Prix Unitaires",
        "Appel d'Offres: AO-2026-001",
        "",
        "Ref  |  Designation                    |  Qte  |  PU (DA)    |  Total (DA)",
        "-----+--------------------------------+-------+-------------+-------------",
        "001  |  Dell Latitude 5540             |  500  |  85.000,00  |  42.500.000",
        "002  |  Sacoche transport              |  500  |  1.500,00   |     750.000",
        "003  |  Souris sans fil                |  500  |  800,00     |     400.000",
        "004  |  Station accueil USB-C          |  100  |  8.500,00   |     850.000",
        "005  |  Formation utilisateurs         |   10  |  50.000,00  |     500.000",
        "-----+--------------------------------+-------+-------------+-------------",
        "     |  TOTAL HT                       |       |             |  45.000.000",
        "     |  TVA 19%                        |       |             |   8.550.000",
        "     |  TOTAL TTC                      |       |             |  53.550.000",
        "",
        "Montant en lettres: Cinquante-trois millions cinq cent",
        "cinquante mille dinars algeriens.",
        "Validite de l'offre: 120 jours",
    ]),
    "Offre_Financiere_TechnoPlus.pdf", 1,
)
print(f"Doc {doc2.id_document}: Offre Financiere (Op. 1)")

doc3 = upload_doc(
    make_pdf("DECLARATION A SOUSCRIRE", [
        "DECLARATION A SOUSCRIRE",
        "",
        "Je soussigne, M. Karim BENALI,",
        "Agissant en qualite de Gerant de SARL TechnoPlus Algerie,",
        "",
        "Declare avoir pris connaissance des pieces constitutives",
        "du marche et m'engage a respecter les clauses et conditions",
        "du cahier des charges relatif a l'appel d'offres AO-2026-001.",
        "",
        "Je m'engage a livrer les fournitures dans les delais prevus",
        "et conformement aux specifications techniques exigees.",
        "",
        "Je declare que l'entreprise n'est pas en etat de faillite,",
        "de liquidation judiciaire ou de cessation d'activite.",
        "",
        "Fait a Alger, le 10/05/2026",
        "Signature et cachet de l'entreprise",
        "",
        "M. Karim BENALI",
        "Gerant SARL TechnoPlus Algerie",
    ]),
    "Declaration_a_Souscrire_TechnoPlus.pdf", 1,
)
print(f"Doc {doc3.id_document}: Declaration a Souscrire (Op. 1)")

doc4 = upload_doc(
    make_pdf("DECLARATION DE PROBITE", [
        "DECLARATION DE PROBITE",
        "",
        "Je soussigne, M. Karim BENALI,",
        "Gerant de SARL TechnoPlus Algerie,",
        "",
        "Declare sur l'honneur que ni moi, ni aucun membre de",
        "l'entreprise n'a fait l'objet de poursuites pour corruption",
        "ou tentative de corruption d'agents publics.",
        "",
        "Je m'engage a ne recourir a aucune pratique de corruption,",
        "de favoritisme ou de collusion avec d'autres soumissionnaires",
        "ou toute autre partie prenante dans le cadre du present",
        "appel d'offres.",
        "",
        "Je suis informe que toute fausse declaration entrainera",
        "l'exclusion de la participation aux marches publics",
        "conformement a la legislation en vigueur.",
        "",
        "Fait a Alger, le 10/05/2026",
        "Signature et cachet",
        "M. Karim BENALI",
    ]),
    "Declaration_de_Probite_TechnoPlus.pdf", 1,
)
print(f"Doc {doc4.id_document}: Declaration de Probite (Op. 1)")


# ══════════════════════════════════════════════════════════════════════
# OPERATEUR 2 — Dossier INCOMPLET (2/4) → attendu: PIECES_MANQUANTES
# Manquent: Declaration a souscrire, Declaration de probite
# ══════════════════════════════════════════════════════════════════════

doc5 = upload_doc(
    make_pdf("OFFRE TECHNIQUE", [
        "OFFRE TECHNIQUE",
        "Appel d'Offres: AO-2026-001",
        "",
        "EURL InfoServices Oran propose:",
        "500 ordinateurs HP ProBook 450 G10",
        "Processeur: Intel Core i5-1335U",
        "Memoire: 8 Go DDR4",
        "Stockage: SSD 256 Go",
        "Garantie: 2 ans",
    ], company="EURL InfoServices Oran"),
    "Offre_Technique_InfoServices.pdf", 2,
)
print(f"Doc {doc5.id_document}: Offre Technique (Op. 2)")

doc6 = upload_doc(
    make_pdf("OFFRE FINANCIERE", [
        "OFFRE FINANCIERE",
        "Appel d'Offres: AO-2026-001",
        "",
        "Montant global HT: 52.000.000 DA",
        "TVA 19%: 9.880.000 DA",
        "Montant TTC: 61.880.000 DA",
    ], company="EURL InfoServices Oran"),
    "Offre_Financiere_InfoServices.pdf", 2,
)
print(f"Doc {doc6.id_document}: Offre Financiere (Op. 2)")


# ── Lier les documents aux soumissions ──

s1 = Soumission.objects.get(id_soumission=1)
s1.document_ids = [doc1.id_document, doc2.id_document, doc3.id_document, doc4.id_document]
s1.conformite_statut = None
s1.conformite_rapport = None
s1.save()
print(f"\nSoumission 1: document_ids={s1.document_ids} (4/4 docs — dossier COMPLET)")

s2 = Soumission.objects.get(id_soumission=2)
s2.document_ids = [doc6.id_document]
s2.conformite_statut = None
s2.conformite_rapport = None
s2.save()
print(f"Soumission 2: document_ids={s2.document_ids} (1/2 docs — INCOMPLET)")

print("\n--- Operateurs 1 & 2 termines (PDFs textuels) ---")

# ======================================================================
# OPERATEUR 3 — PDFs SCANNES (images) → teste le vrai OCR Tesseract
# Dossier COMPLET (4/4) → attendu: CONFORME (via OCR)
# ======================================================================

print("\n=== OPERATEUR 3: Creation des PDFs scannes (images) ===")

from pdf2image import convert_from_bytes
from PIL import Image


def make_scanned_pdf(title, body_lines, company="SPA BuildTech Constantine"):
    """
    1. Genere un PDF textuel avec fpdf2
    2. Convertit chaque page en image (comme un scanner)
    3. Re-cree un PDF a partir des images → pas de texte embarque
    Resultat: pypdf ne trouvera rien, Tesseract sera force.
    """
    text_pdf_bytes = make_pdf(title, body_lines, company)

    # Convertir en images (simule un scan a 200 DPI)
    images = convert_from_bytes(text_pdf_bytes, dpi=100)

    # Recreer un PDF depuis les images (pas de texte embarque)
    scanned_pdf = FPDF()
    for img in images:
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Sauver temporairement pour fpdf2
        temp_path = f"/tmp/scan_page_{uuid.uuid4().hex[:8]}.png"
        img.save(temp_path, format="PNG")

        scanned_pdf.add_page()
        scanned_pdf.image(temp_path, x=0, y=0, w=210, h=297)

        import os
        os.remove(temp_path)

    return bytes(scanned_pdf.output())


try:
    doc7 = upload_doc(
        make_scanned_pdf("OFFRE TECHNIQUE", [
            "OFFRE TECHNIQUE",
            "Appel d'Offres: AO-2026-001",
            "",
            "1. PRESENTATION",
            "   SPA BuildTech Constantine",
            "   Specialisee en solutions IT depuis 2015",
            "   60 employes qualifies",
            "",
            "2. PROPOSITION TECHNIQUE",
            "   500 ordinateurs HP EliteBook 840 G10",
            "   Processeur: Intel Core i7-1355U",
            "   Memoire: 16 Go DDR5",
            "   Stockage: SSD 512 Go",
            "   Ecran: 14 pouces FHD",
            "   Garantie: 3 ans constructeur",
            "",
            "3. PLANNING DE LIVRAISON",
            "   Livraison en 2 lots sous 45 jours",
        ]),
        "Offre_Technique_BuildTech_SCAN.pdf", 3,
    )
    print(f"Doc {doc7.id_document}: Offre Technique SCANNE (Op. 3)")

    doc8 = upload_doc(
        make_scanned_pdf("OFFRE FINANCIERE", [
            "OFFRE FINANCIERE",
            "Bordereau des Prix Unitaires",
            "Appel d'Offres: AO-2026-001",
            "",
            "HP EliteBook 840 G10 x 500 = 40.000.000 DA HT",
            "Accessoires et cables x 500 = 1.250.000 DA HT",
            "Formation x 5 sessions = 500.000 DA HT",
            "",
            "TOTAL HT: 41.750.000 DA",
            "TVA 19%: 7.932.500 DA",
            "TOTAL TTC: 49.682.500 DA",
        ]),
        "Offre_Financiere_BuildTech_SCAN.pdf", 3,
    )
    print(f"Doc {doc8.id_document}: Offre Financiere SCANNE (Op. 3)")

    # ── Creer Soumission 3 si elle n'existe pas ──
    s3, created = Soumission.objects.get_or_create(
        id_soumission=3,
        defaults={
            "id_appel_offre": 1,
            "id_soumissionnaire": 3,
            "document_ids": [doc7.id_document, doc8.id_document],
            "statut": "soumise",
            "montant_financier": 49682500,
            "date_soumission": "2026-05-09",
        }
    )
    if not created:
        s3.id_appel_offre = 1
        s3.document_ids = [doc7.id_document, doc8.id_document]
        s3.conformite_statut = None
        s3.conformite_rapport = None
        s3.save()
    print(f"\nSoumission 3: document_ids={s3.document_ids} (2 docs SCANNES — test OCR Tesseract)")

except Exception as e:
    print(f"ERREUR creation PDFs scannes: {e}")
    import traceback
    traceback.print_exc()


# ======================================================================
# TEST 4 — Mix texte + scan (1 texte + 1 scan) → test cooperation engines
# Prouve que pypdf et Tesseract cooperent dans une seule analyse
# ======================================================================

print("\n=== TEST 4: Mix texte + scan ===")

try:
    doc_mix1 = upload_doc(
        make_pdf("OFFRE TECHNIQUE", [
            "OFFRE TECHNIQUE",
            "Appel d'Offres: AO-2026-001",
            "",
            "SARL MixCorp Annaba propose:",
            "Materiel informatique derniere generation",
            "500 postes Dell OptiPlex 7010",
        ], company="SARL MixCorp Annaba"),
        "Offre_Technique_MixCorp.pdf", 4,
    )
    print(f"Doc {doc_mix1.id_document}: Offre Technique TEXTE (Op. 4)")

    doc_mix2 = upload_doc(
        make_scanned_pdf("OFFRE FINANCIERE", [
            "OFFRE FINANCIERE",
            "Bordereau des Prix",
            "Appel d'Offres: AO-2026-001",
            "",
            "500 x Dell OptiPlex 7010 = 37.500.000 DA HT",
            "TOTAL TTC: 44.625.000 DA",
        ], company="SARL MixCorp Annaba"),
        "Offre_Financiere_MixCorp_SCAN.pdf", 4,
    )
    print(f"Doc {doc_mix2.id_document}: Offre Financiere SCANNE (Op. 4)")

    s4, created = Soumission.objects.get_or_create(
        id_soumission=4,
        defaults={
            "id_appel_offre": 1,
            "id_soumissionnaire": 4,
            "document_ids": [doc_mix1.id_document, doc_mix2.id_document],
            "statut": "soumise",
            "montant_financier": 44625000,
            "date_soumission": "2026-05-09",
        }
    )
    if not created:
        s4.id_appel_offre = 1
        s4.document_ids = [doc_mix1.id_document, doc_mix2.id_document]
        s4.conformite_statut = None
        s4.conformite_rapport = None
        s4.save()
    print(f"Soumission 4: {s4.document_ids} (1 texte + 1 scan = MIX)")

except Exception as e:
    print(f"ERREUR test 4: {e}")
    import traceback
    traceback.print_exc()


# ======================================================================
# TEST 5 — Mauvais types de documents (2 docs fournis mais 2x probite)
# → attendu: PIECES_MANQUANTES (les 2 docs sont du meme type)
# Prouve que le NLP classifie par CONTENU, pas juste par nombre
# ======================================================================

print("\n=== TEST 5: Mauvais documents ===")

try:
    wrong_docs = []
    for i in range(1, 3):
        d = upload_doc(
            make_pdf("DECLARATION DE PROBITE", [
                "DECLARATION DE PROBITE",
                "",
                f"Copie numero {i}",
                "Je soussigne, M. Omar MANSOURI,",
                "Gerant de EURL FauxDocs Setif,",
                "Declare sur l'honneur n'avoir jamais fait",
                "l'objet de poursuites pour corruption.",
                "",
                "Fait a Setif, le 10/05/2026",
            ], company="EURL FauxDocs Setif"),
            f"Document_{i}_FauxDocs.pdf", 5,
        )
        wrong_docs.append(d)
        print(f"Doc {d.id_document}: Probite copie {i} (Op. 5)")

    s5, created = Soumission.objects.get_or_create(
        id_soumission=5,
        defaults={
            "id_appel_offre": 1,
            "id_soumissionnaire": 5,
            "document_ids": [d.id_document for d in wrong_docs],
            "statut": "soumise",
            "montant_financier": 0,
            "date_soumission": "2026-05-09",
        }
    )
    if not created:
        s5.id_appel_offre = 1
        s5.document_ids = [d.id_document for d in wrong_docs]
        s5.conformite_statut = None
        s5.conformite_rapport = None
        s5.save()
    print(f"Soumission 5: {s5.document_ids} (2x probite = MAUVAIS TYPES)")

except Exception as e:
    print(f"ERREUR test 5: {e}")
    import traceback
    traceback.print_exc()


# ======================================================================
# TEST 6 — PDF vide / corrompu (3 bons + 1 vide)
# → attendu: PIECES_MANQUANTES (declaration souscrire non classifiee)
# Prouve la robustesse: pas de crash, fallback gracieux
# ======================================================================

print("\n=== TEST 6: PDF vide / corrompu ===")

try:
    doc_ok1 = upload_doc(
        make_pdf("OFFRE TECHNIQUE", [
            "OFFRE TECHNIQUE",
            "SARL RobustTest Tlemcen",
            "Proposition de materiel informatique",
        ], company="SARL RobustTest Tlemcen"),
        "Offre_Technique_RobustTest.pdf", 6,
    )
    print(f"Doc {doc_ok1.id_document}: Offre Technique OK (Op. 6)")

    doc_ok2 = upload_doc(
        make_pdf("OFFRE FINANCIERE", [
            "OFFRE FINANCIERE",
            "TOTAL TTC: 55.000.000 DA",
        ], company="SARL RobustTest Tlemcen"),
        "Offre_Financiere_RobustTest.pdf", 6,
    )
    print(f"Doc {doc_ok2.id_document}: Offre Financiere OK (Op. 6)")

    # PDF vide: juste un PDF avec une page blanche, aucun texte
    empty_pdf = FPDF()
    empty_pdf.add_page()
    empty_bytes = bytes(empty_pdf.output())

    doc_empty = upload_doc(
        empty_bytes,
        "Document_3_RobustTest.pdf", 6,
    )
    print(f"Doc {doc_empty.id_document}: PDF VIDE (Op. 6)")

    doc_ok3 = upload_doc(
        make_pdf("DECLARATION DE PROBITE", [
            "DECLARATION DE PROBITE",
            "",
            "Je soussigne, M. Hamid ZEROUAL,",
            "Gerant de SARL RobustTest Tlemcen,",
            "Declare sur l'honneur n'avoir jamais fait",
            "l'objet de poursuites pour corruption.",
        ], company="SARL RobustTest Tlemcen"),
        "Declaration_de_Probite_RobustTest.pdf", 6,
    )
    print(f"Doc {doc_ok3.id_document}: Declaration de Probite OK (Op. 6)")

    s6, created = Soumission.objects.get_or_create(
        id_soumission=6,
        defaults={
            "id_appel_offre": 1,
            "id_soumissionnaire": 6,
            "document_ids": [doc_ok1.id_document, doc_ok2.id_document, doc_empty.id_document, doc_ok3.id_document],
            "statut": "soumise",
            "montant_financier": 55000000,
            "date_soumission": "2026-05-09",
        }
    )
    if not created:
        s6.id_appel_offre = 1
        s6.document_ids = [doc_ok1.id_document, doc_ok2.id_document, doc_empty.id_document, doc_ok3.id_document]
        s6.conformite_statut = None
        s6.conformite_rapport = None
        s6.save()
    print(f"Soumission 6: {s6.document_ids} (3 OK + 1 VIDE = ROBUSTESSE)")

except Exception as e:
    print(f"ERREUR test 6: {e}")
    import traceback
    traceback.print_exc()


print("\n=== SEED COMPLET TERMINE ===")
print("Soumissions creees pour AO-2026-001:")
print("  S1: 4 PDFs textuels   (pypdf)            → CONFORME")
print("  S2: 2 PDFs textuels   (incomplet)        → PIECES_MANQUANTES")
print("  S3: 2 PDFs SCANNES    (Tesseract)        → PIECES_MANQUANTES (test OCR)")
print("  S4: 1 texte + 1 scan  (MIX)             → PIECES_MANQUANTES (test mix)")
print("  S5: 2x meme document  (mauvais types)    → PIECES_MANQUANTES (NLP)")
print("  S6: 3 OK + 1 PDF vide (robustesse)       → PIECES_MANQUANTES")
