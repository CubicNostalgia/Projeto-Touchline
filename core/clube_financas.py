class ClubeFinancasMixin:
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
        custo_staff = self.custo_staff_mensal() * 12 if hasattr(self, "custo_staff_mensal") else 0
        custo_base_invest = self.custo_investimento_base_mensal() * 12 if hasattr(self, "custo_investimento_base_mensal") else 0
        return int(custo_base + folha + custo_infra + custo_staff + custo_base_invest)

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
