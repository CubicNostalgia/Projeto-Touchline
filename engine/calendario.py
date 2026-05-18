import random
from datetime import datetime, date, timedelta
from data.database import (
    DATAS_FIFA_2026,
    PAUSAS_TORNEIOS_2026,
    JANELAS_CALENDARIO_2026,
    SERIE_D_FORMATO,
    COPA_BRASIL_CALENDARIO_2026,
)


ANO_BASE_CALENDARIO = 2026


def _data_no_ano(data_base: date, temporada_ano: int):
    return date(temporada_ano, data_base.month, data_base.day)


def _intervalo_no_ano(inicio: date, fim: date, temporada_ano: int):
    return _data_no_ano(inicio, temporada_ano), _data_no_ano(fim, temporada_ano)


def _datas_fifa(temporada_ano: int):
    return [_intervalo_no_ano(inicio, fim, temporada_ano) for inicio, fim in DATAS_FIFA_2026]


def _pausas_torneios(temporada_ano: int):
    pausas = []
    for pausa in PAUSAS_TORNEIOS_2026:
        inicio, fim = _intervalo_no_ano(pausa["inicio"], pausa["fim"], temporada_ano)
        pausas.append({"nome": pausa.get("nome", "Pausa"), "inicio": inicio, "fim": fim})
    return pausas


def _janelas_calendario(temporada_ano: int):
    janelas = {}
    for comp_id, janela in JANELAS_CALENDARIO_2026.items():
        inicio, fim = _intervalo_no_ano(janela["inicio"], janela["fim"], temporada_ano)
        janelas[comp_id] = {"inicio": inicio, "fim": fim}
    return janelas


def _copa_brasil_calendario(temporada_ano: int):
    return [(fase, _data_no_ano(data_base, temporada_ano)) for fase, data_base in COPA_BRASIL_CALENDARIO_2026]


def _data_bloqueada(dia: date, considerar_fifa=True):
    temporada_ano = dia.year
    datas_fifa = _datas_fifa(temporada_ano)
    pausas = _pausas_torneios(temporada_ano)
    if considerar_fifa:
        for inicio, fim in datas_fifa:
            if inicio <= dia <= fim:
                return True
    for pausa in pausas:
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


def _alocar_datas(quantidade_rodadas, inicio: date, fim: date):
    datas = []
    datas.extend(_datas_disponiveis(inicio, fim, [5, 2], considerar_fifa=False))  # sÃ¡bado e quarta
    if len(datas) < quantidade_rodadas:
        extras = _datas_disponiveis(inicio, fim, [6], considerar_fifa=False)  # domingo
        datas.extend([d for d in extras if d not in datas])
    if len(datas) < quantidade_rodadas:
        extras = _datas_disponiveis(inicio, fim, [1, 3, 4], considerar_fifa=False)  # ter/qui/sex
        datas.extend([d for d in extras if d not in datas])
    datas = sorted(datas)[:quantidade_rodadas]
    return datas


def _distribuir_datas_no_intervalo(candidatas, quantidade, inicio, fim):
    if quantidade <= 0:
        return []
    candidatas = sorted(set(candidatas))
    if not candidatas:
        return []
    if quantidade == 1:
        return [candidatas[0]]

    span = max(1, (fim - inicio).days)
    selecionadas = []
    ultimo = None
    cursor = 0
    for i in range(quantidade):
        alvo = inicio + timedelta(days=round((span * i) / (quantidade - 1)))
        escolha = None
        for idx in range(cursor, len(candidatas)):
            candidato = candidatas[idx]
            if ultimo and candidato <= ultimo:
                continue
            if candidato >= alvo:
                escolha = candidato
                cursor = idx + 1
                break
        if escolha is None:
            for idx in range(cursor, len(candidatas)):
                candidato = candidatas[idx]
                if not ultimo or candidato > ultimo:
                    escolha = candidato
                    cursor = idx + 1
                    break
        if escolha is None:
            break
        selecionadas.append(escolha)
        ultimo = escolha
    return selecionadas


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


def gerar_calendario_brasileirao(clubes, competicao_id, inicio_override=None, temporada_ano=ANO_BASE_CALENDARIO):
    janela = _janelas_calendario(temporada_ano)[competicao_id]
    inicio_base = inicio_override or janela["inicio"]
    fim = janela["fim"]
    rodadas = _gerar_rodadas_pontos_corridos(clubes)

    candidatas = []
    candidatas.extend(_datas_disponiveis(inicio_base, fim, [5, 6], considerar_fifa=False))  # sabado/domingo
    candidatas.extend(_datas_disponiveis(inicio_base, fim, [2, 3], considerar_fifa=False))  # quarta/quinta
    candidatas.extend(_datas_disponiveis(inicio_base, fim, [1, 4], considerar_fifa=False))  # terca/sexta
    datas = _distribuir_datas_no_intervalo(candidatas, len(rodadas), inicio_base, fim)

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


def gerar_calendario_paulistao(clubes, temporada_ano=ANO_BASE_CALENDARIO):
    janela = _janelas_calendario(temporada_ano)["paulistao_a1"]
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


