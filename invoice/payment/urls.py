from django.urls import path
from .views import calculate_retenu_preview, get_retenu_rate, invoice_retenu_add_multiple, invoice_retenu_create, invoice_retenu_delete, process_payment
urlpatterns = [
    # Existing URLs
    path('invoice/<int:invoice_id>/retenu/create/', 
         invoice_retenu_create, 
         name='invoice_retenu_create'),
    
    path('invoice/<int:invoice_id>/retenu/add-multiple/', 
         invoice_retenu_add_multiple, 
         name='invoice_retenu_add_multiple'),
    
    path('retenu/<int:retenu_id>/delete/', 
         invoice_retenu_delete, 
         name='invoice_retenu_delete'),
    
    # AJAX endpoints
    path('api/retenu/<int:retenu_id>/rate/', 
         get_retenu_rate, 
         name='get_retenu_rate'),
    
    path('api/retenu/calculate-preview/', 
         calculate_retenu_preview, 
         name='calculate_retenu_preview'),
    
    # ADD THIS: Payment processing
    path('invoice/<int:invoice_id>/process-payment/', 
         process_payment, 
         name='process_payment'),
]