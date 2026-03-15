from datetime import date
import re
import unicodedata

HIERARQUIA_COMPETICOES = [
    "estadual",
    "regional",
    "nacional",
    "internacional",
    "intercontinental",
    "mundial",
]

COMPETICOES = {
    "paulistao_a1": {"id": "paulistao_a1", "nome": "Paulistão A1", "nivel": "estadual"},
    "bra_a": {"id": "bra_a", "nome": "Campeonato Brasileiro — Série A", "nivel": "nacional"},
    "bra_b": {"id": "bra_b", "nome": "Campeonato Brasileiro — Série B", "nivel": "nacional"},
    "bra_c": {"id": "bra_c", "nome": "Campeonato Brasileiro — Série C", "nivel": "nacional"},
    "bra_d": {"id": "bra_d", "nome": "Campeonato Brasileiro — Série D", "nivel": "nacional"},
}

# Ajuste livre: altere as janelas conforme desejar.
JANELAS_CALENDARIO_2026 = {
    "paulistao_a1": {"inicio": date(2026, 1, 11), "fim": date(2026, 3, 8)},
    "bra_a": {"inicio": date(2026, 3, 29), "fim": date(2026, 12, 6)},
    "bra_b": {"inicio": date(2026, 3, 29), "fim": date(2026, 11, 29)},
    "bra_c": {"inicio": date(2026, 4, 12), "fim": date(2026, 10, 25)},
    "bra_d": {"inicio": date(2026, 4, 12), "fim": date(2026, 9, 27)},
}

DATAS_FIFA_2026 = [
    (date(2026, 3, 23), date(2026, 3, 31)),
    (date(2026, 6, 1), date(2026, 6, 9)),
    (date(2026, 9, 7), date(2026, 9, 15)),
    (date(2026, 10, 5), date(2026, 10, 13)),
    (date(2026, 11, 9), date(2026, 11, 17)),
]

PAUSAS_TORNEIOS_2026 = [
    {"nome": "Copa do Mundo", "inicio": date(2026, 6, 11), "fim": date(2026, 7, 19)}
]

CLUBES_SERIE_A = [
    {"id": "flamen", "nome": "FLAMEN", "forca_base": 80, "reputacao": 5, "competicoes": ["bra_a"]},
    {"id": "palmei", "nome": "PALMEI", "forca_base": 79, "reputacao": 5, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "corinthns", "nome": "CORINTHNS", "forca_base": 77, "reputacao": 5, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "s_paulo", "nome": "S PAULO", "forca_base": 77, "reputacao": 5, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "gremio", "nome": "GREMIO", "forca_base": 76, "reputacao": 4, "competicoes": ["bra_a"]},
    {"id": "inter", "nome": "INTER", "forca_base": 76, "reputacao": 4, "competicoes": ["bra_a"]},
    {"id": "atl_mineiro", "nome": "ATL MINEIRO", "forca_base": 77, "reputacao": 4, "competicoes": ["bra_a"]},
    {"id": "ath_paranaense", "nome": "ATH PARANAENSE", "forca_base": 74, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "bahia", "nome": "BAHIA", "forca_base": 75, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "braga", "nome": "BRAGA", "forca_base": 74, "reputacao": 3, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "fluminse", "nome": "FLUMINSE", "forca_base": 74, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "vasco", "nome": "VASCO", "forca_base": 73, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "vitoria", "nome": "VITORIA", "forca_base": 73, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "santos", "nome": "SANTOS", "forca_base": 74, "reputacao": 4, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "crtiba", "nome": "CRTIBA", "forca_base": 71, "reputacao": 3, "competicoes": ["bra_a"]},
    {"id": "chape", "nome": "CHAPE", "forca_base": 71, "reputacao": 2, "competicoes": ["bra_a"]},
    {"id": "remo", "nome": "REMO", "forca_base": 70, "reputacao": 2, "competicoes": ["bra_a"]},
    {"id": "mirassol", "nome": "MIRASSOL", "forca_base": 71, "reputacao": 2, "competicoes": ["bra_a", "paulistao_a1"]},
    {"id": "botafo", "nome": "BOTAFO", "forca_base": 76, "reputacao": 4, "competicoes": ["bra_a"]},
    {"id": "cruzro", "nome": "CRUZRO", "forca_base": 75, "reputacao": 4, "competicoes": ["bra_a"]},
]