def gerar_calendario_paulistao_a2(clubes, temporada_ano=ANO_BASE_CALENDARIO):
    janela = _janelas_calendario(temporada_ano)["paulistao_a2"]
    rodadas = _gerar_rodadas_turno_simples(clubes)
    datas = _alocar_datas(len(rodadas), janela["inicio"], janela["fim"])
    calendario = []
    for idx, rodada in enumerate(rodadas, start=1):
        dia = datas[idx - 1]
        data_jogo = datetime(dia.year, dia.month, dia.day, 16, 0)
        calendario.append(
            {
                "rodada": idx,
                "competicao": "paulistao_a2",
                "data": data_jogo,
                "partidas": rodada,
                "fase": "grupo",
            }
        )
    ultima_data = calendario[-1]["data"] if calendario else datetime.combine(janela["inicio"], datetime.min.time())
    calendario.append(
        {
            "competicao": "paulistao_a2",
            "data": ultima_data + timedelta(days=7),
            "fase": "paulistao_a2_quadrangulares",
        }
    )
    return calendario


def _gerar_rodadas_cruzadas(grupo_a, grupo_b):
    grupo_a = grupo_a[:]
    grupo_b = grupo_b[:]
    random.shuffle(grupo_a)
    random.shuffle(grupo_b)
    rodadas = []
    for _ in range(len(grupo_a)):
        rodada = []
        for i in range(len(grupo_a)):
            casa = grupo_a[i]
            fora = grupo_b[i]
            rodada.append((casa, fora))
        rodadas.append(rodada)
        grupo_b = [grupo_b[-1]] + grupo_b[:-1]
    return rodadas


def gerar_calendario_cariocao(grupo_a, grupo_b, temporada_ano=ANO_BASE_CALENDARIO):
    janela = _janelas_calendario(temporada_ano)["cariocao_a1"]
    rodadas = _gerar_rodadas_cruzadas(grupo_a, grupo_b)
    datas = _alocar_datas(len(rodadas), janela["inicio"], janela["fim"])

    calendario = []
    for idx, rodada in enumerate(rodadas, start=1):
        dia = datas[idx - 1]
        data_jogo = datetime(dia.year, dia.month, dia.day, 16, 0)
        calendario.append(
            {
                "rodada": idx,
                "competicao": "cariocao_a1",
                "data": data_jogo,
                "partidas": rodada,
                "fase": "grupo",
            }
        )

    ultima_data = calendario[-1]["data"] if calendario else datetime.combine(janela["inicio"], datetime.min.time())
    calendario.append(
        {
            "competicao": "cariocao_a1",
            "data": ultima_data + timedelta(days=7),
            "fase": "cariocao_quartas",
        }
    )
    return calendario


def gerar_calendario_copa_brasil(temporada_ano=ANO_BASE_CALENDARIO):
    calendario = []
    datas_copa = _copa_brasil_calendario(temporada_ano)
    cursor = datetime.combine(datas_copa[0][1], datetime.min.time())
    for fase, data_base in datas_copa:
        cursor = datetime.combine(data_base, datetime.min.time())
        cursor = _proxima_data_valida(cursor, cursor.weekday(), considerar_fifa=True)
        data_jogo = datetime(cursor.year, cursor.month, cursor.day, 21, 30)
        calendario.append({"competicao": "copa_brasil", "data": data_jogo, "fase": f"cdb_{fase}"})
    return calendario


def gerar_calendario_serie_c(clubes, temporada_ano):
    janela = _janelas_calendario(temporada_ano)["bra_c"]
    inicio = janela["inicio"]
    fim = janela["fim"]
    rodadas = _gerar_rodadas_turno_simples(clubes)
    datas = _alocar_datas(len(rodadas), inicio, fim)

    calendario = []
    for idx, rodada in enumerate(rodadas, start=1):
        dia = datas[idx - 1]
        data_jogo = datetime(dia.year, dia.month, dia.day, 20, 0)
        calendario.append({"rodada": idx, "competicao": "bra_c_fase1", "data": data_jogo, "partidas": rodada})

    ultima_data = calendario[-1]["data"] if calendario else datetime.combine(inicio, datetime.min.time())
    calendario.append(
        {
            "competicao": "bra_c",
            "data": ultima_data + timedelta(days=7),
            "fase": "serie_c_grupos",
        }
    )
    return calendario


def gerar_calendario_serie_d(clubes, temporada_ano):
    janela = _janelas_calendario(temporada_ano)["bra_d"]
    inicio = janela["inicio"]
    fim = janela["fim"]
    grupos = SERIE_D_FORMATO["grupos"]
    times_por_grupo = SERIE_D_FORMATO["times_por_grupo"]

    clubes = clubes[:]
    random.shuffle(clubes)
    grupos_lista = [[] for _ in range(grupos)]
    for i, clube in enumerate(clubes):
        grupos_lista[i % grupos].append(clube)

    calendario = []
    for idx_grupo, clubes_grupo in enumerate(grupos_lista, start=1):
        if not clubes_grupo:
            continue
        rodadas = _gerar_rodadas_pontos_corridos(clubes_grupo)
        datas = _alocar_datas(len(rodadas), inicio, fim)
        for idx_rodada, rodada in enumerate(rodadas, start=1):
            dia = datas[idx_rodada - 1]
            data_jogo = datetime(dia.year, dia.month, dia.day, 16, 0)
            calendario.append(
                {
                    "rodada": idx_rodada,
                    "competicao": f"bra_d_g{idx_grupo:02d}",
                    "data": data_jogo,
                    "partidas": rodada,
                }
            )

    ultima_data = calendario[-1]["data"] if calendario else datetime.combine(inicio, datetime.min.time())
    calendario.append(
        {
            "competicao": "bra_d",
            "data": ultima_data + timedelta(days=7),
            "fase": "serie_d_mata_mata",
        }
    )
    return calendario
