class FinancialManager:
    def __init__(self):
        self.budget = 0.0
        self.salaries = 0.0
        self.revenues = 0.0

    def set_budget(self, amount):
        self.budget = amount

    def add_salary(self, amount):
        self.salaries += amount

    def add_revenue(self, amount):
        self.revenues += amount

    def get_financial_status(self):
        return {
            'Budget': self.budget,
            'Salaries': self.salaries,
            'Revenues': self.revenues
        }