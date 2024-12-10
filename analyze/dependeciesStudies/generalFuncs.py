import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

def custom_json_serializer(obj):
    """
    Converte un oggetto Python in una struttura JSON serializzabile.
    Gestisce tipi speciali come set, datetime, Decimal, UUID, etc.
    
    Args:
        obj: L'oggetto da serializzare
        
    Returns:
        str: Stringa JSON dell'oggetto serializzato
    """
    def serialize_object(obj):
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
            
        # Gestione oggetti custom con __dict__
        if hasattr(obj, '__dict__'):
            return obj.__dict__
            
        # Gestione iterabili custom
        try:
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                return list(obj)
        except:
            pass
            
        raise TypeError(f'Oggetto di tipo {type(obj)} non serializzabile')

    return json.dumps(obj, default=serialize_object, ensure_ascii=False)