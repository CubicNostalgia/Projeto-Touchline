import json
from pathlib import Path

SAVE_PATH = Path("save_game.json")


def save_exists():
    return SAVE_PATH.exists()


def carregar_save():
    if not SAVE_PATH.exists():
        return None
    with SAVE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def salvar_save(data):
    with SAVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def iniciar_novo_save(clubes, temporada_ano=2026):
    data = {
        "meta": {"temporada_atual": temporada_ano},
        "clubes": [c.to_dict() for c in clubes],
    }
    salvar_save(data)
    return data