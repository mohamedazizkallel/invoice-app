from django.core.management.base import BaseCommand
from .models import Retenu 

class Command(BaseCommand):
    help = 'Populate Retenu model with all Tunisian tax retention rates'

    def handle(self, *args, **kwargs):
        retenu_data = [
            # Category 1: Acquisitions
            ('ACQUISITIONS', 'ACQ_PM_IS', 1.0),
            ('ACQUISITIONS', 'ACQ_COMMISSION_PM', 2.0),
            ('ACQUISITIONS', 'ACQ_1000_2_3', 0.5),
            ('ACQUISITIONS', 'ACQ_1000_OTHER', 1.0),
            ('ACQUISITIONS', 'ACQ_1000_15', 1.5),
            ('ACQUISITIONS', 'ACQ_COMMISSION_PP', 5.0),
            
            # Category 2: Loyers
            ('LOYERS', 'LOYER_HOTEL', 10.0),
            ('LOYERS', 'LOYER_RESIDENT', 10.0),
            
            # Category 3: Activités non commerciales
            ('ACTIVITES_NC', 'BNC_REEL', 10.0),
            ('ACTIVITES_NC', 'REMUN_PERFORMANCE', 10.0),
            ('ACTIVITES_NC', 'REMUN_ARTISTES', 5.0),
            ('ACTIVITES_NC', 'BNC_FORFAIT', 15.0),
            
            # Category 4: Cessions
            ('CESSIONS', 'CESSION_FONDS', 5.0),
            ('CESSIONS', 'CESSION_IMMEUBLE', 2.5),
            
            # Category 5: Dividendes
            ('DIVIDENDES', 'DIVIDENDE_PP', 10.0),
            
            # Category 6: Capitaux mobiliers
            ('CAPITAUX', 'CAPITAUX_MOB', 20.0),
            
            # Category 7: Jeux
            ('JEUX', 'JEUX_PARI', 25.0),
            
            # Category 8: Jetons
            ('JETONS', 'JETONS_PRESENCE', 20.0),
        ]
        
        created_count = 0
        updated_count = 0
        
        self.stdout.write('Populating Retenu data...\n')
        
        for category, subcategory, rate in retenu_data:
            retenu, created = Retenu.objects.update_or_create(
                subcategory=subcategory,
                defaults={
                    'category': category,
                    'rate': rate,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {retenu}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {retenu}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully processed {len(retenu_data)} retention types'
            )
        )
        self.stdout.write(self.style.SUCCESS(f'  - Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  - Updated: {updated_count}'))