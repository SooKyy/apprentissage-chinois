from sqlalchemy.orm import Session

from app.models import Setting

KINDS = ("reco", "ecoute", "prod")

DEFAULTS: dict[str, object] = {
    "new_per_day": 12,  # cartes neuves par jour (un mot = une carte par type activé)
    "desired_retention": 0.9,
    "card_kinds": ["reco", "ecoute"],
    "auto_enrich": True,
    "tts_rate": 1.0,
    "show_english": True,
}


def get_all(db: Session) -> dict[str, object]:
    values = dict(DEFAULTS)
    for row in db.query(Setting).all():
        if row.key in DEFAULTS:
            values[row.key] = row.value
    return values


def get(db: Session, key: str):
    row = db.get(Setting, key)
    return DEFAULTS[key] if row is None else row.value


def validate(key: str, value: object) -> object:
    if key not in DEFAULTS:
        raise ValueError(f"réglage inconnu : {key}")
    if key == "new_per_day":
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 200:
            raise ValueError("new_per_day doit être un entier entre 0 et 200")
    elif key == "desired_retention":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.7 <= value <= 0.97:
            raise ValueError("desired_retention doit être entre 0.70 et 0.97")
        value = float(value)
    elif key == "card_kinds":
        if not isinstance(value, list) or not value or any(kind not in KINDS for kind in value):
            raise ValueError(f"card_kinds doit être une liste non vide parmi {KINDS}")
        value = [kind for kind in KINDS if kind in value]
    elif key == "tts_rate":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.5 <= value <= 1.5:
            raise ValueError("tts_rate doit être entre 0.5 et 1.5")
        value = float(value)
    elif not isinstance(value, bool):
        raise ValueError(f"{key} doit être un booléen")
    return value


def update(db: Session, changes: dict[str, object]) -> dict[str, object]:
    cleaned = {key: validate(key, value) for key, value in changes.items()}
    for key, value in cleaned.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return get_all(db)
