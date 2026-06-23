"""
Management command: create_cdc_document
----------------------------------------
Generates a sample CDC (Cahier des Charges) text document,
uploads it to MinIO, creates a Document record in the database,
and links it to an AppelOffres record via id_doc_cdc.

Usage:
  python manage.py create_cdc_document
  python manage.py create_cdc_document --reference INT-AO-001
  python manage.py create_cdc_document --appel-id 1
"""

import hashlib
import io
import uuid
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from documents_service.models import Document
from documents_service.services.minio_client import MinioStorageService


CDC_TEMPLATE = """
═══════════════════════════════════════════════════════════════
         CAHIER DES CHARGES (CDC)
         DOCUMENT DE RÉFÉRENCE – APPEL D'OFFRES
═══════════════════════════════════════════════════════════════

Référence         : {reference}
Date de création  : {date}
Émis par          : Service Contractant

───────────────────────────────────────────────────────────────
1. OBJET DE L'APPEL D'OFFRES
───────────────────────────────────────────────────────────────

  Le présent cahier des charges a pour objet de définir les
  conditions et spécifications techniques requises pour la
  réalisation de la prestation décrite dans l'appel d'offres
  référencé ci-dessus.

───────────────────────────────────────────────────────────────
2. CONDITIONS DE PARTICIPATION
───────────────────────────────────────────────────────────────

  Les candidats doivent satisfaire aux conditions suivantes :

  a) Être une personne morale légalement constituée.
  b) Disposer d'une capacité financière suffisante.
  c) Fournir les justificatifs demandés.
  d) Ne pas faire l'objet d'une procédure collective.

───────────────────────────────────────────────────────────────
3. SPÉCIFICATIONS TECHNIQUES
───────────────────────────────────────────────────────────────

  3.1 Exigences générales
      - Respect des normes algériennes en vigueur.
      - Délai d'exécution à définir par le soumissionnaire.
      - Garantie minimale de 12 mois après réception.

  3.2 Documents à fournir
      - Offre technique détaillée.
      - Offre financière.
      - Référence professionnelles.
      - Extrait de rôle apuré.
      - Casier judiciaire.
      - Attestation de mise à jour CNAS/CASNOS.

───────────────────────────────────────────────────────────────
4. CRITÈRES D'ÉVALUATION
───────────────────────────────────────────────────────────────

  Les offres seront évaluées selon les critères suivants :

  - Offre technique    : 50 points
  - Offre financière   : 50 points
  ─────────────────────────────────
  Total                : 100 points

───────────────────────────────────────────────────────────────
5. CLAUSE DE CONFIDENTIALITÉ
───────────────────────────────────────────────────────────────

  Ce document est confidentiel et réservé uniquement aux
  candidats autorisés à participer à cet appel d'offres.
  Toute divulgation non autorisée est interdite.

═══════════════════════════════════════════════════════════════
  Plateforme Al-Mizan – Document généré automatiquement
═══════════════════════════════════════════════════════════════
"""


class Command(BaseCommand):
    help = 'Crée un document CDC pour un appel d\'offres et l\'uploade dans MinIO'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reference',
            type=str,
            default='INT-AO-001',
            help='Référence de l\'appel d\'offres (défaut: INT-AO-001)',
        )
        parser.add_argument(
            '--appel-id',
            type=int,
            default=None,
            help='ID direct de l\'appel d\'offres (surpasse --reference)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Remplacer le document CDC existant s\'il y en a déjà un',
        )

    def handle(self, *args, **options):
        reference = options['reference']
        appel_id = options.get('appel_id')
        force = options['force']

        # --- Import AppelOffres here to avoid app-label issues ---
        try:
            from appels_service.models import AppelOffres
        except ImportError:
            try:
                from services.appels_service.models import AppelOffres
            except ImportError:
                raise CommandError('Impossible d\'importer le modèle AppelOffres.')

        # --- Lookup the appel ---
        if appel_id:
            try:
                appel = AppelOffres.objects.get(pk=appel_id)
            except AppelOffres.DoesNotExist:
                raise CommandError(f'Aucun appel d\'offres avec id={appel_id}.')
        else:
            try:
                appel = AppelOffres.objects.get(reference=reference)
            except AppelOffres.DoesNotExist:
                raise CommandError(f'Aucun appel d\'offres avec référence="{reference}".')
            except AppelOffres.MultipleObjectsReturned:
                appel = AppelOffres.objects.filter(reference=reference).first()

        self.stdout.write(f'Appel trouvé : [{appel.id_appel_offres}] {appel.reference} – {appel.titre}')

        # --- Check if already has CDC ---
        if appel.id_doc_cdc and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Cet appel a déjà un CDC (id_doc_cdc={appel.id_doc_cdc}). '
                    f'Utilisez --force pour le remplacer.'
                )
            )
            return

        # --- Generate CDC content ---
        cdc_content = CDC_TEMPLATE.format(
            reference=appel.reference,
            date=datetime.now().strftime('%d/%m/%Y à %H:%M'),
        ).encode('utf-8')

        file_size = len(cdc_content)
        sha256 = hashlib.sha256(cdc_content).hexdigest()

        # --- Upload to MinIO ---
        minio = MinioStorageService()
        unique_name = f"{uuid.uuid4()}.txt"
        storage_url = unique_name

        try:
            file_stream = io.BytesIO(cdc_content)
            minio.s3_client.upload_fileobj(file_stream, minio.bucket, unique_name)
            self.stdout.write(self.style.SUCCESS(f'Fichier uploadé dans MinIO : {unique_name}'))
        except Exception as e:
            raise CommandError(f'Erreur lors de l\'upload MinIO : {e}')

        # --- Create Document record and link to appel ---
        with transaction.atomic():
            doc = Document.objects.create(
                related_type='appel_offre',
                id_operateur_economique=None,
                nom=f'CDC_{appel.reference}.txt',
                type_document='cdc',
                storage_url=storage_url,
                hash_sha256=sha256,
                taille_fichier=file_size,
                is_encrypted=False,
            )
            self.stdout.write(f'Document créé en BDD : id_document={doc.id_document}')

            appel.id_doc_cdc = doc.id_document
            appel.save(update_fields=['id_doc_cdc'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Appel [{appel.reference}] mis à jour : id_doc_cdc={doc.id_document}'
                )
            )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Opération terminée avec succès ==='))
        self.stdout.write(f'  Appel       : {appel.reference} (id={appel.id_appel_offres})')
        self.stdout.write(f'  Document    : {doc.nom} (id={doc.id_document})')
        self.stdout.write(f'  MinIO key   : {unique_name}')
        self.stdout.write(f'  Taille      : {file_size} octets')
