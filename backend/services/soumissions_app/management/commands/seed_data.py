import random
from django.core.management.base import BaseCommand
from soumissions_app.models import Soumission, SoumissionStatut
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Génère des données de test (mock data) pour le module soumissions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Supression des anciennes données..."))
        Soumission.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()
        
        # Create a test user
        user, _ = User.objects.get_or_create(username='testuser', defaults={'password': 'password123'})
        
        self.stdout.write(self.style.SUCCESS('Création de 5 soumissions mockées...'))
        
        statuts = [
            SoumissionStatut.SOUMIS,
            SoumissionStatut.EN_OUVERTURE,
            SoumissionStatut.EN_EVALUATION,
            SoumissionStatut.EVALU_TERMINEE,
            SoumissionStatut.RETRAITE
        ]
        
        for i in range(1, 6):
            # Using dummy URLs since the document service is not required to be running
            Soumission.objects.create(
                id_appel_offre=100 + i,
                id_soumissionnaire=user.id,
                offre_financiere_chiffree_url=f'http://minio/bucket/file_{i}.pdf.enc',
                cle_dechiffrement_hash=f'fake_encrypted_aes_key_{i}',
                statut=random.choice(statuts),
                montant_financier=random.uniform(100000.0, 5000000.0) if i % 2 == 0 else None,
            )
            
        self.stdout.write(self.style.SUCCESS('Données générées avec succès !'))
