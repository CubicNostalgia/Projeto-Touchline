import db_manager


def carregar_clubes_serie_a(estado_mundo=None):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao("bra_a")


def carregar_clubes_serie_b_2026(estado_mundo=None):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao("bra_b")


def carregar_clubes_serie_c_2026(estado_mundo=None):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao("bra_c")


def carregar_clubes_serie_d_2026(estado_mundo=None):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao("bra_d")


def carregar_clubes_paulistao(clubes_existentes=None, estado_mundo=None):
    db_manager.seed_database_if_needed()
    return db_manager.carregar_clubes_por_competicao("paulistao_a1")
