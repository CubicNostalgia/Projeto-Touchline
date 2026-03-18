class ClubeStaffMixin:
    STAFF_SALARIOS = {
        1: 1_500,
        2: 3_500,
        3: 8_000,
        4: 20_000,
        5: 50_000,
        6: 120_000,
        7: 300_000,
    }

    def _clamp_staff(self, nivel):
        try:
            nivel = int(nivel)
        except (TypeError, ValueError):
            nivel = 1
        return max(1, min(7, nivel))

    def custo_staff_mensal(self):
        return self.STAFF_SALARIOS.get(self.nivel_auxiliar, 1_500) + self.STAFF_SALARIOS.get(self.nivel_olheiro, 1_500)

    def definir_nivel_auxiliar(self, nivel):
        self.nivel_auxiliar = self._clamp_staff(nivel)

    def definir_nivel_olheiro(self, nivel):
        self.nivel_olheiro = self._clamp_staff(nivel)
