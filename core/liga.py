class Liga:
    def __init__(self, nome: str, clubes: list):
        self.nome = nome
        self.clubes = clubes

    def __repr__(self):
        return f"Liga({self.nome})"