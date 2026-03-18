import random

import db_manager

TEMPLATES_GOLEADA = [
    "{vencedor} atropela {perdedor} com um placar imponente",
    "{vencedor} nao toma conhecimento e goleia {perdedor}",
    "Show de {vencedor}: goleada sobre {perdedor}",
    "Placar elastico: {vencedor} aplica goleada em {perdedor}",
    "{vencedor} domina e constroi vitoria folgada sobre {perdedor}",
]

TEMPLATES_GOLEADA_PESADA = [
    "Massacre: {vencedor} impoe goleada historica sobre {perdedor}",
    "{vencedor} faz chover e nao perdoa {perdedor}",
    "Placar arrasador: {vencedor} atropela {perdedor}",
]

TEMPLATES_ZEBRA = [
    "Zebra historica: {vencedor} derruba o favorito {perdedor}",
    "{vencedor} surpreende o gigante {perdedor}",
    "No improvavel, {vencedor} vence {perdedor}",
    "Resultado chocante: {vencedor} supera {perdedor}",
    "Inesperado: {vencedor} cala {perdedor}",
]

TEMPLATES_EQUILIBRADO = [
    "Equilibrio total entre {casa} e {fora}",
    "Empate movimentado entre {casa} e {fora}",
    "{casa} e {fora} dividem pontos em jogo disputado",
]

TEMPLATES_CLASSICO = [
    "Duelo de gigantes: {casa} e {fora} fazem jogo grande",
    "Classico de peso entre {casa} e {fora}",
    "No topo do futebol, {casa} enfrenta {fora} em grande estilo",
]


def registrar_noticia(temporada_ano, rodada, tipo, prioridade, titulo, corpo):
    db_manager.inserir_noticia(temporada_ano, rodada, tipo, prioridade, titulo, corpo)


def listar_noticias(temporada_ano=None, limite=20):
    return db_manager.listar_noticias(temporada_ano=temporada_ano, limite=limite)


def processar_rodada(partidas, temporada_ano, rodada):
    noticias_rodada = []
    for partida in partidas:
        casa = partida["casa"]
        fora = partida["fora"]
        gols_casa = partida["gols_casa"]
        gols_fora = partida["gols_fora"]
        diff = abs(gols_casa - gols_fora)

        if diff >= 5:
            vencedor = casa if gols_casa > gols_fora else fora
            perdedor = fora if vencedor == casa else casa
            titulo = random.choice(TEMPLATES_GOLEADA_PESADA).format(vencedor=vencedor.nome, perdedor=perdedor.nome)
            corpo = f"Placar final: {casa.nome} {gols_casa} x {gols_fora} {fora.nome}."
            noticias_rodada.append({"tipo": "goleada", "prioridade": 3, "titulo": titulo, "corpo": corpo})
        elif diff >= 4:
            vencedor = casa if gols_casa > gols_fora else fora
            perdedor = fora if vencedor == casa else casa
            titulo = random.choice(TEMPLATES_GOLEADA).format(vencedor=vencedor.nome, perdedor=perdedor.nome)
            corpo = f"Placar final: {casa.nome} {gols_casa} x {gols_fora} {fora.nome}."
            noticias_rodada.append({"tipo": "goleada", "prioridade": 2, "titulo": titulo, "corpo": corpo})

        vencedor = None
        perdedor = None
        if gols_casa > gols_fora:
            vencedor, perdedor = casa, fora
        elif gols_fora > gols_casa:
            vencedor, perdedor = fora, casa

        if vencedor and perdedor:
            diff_tier = getattr(perdedor, "reputacao_tier", 0) - getattr(vencedor, "reputacao_tier", 0)
            if diff_tier >= 3:
                titulo = random.choice(TEMPLATES_ZEBRA).format(vencedor=vencedor.nome, perdedor=perdedor.nome)
                corpo = f"Vitoria improvavel: {casa.nome} {gols_casa} x {gols_fora} {fora.nome}."
                noticias_rodada.append({"tipo": "zebra", "prioridade": 3, "titulo": titulo, "corpo": corpo})

        if (
            getattr(casa, "reputacao_tier", 0) >= 10
            and getattr(fora, "reputacao_tier", 0) >= 10
            and diff <= 1
        ):
            titulo = random.choice(TEMPLATES_CLASSICO).format(casa=casa.nome, fora=fora.nome)
            corpo = f"Placar final: {casa.nome} {gols_casa} x {gols_fora} {fora.nome}."
            noticias_rodada.append({"tipo": "classico", "prioridade": 2, "titulo": titulo, "corpo": corpo})

        if gols_casa == gols_fora and (gols_casa + gols_fora) >= 4:
            titulo = random.choice(TEMPLATES_EQUILIBRADO).format(casa=casa.nome, fora=fora.nome)
            corpo = f"Empate: {casa.nome} {gols_casa} x {gols_fora} {fora.nome}."
            noticias_rodada.append({"tipo": "empate", "prioridade": 1, "titulo": titulo, "corpo": corpo})

    noticias_rodada.sort(key=lambda n: n["prioridade"], reverse=True)
    for noticia in noticias_rodada[:3]:
        registrar_noticia(
            temporada_ano,
            rodada,
            noticia["tipo"],
            noticia["prioridade"],
            noticia["titulo"],
            noticia["corpo"],
        )
