from django.db import migrations


def seed_retenu_types(apps, schema_editor):
    Retenu = apps.get_model('payment', 'Retenu')

    retenu_data = [
        # Category 1: Acquisitions
        ('ACQUISITIONS', 'ACQ_PM_IS', 1.00),
        ('ACQUISITIONS', 'ACQ_COMMISSION_PM', 2.00),
        ('ACQUISITIONS', 'ACQ_1000_2_3', 0.50),
        ('ACQUISITIONS', 'ACQ_1000_OTHER', 1.00),
        ('ACQUISITIONS', 'ACQ_1000_15', 1.50),
        ('ACQUISITIONS', 'ACQ_COMMISSION_PP', 5.00),
        # Category 2: Loyers
        ('LOYERS', 'LOYER_HOTEL', 10.00),
        ('LOYERS', 'LOYER_RESIDENT', 10.00),
        # Category 3: Activités non commerciales
        ('ACTIVITES_NC', 'BNC_REEL', 10.00),
        ('ACTIVITES_NC', 'REMUN_PERFORMANCE', 10.00),
        ('ACTIVITES_NC', 'REMUN_ARTISTES', 5.00),
        ('ACTIVITES_NC', 'BNC_FORFAIT', 15.00),
        # Category 4: Cessions
        ('CESSIONS', 'CESSION_FONDS', 5.00),
        ('CESSIONS', 'CESSION_IMMEUBLE', 2.50),
        # Category 5: Dividendes
        ('DIVIDENDES', 'DIVIDENDE_PP', 10.00),
        # Category 6: Capitaux mobiliers
        ('CAPITAUX', 'CAPITAUX_MOB', 20.00),
        # Category 7: Jeux
        ('JEUX', 'JEUX_PARI', 25.00),
        # Category 8: Jetons
        ('JETONS', 'JETONS_PRESENCE', 20.00),
    ]

    for category, subcategory, rate in retenu_data:
        Retenu.objects.get_or_create(
            subcategory=subcategory,
            defaults={
                'category': category,
                'rate': rate,
                'is_active': True,
            }
        )


def reverse_seed(apps, schema_editor):
    Retenu = apps.get_model('payment', 'Retenu')
    Retenu.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0003_purchaseretenu'),
    ]

    operations = [
        migrations.RunPython(seed_retenu_types, reverse_seed),
    ]
