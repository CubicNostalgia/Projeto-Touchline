import random

OBJETIVOS_TEMPORADA_BASE = [
    "Acesso Direto: Terminar dentro da zona de promocao automatica.",
    "Solidez na Elite: Garantir permanencia sem depender da ultima rodada.",
    "Equilibrio Salarial: Reduzir a folha em 15% ate dezembro.",
    "Projeto Prata da Casa: Integrar 3 jogadores da base ao elenco principal.",
    "Soberania Regional: Melhor campanha entre os clubes do interior.",
    "Meta de Arrecadacao: Alcancar fase-alvo da Copa do Brasil.",
    "Valorizacao de Ativos: Elevar valor de mercado total do elenco em 20%.",
    "Reestruturacao Etaria: Baixar media de idade dos titulares abaixo de 27.",
    "Efetividade em Casa: Aproveitamento superior a 65% no estadio.",
    "Blindagem Defensiva: Sofrer menos de 1 gol por jogo na liga.",
    "Reducao de Encargos: Nao estourar o orcamento anual de emergencias.",
    "Fidelizacao Tatica: Manter padrao tatico com consistencia de posse.",
    "Recuperacao de Prestigio: Subir 5 posicoes no ranking nacional.",
    "Garantia de Calendario: Classificar para competicao nacional no ano seguinte.",
    "Limpeza de Excedentes: Negociar jogadores sem uso no ultimo semestre.",
    "Preparo Fisico de Elite: Reduzir lesoes musculares vs ano anterior.",
    "Aproveitamento de Janela: Reforcar apenas posicoes carentes do elenco.",
    "Paz com a Torcida: Manter aprovacao da diretoria acima de 70%.",
    "Dominio de Classicos: Encerrar ano com saldo positivo em duelos diretos.",
    "Consistencia de Resultados: Evitar sequencias de 4 derrotas na liga.",
]

OBJETIVOS_SEMANA_BASE = [
    "Dever de Casa: Vencer adversario abaixo na tabela.",
    "Jogo de Seis Pontos: Nao perder confronto direto por vaga.",
    "Segunda Unidade: Dar ritmo aos reservas em jogo de menor pressao.",
    "Gestao de Energia: Rodar elenco para jogo-chave.",
    "Foco Defensivo: Meta de nao sofrer gols na rodada.",
    "Ajuste de Pontaria: Melhorar conversao ofensiva da semana.",
    "Controle de Nervos: Evitar expulsao em jogo de alta tensao.",
    "Estudo de Campo: Anular principal ponto forte do rival.",
    "Recuperacao de Moral: Vencer apos eliminacao dolorosa.",
    "Aproveitamento da Base: Relacionar jovens para ganhar experiencia.",
    "Estabilidade de Elenco: Resolver ruido de renovacao.",
    "Blindagem de Vestiario: Preservar harmonia apos critica pesada.",
    "Plano de Viagem: Reduzir desgaste em rodada fora.",
    "Efetividade em Bola Parada: Marcar ou nao sofrer em bola parada.",
    "Manutencao de Ritmo: Evitar queda intensa no segundo tempo.",
    "Infiltracao: Criar mais chances por dentro.",
    "Exploracao de Pontas: Forcar superioridade pelos lados.",
    "Saida de Bola: Reduzir erros de passe no terco defensivo.",
    "Pressao Alta: Forcar erro rival na propria saida.",
    "Marcacao Individual: Neutralizar articulador adversario.",
    "Postura Visitante: Contra-atacar com eficiencia fora de casa.",
    "Tempo de Reacao: Nao sofrer gol apos abrir placar.",
    "Preservacao de Titulares: Gerir pendurados antes de classico.",
    "Integracao de Reforco: Dar minutos ao novo contratado.",
    "Lideranca em Campo: Reforcar comando dos experientes.",
]


def _expandir_objetivos(base, total, prefixo):
    objetivos = list(base)
    idx = 1
    while len(objetivos) < total:
        molde = base[(idx - 1) % len(base)]
        objetivos.append(f"{prefixo} {idx}: {molde}")
        idx += 1
    return objetivos[:total]


CATALOGO_OBJ_TEMPORADA = _expandir_objetivos(OBJETIVOS_TEMPORADA_BASE, 70, "Plano")
CATALOGO_OBJ_SEMANA = _expandir_objetivos(OBJETIVOS_SEMANA_BASE, 110, "Ritmo")


