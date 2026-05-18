from __future__ import annotations

import random
from datetime import timedelta

from engine import noticias

NATIONAL_COMP_IDS = ("bra_a", "bra_b", "bra_c", "bra_d")


def processar_triggers_diarios(temporada):
    if not temporada.clube_usuario:
        return
    _limpar_efeitos_expirados(temporada)
    _trigger_desempenho(temporada)
    _trigger_mercado(temporada)


def registrar_resultado_partida(temporada, competicao, casa, fora, gols_casa, gols_fora):
    _atualizar_streak(temporada, casa, fora, gols_casa, gols_fora)
    _trigger_reputacao_pos_jogo(temporada, competicao, casa, fora, gols_casa, gols_fora)


def _meta_state(temporada):
    meta = temporada.estado_mundo.setdefault("meta", {})
    return meta.setdefault(
        "triggers_state",
        {"streak_sem_derrota": {}, "cooldowns": {}},
    )


def _cooldown_ok(temporada, chave, dias_intervalo):
    state = _meta_state(temporada)
    cooldowns = state.setdefault("cooldowns", {})
    hoje = temporada.data_atual
    ultimo = cooldowns.get(chave)
    if not ultimo:
        return True
    try:
        from datetime import date

        ultima_data = date.fromisoformat(ultimo)
    except Exception:
        return True
    return (hoje - ultima_data).days >= dias_intervalo


def _marcar_cooldown(temporada, chave):
    state = _meta_state(temporada)
    state.setdefault("cooldowns", {})[chave] = temporada.data_atual.isoformat()


def _adicionar_efeito_moral(temporada, clube, valor, dias_validade, origem):
    meta = temporada.estado_mundo.setdefault("meta", {})
    efeitos = meta.setdefault("efeitos_ativos", [])
    efeitos.append(
        {
            "clube_id": clube.id,
            "tipo": "moral_proxima_partida",
            "valor": float(valor),
            "expira_em": (temporada.data_atual + timedelta(days=dias_validade)).isoformat(),
            "origem": origem,
        }
    )


def _limpar_efeitos_expirados(temporada):
    meta = temporada.estado_mundo.setdefault("meta", {})
    efeitos = meta.setdefault("efeitos_ativos", [])
    hoje = temporada.data_atual
    validos = []
    for efeito in efeitos:
        try:
            from datetime import date

            expira = date.fromisoformat(efeito.get("expira_em", hoje.isoformat()))
        except Exception:
            expira = hoje
        if expira >= hoje:
            validos.append(efeito)
    meta["efeitos_ativos"] = validos


def _atualizar_streak(temporada, casa, fora, gols_casa, gols_fora):
    state = _meta_state(temporada)
    streak = state.setdefault("streak_sem_derrota", {})
    cid_casa = casa.id
    cid_fora = fora.id
    if gols_casa > gols_fora:
        streak[cid_casa] = int(streak.get(cid_casa, 0)) + 1
        streak[cid_fora] = 0
    elif gols_fora > gols_casa:
        streak[cid_fora] = int(streak.get(cid_fora, 0)) + 1
        streak[cid_casa] = 0
    else:
        streak[cid_casa] = int(streak.get(cid_casa, 0)) + 1
        streak[cid_fora] = int(streak.get(cid_fora, 0)) + 1


def _trigger_desempenho(temporada):
    clube = temporada.clube_usuario
    state = _meta_state(temporada)
    streak = int(state.setdefault("streak_sem_derrota", {}).get(clube.id, 0))
    if streak < 5:
        return
    milestone = 5 if streak < 8 else 8 if streak < 12 else 12
    chave = f"desempenho_{clube.id}_{milestone}"
    if not _cooldown_ok(temporada, chave, 10):
        return
    titulo = f"{clube.nome} embala e nao perde ha {streak} jogos"
    corpo = "A torcida comeca a sonhar alto com a campanha e o elenco ganha confianca."
    noticias.registrar_noticia(
        temporada.estado_mundo["meta"]["temporada_atual"],
        rodada=getattr(temporada, "rodada_atual", None),
        tipo="trigger_desempenho",
        prioridade=2,
        titulo=titulo,
        corpo=corpo,
    )
    _adicionar_efeito_moral(temporada, clube, valor=0.65, dias_validade=20, origem=titulo)
    _marcar_cooldown(temporada, chave)


def _trigger_mercado(temporada):
    clube = temporada.clube_usuario
    chave = f"mercado_{clube.id}"
    if not _cooldown_ok(temporada, chave, 7):
        return
    elenco = [j for j in clube.elenco if j.idade <= 27]
    if not elenco:
        return
    if random.random() > 0.2:
        return
    alvo = random.choice(elenco)
    rivais = [
        c
        for c in temporada.todos_clubes.values()
        if c.id != clube.id and any(comp in NATIONAL_COMP_IDS for comp in c.competicoes)
    ]
    if not rivais:
        return
    interessado = random.choice(rivais)
    titulo = f"{interessado.nome} monitora {alvo.nome} de {clube.nome}"
    corpo = (
        f"O mercado aquece com rumores de proposta pelo atleta {alvo.posicao} ({alvo.overall} OVR). "
        "A diretoria acompanha a movimentacao."
    )
    noticias.registrar_noticia(
        temporada.estado_mundo["meta"]["temporada_atual"],
        rodada=getattr(temporada, "rodada_atual", None),
        tipo="trigger_mercado",
        prioridade=1,
        titulo=titulo,
        corpo=corpo,
    )
    _marcar_cooldown(temporada, chave)


def _trigger_reputacao_pos_jogo(temporada, competicao, casa, fora, gols_casa, gols_fora):
    if competicao != "copa_brasil":
        return
    clube = temporada.clube_usuario
    if not clube:
        return

    vencedor = None
    perdedor = None
    if gols_casa > gols_fora:
        vencedor, perdedor = casa, fora
    elif gols_fora > gols_casa:
        vencedor, perdedor = fora, casa
    if not vencedor or vencedor.id != clube.id:
        return

    gap_tier = getattr(perdedor, "reputacao_tier", 0) - getattr(vencedor, "reputacao_tier", 0)
    if gap_tier < 2:
        return

    chave = f"reputacao_cdb_{clube.id}_{temporada.rodada_atual}"
    if not _cooldown_ok(temporada, chave, 3):
        return

    ganho_pp = int(250 + 90 * gap_tier)
    vencedor.prestigio_acumulado += ganho_pp
    vencedor.sincronizar_reputacao_por_prestigio()
    titulo = f"Apos bater {perdedor.nome}, prestigio de {vencedor.nome} cresce no pais"
    corpo = (
        f"O impacto da classificacao elevou o prestígio nacional do clube em {ganho_pp} pontos de prestigio."
    )
    noticias.registrar_noticia(
        temporada.estado_mundo["meta"]["temporada_atual"],
        rodada=getattr(temporada, "rodada_atual", None),
        tipo="trigger_reputacao",
        prioridade=3,
        titulo=titulo,
        corpo=corpo,
    )
    _adicionar_efeito_moral(temporada, vencedor, valor=0.5, dias_validade=12, origem=titulo)
    _marcar_cooldown(temporada, chave)
