import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

if user:
    user.set_password("new_password")
    user.save()
    print(f"Mot de passe modifié avec succès pour: {user.email}")
else:
    print("Aucun utilisateur trouvé dans la base de données.")