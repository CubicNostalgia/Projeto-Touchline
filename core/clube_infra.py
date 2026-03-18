class ClubeInfraMixin:
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
