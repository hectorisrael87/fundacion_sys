from decimal import Decimal, ROUND_HALF_UP
from num2words import num2words

def monto_en_letras(monto) -> str:
    """
    Devuelve: "Tres mil doscientos 00/100"
    """
    if monto is None:
        return "-"

    m = Decimal(str(monto)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    entero = int(m)
    centavos = int((m - Decimal(entero)) * 100)

    letras = num2words(entero, lang="es").replace(" y ", " ").capitalize()
    return f"{letras} {centavos:02d}/100"
