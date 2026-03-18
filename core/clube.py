import random

from core.jogador import Jogador
from core.clube_base import ClubeBaseMixin
from core.clube_financas import ClubeFinancasMixin
from core.clube_infra import ClubeInfraMixin
from core.clube_reputacao import ClubeReputacaoMixin
from core.clube_staff import ClubeStaffMixin

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


class Clube(ClubeReputacaoMixin, ClubeInfraMixin, ClubeFinancasMixin, ClubeBaseMixin, ClubeStaffMixin):
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
        if self.nivel_base <= 0:
            self.infraestrutura["base"] = max(1, self._nivel_padrao_base())
        self.base_jovens = self._carregar_base(dados_iniciais.get("base_jovens", []))
        self.torcida_expectativa = dados_iniciais.get("torcida_expectativa", 50)
        self.job_security = dados_iniciais.get(
            "job_security",
            {"risco": "estavel", "demissao_imediata": False, "objetivo": "Manter estabilidade"},
        )
        self.status_financeiro = dados_iniciais.get("status_financeiro", "estavel")
        self.investimento_base = dados_iniciais.get("investimento_base", "medio")
        self.nivel_auxiliar = self._clamp_staff(dados_iniciais.get("nivel_auxiliar", 1))
        self.nivel_olheiro = self._clamp_staff(dados_iniciais.get("nivel_olheiro", 1))

        self.formacao = "4-3-3"
        self.titulares_customizados = None

    @property
    def forca(self):
        return round(self.calcular_forca_atual(self.escalar_titulares()), 1)


    def _carregar_base(self, base_serializada):
        base = []
        for item in base_serializada or []:
            if isinstance(item, Jogador):
                base.append(item)
            elif isinstance(item, dict):
                base.append(Jogador.from_dict(item))
        return base


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
            if hasattr(jogador, "registrar_partida"):
                jogador.registrar_partida(90)
            else:
                jogador.aplicar_fadiga(90)
            risco_individual = risco_lesao * (1.6 if "Vidro" in getattr(jogador, "defeitos", []) else 1.0)
            if random.random() < risco_individual:
                dias = int(6 + (30 - self.nivel_ct) * 0.6 + random.randint(0, 6))
                jogador.aplicar_lesao(dias)

    def atualizar_desenvolvimento(self, resultado):
        ajuste = 0.6 if resultado == "V" else (-0.4 if resultado == "D" else 0.1)
        bonus_ct = (self.nivel_ct / 30) * 0.35
        mentores = {j.posicao for j in self.elenco if j.idade >= 32}
        for jogador in self.escalar_titulares():
            jogador.atualizar_forma(ajuste)
            bonus = bonus_ct * (2 if jogador.idade <= 21 and jogador.posicao in mentores else 1)
            jogador.evoluir(bonus_ct=bonus)

    def media_por_posicao(self, apenas_titulares=False):
        base = self.escalar_titulares() if apenas_titulares else self.elenco
        medias = {}
        for pos in ["GOL", "LD", "ZAG", "LE", "VOL", "MC", "MEI", "PD", "PE", "ATA"]:
            jogadores = [j for j in base if j.posicao == pos]
            medias[pos] = round(sum(j.overall for j in jogadores) / len(jogadores), 1) if jogadores else 0
        return medias


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
            "investimento_base": self.investimento_base,
            "nivel_auxiliar": self.nivel_auxiliar,
            "nivel_olheiro": self.nivel_olheiro,
            "base_jovens": [j.to_dict() for j in self.base_jovens],
            "competicoes": self.competicoes,
        }
