class Liga:
    def __init__(self, nome: str, clubes: list, competicao_id: str | None = None):
        self.nome = nome
        self.clubes = clubes
        self.competicao_id = competicao_id
        self.tabela = {}
        self._inicializar_tabela()

    def __repr__(self):
        return f"Liga({self.nome})"

    @staticmethod
    def _init_linha():
        return {"pontos": 0, "vitorias": 0, "empates": 0, "derrotas": 0, "gols_pro": 0, "gols_contra": 0}

    def _inicializar_tabela(self):
        for clube in self.clubes:
            self.tabela.setdefault(clube, self._init_linha())

    def registrar_resultado(self, casa, fora, gols_casa, gols_fora):
        self.tabela.setdefault(casa, self._init_linha())
        self.tabela.setdefault(fora, self._init_linha())
        t_casa = self.tabela[casa]
        t_fora = self.tabela[fora]
        t_casa["gols_pro"] += gols_casa
        t_casa["gols_contra"] += gols_fora
        t_fora["gols_pro"] += gols_fora
        t_fora["gols_contra"] += gols_casa

        if gols_casa > gols_fora:
            t_casa["vitorias"] += 1
            t_casa["pontos"] += 3
            t_fora["derrotas"] += 1
        elif gols_fora > gols_casa:
            t_fora["vitorias"] += 1
            t_fora["pontos"] += 3
            t_casa["derrotas"] += 1
        else:
            t_casa["empates"] += 1
            t_fora["empates"] += 1
            t_casa["pontos"] += 1
            t_fora["pontos"] += 1

    def classificacao(self):
        return sorted(
            self.tabela.items(),
            key=lambda item: (item[1]["pontos"], item[1]["gols_pro"] - item[1]["gols_contra"], item[1]["gols_pro"]),
            reverse=True,
        )
