TIER_CATEGORIAS = {
    "Regional": range(1, 4),
    "Emergente": range(4, 7),
    "Nacional": range(7, 10),
    "Gigante": range(10, 13),
    "Global": range(13, 16),
}


class ClubeReputacaoMixin:
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

    def sincronizar_reputacao_por_prestigio(self):
        tier = 1
        for nivel in range(1, 16):
            if self.prestigio_acumulado >= self.alvo_pp_tier(nivel):
                tier = nivel
            else:
                break
        self.reputacao_tier = max(1, min(15, tier))
        self.reputacao = min(100, max(1, int((self.reputacao_tier / 15) * 100)))

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
