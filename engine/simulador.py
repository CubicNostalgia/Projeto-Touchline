import random


def simular_partida(casa, fora, derby=False, venda_mando=False):
    f_casa = casa.forca_titular()
    f_fora = fora.forca_titular()

    if hasattr(casa, "bonus_casa"):
        bonus_casa = casa.bonus_casa(derby=derby, vender_mando=venda_mando)
    else:
        bonus_casa = 2

    potencial_casa = f_casa + bonus_casa
    potencial_fora = f_fora

    gols_casa = calcular_gols(potencial_casa, potencial_fora)
    gols_fora = calcular_gols(potencial_fora, potencial_casa)

    return gols_casa, gols_fora


def calcular_gols(ataque, defesa):
    diff = ataque - defesa
    variacao_dia = random.uniform(-1.5, 1.5)

    esperanca_gols = 1.1 + (diff * 0.14) + variacao_dia
    esperanca_gols = max(0.1, esperanca_gols)

    sorte = random.random()

    if sorte < 0.25:
        return 0 if esperanca_gols < 2 else 1

    if sorte < 0.75:
        return int(esperanca_gols)

    return int(esperanca_gols + 1.5)
