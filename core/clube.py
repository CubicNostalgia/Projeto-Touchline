import random

from core.jogador import Jogador
from utils.gerador_jogadores import gerar_newgen_base

FORMACOES = {
    "4-3-3": {"GOL": 1, "LD": 1, "ZAG": 2, "LE": 1, "VOL": 1, "MC": 2, "PE": 1, "PD": 1, "ATA": 1},
    "4-4-2": {"GOL": 1, "LD": 1, "ZAG": 2, "LE": 1, "VOL": 2, "MC": 2, "ATA": 2},
    "3-5-2": {"GOL": 1, "ZAG": 3, "VOL": 2, "MC": 2, "PE": 1, "PD": 1, "ATA": 2},
    "3-3-2-2": {"GOL": 1, "ZAG": 3, "VOL": 1, "MC": 2, "MEI": 2, "ATA": 2},
    "5-4-1": {"GOL": 1, "LD": 1, "ZAG": 3, "LE": 1, "VOL": 2, "MC": 2, "ATA": 1},
    "4-1-4-1": {"GOL": 1, "LD": 1, "ZAG": 2, "LE": 1, "VOL": 1, "MC": 2, "PE": 1, "PD": 1, "ATA": 1},
    "3-2-3-2": {"GOL": 1, "ZAG": 3, "VOL": 2, "MC": 1, "MEI": 2, "ATA": 2},
    "4-2-4": {"GOL": 1, "LD": 1, "ZAG": 2, "LE": 1, "VOL": 2, "PE": 1, "PD": 1, "ATA": 2},
}

TIER_CATEGORIAS = {
    "Regional": range(1, 4),
    "Emergente": range(4, 7),
    "Nacional": range(7, 10),
    "Gigante": range(10, 13),
    "Global": range(13, 16),
}

POSICOES_BASE = ["GOL", "LD", "ZAG", "LE", "VOL", "MC", "MEI", "PD", "PE", "ATA"]


