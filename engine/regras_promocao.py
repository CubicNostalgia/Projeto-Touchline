import random


def jogo_unico_time_mandante(mandante, visitante):
    gols_m = random.randint(0, 3) + 1
    gols_v = random.randint(0, 3)
    if gols_m == gols_v:
        return mandante
    return mandante if gols_m > gols_v else visitante


def definir_subidas_serie_b(classificacao):
    # classificacao: lista ordenada [ (clube, dados), ... ]
    top2 = [classificacao[0][0], classificacao[1][0]]
    terceiro = classificacao[2][0]
    quarto = classificacao[3][0]
    quinto = classificacao[4][0]
    sexto = classificacao[5][0]

    vencedor_a = jogo_unico_time_mandante(terceiro, sexto)
    vencedor_b = jogo_unico_time_mandante(quarto, quinto)

    return {
        "acesso_direto": [c.nome for c in top2],
        "acesso_playoff": [vencedor_a.nome, vencedor_b.nome],
        "rebaixados": [c.nome for c, _ in classificacao[-4:]],
    }
