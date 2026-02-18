from django import forms
from .models import InvoiceRetenu, PurchaseRetenu, Retenu

class InvoiceRetenuForm(forms.ModelForm):

    
    class Meta:
        model = InvoiceRetenu
        fields = ['retenu_type', 'base_amount']
        widgets = {
            'retenu_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'retenu_type_select'
            }),
            'base_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': '0.000',
                'id': 'base_amount_input'
            }),

        }
    
    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)
        
        # Only show active retenu types
        self.fields['retenu_type'].queryset = Retenu.objects.filter(is_active=True)
        
        # Set initial base amount to invoice total if available
        if self.invoice and not self.instance.pk:
            self.fields['base_amount'].initial = self.invoice.total_amount
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set invoice if provided
        if self.invoice:
            instance.invoice = self.invoice
        
        # Set the rate from the selected retenu_type
        if instance.retenu_type:
            instance.retenu_rate = instance.retenu_type.rate
        
        if commit:
            instance.save()
        
        return instance


class MultipleInvoiceRetenuForm(forms.Form):
    """
    Form to add multiple retenues at once to an invoice
    """
    
    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)
        
        # Dynamically create fields for each active retenu type
        retenu_types = Retenu.objects.filter(is_active=True).order_by('category', 'rate')
        
        for retenu in retenu_types:
            # Checkbox to select this retenu type
            self.fields[f'retenu_{retenu.id}_selected'] = forms.BooleanField(
                required=False,
                label=str(retenu),
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
            
            # Base amount for this retenu type
            self.fields[f'retenu_{retenu.id}_base'] = forms.DecimalField(
                required=False,
                max_digits=10,
                decimal_places=3,
                initial=self.invoice.total_amount if self.invoice else None,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm',
                    'step': '0.001',
                    'placeholder': '0.000'
                })
            )
    
    def save(self):
        """Create InvoiceRetenu instances for selected retenues"""
        if not self.invoice:
            return []
        
        created_retenues = []
        retenu_types = Retenu.objects.filter(is_active=True)
        
        for retenu in retenu_types:
            selected = self.cleaned_data.get(f'retenu_{retenu.id}_selected', False)
            base_amount = self.cleaned_data.get(f'retenu_{retenu.id}_base')
            
            if selected and base_amount:
                invoice_retenu = InvoiceRetenu.objects.create(
                    invoice=self.invoice,
                    retenu_type=retenu,
                    base_amount=base_amount,
                    retenu_rate=retenu.rate
                )
                created_retenues.append(invoice_retenu)
        
        return created_retenues


class PurchaseRetenuForm(forms.ModelForm):
    """Form for adding retenu to a purchase"""
    class Meta:
        model = PurchaseRetenu
        fields = ['retenu_type', 'base_amount']
        widgets = {
            'retenu_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'purchase_retenu_type_select'
            }),
            'base_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': '0.000',
                'id': 'purchase_base_amount_input'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.purchase = kwargs.pop('purchase', None)
        super().__init__(*args, **kwargs)
        self.fields['retenu_type'].queryset = Retenu.objects.filter(is_active=True)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.purchase:
            instance.purchase = self.purchase
        if instance.retenu_type:
            instance.retenu_rate = instance.retenu_type.rate
        if commit:
            instance.save()
        return instance