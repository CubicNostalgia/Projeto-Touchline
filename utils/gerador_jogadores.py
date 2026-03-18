import random
from typing import Optional

from core.jogador import Jogador

PRENOMES = [
    "Gabriel", "Lucas", "Matheus", "Vitor", "Bruno", "Felipe", "Igor", "Caio", "Rafael", "Diego",
    "Renan", "Arthur", "Pedro", "Thiago", "Andre", "Leandro", "Henrique", "Danilo", "Eduardo", "Samuel",
    "Wagner", "Walace", "Anderson", "Hugo", "Gustavo", "Enzo", "Pablo", "Otávio", "Jefferson", "Jeferson",
    "Cristian", "Joaquim", "Jonas", "Cléber"
]
MEIOS_SUFIXO = ["Neto", "Junior"]
SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Pereira", "Lima", "Ferreira", "Costa", "Rodrigues", "Almeida",
    "Ribeiro", "Carvalho", "Gomes", "Martins", "Araújo", "Rocha", "Barbosa", "Teixeira", "Correia", "Farias",
    "Vasconcelos", "Sales", "Telles", "Tavares", "Melo", "Guimarães"
]
APELIDOS = ["Juninho", "Dudu", "Pedrinho", "Vitinho", "Fernandinho", "Tetê", "Bolacha", "Canela", "Tomate", "Tanque"]

POSICOES_ELENCO = {
    "GOL": 3,
    "LD": 2,
    "ZAG": 4,
    "LE": 2,
    "VOL": 3,
    "MC": 4,
    "MEI": 2,
    "PD": 2,
    "PE": 2,
    "ATA": 3,
}

SOBRENOMES_DA = {
    "Silva", "Costa", "Rocha"
}

SOBRENOMES_DOS = {"Santos"}

HABILIDADES_POS = [
    "Pe de Canhao",
    "Mestre do Passe",
    "Ladrao de Bola",
    "Lider Nato",
    "Garcom",
]

DEFEITOS = [
    "Vidro",
    "Pulmao de Fumante",
    "Pavio Curto",
    "Pipoqueiro",
    "Tijolo no Pe",
    "Cego de um Olho",
]


def _preposicao_para_sobrenome(sobrenome):
    if sobrenome in SOBRENOMES_DOS:
        return "dos"
    if sobrenome in SOBRENOMES_DA:
        return "da"
    return "de"


def gerar_nome():
    modelo = random.random()
    if modelo < 0.15:
        return random.choice(APELIDOS)
    if modelo < 0.55:
        return f"{random.choice(PRENOMES)} {random.choice(SOBRENOMES)}"
    if modelo < 0.85:
        sobrenome = random.choice(SOBRENOMES)
        preposicao = _preposicao_para_sobrenome(sobrenome)
        return f"{random.choice(PRENOMES)} {preposicao} {sobrenome}"
    return f"{random.choice(PRENOMES)} {random.choice(MEIOS_SUFIXO)} {random.choice(SOBRENOMES)}"


def gerar_over(forca_base: int):
    return max(56, min(84, forca_base + random.choice([-3, -2, -1, 0, 1, 2])))


def calcular_salario(overall: int, idade: int, potencial: int):
    base = 800 + (overall ** 2) * 6
    bonus_pot = max(0, (potencial - overall) * 120)
    bonus_idade = -max(0, idade - 30) * 120
    return int(max(600, base + bonus_pot + bonus_idade))

def gerar_traits(potencial: int, idade: int):
    habilidades = []
    defeitos = []

    chance_habilidade = 0.08 + max(0, (potencial - 80) * 0.006)
    if random.random() < chance_habilidade:
        habilidades.append(random.choice(HABILIDADES_POS))
    if potencial >= 88 and random.random() < 0.06:
        habilidades.append(random.choice(HABILIDADES_POS))

    chance_defeito = 0.12 + (0.05 if idade >= 30 else 0)
    if random.random() < chance_defeito:
        defeitos.append(random.choice(DEFEITOS))
    if random.random() < 0.04:
        defeitos.append(random.choice(DEFEITOS))

    habilidades = list(dict.fromkeys(habilidades))
    defeitos = list(dict.fromkeys(defeitos))
    return habilidades, defeitos


def gerar_jogador(
    forca_base: int,
    posicao: str,
    idade: Optional[int] = None,
    potencial: Optional[int] = None,
    status_base: str = "profissional",
    origem_base: bool = False,
    ):
    idade = idade if idade is not None else random.randint(17, 35)
    overall = gerar_over(forca_base)
    if potencial is None:
        potencial = max(overall, min(91, overall + random.randint(1, 8) - max(0, idade - 25) // 2))
    salario = calcular_salario(overall, idade, potencial)
    habilidades, defeitos = gerar_traits(potencial, idade)
    return Jogador(
        gerar_nome(),
        overall,
        posicao,
        idade=idade,
        potencial=potencial,
        salario=salario,
        status_base=status_base,
        origem_base=origem_base,
        habilidades=habilidades,
        defeitos=defeitos,
    )


def gerar_newgen_base(nivel_base: int, posicao: str):
    nivel = max(0, min(30, int(nivel_base)))
    idade = random.randint(16, 19)
    ovr_base = 45 + (nivel * 0.85)
    overall = int(max(45, min(78, ovr_base + random.randint(-3, 3))))

    pot_min = 55 + int(nivel * 1.1)
    pot_max = 65 + int(nivel * 1.25)
    if nivel >= 28:
        pot_min = max(pot_min, 85)
    pot_min = min(pot_min, 95)
    pot_max = min(max(pot_max, pot_min), 95)
    potencial = max(overall, random.randint(pot_min, pot_max))
    salario = calcular_salario(overall, idade, potencial)
    habilidades, defeitos = gerar_traits(potencial, idade)

    return Jogador(
        gerar_nome(),
        overall,
        posicao,
        idade=idade,
        potencial=potencial,
        salario=salario,
        status_base="base",
        origem_base=True,
        habilidades=habilidades,
        defeitos=defeitos,
    )


def gerar_elenco(forca_base: int):
    elenco = []
    for posicao, quantidade in POSICOES_ELENCO.items():
        for _ in range(quantidade):
            elenco.append(gerar_jogador(forca_base, posicao))
    return elenco