def _folha_salarial(clube):
    return sum(int(getattr(j, "salario", 0) or 0) for j in clube.elenco)


def gerar_objetivos_por_clube(clube):
    objetivos = []
    comps = set(clube.competicoes)

    if "paulistao_a1" in comps:
        if clube.forca >= 75 or clube.reputacao_tier >= 9:
            objetivos.append({"id": "paulistao_semifinal", "texto": "Alcancar a semifinal do Paulistao A1", "tier": "longo"})
        else:
            objetivos.append({"id": "paulistao_quartas", "texto": "Alcancar as quartas do Paulistao A1", "tier": "longo"})

    if "paulistao_a2" in comps:
        if clube.forca >= 62 or clube.reputacao_tier >= 6:
            objetivos.append({"id": "paulistao_a2_acesso", "texto": "Conquistar o acesso no Paulistao A2", "tier": "longo"})
        else:
            objetivos.append({"id": "paulistao_a2_top4", "texto": "Chegar ao top-4 do Paulistao A2", "tier": "longo"})

    if "cariocao_a1" in comps:
        if clube.forca >= 74 or clube.reputacao_tier >= 8:
            objetivos.append({"id": "cariocao_semis", "texto": "Alcancar as semifinais do Cariocao", "tier": "longo"})
        else:
            objetivos.append({"id": "cariocao_quartas", "texto": "Alcancar as quartas do Cariocao", "tier": "longo"})

    if "bra_a" in comps:
        meta = "Terminar no top-8 da Serie A" if clube.reputacao_tier >= 9 else "Terminar no top-12 da Serie A"
        objetivos.append({"id": "liga_top", "texto": meta, "tier": "longo"})
    elif "bra_b" in comps:
        meta = "Disputar acesso (top-6 da Serie B)" if clube.reputacao_tier >= 5 else "Terminar no top-10 da Serie B"
        objetivos.append({"id": "liga_top", "texto": meta, "tier": "longo"})

    if any(c in comps for c in ("bra_a", "bra_b", "bra_c", "bra_d")):
        if clube.reputacao_tier >= 9:
            objetivos.append({"id": "copa_brasil_fase5", "texto": "Chegar a 5a fase da Copa do Brasil", "tier": "longo"})
        else:
            objetivos.append({"id": "copa_brasil_fase3", "texto": "Chegar a 3a fase da Copa do Brasil", "tier": "longo"})

    limite_folha = int(_folha_salarial(clube) * 1.08)
    objetivos.append(
        {
            "id": "financeiro_folha",
            "texto": f"Curto prazo (mensal): manter folha salarial abaixo de R$ {limite_folha:,}".replace(",", "."),
            "tier": "curto",
            "limite": limite_folha,
        }
    )
    objetivos.append(
        {
            "id": "base_revelar_70",
            "texto": "Longo prazo (temporada): revelar jogador da base com OVR 70+",
            "tier": "longo",
        }
    )
    objetivos.append({"id": "base", "texto": "Utilizar pelo menos 3 jogadores da Academia de Base", "tier": "longo"})
    return objetivos


def gerar_catalogo_objetivos():
    return {
        "temporada": list(CATALOGO_OBJ_TEMPORADA),
        "semanais": list(CATALOGO_OBJ_SEMANA),
    }


def selecionar_objetivos_semanais(clube, quantidade=5):
    seed = hash((clube.id, clube.reputacao_tier, len(clube.elenco)))
    rng = random.Random(seed)
    amostra = list(CATALOGO_OBJ_SEMANA)
    rng.shuffle(amostra)
    return amostra[: max(1, quantidade)]


def mensagem_boas_vindas_objetivos(clube, objetivos):
    print(f"\nA diretoria lhe da as boas-vindas ao {clube.nome}!")
    print("Seus objetivos para esta gestao:")
    for objetivo in objetivos:
        tag = "[Mensal]" if objetivo.get("tier") == "curto" else "[Temporada]"
        print(f"- {tag} {objetivo['texto']}")


def mensagem_resultado_objetivos(resultados):
    print("\nBalanco de objetivos da diretoria")
    for item in resultados:
        status = "[OK]" if item["cumprido"] else "[X]"
        print(f"{status} {item['texto']}")
