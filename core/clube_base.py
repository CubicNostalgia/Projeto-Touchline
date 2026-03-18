import random

from utils.gerador_jogadores import gerar_newgen_base

POSICOES_BASE = ["GOL", "LD", "ZAG", "LE", "VOL", "MC", "MEI", "PD", "PE", "ATA"]


class ClubeBaseMixin:
    def _alvo_base_jovens(self):
        tier = getattr(self, "reputacao_tier", 5)
        alvo = 2 + max(0, tier // 2) + max(0, self.nivel_base // 10)
        return max(4, min(12, alvo))

    def _garantir_base_minima(self):
        alvo = self._alvo_base_jovens()
        faltantes = max(0, alvo - len(self.base_jovens))
        if faltantes <= 0:
            return []
        novos = []
        for _ in range(faltantes):
            posicao = random.choice(POSICOES_BASE)
            nivel_ajustado = max(0, min(30, self.nivel_base + self._bonus_nivel_base_investimento()))
            novos.append(gerar_newgen_base(nivel_ajustado, posicao))
        self.base_jovens.extend(novos)
        return novos
    def avancar_ano(self):
        for jogador in self.elenco + self.base_jovens:
            jogador.idade += 1

    def _multiplicador_investimento_base(self):
        investimento = getattr(self, "investimento_base", "medio")
        if investimento == "alto":
            return 1.15
        if investimento == "baixo":
            return 0.85
        return 1.0

    def _bonus_nivel_base_investimento(self):
        investimento = getattr(self, "investimento_base", "medio")
        if investimento == "alto":
            return 4
        if investimento == "baixo":
            return -4
        return 0

    def _quantidade_newgens(self):
        tier = getattr(self, "reputacao_tier", 5)
        investimento = getattr(self, "investimento_base", "medio")
        base = 1 + max(0, tier - 1) // 2
        if self.nivel_base >= 20:
            base += 1
        if investimento == "alto":
            base += 1
        elif investimento == "baixo":
            base -= 1
        return max(1, min(8, base))

    def custo_investimento_base_mensal(self):
        investimento = getattr(self, "investimento_base", "medio")
        return {"baixo": 5_000, "medio": 20_000, "alto": 60_000}.get(investimento, 20_000)

    def gerar_newgens_anuais(self, quantidade=None):
        if self.nivel_base <= 0:
            return []
        quantidade = quantidade if quantidade is not None else self._quantidade_newgens()
        novos = []
        for _ in range(quantidade):
            posicao = random.choice(POSICOES_BASE)
            nivel_ajustado = max(0, min(30, self.nivel_base + self._bonus_nivel_base_investimento()))
            novos.append(gerar_newgen_base(nivel_ajustado, posicao))
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
        novos = []
        promovidos = []
        if inicio_temporada:
            self.avancar_ano()
            novos = self.gerar_newgens_anuais()
            novos += self._garantir_base_minima()
        self._forcar_transicao_sub21()
        if crise_financeira:
            promovidos = self.auto_promover_jovens(quantidade=3)
        return {"novos": novos, "promovidos": promovidos}