class Clube:
    def __init__(self, id, nome, elenco, reputacao=50, competicoes=None, dados_iniciais=None):
        dados_iniciais = dados_iniciais or {}
        self.id = id
        self.nome = nome
        self.elenco = elenco
        self.competicoes = competicoes or []

        self.reputacao = dados_iniciais.get("reputacao", reputacao)
        self.reputacao_tier = dados_iniciais.get("reputacao_tier", max(1, min(15, int(self.reputacao / 7))))
        self.prestigio_acumulado = dados_iniciais.get(
            "prestigio_acumulado",
            self.alvo_pp_tier(self.reputacao_tier),
        )
        self.sincronizar_reputacao_por_prestigio()

        self.financas = dados_iniciais.get("financas", 1_000_000)
        self.infraestrutura = self._normalizar_infraestrutura(dados_iniciais.get("infraestrutura"))
        self.base_jovens = self._carregar_base(dados_iniciais.get("base_jovens", []))
        self.torcida_expectativa = dados_iniciais.get("torcida_expectativa", 50)
        self.job_security = dados_iniciais.get(
            "job_security",
            {"risco": "estavel", "demissao_imediata": False, "objetivo": "Manter estabilidade"},
        )
        self.status_financeiro = dados_iniciais.get("status_financeiro", "estavel")

        self.formacao = "4-3-3"
        self.titulares_customizados = None

    @property
    def forca(self):
        return round(self.calcular_forca_atual(self.escalar_titulares()), 1)

    @staticmethod
    def alvo_pp_tier(tier):
        return int(100 * (tier ** 2.5))

    @staticmethod
    def decaimento_percentual_tier(tier):
        return 15 / (tier ** 1.2)

    @property
    def categoria_tier(self):
        for categoria, faixa in TIER_CATEGORIAS.items():
            if self.reputacao_tier in faixa:
                return categoria
        return "Regional"

    @property
    def nivel_ct(self):
        return self.infraestrutura.get("ct", 0)

    @property
    def nivel_base(self):
        return self.infraestrutura.get("base", 0)

    @property
    def nivel_estadio(self):
        return self.infraestrutura.get("estadio_nivel", 0)

    @property
    def capacidade_estadio(self):
        return self.infraestrutura.get("estadio_capacidade", 5000)

    def _clamp_nivel(self, valor):
        return max(0, min(30, int(valor)))

    def _clamp_capacidade(self, valor):
        return max(500, min(80_000, int(valor)))

    def _nivel_padrao_ct(self):
        return max(0, min(30, int(4 + self.reputacao_tier * 1.4)))

    def _nivel_padrao_base(self):
        return max(0, min(30, int(2 + self.reputacao_tier * 1.2)))

    def _nivel_padrao_estadio(self):
        return max(0, min(30, int(3 + self.reputacao_tier * 1.5)))

    def _capacidade_padrao_estadio(self):
        return self._clamp_capacidade(5_000 + (self.reputacao_tier - 1) * 5_500)

    def _normalizar_infraestrutura(self, infraestrutura):
        infra = dict(infraestrutura or {})
        estadio = infra.get("estadio")
        if isinstance(estadio, dict):
            infra.setdefault("estadio_nivel", estadio.get("nivel"))
            infra.setdefault("estadio_capacidade", estadio.get("capacidade"))

        ct = infra.get("ct", self._nivel_padrao_ct())
        base = infra.get("base", self._nivel_padrao_base())
        estadio_nivel = infra.get("estadio_nivel", self._nivel_padrao_estadio())
        estadio_capacidade = infra.get("estadio_capacidade", self._capacidade_padrao_estadio())

        return {
            "ct": self._clamp_nivel(ct),
            "base": self._clamp_nivel(base),
            "estadio_nivel": self._clamp_nivel(estadio_nivel),
            "estadio_capacidade": self._clamp_capacidade(estadio_capacidade),
        }

    def _carregar_base(self, base_serializada):
        base = []
        for item in base_serializada or []:
            if isinstance(item, Jogador):
                base.append(item)
            elif isinstance(item, dict):
                base.append(Jogador.from_dict(item))
        return base

    def sincronizar_reputacao_por_prestigio(self):
        tier = 1
        for nivel in range(1, 16):
            if self.prestigio_acumulado >= self.alvo_pp_tier(nivel):
                tier = nivel
            else:
                break
        self.reputacao_tier = max(1, min(15, tier))
        self.reputacao = min(100, max(1, int((self.reputacao_tier / 15) * 100)))

    def calcular_forca_atual(self, jogadores):
        if not jogadores:
            return 0
        media_elenco = sum(p.overall for p in jogadores) / len(jogadores)
        bonus_ct = self.nivel_ct * 0.8
        return media_elenco + bonus_ct

    def definir_formacao(self, formacao):
        if formacao in FORMACOES:
            self.formacao = formacao
            self.titulares_customizados = None

    def definir_titulares(self, indices_jogadores):
        if len(indices_jogadores) != 11:
            return False
        if len(set(indices_jogadores)) != 11:
            return False
        if not all(0 <= i < len(self.elenco) for i in indices_jogadores):
            return False

        self.titulares_customizados = [self.elenco[i] for i in indices_jogadores]
        return True

    def _melhores_da_posicao(self, posicao, qtd):
        jogadores = sorted(
            [j for j in self.elenco if j.posicao == posicao and getattr(j, "disponivel", True)],
            key=lambda j: j.over_match,
            reverse=True,
        )
        return jogadores[:qtd]

    def escalar_titulares(self):
        if self.titulares_customizados and len(self.titulares_customizados) == 11:
            return self.titulares_customizados

        titulares = []
        for pos, qtd in FORMACOES[self.formacao].items():
            titulares.extend(self._melhores_da_posicao(pos, qtd))

        if len(titulares) < 11:
            restantes = sorted(
                [j for j in self.elenco if j not in titulares],
                key=lambda j: j.over_match,
                reverse=True,
            )
            titulares.extend(restantes[: 11 - len(titulares)])
        return titulares[:11]

    def reservas(self):
        titulares = set(self.escalar_titulares())
        return [j for j in self.elenco if j not in titulares]

    def forca_titular(self):
        titulares = self.escalar_titulares()
        if not titulares:
            return 0
        return round(sum(j.over_match for j in titulares) / len(titulares), 1)

    def recuperacao_por_dia(self):
        return round(6 + (self.nivel_ct / 30) * 44, 1)

    def recuperar_elenco(self, dias_descanso=3):
        rec = self.recuperacao_por_dia()
        for jogador in self.elenco:
            jogador.recuperar_fadiga(dias_descanso, recuperacao_por_dia=rec)

    def risco_lesao_por_partida(self):
        risco = 0.15 - (self.nivel_ct / 30) * 0.12
        return max(0.03, round(risco, 3))

    def aplicar_partida(self):
        risco_lesao = self.risco_lesao_por_partida()
        for jogador in self.escalar_titulares():
            jogador.aplicar_fadiga(90)
            if random.random() < risco_lesao:
                dias = int(6 + (30 - self.nivel_ct) * 0.6 + random.randint(0, 6))
                jogador.aplicar_lesao(dias)

    def atualizar_desenvolvimento(self, resultado):
        ajuste = 0.6 if resultado == "V" else (-0.4 if resultado == "D" else 0.1)
        bonus_ct = (self.nivel_ct / 30) * 0.35
        for jogador in self.escalar_titulares():
            jogador.atualizar_forma(ajuste)
            jogador.evoluir(bonus_ct=bonus_ct)

    def media_por_posicao(self, apenas_titulares=False):
        base = self.escalar_titulares() if apenas_titulares else self.elenco
        medias = {}
        for pos in ["GOL", "LD", "ZAG", "LE", "VOL", "MC", "MEI", "PD", "PE", "ATA"]:
            jogadores = [j for j in base if j.posicao == pos]
            medias[pos] = round(sum(j.overall for j in jogadores) / len(jogadores), 1) if jogadores else 0
        return medias

    def calcular_pp_anual(self, titulos=0, elite_assiduo=False):
        media_ovr = sum(j.overall for j in self.elenco) / len(self.elenco)
        bonus_titulos = titulos * (320 + (self.reputacao_tier * 30))
        bonus_ovr = max(0, int((media_ovr - 58) * 18))
        bonus_infra = int(self.nivel_ct * 45 + self.nivel_base * 30 + self.nivel_estadio * 20)
        bonus_elite = 220 if elite_assiduo else 0
        return bonus_titulos + bonus_ovr + bonus_infra + bonus_elite

    def requisito_tier_por_ovr(self, ovr_jogador):
        return min(15, max(1, int((ovr_jogador - 45) / 3)))

    def pode_contratar_jogador(self, ovr_jogador):
        return self.reputacao_tier >= self.requisito_tier_por_ovr(ovr_jogador)

    def cota_tv_por_tier(self):
        piso = 500_000
        teto = 650_000_000
        frac = (self.reputacao_tier - 1) / 14
        return int(piso + (teto - piso) * (frac ** 1.45))

    def multiplicador_valor_mercado(self):
        return round(0.75 + (self.reputacao_tier / 15) * 1.75, 2)

    def calcular_valor_venda(self, valor_base):
        return int(valor_base * self.multiplicador_valor_mercado())

    def ticket_medio(self):
        return int(25 + (self.reputacao_tier * 4) + (self.nivel_estadio * 2))

    def capacidade_neutra(self, adversario_tier=None):
        adversario_tier = adversario_tier or 10
        base = 25_000 + (adversario_tier * 4_000)
        return self._clamp_capacidade(max(self.capacidade_estadio, base))

    def deve_vender_mando(self, adversario):
        if self.nivel_estadio > 5:
            return False
        if adversario.reputacao_tier < 10:
            return False
        receita_casa = self.calcular_bilheteria(
            capacidade_estadio=self.capacidade_estadio,
            vender_mando=False,
            adversario_tier=adversario.reputacao_tier,
        )
        receita_neutra = self.calcular_bilheteria(
            capacidade_estadio=self.capacidade_estadio,
            vender_mando=True,
            adversario_tier=adversario.reputacao_tier,
        )
        return receita_neutra > receita_casa * 1.15

    def bonus_casa(self, derby=False, vender_mando=False):
        if vender_mando:
            return 0.0
        base = 0.8 + (self.nivel_estadio / 30) * 3.2
        if derby:
            base *= 1.08
        return round(base, 2)

    def calcular_bilheteria(self, capacidade_estadio=None, fase_vitorias=0, derby=False, vender_mando=False, adversario_tier=None):
        capacidade = self.capacidade_estadio if capacidade_estadio is None else capacidade_estadio
        capacidade = self._clamp_capacidade(capacidade)
        base_torcida = int(2_500 + (self.reputacao_tier ** 1.7) * 1_700)
        bonus_fase = 1 + (min(fase_vitorias, 8) * 0.03)
        bonus_importancia = 1.2 if derby else 1.0
        ticket_medio = self.ticket_medio()

        if vender_mando:
            capacidade = self.capacidade_neutra(adversario_tier=adversario_tier)
            ticket_medio = int(ticket_medio * 1.18)

        publico = min(capacidade, int(base_torcida * bonus_fase * bonus_importancia))
        return int(publico * ticket_medio)

    def custo_manutencao_infra_mensal(self):
        ct = self.nivel_ct
        base = self.nivel_base
        estadio = self.nivel_estadio
        custo_infra = (4_500 * (ct ** 1.7)) + (3_800 * (base ** 1.6)) + (5_000 * (estadio ** 1.8))
        custo_capacidade = self.capacidade_estadio * 75
        return int(custo_infra + custo_capacidade)

    def _custo_operacional_anual(self):
        custo_base = 220_000 * (self.reputacao_tier ** 1.45)
        folha = sum(j.overall for j in self.elenco) * (1_400 + (self.reputacao_tier * 110))
        custo_infra = self.custo_manutencao_infra_mensal() * 12
        return int(custo_base + folha + custo_infra)

    def atualizar_job_security(self, titulos=0, permaneceu_elite=False):
        if self.reputacao_tier == 15:
            demissao = titulos == 0
            risco = "critico" if demissao else "estavel"
            objetivo = "Conquistar ao menos 1 titulo por temporada"
        elif self.reputacao_tier >= 10:
            demissao = titulos == 0 and not permaneceu_elite
            risco = "alto" if demissao else "moderado"
            objetivo = "Disputar titulos e vaga continental"
        else:
            demissao = not permaneceu_elite and "bra_a" in self.competicoes
            risco = "alto" if demissao else "baixo"
            objetivo = "Permanencia e estabilidade"
        self.job_security = {"risco": risco, "demissao_imediata": demissao, "objetivo": objetivo}

    def aplicar_manutencao_anual(self):
        custo_total = self._custo_operacional_anual()
        self.financas += self.cota_tv_por_tier()
        self.financas -= custo_total

        crise = self.financas < 0
        if crise:
            self.infraestrutura["ct"] = max(0, self.nivel_ct - 1)
            self.infraestrutura["base"] = max(0, self.nivel_base - 1)
            self.infraestrutura["estadio_nivel"] = max(0, self.nivel_estadio - 1)
            perda_pp = int(self.alvo_pp_tier(self.reputacao_tier) * 0.08)
            self.prestigio_acumulado = max(0, self.prestigio_acumulado - perda_pp)
            self.status_financeiro = "crise"
        else:
            self.status_financeiro = "estavel"
        return crise

    def atualizar_reputacao_financas_fim_ano(self, titulos=0, elite_assiduo=False, permaneceu_elite=False):
        self.prestigio_acumulado += self.calcular_pp_anual(titulos=titulos, elite_assiduo=elite_assiduo)

        taxa_decaimento = self.decaimento_percentual_tier(max(1, self.reputacao_tier)) / 100
        self.prestigio_acumulado = max(0, int(self.prestigio_acumulado * (1 - taxa_decaimento)))

        crise = self.aplicar_manutencao_anual()
        self.sincronizar_reputacao_por_prestigio()
        self.atualizar_job_security(titulos=titulos, permaneceu_elite=permaneceu_elite)
        return crise

    def avancar_ano(self):
        for jogador in self.elenco + self.base_jovens:
            jogador.idade += 1

    def gerar_newgens_anuais(self, quantidade=None):
        if self.nivel_base <= 0:
            return []
        quantidade = quantidade if quantidade is not None else (1 + self.nivel_base // 10)
        novos = []
        for _ in range(quantidade):
            posicao = random.choice(POSICOES_BASE)
            novos.append(gerar_newgen_base(self.nivel_base, posicao))
        if self.nivel_base >= 30 and not any(j.potencial >= 85 for j in novos):
            alvo = max(novos, key=lambda j: j.potencial)
            alvo.potencial = max(alvo.potencial, 85)
        self.base_jovens.extend(novos)
        return novos

    def promover_jovem(self, jogador, definitivo=False):
        if jogador in self.base_jovens:
            self.base_jovens.remove(jogador)
        if jogador not in self.elenco:
            self.elenco.append(jogador)
        jogador.status_base = "profissional" if definitivo else "transicao"
        jogador.origem_base = True

    def devolver_para_base(self, jogador):
        if jogador.idade >= 22:
            return False
        if jogador not in self.elenco:
            return False
        if jogador not in self.base_jovens:
            self.base_jovens.append(jogador)
        self.elenco.remove(jogador)
        jogador.status_base = "base"
        jogador.origem_base = True
        return True

    def _limite_promocao_definitiva(self):
        return min(80, int(58 + (self.reputacao_tier * 1.1)))

    def _dispensar_jovem(self, jogador):
        if jogador in self.base_jovens:
            self.base_jovens.remove(jogador)
        if jogador in self.elenco:
            self.elenco.remove(jogador)

    def _forcar_transicao_sub21(self):
        limite = self._limite_promocao_definitiva()
        candidatos = []
        for jogador in list(self.base_jovens):
            if jogador.idade >= 22:
                candidatos.append(jogador)
        for jogador in [j for j in self.elenco if j.status_base == "transicao" and j.idade >= 22]:
            candidatos.append(jogador)

        for jogador in candidatos:
            if jogador.overall >= limite:
                self.promover_jovem(jogador, definitivo=True)
            else:
                self._dispensar_jovem(jogador)

    def auto_promover_jovens(self, quantidade=3):
        jovens = [j for j in self.base_jovens if j.idade <= 21]
        jovens.sort(key=lambda j: (j.potencial, j.overall), reverse=True)
        promovidos = []
        for jogador in jovens[:quantidade]:
            self.promover_jovem(jogador, definitivo=False)
            promovidos.append(jogador)
        return promovidos

    def processar_transicao_base(self, inicio_temporada=False, crise_financeira=False):
        if inicio_temporada:
            self.avancar_ano()
            self.gerar_newgens_anuais()
        self._forcar_transicao_sub21()
        if inicio_temporada or crise_financeira:
            self.auto_promover_jovens(quantidade=3)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "reputacao": self.reputacao,
            "reputacao_tier": self.reputacao_tier,
            "categoria_tier": self.categoria_tier,
            "prestigio_acumulado": self.prestigio_acumulado,
            "meta_pp_proximo_tier": self.alvo_pp_tier(min(15, self.reputacao_tier + 1)),
            "financas": self.financas,
            "infraestrutura": self.infraestrutura,
            "torcida_expectativa": self.torcida_expectativa,
            "job_security": self.job_security,
            "status_financeiro": self.status_financeiro,
            "base_jovens": [j.to_dict() for j in self.base_jovens],
            "competicoes": self.competicoes,
        }
