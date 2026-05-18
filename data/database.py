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
    "paulistao_a1": {"id": "paulistao_a1", "nome": "Paulistao A1", "nivel": "estadual"},
    "paulistao_a2": {"id": "paulistao_a2", "nome": "Paulistao A2", "nivel": "estadual"},
    "paulistao_a3": {"id": "paulistao_a3", "nome": "Paulistao A3", "nivel": "estadual"},
    "cariocao_a1": {"id": "cariocao_a1", "nome": "Cariocao A1", "nivel": "estadual"},
    "copa_brasil": {"id": "copa_brasil", "nome": "Copa do Brasil", "nivel": "nacional"},
    "bra_a": {"id": "bra_a", "nome": "Campeonato Brasileiro - Serie A", "nivel": "nacional"},
    "bra_b": {"id": "bra_b", "nome": "Campeonato Brasileiro - Serie B", "nivel": "nacional"},
    "bra_c": {"id": "bra_c", "nome": "Campeonato Brasileiro - Serie C", "nivel": "nacional"},
    "bra_d": {"id": "bra_d", "nome": "Campeonato Brasileiro - Serie D", "nivel": "nacional"},
    # Competicoes auxiliares geradas em runtime
    "paulistao_a2_g2": {"id": "paulistao_a2_g2", "nome": "Paulistao A2 - Grupo 2", "nivel": "estadual"},
    "paulistao_a2_g3": {"id": "paulistao_a2_g3", "nome": "Paulistao A2 - Grupo 3", "nivel": "estadual"},
    "paulistao_a2_sf_g1": {"id": "paulistao_a2_sf_g1", "nome": "Paulistao A2 - Semi Grupo 1", "nivel": "estadual"},
    "paulistao_a2_sf_g2": {"id": "paulistao_a2_sf_g2", "nome": "Paulistao A2 - Semi Grupo 2", "nivel": "estadual"},
}

# Ajuste livre: altere as janelas conforme desejar.
JANELAS_CALENDARIO_2026 = {
    "paulistao_a1": {"inicio": date(2026, 1, 11), "fim": date(2026, 3, 8)},
    "paulistao_a2": {"inicio": date(2026, 1, 18), "fim": date(2026, 4, 12)},
    "cariocao_a1": {"inicio": date(2026, 1, 18), "fim": date(2026, 3, 15)},
    "copa_brasil": {"inicio": date(2026, 2, 4), "fim": date(2026, 11, 25)},
    "bra_a": {"inicio": date(2026, 3, 29), "fim": date(2026, 12, 6)},
    "bra_b": {"inicio": date(2026, 3, 29), "fim": date(2026, 11, 29)},
    "bra_c": {"inicio": date(2026, 4, 12), "fim": date(2026, 10, 25)},
    "bra_d": {"inicio": date(2026, 4, 12), "fim": date(2026, 9, 27)},
}

# Copa do Brasil 2026 - fases e datas base (ajustadas pelo calendario para evitar pausas/FIFA)
COPA_BRASIL_CALENDARIO_2026 = [
    ("f1", date(2026, 2, 4)),
    ("f2", date(2026, 2, 18)),
    ("f3", date(2026, 3, 5)),
    ("f4", date(2026, 4, 8)),
    ("f5_ida", date(2026, 5, 6)),
    ("f5_volta", date(2026, 5, 27)),
    ("f6_ida", date(2026, 8, 5)),
    ("f6_volta", date(2026, 8, 26)),
    ("f7_ida", date(2026, 9, 23)),
    ("f7_volta", date(2026, 10, 14)),
    ("f8_ida", date(2026, 10, 28)),
    ("f8_volta", date(2026, 11, 4)),
    ("final", date(2026, 11, 25)),
]

# Premiacao acumulativa por fase (valores totais ao atingir a fase)
COPA_BRASIL_PREMIACAO_2026 = {
    "grupos": {
        "I": {"f1": 1_800_000, "f2": 2_400_000, "f3": 3_000_000, "f4": 3_600_000},
        "II": {"f1": 1_200_000, "f2": 1_600_000, "f3": 2_000_000, "f4": 2_400_000},
        "III": {"f1": 400_000, "f2": 830_000, "f3": 950_000, "f4": 1_070_000},
    },
    "fase_unificada": 2_000_000,
    "premio_titulo": 78_000_000,
}

