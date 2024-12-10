import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from pathlib import Path


def custom_json_serializer(obj):
    """
    Converte un oggetto Python in una struttura JSON serializzabile.
    Gestisce tipi speciali come set, datetime, Decimal, UUID, Path, etc.
    Converte anche le chiavi non serializzabili in stringhe.

    Args:
        obj: L'oggetto da serializzare

    Returns:
        str: Stringa JSON dell'oggetto serializzato
    """

    def convert_key(key):
        # Converti le chiavi non serializzabili in stringhe
        if isinstance(key, Path):
            return str(key)
        if isinstance(key, (datetime, date)):
            return key.isoformat()
        if isinstance(key, (Decimal, UUID)):
            return str(key)
        return key

    def serialize_object(obj):
        # Gestione dizionari con chiavi non serializzabili
        if isinstance(obj, dict):
            return {convert_key(k): serialize_object(v) for k, v in obj.items()}

        # Gestione set
        if isinstance(obj, set):
            return list(obj)

        # Gestione datetime e date
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        # Gestione Decimal
        if isinstance(obj, Decimal):
            return str(obj)

        # Gestione UUID
        if isinstance(obj, UUID):
            return str(obj)

        # Gestione Path
        if isinstance(obj, Path):
            return str(obj)

        # Gestione oggetti custom con __dict__
        if hasattr(obj, '__dict__'):
            return serialize_object(obj.__dict__)

        # Gestione iterabili custom
        try:
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                return [serialize_object(item) for item in obj]
        except:
            pass

        return obj

    try:
        return json.dumps(serialize_object(obj), ensure_ascii=False)
    except TypeError as e:
        raise TypeError(f'Oggetto non serializzabile: {str(e)}')