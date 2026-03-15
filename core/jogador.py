class Jogador:
    def __init__(
        self,
        nome: str,
        overall: int,
        posicao: str,
        idade: int = 23,
        potencial: int = 80,
        salario: int | None = None,
        status_base: str = "profissional",
        origem_base: bool = False,
        lesao_dias: int = 0,
    ):
        self.nome = nome
        self.overall = overall
        self.posicao = posicao
        self.idade = idade
        self.potencial = potencial
        self.salario = int(salario) if salario is not None else 0
        self.status_base = status_base
        self.origem_base = origem_base
        self.lesao_dias = max(0, int(lesao_dias))
        self.fadiga = 0
        self.forma = 0.0
        self.jogos_temporada = 0

    @property
    def disponivel(self):
        return self.lesao_dias <= 0

    @property
    def over_match(self):
        penalidade_fadiga = self.fadiga * 0.12
        bonus_forma = self.forma * 0.5
        penalidade_lesao = 8 if not self.disponivel else 0
        return max(45, round(self.overall - penalidade_fadiga - penalidade_lesao + bonus_forma, 1))

    def aplicar_fadiga(self, minutos=90):
        self.fadiga = min(100, self.fadiga + (minutos / 90) * 16)
        self.jogos_temporada += 1

    def recuperar_fadiga(self, dias_descanso=3, recuperacao_por_dia=9):
        self.fadiga = max(0, self.fadiga - (dias_descanso * recuperacao_por_dia))
        self.lesao_dias = max(0, self.lesao_dias - dias_descanso)

    def atualizar_forma(self, desempenho):
        self.forma = max(-5, min(5, self.forma * 0.65 + desempenho))

    def evoluir(self, bonus_ct=0.0):
        ajuste_idade = -0.35 if self.idade >= 31 else (0.25 if self.idade <= 23 else 0.05)
        gap_potencial = (self.potencial - self.overall) / 18
        ajuste_forma = self.forma * 0.08
        variacao = ajuste_idade + gap_potencial + ajuste_forma + bonus_ct
        self.overall = int(max(50, min(92, round(self.overall + variacao))))

    def aplicar_lesao(self, dias):
        self.lesao_dias = max(self.lesao_dias, int(dias))

    def __repr__(self):
        return f"{self.nome} ({self.posicao}) - {self.overall}"

    def to_dict(self):
        return {
            "nome": self.nome,
            "overall": self.overall,
            "posicao": self.posicao,
            "idade": self.idade,
            "potencial": self.potencial,
            "salario": self.salario,
            "status_base": self.status_base,
            "origem_base": self.origem_base,
            "fadiga": self.fadiga,
            "forma": self.forma,
            "jogos_temporada": self.jogos_temporada,
            "lesao_dias": self.lesao_dias,
        }

    @classmethod
    def from_dict(cls, data):
        jogador = cls(
            data.get("nome", "Jogador"),
            data.get("overall", 60),
            data.get("posicao", "MC"),
            idade=data.get("idade", 19),
            potencial=data.get("potencial", 75),
            salario=data.get("salario", 0),
            status_base=data.get("status_base", "profissional"),
            origem_base=data.get("origem_base", False),
            lesao_dias=data.get("lesao_dias", 0),
        )
        jogador.fadiga = data.get("fadiga", 0)
        jogador.forma = data.get("forma", 0.0)
        jogador.jogos_temporada = data.get("jogos_temporada", 0)
        return jogador