# Entradas por fase (formato 2026)
COPA_BRASIL_ENTRADAS_2026 = {
    "fase1_total": 28,
    "fase2_novos": 74,
    "fase3_novos": 4,  # campeoes regionais + Serie C + Serie D
    "fase5_serie_a": 20,
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
    {"id": "vasco", "nome": "VASCO DA GAMA", "forca_base": 73, "reputacao": 3, "competicoes": ["bra_a"]},
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

PAULISTAO_A2_2026 = [
    "AGUA SNTA",
    "FERROVIA SP",
    "GREMIO PRUDEN",
    "INTER LIM",
    "ITUANO",
    "JUVENTUS SP",
    "LINENS",
    "MONTE AZUL",
    "OSASC SPORT",
    "SANT ANDRE",
    "S BENTO",
    "SERTAOZIN",
    "SAO JOSE SP",
    "TAUBATE",
    "VOTUPORANGUEN",
    "XV PIRACICA",
]

CARIOCAO_A1_2026 = [
    "BANGU",
    "BOAVISTA RJ",
    "BOTAFO",
    "FLAMEN",
    "FLUMINSE",
    "MADUREI",
    "MARICA",
    "NOVA IGUACU",
    "PORTUGSA RJ",
    "SAMPAIO CORRE RJ",
    "VASCO DA GAMA",
    "VOLTA REDON",
]


def _slug_id(nome):
    normalizado = unicodedata.normalize("NFKD", nome)
    ascii_nome = "".join(c for c in normalizado if not unicodedata.combining(c))
    ascii_nome = ascii_nome.upper().replace("-", " ")
    slug = "".join(c.lower() if c.isalnum() else "_" for c in ascii_nome).strip("_")
    return re.sub(r"_+", "_", slug)


ESTADOS_POR_CLUBE = {
    "A DE MARABA": "PA",
    "ABC": "RN",
    "ABECAT": "GO",
    "AGUA SNTA": "SP",
    "ALTOS": "PI",
    "AMAZONAS": "AM",
    "AMERIC MG": "MG",
    "AMERICA RJ": "RJ",
    "AMERICA RN": "RN",
    "ANAPOLIS": "GO",
    "APARACIDEN": "GO",
    "ARAGUAIN": "TO",
    "ASA": "AL",
    "ATH PARANAENSE": "PR",
    "ATHL CLUB": "MG",
    "ATL ALAGOIN": "BA",
    "ATL CEAREN": "CE",
    "ATL GOIANIEN": "GO",
    "ATL MINEIRO": "MG",
    "AVAI": "SC",
    "AZURIZ": "PR",
    "BAHIA": "BA",
    "BANGU": "RJ",
    "BARRA": "SC",
    "BETIM": "MG",
    "BLUMENAU": "SC",
    "BOAVISTA RJ": "RJ",
    "BOTAFO": "RJ",
    "BOTAFO PB": "PB",
    "BOTAFO SP": "SP",
    "BRAGA": "SP",
    "BRASIL PEL": "RS",
    "BRASILIEN": "DF",
    "BRUSQUE": "SC",
    "CAPITAL DF": "DF",
    "CASCAVEL": "PR",
    "CAXIAS": "RS",
    "CEARA": "CE",
    "CEILAND": "DF",
    "CENTRAL": "PE",
    "CHAPE": "SC",
    "CIANORT": "PR",
    "CONFIAN": "SE",
    "CORINTHNS": "SP",
    "CRAC": "GO",
    "CRB": "AL",
    "CRICIUM": "SC",
    "CRTIBA": "PR",
    "CRUZRO": "MG",
    "CSA": "AL",
    "CSE": "AL",
    "CUIABA": "MT",
    "DECIS GOIANA": "GO",
    "DEMOCRA GV": "MG",
    "FERROVIA CE": "CE",
    "FERROVIA SP": "SP",
    "FIGUEIREN": "SC",
    "FLAMEN": "RJ",
    "FLORES": "CE",
    "FLUMINSE": "RJ",
    "FLUMINSE PI": "PI",
    "FORTAL": "CE",
    "GALVZ": "AC",
    "GAMA": "DF",
    "GAS": "RR",
    "GOIAS": "GO",
    "GOIATUB": "GO",
    "GREMIO": "RS",
    "GREMIO PRUDEN": "SP",
    "GUAPORE": "RO",
    "GUARANI": "SP",
    "GUARANY BAGE": "RS",
    "HUMAITA": "AC",
    "IAPE": "MA",
    "IGUATU": "CE",
    "IMPERTRIZ": "MA",
    "INDEPENDENC": "PA",
    "INHUMAS": "GO",
    "INTER": "RS",
    "INTER LIM": "SP",
    "ITABAIA": "SE",
    "ITUANO": "SP",
    "IVINHEMA": "MS",
    "JACUIPEN": "BA",
    "JOINVIL": "SC",
    "JUAZEIREN": "BA",
    "JUVENTUS SP": "SP",
    "JUVNTUD RS": "RS",
    "LAGART": "SE",
    "LAGUNA": "SC",
    "LINENS": "SP",
    "LONDRIN": "PR",
    "LUVERDEN": "MT",
    "MADUREI": "RJ",
    "MAGUARY": "PE",
    "MANAUARA": "AM",
    "MANAUS": "AM",
    "MARACANA CE": "CE",
    "MARANHAO": "MA",
    "MARCIL DIAS": "SC",
    "MARICA": "RJ",
    "MARING": "PR",
    "MIRASSOL": "SP",
    "MIXTO": "MT",
    "MONTE AZUL": "SP",
    "MONT RORAIM": "RR",
    "MOTO CLUB": "MA",
    "NACIONAL AM": "AM",
    "NAUTCO": "PE",
    "NOROEST": "SP",
    "NOVA IGUACU": "RJ",
    "NOVORIZON": "SP",
    "OPERAR MS": "MS",
    "OPERAR PR": "PR",
    "OPERAR VG": "MT",
    "ORATORI": "AP",
    "OSASC SPORT": "SP",
    "PALMEI": "SP",
    "PARNAHYB": "PI",
    "PAYSAN": "PA",
    "PIAUI": "PI",
    "PNT PRETA": "SP",
    "PORTO BA": "BA",
    "PORTO VELHO": "RO",
    "PORTUGSA": "SP",
    "PORTUGSA RJ": "RJ",
    "POUSO ALEG": "MG",
    "PRIMVERA": "SP",
    "PRIMVERA MT": "MT",
    "REAL NOROEST": "ES",
    "REMO": "PA",
    "RETRO": "PE",
    "RIO BRANC ES": "ES",
    "S BENTO": "SP",
    "S BERNAR": "SP",
    "S JOSEENSE": "PR",
    "S PAULO": "SP",
    "S RAIMUNDO RR": "RR",
    "SAMPAIO CORRE MA": "MA",
    "SAMPAIO CORRE RJ": "RJ",
    "SANT ANDRE": "SP",
    "SANT CATARIN": "SC",
    "SANTA CRZ": "PE",
    "SANTOS": "SP",
    "SAO JOSE SP": "SP",
    "SAO JOSE RS": "RS",
    "SAO LUIZ": "RS",
    "SERGIPE": "SE",
    "SERRA BRANC": "PB",
    "SERTAOZIN": "SP",
    "SOUSA PB": "PB",
    "SPORT": "PE",
    "TAUBATE": "SP",
    "TIROL": "RN",
    "TOCANTINOP": "TO",
    "TOMBENS": "MG",
    "TREM": "AP",
    "TREZE": "PB",
    "TUNA LUSO": "PA",
    "UBERLAN": "MG",
    "UNIAO RONDONO": "RO",
    "VASCO DA GAMA": "RJ",
    "VEL CLUBE": "SP",
    "VIL NOVA GO": "GO",
    "VITORIA": "BA",
    "VITORIA ES": "ES",
    "VOLTA REDON": "RJ",
    "VOTUPORANGUEN": "SP",
    "XV PIRACICA": "SP",
    "YPIRNGA ERE": "RS",
}

SIGLAS_ESTADO = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG",
    "MS", "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR",
    "RS", "SC", "SE", "SP", "TO",
]


