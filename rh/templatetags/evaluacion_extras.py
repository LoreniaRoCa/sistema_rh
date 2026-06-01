from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """Obtiene un valor del diccionario usando la llave, convirtiendo ambos a string para asegurar match"""
    if not dictionary:
        return ""
    # Convertimos la llave a string por si en el dict es Int y en el HTML es String, o viceversa
    return dictionary.get(key) or dictionary.get(str(key)) or dictionary.get(int(key) if str(key).isdigit() else key) or ""

@register.filter
def punto_decimal(value):
    """
    Fuerza el formateo a dos decimales y reemplaza la coma por un punto.
    """
    if value is None or value == "":
        return "0.00"
    try:
        # Formateamos inicialmente con dos decimales de forma nativa en Python
        formateado = "{:.2f}".format(float(value))
        # Nos aseguramos de intercambiar cualquier coma remanente por punto
        return formateado.replace(',', '.')
    except (ValueError, TypeError):
        return value    