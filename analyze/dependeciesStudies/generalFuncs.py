import json
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from pathlib import Path
from typing import Any, Union, Dict, List, Set


class JSONSerializationError(TypeError):
    """Eccezione personalizzata per errori di serializzazione JSON"""
    pass


class CustomJSONSerializer:
    """
    Classe per la serializzazione JSON di oggetti Python con tipi complessi.
    Supporta la serializzazione di set, datetime, Decimal, UUID, Path e oggetti custom.
    """

    @staticmethod
    def _convert_key(key: Any) -> str:
        """Converte le chiavi non serializzabili in stringhe."""
        if isinstance(key, (Path, datetime, date, Decimal, UUID)):
            return str(key)
        return key

    @classmethod
    def _serialize_object(cls, obj: Any) -> Union[Dict, List, str, Any]:
        """Serializza un oggetto Python in un formato JSON compatibile."""

        # Gestione tipi base
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        # Gestione dizionari
        if isinstance(obj, dict):
            return {
                cls._convert_key(k): cls._serialize_object(v)
                for k, v in obj.items()
            }

        # Gestione collezioni
        if isinstance(obj, (list, tuple)):
            return [cls._serialize_object(item) for item in obj]
        if isinstance(obj, set):
            return [cls._serialize_object(item) for item in sorted(obj)]

        # Gestione tipi speciali
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, Path):
            return str(obj)

        # Gestione oggetti custom
        if hasattr(obj, 'to_json'):
            return cls._serialize_object(obj.to_json())
        if hasattr(obj, '__dict__'):
            return cls._serialize_object(obj.__dict__)

        # Gestione iterabili custom
        try:
            if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
                return [cls._serialize_object(item) for item in obj]
        except Exception:
            pass

        raise JSONSerializationError(
            f"Impossibile serializzare oggetto di tipo {type(obj).__name__}"
        )

    @classmethod
    def dumps(cls, obj: Any, **kwargs) -> str:
        """
        Serializza un oggetto Python in una stringa JSON.

        Args:
            obj: L'oggetto da serializzare
            **kwargs: Argomenti opzionali da passare a json.dumps

        Returns:
            str: Stringa JSON dell'oggetto serializzato

        Raises:
            JSONSerializationError: Se l'oggetto non può essere serializzato
        """
        try:
            serialized = cls._serialize_object(obj)
            return json.dumps(serialized, ensure_ascii=False, **kwargs)
        except Exception as e:
            raise JSONSerializationError(f"Errore di serializzazione: {str(e)}")


def custom_json_serializer(obj: Any, **kwargs) -> str:
    """Funzione di utilità per serializzare oggetti Python in JSON."""
    return CustomJSONSerializer.dumps(obj, **kwargs)