def _inferir_estado(nome):
    nome = nome.upper().strip()
    if nome in ESTADOS_POR_CLUBE:
        return ESTADOS_POR_CLUBE[nome]
    for sigla in SIGLAS_ESTADO:
        if re.search(rf"\\b{sigla}\\b", nome):
            return sigla
    return None


def _aplicar_estado(lista):
    for clube in lista:
        if "estado" not in clube or not clube["estado"]:
            clube["estado"] = _inferir_estado(clube["nome"]) or "OUT"


def _montar_clubes(nomes, competicao_id, forca_base, reputacao):
    return [
        {
            "id": _slug_id(nome),
            "nome": nome,
            "forca_base": forca_base,
            "reputacao": reputacao,
            "estado": _inferir_estado(nome) or "OUT",
            "competicoes": [competicao_id],
        }
        for nome in nomes
    ]


def _nomes_clubes(*listas):
    nomes = set()
    for lista in listas:
        for clube in lista:
            nomes.add(clube["nome"])
    return nomes


def _criar_clubes_estaduais(nomes, competicao_id, forca_base=55, reputacao=1):
    base_nomes = _nomes_clubes(CLUBES_SERIE_A, CLUBES_SERIE_B_2026, CLUBES_SERIE_C_2026, CLUBES_SERIE_D_2026)
    novos = [n for n in nomes if n not in base_nomes]
    clubes = _montar_clubes(novos, competicao_id, forca_base, reputacao)
    for clube in clubes:
        estado = _inferir_estado(clube["nome"])
        clube["estado"] = estado if estado else "SP"
    return clubes


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

