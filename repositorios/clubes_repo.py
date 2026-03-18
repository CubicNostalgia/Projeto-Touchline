import db_manager


def carregar_por_competicao(competicao_id):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao(competicao_id)
