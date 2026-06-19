from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    if not dictionary:
        return None

    if key in dictionary:
        return dictionary[key]

    str_key = str(key)
    if str_key in dictionary:
        return dictionary[str_key]

    try:
        int_key = int(key)
        if int_key in dictionary:
            return dictionary[int_key]
    except (ValueError, TypeError):
        pass

    return None

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