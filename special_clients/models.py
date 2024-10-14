from django.db import models
from products.models import Base


#añadir clientes, nombre telefono. tipo precio

#Precios
# Precio de compra
# Precio publico
# Precio minorista
# Precio medio mayoreo 
# precio mayoreo
# Añadir descuento por cierta cantidad


#definir si los tipos de descuento tienen un % comun, si eres x tipo, tu descuento es de n% en la compra total, eso facilitaria la operacion
class SpecialClientType(Base):
    pass


class SpecialClient(models.Model):
    special_client_type = models.ForeignKey(SpecialClientType, on_delete=models.CASCADE)   
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    phone_numer = models.CharField(max_length=10)



