import random
from datetime import datetime, date, timedelta
from data.database import DATAS_FIFA_2026, PAUSAS_TORNEIOS_2026, JANELAS_CALENDARIO_2026


def _data_bloqueada(dia: date, considerar_fifa=True):
    if considerar_fifa:
        for inicio, fim in DATAS_FIFA_2026:
            if inicio <= dia <= fim:
                return True
    for pausa in PAUSAS_TORNEIOS_2026:
        if pausa["inicio"] <= dia <= pausa["fim"]:
            return True
    return False


def _proxima_data_valida(cursor, dia_semana, considerar_fifa=True):
    while True:
        if cursor.weekday() == dia_semana and not _data_bloqueada(cursor.date(), considerar_fifa=considerar_fifa):
            return cursor
        cursor += timedelta(days=1)


def _datas_disponiveis(inicio: date, fim: date, dias_semana, considerar_fifa=True):
    datas = []
    cursor = inicio
    while cursor <= fim:
        if cursor.weekday() in dias_semana and not _data_bloqueada(cursor, considerar_fifa=considerar_fifa):
            datas.append(cursor)
        cursor += timedelta(days=1)
    return datas


def _gerar_rodadas_pontos_corridos(clubes):
    clubes = clubes[:]
    if len(clubes) % 2:
        clubes.append(None)
    n = len(clubes)
    ida = []
    for _ in range(n - 1):
        rodada = []
        for i in range(n // 2):
            casa, fora = clubes[i], clubes[n - 1 - i]
            if casa and fora:
                rodada.append((casa, fora))
        ida.append(rodada)
        clubes = [clubes[0]] + [clubes[-1]] + clubes[1:-1]
    volta = [[(f, c) for c, f in r] for r in ida]
    return ida + volta


def _gerar_rodadas_turno_simples(clubes):
    clubes = clubes[:]
    random.shuffle(clubes)
    if len(clubes) % 2:
        clubes.append(None)
    n = len(clubes)
    rodadas = []
    for _ in range(n - 1):
        rodada = []
        for i in range(n // 2):
            casa, fora = clubes[i], clubes[n - 1 - i]
            if casa and fora:
                rodada.append((casa, fora))
        rodadas.append(rodada)
        clubes = [clubes[0]] + [clubes[-1]] + clubes[1:-1]
    return rodadas


def gerar_calendario_brasileirao(clubes, competicao_id, inicio_override=None):
    janela = JANELAS_CALENDARIO_2026[competicao_id]
    inicio_base = inicio_override or janela["inicio"]
    fim = janela["fim"]
    rodadas = _gerar_rodadas_pontos_corridos(clubes)

    datas = []
    datas.extend(_datas_disponiveis(inicio_base, fim, [5, 2], considerar_fifa=False))  # sÃ¡bado e quarta
    if len(datas) < len(rodadas):
        extras = _datas_disponiveis(inicio_base, fim, [6], considerar_fifa=False)  # domingo
        datas.extend([d for d in extras if d not in datas])
    if len(datas) < len(rodadas):
        extras = _datas_disponiveis(inicio_base, fim, [1, 3, 4], considerar_fifa=False)  # ter/qui/sex
        datas.extend([d for d in extras if d not in datas])

    datas = sorted(datas)

    if len(datas) < len(rodadas):
        cursor = datetime.combine(fim, datetime.min.time())
        while len(datas) < len(rodadas):
            cursor += timedelta(days=1)
            if cursor.weekday() in [5, 2, 6, 1, 3, 4] and not _data_bloqueada(cursor.date(), considerar_fifa=False):
                datas.append(cursor.date())

    calendario = []
    for idx, rodada in enumerate(rodadas, start=1):
        dia = datas[idx - 1]
        if dia.weekday() == 2:
            horario = (19, 30)
        elif dia.weekday() == 6:
            horario = (16, 0)
        elif dia.weekday() in (1, 3, 4):
            horario = (21, 30)
        else:
            horario = (20, 0)
        data_jogo = datetime(dia.year, dia.month, dia.day, horario[0], horario[1])
        calendario.append({"rodada": idx, "competicao": competicao_id, "data": data_jogo, "partidas": rodada})
    return calendario


def gerar_rodadas_paulistao(clubes):
    rodadas = _gerar_rodadas_turno_simples(clubes)
    return rodadas[:8]


def gerar_calendario_paulistao(clubes):
    janela = JANELAS_CALENDARIO_2026["paulistao_a1"]
    inicio = datetime.combine(janela["inicio"], datetime.min.time()).replace(hour=16)
    cursor = inicio
    rodadas = gerar_rodadas_paulistao(clubes)
    calendario = []
    for idx, rodada in enumerate(rodadas, start=1):
        dia_semana, horario = (6, (16, 0)) if idx % 2 else (2, (21, 30))  # domingo/quarta
        cursor = _proxima_data_valida(cursor, dia_semana, considerar_fifa=False)
        data_jogo = datetime(cursor.year, cursor.month, cursor.day, horario[0], horario[1])
        calendario.append({"rodada": idx, "competicao": "paulistao_a1", "data": data_jogo, "partidas": rodada, "fase": "grupo"})
        cursor += timedelta(days=3)

    cursor = _proxima_data_valida(cursor, 6, considerar_fifa=False)
    data_jogo = datetime(cursor.year, cursor.month, cursor.day, 16, 0)
    calendario.append({"competicao": "paulistao_a1", "data": data_jogo, "fase": "quartas"})
    cursor += timedelta(days=3)

    cursor = _proxima_data_valida(cursor, 2, considerar_fifa=False)
    data_jogo = datetime(cursor.year, cursor.month, cursor.day, 21, 30)
    calendario.append({"competicao": "paulistao_a1", "data": data_jogo, "fase": "semis"})
    cursor += timedelta(days=3)

    cursor = _proxima_data_valida(cursor, 6, considerar_fifa=False)
    data_jogo = datetime(cursor.year, cursor.month, cursor.day, 16, 0)
    calendario.append({"competicao": "paulistao_a1", "data": data_jogo, "fase": "final_ida"})
    cursor += timedelta(days=7)

    cursor = _proxima_data_valida(cursor, 6, considerar_fifa=False)
    data_jogo = datetime(cursor.year, cursor.month, cursor.day, 16, 0)
    calendario.append({"competicao": "paulistao_a1", "data": data_jogo, "fase": "final_volta"})

    return calendario
