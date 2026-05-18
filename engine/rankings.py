from collections import defaultdict


PONTOS_DIVISAO_BASE = {
    "bra_a": 1000,
    "bra_b": 700,
    "bra_c": 500,
    "bra_d": 300,
}

PONTOS_LIGA_FATOR = {
    "bra_a": 12,
    "bra_b": 10,
    "bra_c": 8,
    "bra_d": 6,
}

PONTOS_COPA_FASE = {
    "f1": 20,
    "f2": 40,
    "f3": 60,
    "f4": 80,
    "f5": 110,
    "f6": 140,
    "f7": 180,
    "f8": 210,
    "final": 240,
    "campeao": 80,
}


def grupo_copa_brasil(clube):
    if "bra_a" in clube.competicoes:
        return "I"
    if "bra_b" in clube.competicoes:
        return "II"
    return "III"


def _divisao_principal(clube):
    for comp in ("bra_a", "bra_b", "bra_c", "bra_d"):
        if comp in clube.competicoes:
            return comp
    return None


def calcular_pontos_temporada(clubes, classificacoes=None, copa_estado=None):
    pontos = {}
    classificacoes = classificacoes or {}
    copa_estado = copa_estado or {}
    fase_por_clube = copa_estado.get("fase_por_clube", {})
    campeao_copa = copa_estado.get("campeao_id")

    for clube in clubes:
        total = 0
        comp = _divisao_principal(clube)
        if comp:
            total += PONTOS_DIVISAO_BASE.get(comp, 0)

        if comp in classificacoes:
            classif = classificacoes[comp]
            total_times = len(classif)
            pos = next((i for i, (c, _) in enumerate(classif, start=1) if c.id == clube.id), None)
            if pos:
                fator = PONTOS_LIGA_FATOR.get(comp, 6)
                total += max(1, total_times - pos + 1) * fator

        fase = fase_por_clube.get(clube.id)
        if fase in PONTOS_COPA_FASE:
            total += PONTOS_COPA_FASE[fase]
        if campeao_copa and clube.id == campeao_copa:
            total += PONTOS_COPA_FASE.get("campeao", 0)

        pontos[clube.id] = total
    return pontos


def atualizar_historico_rnc(historico, ano, pontos_ano):
    historico = historico or {}
    historico[str(ano)] = pontos_ano
    # limita a 6 anos para nao crescer indefinidamente
    anos = sorted(historico.keys(), reverse=True)
    for ano_remover in anos[6:]:
        historico.pop(ano_remover, None)
    return historico


def calcular_rnc_atual(historico, ano_atual):
    pesos = {
        str(ano_atual): 5,
        str(ano_atual - 1): 4,
        str(ano_atual - 2): 3,
        str(ano_atual - 3): 2,
        str(ano_atual - 4): 1,
    }
    rnc = defaultdict(int)
    for ano, pontos in (historico or {}).items():
        peso = pesos.get(str(ano))
        if not peso:
            continue
        for clube_id, valor in pontos.items():
            rnc[clube_id] += int(valor) * peso
    return dict(rnc)


def ordenar_clubes_por_rnc(clubes, rnc_pontos=None):
    rnc_pontos = rnc_pontos or {}

    def chave(clube):
        return (rnc_pontos.get(clube.id, 0), clube.reputacao_tier, clube.reputacao)

    return sorted(clubes, key=chave, reverse=True)


def aplicar_rnc_em_clubes(clubes_ordenados, rnc_pontos=None):
    rnc_pontos = rnc_pontos or {}
    total = len(clubes_ordenados)
    for idx, clube in enumerate(clubes_ordenados, start=1):
        clube.rnc_rank = idx
        clube.rnc_pontos = int(rnc_pontos.get(clube.id, 0))
        # bonus de tier por ranking
        if idx <= 10:
            clube.rnc_bonus_tier = 2
        elif idx <= 30:
            clube.rnc_bonus_tier = 1
        else:
            clube.rnc_bonus_tier = 0
        # multiplicador de patrocinio baseado em percentil
        if total > 1:
            perc = 1 - ((idx - 1) / (total - 1))
        else:
            perc = 1.0
        clube.multiplicador_patrocinio = round(0.7 + (perc * 0.6), 2)
    return clubes_ordenados


def calcular_rnf(rnc_pontos, clubes):
    rnf = defaultdict(int)
    for clube in clubes:
        estado = getattr(clube, "estado_federacao", "OUT")
        rnf[estado] += int(rnc_pontos.get(clube.id, 0))
    return dict(rnf)
