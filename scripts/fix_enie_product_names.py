"""
Script para corregir la ñ en los nombres de productos de un tenant usando expresiones regulares.

Detecta dos tipos de error:
    1) La ñ quedó como símbolo roto:  "Ni�a", "Pesta�as"
    2) La ñ se escribió como n:       "Nina", "Pestanas", "Cumpleanos"

Muestra preview y pide confirmación. Los nombres ambiguos se marcan para revisión manual.

Uso:
    ./manage_prod.py runscript fix_enie_product_names
"""
import re

from products.models import Product
from accounts.models import Tenant

# En las palabras de abajo, [n�] quiere decir "una n o el símbolo roto".
X = r"[n�]"

# (patrón, reemplazo). Se aplican en orden y sin importar mayúsculas.
REGLAS = [
    # --- El símbolo roto en realidad era otra letra ---
    (r"\blap�(z|cera)", r"lapi\1"),
    (r"\bp�(yaso)", r"pa\1"),
    (r"\bp�(luche)", r"pe\1"),
    (r"\bbo�(lsa)", r"bo\1"),
    (r"\bp�(nzas?)", r"pi\1"),
    (r"\bpa�(ette)", r"pal\1"),
    (r"\bestre�(as?)\b", r"estrell\1"),
    (r"\b(https?)�--", r"\1://"),

    # --- Palabras con ñ (rotas o escritas con n) ---
    (rf"\bni{X}a(?=lluvia)", r"niña "),
    (rf"\bni{X}i?([oa]s?)\b", r"niñ\1"),
    (rf"\bpest(?:a{X}|{X})a(s?)s?\b", r"pestaña\1"),
    (rf"\bcortau{X}as\b", r"cortauñas"),
    (r"\bu�as\b", r"uñas"),
    (r"\bmo�(o|os|ito|itos)\b", r"moñ\1"),
    (rf"\bcu+mplea{X}os\b", r"cumpleaños"),
    (rf"\bm[n]?u{X}(ec[ao]s?|equeras?)\b", r"muñ\1"),
    (rf"\bdise{X}(os?)\b", r"diseñ\1"),
    (rf"\b(tela)?ara{X}(as?)\b", r"\1arañ\2"),
    (rf"\bba{X}(os?)\b", r"bañ\1"),
    (rf"\bpi{X}(as?|atas?|on)\b", r"piñ\1"),
    (rf"\btama{X}(os?)\b", r"tamañ\1"),
    (r"\bso�(ar|ador[ae]?s?)\b", r"soñ\1"),
    (rf"\bsue{X}(os?)\b", r"sueñ\1"),
    (rf"\bcari{X}(os\w*)\b", r"cariñ\1"),
    (rf"\bpeque{X}(os?|as?)\b", r"pequeñ\1"),
    (rf"\bcasta{X}(os?|as?)\b", r"castañ\1"),
    (r"\bpa�(al(?:es)?)\b", r"pañ\1"),
    (rf"\bcig[uü]e{X}a\b", r"cigüeña"),
    (r"\ba�(os?)\b", r"añ\1"),

    # --- Último recurso: cualquier otro símbolo roto pasa a ñ ---
    (r"�", "ñ"),
]
REGLAS = [(re.compile(p, re.IGNORECASE), r) for p, r in REGLAS]

# Palabras ambiguas con n (solo se marcan) y palabras que terminan en símbolo roto.
DUDOSAS = re.compile(r"\b(?:mono|unas|ano|pena|cana|pina)\b|\w�(?!\w)", re.IGNORECASE)


def con_mayusculas(original, nuevo):
    """Copia el estilo de mayúsculas de la palabra original."""
    if original.isupper() and len(original) > 1:
        return nuevo.upper()
    if original[:1].isupper():
        return nuevo[:1].upper() + nuevo[1:]
    return nuevo


def corregir(texto):
    for patron, reemplazo in REGLAS:
        texto = patron.sub(
            lambda m, r=reemplazo: con_mayusculas(m.group(0), m.expand(r)), texto
        )
    return texto


def run():
    """Función ejecutada por django-extensions runscript"""
    tenant_shortname = input("Escribe el short_name del tenant: ").strip()
    if not tenant_shortname:
        print("❌ El short_name no puede estar vacío")
        return

    try:
        tenant = Tenant.objects.get(short_name=tenant_shortname)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant con short_name '{tenant_shortname}' no existe")
        return

    max_len = Product._meta.get_field("name").max_length
    changes = []
    dudosos = []
    for product in Product.objects.filter(brand__tenant=tenant).only("id", "code", "name"):
        new_name = corregir(product.name)
        if new_name != product.name:
            changes.append((product, new_name))
        if DUDOSAS.search(product.name):
            dudosos.append(product)

    print(f"🔎 {len(changes)} productos a corregir en el tenant: {tenant.name}")
    for product, new_name in changes[:100]:
        print(f"  [{product.code}] '{product.name}' -> '{new_name}'")
    if len(changes) > 100:
        print(f"  ... y {len(changes) - 100} más")

    if dudosos:
        print(f"⚠️  {len(dudosos)} productos para revisar manualmente:")
        for product in dudosos:
            print(f"  [{product.code}] '{product.name}'")

    if not changes:
        return

    too_long = [p.code for p, n in changes if len(n) > max_len]
    if too_long:
        print(f"❌ Nombre excede {max_len} caracteres en: {', '.join(too_long)}. Abortado")
        return

    if input("¿Aplicar cambios? (si/no): ").strip().lower() not in ("si", "sí", "s", "yes", "y"):
        print("Cancelado")
        return

    for product, new_name in changes:
        product.name = new_name
    Product.objects.bulk_update([p for p, _ in changes], ["name"], batch_size=500)

    print(f"✅ Listo. Se corrigieron {len(changes)} productos")