# Ajuste livre de forças/reputação da Série B (faixa sugerida 64-70).
CLUBES_SERIE_B_2026 = [
    {"id": "americ_mg", "nome": "AMERIC MG", "forca_base": 69, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "athl_club", "nome": "ATHL CLUB", "forca_base": 65, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "atl_goianien", "nome": "ATL GOIANIEN", "forca_base": 68, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "avai", "nome": "AVAI", "forca_base": 67, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "botafo_sp", "nome": "BOTAFO SP", "forca_base": 66, "reputacao": 2, "competicoes": ["bra_b", "paulistao_a1"]},
    {"id": "crb", "nome": "CRB", "forca_base": 66, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "ceara", "nome": "CEARA", "forca_base": 70, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "cricium", "nome": "CRICIUM", "forca_base": 67, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "cuiaba", "nome": "CUIABA", "forca_base": 68, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "fortal", "nome": "FORTAL", "forca_base": 70, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "goias", "nome": "GOIAS", "forca_base": 69, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "juvntud_rs", "nome": "JUVNTUD RS", "forca_base": 68, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "londrin", "nome": "LONDRIN", "forca_base": 65, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "novorizon", "nome": "NOVORIZON", "forca_base": 68, "reputacao": 3, "competicoes": ["bra_b", "paulistao_a1"]},
    {"id": "nautco", "nome": "NAUTCO", "forca_base": 66, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "operar_pr", "nome": "OPERAR PR", "forca_base": 67, "reputacao": 2, "competicoes": ["bra_b"]},
    {"id": "pnt_preta", "nome": "PNT PRETA", "forca_base": 64, "reputacao": 2, "competicoes": ["bra_b", "paulistao_a1"]},
    {"id": "sport", "nome": "SPORT", "forca_base": 69, "reputacao": 3, "competicoes": ["bra_b"]},
    {"id": "s_bernar", "nome": "S BERNAR", "forca_base": 68, "reputacao": 3, "competicoes": ["bra_b", "paulistao_a1"]},
    {"id": "vil_nova_go", "nome": "VIL NOVA GO", "forca_base": 66, "reputacao": 2, "competicoes": ["bra_b"]},
]

PAULISTAO_EXTRAS_2026 = []


PAULISTAO_POTES_2026 = {
    "A": ["CORINTHNS", "PALMEI", "SANTOS", "S PAULO"],
    "B": ["S BERNAR", "NOVORIZON", "BRAGA", "MIRASSOL"],
    "C": ["PNT PRETA", "GUARANI", "VEL CLUBE", "PORTUGSA"],
    "D": ["BOTAFO SP", "NOROEST", "PRIMVERA", "INTER LIM"],
}


def _slug_id(nome):
    normalizado = unicodedata.normalize("NFKD", nome)
    ascii_nome = "".join(c for c in normalizado if not unicodedata.combining(c))
    ascii_nome = ascii_nome.upper().replace("-", " ")
    slug = "".join(c.lower() if c.isalnum() else "_" for c in ascii_nome).strip("_")
    return re.sub(r"_+", "_", slug)


def _montar_clubes(nomes, competicao_id, forca_base, reputacao):
    return [
        {
            "id": _slug_id(nome),
            "nome": nome,
            "forca_base": forca_base,
            "reputacao": reputacao,
            "competicoes": [competicao_id],
        }
        for nome in nomes
    ]


def _adicionar_competicao_por_nome(clubes, nomes, competicao_id):
    alvo = set(nomes)
    for clube in clubes:
        if clube["nome"] in alvo and competicao_id not in clube["competicoes"]:
            clube["competicoes"].append(competicao_id)


