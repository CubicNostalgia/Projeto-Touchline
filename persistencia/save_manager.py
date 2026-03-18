from pathlib import Path

import db_manager

LEGACY_SAVE_PATH = Path("save_game.json")


def save_exists():
    return db_manager.save_exists() or LEGACY_SAVE_PATH.exists()


def carregar_save():
    if db_manager.save_exists():
        return db_manager.carregar_estado_mundo()

    if not LEGACY_SAVE_PATH.exists():
        return None
    return _migrar_json_para_db()


def salvar_save(data):
    clubes = data.get("clubes", [])
    temporada_ano = data.get("meta", {}).get("temporada_atual", 2026)
    clubes_obj = []
    for clube in clubes:
        if hasattr(clube, "id"):
            clubes_obj.append(clube)
        else:
            elenco = clube.get("elenco", [])
            if not elenco:
                base_clube = db_manager.carregar_clube_por_id(clube["id"], temporada_ano=temporada_ano)
                if base_clube:
                    _aplicar_estado_clube(base_clube, clube)
                    clubes_obj.append(base_clube)
                    continue

            from core.clube import Clube
            from core.jogador import Jogador

            elenco_objs = [Jogador.from_dict(j) for j in elenco]
            dados_iniciais = clube.copy()
            dados_iniciais.pop("elenco", None)
            clubes_obj.append(
                Clube(
                    id=clube["id"],
                    nome=clube["nome"],
                    elenco=elenco_objs,
                    reputacao=clube.get("reputacao", 50),
                    competicoes=clube.get("competicoes", []),
                    dados_iniciais=dados_iniciais,
                )
            )
    db_manager.salvar_clubes(clubes_obj, temporada_ano=temporada_ano)
    db_manager.salvar_meta_temporada(temporada_ano)


def iniciar_novo_save(clubes, temporada_ano=2026):
    data = {
        "meta": {"temporada_atual": temporada_ano},
        "clubes": [c.to_dict() for c in clubes],
    }
    db_manager.salvar_clubes(clubes, temporada_ano=temporada_ano)
    db_manager.salvar_meta_temporada(temporada_ano)
    return data


def _migrar_json_para_db():
    import json

    with LEGACY_SAVE_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    salvar_save(data)
    return db_manager.carregar_estado_mundo()


def _aplicar_estado_clube(clube_obj, estado):
    clube_obj.reputacao = estado.get("reputacao", clube_obj.reputacao)
    clube_obj.reputacao_tier = estado.get("reputacao_tier", clube_obj.reputacao_tier)
    clube_obj.prestigio_acumulado = estado.get("prestigio_acumulado", clube_obj.prestigio_acumulado)
    clube_obj.financas = estado.get("financas", clube_obj.financas)
    clube_obj.infraestrutura = estado.get("infraestrutura", clube_obj.infraestrutura)
    clube_obj.torcida_expectativa = estado.get("torcida_expectativa", clube_obj.torcida_expectativa)
    clube_obj.job_security = estado.get("job_security", clube_obj.job_security)
    clube_obj.status_financeiro = estado.get("status_financeiro", clube_obj.status_financeiro)
    clube_obj.investimento_base = estado.get("investimento_base", getattr(clube_obj, "investimento_base", "medio"))
    clube_obj.nivel_auxiliar = estado.get("nivel_auxiliar", getattr(clube_obj, "nivel_auxiliar", 1))
    clube_obj.nivel_olheiro = estado.get("nivel_olheiro", getattr(clube_obj, "nivel_olheiro", 1))
    clube_obj.competicoes = estado.get("competicoes", clube_obj.competicoes)
