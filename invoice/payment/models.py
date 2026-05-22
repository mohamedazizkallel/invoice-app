from django.db import models
from decimal import Decimal
import datetime

class Retenu(models.Model):
    """
    Model for tax retention (Retenue à la source) in Tunisia
    """
    
    # Category choices
    CATEGORY_CHOICES = [
        ('ACQUISITIONS', '1. Acquisitions des marchandises, matériel, équipements et services'),
        ('LOYERS', '2. Loyers'),
        ('ACTIVITES_NC', '3. Rémunération des activités non commerciales'),
        ('CESSIONS', '4. Cessions de fonds de commerce et immeubles'),
        ('DIVIDENDES', '5. Dividendes'),
        ('CAPITAUX', '6. Revenus des capitaux mobiliers'),
        ('JEUX', '7. Jeux de pari et loterie'),
        ('JETONS', '8. Jetons de présence et tantièmes'),
    ]
    
    # Subcategory choices
    SUBCATEGORY_CHOICES = [
        # Category 1: Acquisitions
        ('ACQ_PM_IS', 'Acquisitions auprès de personnes morales soumises à l\'IS (règle générale) - 1%'),
        ('ACQ_COMMISSION_PM', 'Commission des distributeurs agréés (PM) - 2%'),
        ('ACQ_1000_2_3', 'Acquisitions ≥ 1.000 D TTC (PP 2/3 ou PM IS 10%) - 0.5%'),
        ('ACQ_1000_OTHER', 'Acquisitions ≥ 1.000 D TTC (IS autre que 15% et 10%) - 1%'),
        ('ACQ_1000_15', 'Acquisitions ≥ 1.000 D TTC (IS 15%) - 1.5%'),
        ('ACQ_COMMISSION_PP', 'Commission des distributeurs agréés (PP) - 5%'),
        
        # Category 2: Loyers
        ('LOYER_HOTEL', 'Loyers d\'hôtels - 10%'),
        ('LOYER_RESIDENT', 'Loyers résidents établis - 10%'),
        
        # Category 3: Activités non commerciales
        ('BNC_REEL', 'Honoraires BNC régime réel - 10%'),
        ('REMUN_PERFORMANCE', 'Rémunérations performance - 10%'),
        ('REMUN_ARTISTES', 'Rémunérations artistes et créateurs - 5%'),
        ('BNC_FORFAIT', 'Honoraires BNC forfait d\'assiette - 15%'),
        
        # Category 4: Cessions
        ('CESSION_FONDS', 'Cession de fonds de commerce - 5%'),
        ('CESSION_IMMEUBLE', 'Cession d\'immeubles - 2.5%'),
        
        # Category 5: Dividendes
        ('DIVIDENDE_PP', 'Dividendes PP résidentes - 10%'),
        
        # Category 6: Capitaux mobiliers
        ('CAPITAUX_MOB', 'Revenus capitaux mobiliers - 20%'),
        
        # Category 7: Jeux
        ('JEUX_PARI', 'Jeux de pari et loterie - 25%'),
        
        # Category 8: Jetons
        ('JETONS_PRESENCE', 'Jetons de présence et tantièmes - 20%'),
    ]
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Catégorie"
    )
    
    subcategory = models.CharField(
        max_length=30,
        choices=SUBCATEGORY_CHOICES,
        verbose_name="Type de retenue",
        unique=True
    )
    
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Taux (%)"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Retenue à la source"
        verbose_name_plural = "Retenues à la source"
        ordering = ['category', 'rate']
    
    def __str__(self):
        return f"{self.get_subcategory_display()}"


class InvoiceRetenu(models.Model):
    """
    Retention applied to an invoice - amounts calculated automatically
    """
    invoice = models.ForeignKey(
        'sales.Invoice',
        on_delete=models.CASCADE,
        related_name='retenues'
    )
    
    retenu_type = models.ForeignKey(
        Retenu,
        on_delete=models.PROTECT,
        verbose_name="Type de retenue"
    )
    
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Montant de base (D)",
        help_text="Montant sur lequel la retenue est calculée"
    )
    
    retenu_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Taux appliqué (%)",
        help_text="Taux au moment de la création"
    )
    
    retenu_amount = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Montant retenu (D)",
        help_text="Calculé automatiquement: base_amount × (taux / 100)"
    )
    
    depo_date = models.PositiveIntegerField(default=datetime.date.today().year)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Retenue sur facture"
        verbose_name_plural = "Retenues sur factures"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.retenu_type} - {self.retenu_amount}D sur Invoice #{self.invoice.id}"
    
    def save(self, *args, **kwargs):
        if self.retenu_type and not self.retenu_rate:
            self.retenu_rate = self.retenu_type.rate

        if self.base_amount and self.retenu_rate:
            self.retenu_amount = (
                self.base_amount * self.retenu_rate
            ) / Decimal('100')

        super().save(*args, **kwargs)

        
    def calculate_amount(self):
        """Recalculate the retention amount"""
        if self.base_amount and self.retenu_rate:
            return (self.base_amount * self.retenu_rate) / Decimal('100')
        return Decimal('0.000')


class PurchaseRetenu(models.Model):
    """Retention applied to a purchase"""
    purchase = models.ForeignKey(
        'sales.Purchase',
        on_delete=models.CASCADE,
        related_name='purchase_retenues'
    )
    retenu_type = models.ForeignKey(
        Retenu,
        on_delete=models.PROTECT,
        verbose_name="Type de retenue"
    )
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Montant de base (D)"
    )
    retenu_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Taux appliqué (%)"
    )
    retenu_amount = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Montant retenu (D)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Retenue sur achat"
        verbose_name_plural = "Retenues sur achats"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.retenu_type} - {self.retenu_amount}D sur Achat #{self.purchase.uniqueId}"

    def save(self, *args, **kwargs):
        if self.retenu_type and not self.retenu_rate:
            self.retenu_rate = self.retenu_type.rate
        if self.base_amount and self.retenu_rate:
            self.retenu_amount = (self.base_amount * self.retenu_rate) / Decimal('100')
        super().save(*args, **kwargs)