CLUBES_SERIE_C_2026 = _montar_clubes(
    [
        "AMAZONAS",
        "ANAPOLIS",
        "BARRA",
        "BOTAFO PB",
        "BRUSQUE",
        "CAXIAS",
        "CONFIAN",
        "FERROVIA SP",
        "FIGUEIREN",
        "FLORES",
        "GUARANI",
        "INTER LIM",
        "ITABAIA",
        "ITUANO",
        "MARANHAO",
        "MARING",
        "PAYSAN",
        "SANTA CRZ",
        "VOLTA REDON",
        "YPIRNGA ERE",
    ],
    "bra_c",
    forca_base=63,
    reputacao=2,
)


CLUBES_SERIE_D_2026 = _montar_clubes(
    [
        "ABC",
        "ABECAT",
        "AGUA SNTA",
        "A DE MARABA",
        "ALTOS",
        "AMERICA RJ",
        "AMERICA RN",
        "APARACIDEN",
        "ARAGUAIN",
        "ASA",
        "ATL CEAREN",
        "ATL ALAGOIN",
        "AZURIZ",
        "BETIM",
        "BRASIL PEL",
        "BRASILIEN",
        "BLUMENAU",
        "CAPITAL DF",
        "CEILAND",
        "CENTRAL",
        "CIANORT",
        "CRAC",
        "CSA",
        "CSE",
        "DECIS GOIANA",
        "DEMOCRA GV",
        "CASCAVEL",
        "FERROVIA CE",
        "FLUMINSE PI",
        "GALVZ",
        "GAMA",
        "GAS",
        "GOIATUB",
        "GUAPORE",
        "PORTO VELHO",
        "GUARANY BAGE",
        "HUMAITA",
        "IAPE",
        "IGUATU",
        "IMPERTRIZ",
        "INDEPENDENC",
        "INHUMAS",
        "IVINHEMA",
        "JACUIPEN",
        "JOINVIL",
        "JUAZEIREN",
        "LAGART",
        "LAGUNA",
        "LUVERDEN",
        "MADUREI",
        "MAGUARY",
        "MANAUARA",
        "MANAUS",
        "MARACANA CE",
        "MARCIL DIAS",
        "MARICA",
        "MIXTO",
        "MONT RORAIM",
        "MOTO CLUB",
        "NACIONAL AM",
        "NOVA IGUACU",
        "NOROEST",
        "OPERAR MS",
        "OPERAR VG",
        "ORATORI",
        "PARNAHYB",
        "PIAUI",
        "PORTO BA",
        "PORTUGSA",
        "PORTUGSA RJ",
        "POUSO ALEG",
        "PRIMVERA MT",
        "REAL NOROEST",
        "RETRO",
        "RIO BRANC ES",
        "SAMPAIO CORRE MA",
        "SAMPAIO CORRE RJ",
        "SANT CATARIN",
        "SAO JOSE RS",
        "S JOSEENSE",
        "SAO LUIZ",
        "S RAIMUNDO RR",
        "SERGIPE",
        "SERRA BRANC",
        "SOUSA PB",
        "TIROL",
        "TOCANTINOP",
        "TOMBENS",
        "TREM",
        "TREZE",
        "TUNA LUSO",
        "UBERLAN",
        "UNIAO RONDONO",
        "VEL CLUBE",
        "VITORIA ES",
        "XV PIRACICA",
    ],
    "bra_d",
    forca_base=58,
    reputacao=1,
)

_adicionar_competicao_por_nome(
    CLUBES_SERIE_C_2026,
    ["GUARANI", "ITUANO", "INTER LIM"],
    "paulistao_a1",
)
_adicionar_competicao_por_nome(
    CLUBES_SERIE_D_2026,
    ["PORTUGSA", "NOROEST", "VEL CLUBE"],
    "paulistao_a1",
)


SERIE_C_EXPANSAO = [
    {"ano": 2026, "clubes": 20, "rebaixados": 2, "acessos": 6},
    {"ano": 2027, "clubes": 24, "rebaixados": 2, "acessos": 6},
    {"ano": 2028, "clubes": 28, "rebaixados": 6, "acessos": 6},
]


SERIE_D_FORMATO = {
    "grupos": 16,
    "times_por_grupo": 6,
    "classificados_por_grupo": 4,
}