CLUBES_ESTADUAIS_2026 = (
    _criar_clubes_estaduais(PAULISTAO_A2_2026, "paulistao_a2", forca_base=55, reputacao=1)
    + _criar_clubes_estaduais(CARIOCAO_A1_2026, "cariocao_a1", forca_base=56, reputacao=1)
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

_adicionar_competicao_por_nome(CLUBES_SERIE_A, CARIOCAO_A1_2026, "cariocao_a1")
_adicionar_competicao_por_nome(CLUBES_SERIE_B_2026, CARIOCAO_A1_2026, "cariocao_a1")
_adicionar_competicao_por_nome(CLUBES_SERIE_C_2026, CARIOCAO_A1_2026, "cariocao_a1")
_adicionar_competicao_por_nome(CLUBES_SERIE_D_2026, CARIOCAO_A1_2026, "cariocao_a1")

_adicionar_competicao_por_nome(CLUBES_SERIE_A, PAULISTAO_A2_2026, "paulistao_a2")
_adicionar_competicao_por_nome(CLUBES_SERIE_B_2026, PAULISTAO_A2_2026, "paulistao_a2")
_adicionar_competicao_por_nome(CLUBES_SERIE_C_2026, PAULISTAO_A2_2026, "paulistao_a2")
_adicionar_competicao_por_nome(CLUBES_SERIE_D_2026, PAULISTAO_A2_2026, "paulistao_a2")
_adicionar_competicao_por_nome(CLUBES_ESTADUAIS_2026, PAULISTAO_A2_2026, "paulistao_a2")
_adicionar_competicao_por_nome(CLUBES_ESTADUAIS_2026, CARIOCAO_A1_2026, "cariocao_a1")

_aplicar_estado(CLUBES_SERIE_A)
_aplicar_estado(CLUBES_SERIE_B_2026)
_aplicar_estado(CLUBES_SERIE_C_2026)
_aplicar_estado(CLUBES_SERIE_D_2026)
_aplicar_estado(CLUBES_ESTADUAIS_2026)


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
