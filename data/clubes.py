from core.clube import Clube
from utils.gerador_jogadores import gerar_elenco
from data.database import CLUBES_SERIE_A, CLUBES_SERIE_B_2026, PAULISTAO_EXTRAS_2026


def _normalizar_reputacao(valor):
    # compatibilidade com base antiga em escala pequena
    return valor if valor > 15 else max(1, min(100, valor * 15))


def _instanciar_clubes(base, estado_mundo=None):
    estado_mundo = estado_mundo or {}
    idx_estado = {c["id"]: c for c in estado_mundo.get("clubes", [])}

    clubes = []
    for c in base:
        estado = idx_estado.get(c["id"], {})
        clubes.append(
            Clube(
                id=c["id"],
                nome=c["nome"],
                elenco=gerar_elenco(c["forca_base"]),
                reputacao=_normalizar_reputacao(c.get("reputacao", 50)),
                competicoes=c.get("competicoes", []),
                dados_iniciais=estado,
            )
        )
    return clubes


def carregar_clubes_serie_a(estado_mundo=None):
    return _instanciar_clubes(CLUBES_SERIE_A, estado_mundo=estado_mundo)


def carregar_clubes_serie_b_2026(estado_mundo=None):
    return _instanciar_clubes(CLUBES_SERIE_B_2026, estado_mundo=estado_mundo)


def carregar_clubes_paulistao(clubes_existentes=None, estado_mundo=None):
    clubes_existentes = clubes_existentes or []
    indice = {c.nome: c for c in clubes_existentes}

    for clube in _instanciar_clubes(CLUBES_SERIE_A + CLUBES_SERIE_B_2026 + PAULISTAO_EXTRAS_2026, estado_mundo=estado_mundo):
        indice.setdefault(clube.nome, clube)

    participantes = [
        "PALMEI", "CORINTHNS", "S PAULO", "BRAGA", "SANTOS", "MIRASSOL", "BOTAFO SP", "NOVORIZON",
        "PNT PRETA", "S BERNAR", "PORTUGSA", "CAPIVARI", "GUARANI", "PRIMVERA", "NOROEST", "VEL CLUBE",
    ]
    return [indice[n] for n in participantes if n in indice]