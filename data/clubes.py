from repositorios import clubes_repo


def carregar_clubes_serie_a(estado_mundo=None):
    return clubes_repo.carregar_por_competicao("bra_a")


def carregar_clubes_serie_b_2026(estado_mundo=None):
    return clubes_repo.carregar_por_competicao("bra_b")


def carregar_clubes_serie_c_2026(estado_mundo=None):
    return clubes_repo.carregar_por_competicao("bra_c")


def carregar_clubes_serie_d_2026(estado_mundo=None):
    return clubes_repo.carregar_por_competicao("bra_d")


def carregar_clubes_paulistao(clubes_existentes=None, estado_mundo=None):
    return clubes_repo.carregar_por_competicao("paulistao_a1")
