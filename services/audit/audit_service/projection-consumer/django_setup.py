"""
Call django_setup.setup() ONCE at the top of consumer.py before any
Django model imports. This is required to use Django ORM outside of
manage.py or wsgi.py contexts.
"""
import os
import django
 
 
def setup():
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'config.settings'
    )
    django.setup()