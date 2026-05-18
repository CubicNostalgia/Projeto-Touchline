from collections import defaultdict
from datetime import date, datetime, timedelta
from core.liga import Liga
import random

from engine.calendario import (
    gerar_calendario_brasileirao,
    gerar_calendario_paulistao,
    gerar_calendario_paulistao_a2,
    gerar_calendario_cariocao,
    gerar_calendario_copa_brasil,
    gerar_calendario_serie_c,
    gerar_calendario_serie_d,
)
from engine.simulador import simular_partida
from engine import noticias, mensagens
from core.objetivos import mensagem_resultado_objetivos
import db_manager
from data.database import SERIE_C_EXPANSAO, SERIE_D_FORMATO, COPA_BRASIL_PREMIACAO_2026
from engine import rankings
from engine import triggers


class TemporadaEngine:
    def __init__(
        self,
        liga,
        clube_usuario=None,
        clubes_paulistao=None,
        clubes_paulistao_a2=None,
        clubes_cariocao=None,
        objetivos=None,
        estado_mundo_inicial=None,
        competicao_id=None,
    ):
        self.liga = liga
        self.competicao_id = competicao_id
        self.clube_usuario = clube_usuario
        self.objetivos = objetivos or []
        self.rodada_atual = 0
        self.estado_mundo = estado_mundo_inicial or {"meta": {"temporada_atual": 2026}, "clubes": []}
        self.paulistao_bracket = {"quartas": None, "semis": None, "finalistas": None, "final_ida": None, "campeao": None}
        self.paulistao_mata_mata_simulado = False
        self.paulistao_a2_estado = {"grupos_gerados": False, "semi_gerados": False, "acessos": [], "campeao": None}
        self.cariocao_estado = {"grupos": {}, "quartas": None, "semis": None, "campeao": None}
        self.copa_brasil_estado = {
            "fase_por_clube": {},
            "premio_fase": {},
            "campeao_id": None,
            "participantes": {},
        }
        self.serie_c_estado = {"grupos_gerados": False, "grupos": {}}
        self.serie_d_estado = {"mata_mata_gerado": False, "quartas_perdedores": [], "acessos": []}

        self.calendario_completo = []
        self.todos_clubes = {c.id: c for c in liga.clubes}
        for lista in (clubes_paulistao or [], clubes_paulistao_a2 or [], clubes_cariocao or []):
            for clube in lista:
                self.todos_clubes.setdefault(clube.id, clube)
        try:
            for clube in db_manager.carregar_todos_clubes(self.estado_mundo["meta"]["temporada_atual"]):
                self.todos_clubes.setdefault(clube.id, clube)
        except Exception:
            pass

        ano_temporada = int(self.estado_mundo.get("meta", {}).get("temporada_atual", 2026))
        if clubes_paulistao:
            self.calendario_completo.extend(gerar_calendario_paulistao(clubes_paulistao, temporada_ano=ano_temporada))
        if clubes_paulistao_a2:
            self.calendario_completo.extend(
                gerar_calendario_paulistao_a2(clubes_paulistao_a2, temporada_ano=ano_temporada)
            )
        if clubes_cariocao:
            grupo_a, grupo_b = self._definir_grupos_cariocao(clubes_cariocao)
            self.cariocao_estado["grupos"] = {"A": grupo_a, "B": grupo_b}
            self.calendario_completo.extend(gerar_calendario_cariocao(grupo_a, grupo_b, temporada_ano=ano_temporada))
        self.calendario_completo.extend(gerar_calendario_copa_brasil(temporada_ano=ano_temporada))
        comp_nacional = competicao_id or ("bra_a" if "Série A" in liga.nome else "bra_b")
        if comp_nacional == "bra_c":
            self.calendario_completo.extend(gerar_calendario_serie_c(liga.clubes, ano_temporada))
        elif comp_nacional == "bra_d":
            self.calendario_completo.extend(gerar_calendario_serie_d(liga.clubes, ano_temporada))
        else:
            self.calendario_completo.extend(
                gerar_calendario_brasileirao(
                    liga.clubes,
                    comp_nacional,
                    inicio_override=None,
                    temporada_ano=ano_temporada,
                )
            )
        self.calendario_completo.sort(key=lambda x: x["data"])

        try:
            db_manager.salvar_calendario(comp_nacional, self.estado_mundo["meta"]["temporada_atual"], self.calendario_completo)
        except Exception:
            pass

        self.tabelas = defaultdict(dict)
        self._reconstruir_tabelas_do_calendario(comp_nacional)
        self._restaurar_tabelas_do_banco()
        self._inicializar_data_atual()
        runtime_restaurado = self._restaurar_runtime_temporada(comp_nacional)

        if not runtime_restaurado:
            self._preparar_clubes_para_temporada(clubes_paulistao, clubes_paulistao_a2, clubes_cariocao)
        self._aplicar_rnc_inicial()
        if not runtime_restaurado or not self.copa_brasil_estado.get("participantes"):
            self._definir_participantes_copa_brasil()
        self.estado_mundo.setdefault("meta", {}).setdefault("efeitos_ativos", [])
        self._persistir_classificacoes_no_banco()

    @staticmethod
    def _init_linha():
        return {"pontos": 0, "vitorias": 0, "empates": 0, "derrotas": 0, "gols_pro": 0, "gols_contra": 0}

    def _reconstruir_tabelas_do_calendario(self, comp_nacional):
        self.tabelas = defaultdict(dict)
        for evento in self.calendario_completo:
            if "partidas" not in evento:
                continue
            comp = evento["competicao"]
            for casa, fora in evento["partidas"]:
                self.tabelas[comp].setdefault(casa, self._init_linha())
                self.tabelas[comp].setdefault(fora, self._init_linha())

        if isinstance(self.liga, Liga):
            self.liga.competicao_id = comp_nacional
            if comp_nacional in self.tabelas:
                self.liga.tabela = self.tabelas[comp_nacional]

    def _restaurar_tabelas_do_banco(self):
        temporada_ano = int(self.estado_mundo.get("meta", {}).get("temporada_atual", 2026))
        for comp, tabela in self.tabelas.items():
            try:
                stats_por_clube = db_manager.carregar_classificacao_competicao(comp, temporada_ano)
                if not stats_por_clube:
                    stats_por_clube = db_manager.reconstruir_classificacao_competicao(comp, temporada_ano)
                    if stats_por_clube:
                        db_manager.salvar_classificacao_competicao(comp, temporada_ano, stats_por_clube)
            except Exception:
                stats_por_clube = {}
            for clube, stats in tabela.items():
                restaurado = stats_por_clube.get(clube.id)
                if restaurado:
                    stats.update(restaurado)

    def _persistir_classificacoes_no_banco(self):
        temporada_ano = int(self.estado_mundo.get("meta", {}).get("temporada_atual", 2026))
        for comp, tabela in self.tabelas.items():
            if not tabela:
                continue
            try:
                db_manager.salvar_classificacao_competicao(comp, temporada_ano, tabela)
            except Exception:
                pass

    @staticmethod
    def _regras_serie_c(ano):
        regras = SERIE_C_EXPANSAO[0]
        for etapa in SERIE_C_EXPANSAO:
            if ano >= etapa["ano"]:
                regras = etapa
        return regras

    def _inicializar_data_atual(self):
        meta = self.estado_mundo.setdefault("meta", {})
        data_iso = meta.get("data_atual")
        data_atual = None
        if data_iso:
            try:
                data_atual = datetime.fromisoformat(data_iso).date()
            except ValueError:
                data_atual = None
        if data_atual and data_atual.year != meta.get("temporada_atual", data_atual.year):
            data_atual = None
        if not data_atual:
            if self.calendario_completo:
                data_atual = self.calendario_completo[0]["data"].date()
            else:
                data_atual = date(meta.get("temporada_atual", 2026), 1, 1)
        self.data_atual = data_atual
        meta["data_atual"] = self.data_atual.isoformat()

    def _serializar_tabelas(self):
        tabelas_serializadas = {}
        for comp, tabela in self.tabelas.items():
            linhas = {}
            for clube, stats in tabela.items():
                linhas[clube.id] = {
                    "pontos": int(stats.get("pontos", 0)),
                    "vitorias": int(stats.get("vitorias", 0)),
                    "empates": int(stats.get("empates", 0)),
                    "derrotas": int(stats.get("derrotas", 0)),
                    "gols_pro": int(stats.get("gols_pro", 0)),
                    "gols_contra": int(stats.get("gols_contra", 0)),
                }
            tabelas_serializadas[comp] = linhas
        return tabelas_serializadas

    def _serializar_valor_runtime(self, valor):
        if valor is None or isinstance(valor, (str, int, float, bool)):
            return valor
        if isinstance(valor, datetime):
            return {"__type__": "datetime", "value": valor.isoformat()}
        if isinstance(valor, date):
            return {"__type__": "date", "value": valor.isoformat()}
        if isinstance(valor, list):
            return [self._serializar_valor_runtime(item) for item in valor]
        if isinstance(valor, tuple):
            return {"__type__": "tuple", "items": [self._serializar_valor_runtime(item) for item in valor]}
        if isinstance(valor, set):
            return {"__type__": "set", "items": [self._serializar_valor_runtime(item) for item in valor]}
        clube_id = getattr(valor, "id", None)
        clube_nome = getattr(valor, "nome", None)
        if clube_id and clube_nome is not None:
            return {"__type__": "clube_ref", "id": clube_id}
        if isinstance(valor, dict):
            return {str(chave): self._serializar_valor_runtime(item) for chave, item in valor.items()}
        return valor

    def _desserializar_valor_runtime(self, valor):
        if isinstance(valor, list):
            return [self._desserializar_valor_runtime(item) for item in valor]
        if not isinstance(valor, dict):
            return valor
        tipo = valor.get("__type__")
        if tipo == "datetime":
            try:
                return datetime.fromisoformat(valor["value"])
            except (KeyError, ValueError):
                return None
        if tipo == "date":
            try:
                return date.fromisoformat(valor["value"])
            except (KeyError, ValueError):
                return None
        if tipo == "tuple":
            return tuple(self._desserializar_valor_runtime(item) for item in valor.get("items", []))
        if tipo == "set":
            return set(self._desserializar_valor_runtime(item) for item in valor.get("items", []))
        if tipo == "clube_ref":
            return self.todos_clubes.get(valor.get("id"))
        return {chave: self._desserializar_valor_runtime(item) for chave, item in valor.items()}

    def _estado_competicoes_runtime(self):
        return {
            "paulistao_bracket": self.paulistao_bracket,
            "paulistao_mata_mata_simulado": self.paulistao_mata_mata_simulado,
            "paulistao_a2_estado": self.paulistao_a2_estado,
            "cariocao_estado": self.cariocao_estado,
            "copa_brasil_estado": self.copa_brasil_estado,
            "serie_c_estado": self.serie_c_estado,
            "serie_d_estado": self.serie_d_estado,
        }

    def _restaurar_estados_competicoes(self, estados_serializados):
        estados = self._desserializar_valor_runtime(estados_serializados)
        if not isinstance(estados, dict):
            return
        for atributo in (
            "paulistao_bracket",
            "paulistao_mata_mata_simulado",
            "paulistao_a2_estado",
            "cariocao_estado",
            "copa_brasil_estado",
            "serie_c_estado",
            "serie_d_estado",
        ):
            if atributo in estados:
                setattr(self, atributo, estados[atributo])

    def _restaurar_calendario_runtime(self, calendario_serializado, comp_nacional):
        calendario = self._desserializar_valor_runtime(calendario_serializado)
        if not isinstance(calendario, list):
            return False
        eventos = []
        for evento in calendario:
            if not isinstance(evento, dict) or "data" not in evento or evento["data"] is None:
                continue
            evento_normalizado = dict(evento)
            if "partidas" in evento_normalizado:
                partidas_validas = []
                for partida in evento_normalizado["partidas"]:
                    if not isinstance(partida, (list, tuple)) or len(partida) != 2:
                        continue
                    casa, fora = partida
                    if casa is None or fora is None:
                        continue
                    partidas_validas.append((casa, fora))
                if not partidas_validas and "fase" not in evento_normalizado:
                    continue
                evento_normalizado["partidas"] = partidas_validas
            eventos.append(evento_normalizado)
        if not eventos:
            return False
        self.calendario_completo = sorted(eventos, key=lambda item: item["data"])
        self._reconstruir_tabelas_do_calendario(comp_nacional)
        return True

    def _restaurar_tabelas(self, tabelas_serializadas):
        if not isinstance(tabelas_serializadas, dict):
            return
        for comp, linhas in tabelas_serializadas.items():
            if not isinstance(linhas, dict):
                continue
            self.tabelas[comp] = {}
            for clube_id, stats in linhas.items():
                clube = self.todos_clubes.get(clube_id)
                if not clube:
                    continue
                self.tabelas[comp][clube] = self._init_linha()
                self.tabelas[comp][clube].update(stats)

    def _snapshot_runtime_temporada(self):
        return {
            "temporada_atual": int(self.estado_mundo.get("meta", {}).get("temporada_atual", 2026)),
            "competicao_id": self.competicao_id,
            "rodada_atual": int(self.rodada_atual),
            "data_atual": self.data_atual.isoformat() if hasattr(self, "data_atual") else None,
            "calendario": self._serializar_valor_runtime(self.calendario_completo),
            "estados_competicoes": self._serializar_valor_runtime(self._estado_competicoes_runtime()),
            "tabelas": self._serializar_tabelas(),
        }

    def _restaurar_runtime_temporada(self, comp_nacional):
        meta = self.estado_mundo.setdefault("meta", {})
        runtime = meta.get("season_runtime")
        if not isinstance(runtime, dict):
            return False
        ano_runtime = int(runtime.get("temporada_atual", -1))
        ano_meta = int(meta.get("temporada_atual", 2026))
        if ano_runtime != ano_meta:
            return False
        comp_runtime = runtime.get("competicao_id")
        if comp_runtime and comp_runtime != comp_nacional:
            return False

        self._restaurar_calendario_runtime(runtime.get("calendario"), comp_nacional)
        self._restaurar_tabelas(runtime.get("tabelas", {}))
        self._restaurar_estados_competicoes(runtime.get("estados_competicoes"))
        rodada = int(runtime.get("rodada_atual", 0))
        self.rodada_atual = max(0, min(rodada, len(self.calendario_completo)))
        data_iso = runtime.get("data_atual")
        if data_iso:
            try:
                self.data_atual = datetime.fromisoformat(data_iso).date()
                meta["data_atual"] = self.data_atual.isoformat()
            except ValueError:
                pass

        if isinstance(self.liga, Liga) and comp_nacional in self.tabelas:
            self.liga.tabela = self.tabelas[comp_nacional]
        return True

    def _aplicar_rnc_inicial(self):
        ano_atual = self.estado_mundo["meta"]["temporada_atual"]
        historico = self.estado_mundo["meta"].get("rnc_historico", {})
        rnc_atual = rankings.calcular_rnc_atual(historico, ano_atual)
        if not rnc_atual:
            rnc_atual = {
                c.id: (c.reputacao_tier * 120) + int(c.forca)
                for c in self.todos_clubes.values()
            }
        ordenados = rankings.ordenar_clubes_por_rnc(list(self.todos_clubes.values()), rnc_atual)
        rankings.aplicar_rnc_em_clubes(ordenados, rnc_atual)
        self.estado_mundo["meta"]["rnc_atual"] = rnc_atual
        self.estado_mundo["meta"]["rnf_atual"] = rankings.calcular_rnf(rnc_atual, list(self.todos_clubes.values()))

    @staticmethod
    def _definir_grupos_cariocao(clubes):
        clubes = clubes[:]
        clubes.sort(key=lambda c: (getattr(c, "rnc_pontos", 0), c.reputacao_tier, c.forca), reverse=True)
        grupo_a, grupo_b = [], []
        for i, clube in enumerate(clubes):
            if i % 2 == 0:
                grupo_a.append(clube)
            else:
                grupo_b.append(clube)
        return grupo_a, grupo_b

    def _definir_participantes_copa_brasil(self):
        clubes = list(self.todos_clubes.values())
        rnc_atual = self.estado_mundo["meta"].get("rnc_atual", {})
        ordenados = rankings.ordenar_clubes_por_rnc(clubes, rnc_atual)
        participantes = ordenados[:126] if len(ordenados) > 126 else ordenados
        meta = self.estado_mundo.get("meta", {})
        for cid in (meta.get("serie_c_campeao"), meta.get("copa_brasil_fase3")):
            if cid and cid in self.todos_clubes and all(c.id != cid for c in participantes):
                participantes.append(self.todos_clubes[cid])

        serie_a = [c for c in clubes if "bra_a" in c.competicoes]
        serie_a.sort(key=lambda c: rnc_atual.get(c.id, 0), reverse=True)
        reservados_f5 = serie_a[:20]

        reservados_f3 = self._reservados_fase3_copa_brasil(participantes, rnc_atual)

        reservados_ids = {c.id for c in reservados_f5 + reservados_f3}
        disponiveis = [c for c in participantes if c.id not in reservados_ids and "bra_a" not in c.competicoes]

        fase1_total = 28 if len(disponiveis) >= 28 else len(disponiveis)
        fase1 = disponiveis[-fase1_total:]
        fase1_ids = {c.id for c in fase1}
        fase2_novos = [c for c in disponiveis if c.id not in fase1_ids]

        self.copa_brasil_estado["participantes"] = {
            "f1": fase1,
            "f2_novos": fase2_novos,
            "f3_novos": reservados_f3,
            "f5_serie_a": reservados_f5,
        }

    def _reservados_fase3_copa_brasil(self, participantes, rnc_atual):
        reservados = []
        meta = self.estado_mundo.get("meta", {})
        campeao_c = meta.get("serie_c_campeao")
        campeao_d = meta.get("copa_brasil_fase3")

        def _buscar_por_id(cid):
            return next((c for c in participantes if c.id == cid), None)

        for cid in (campeao_c, campeao_d):
            if not cid:
                continue
            clube = _buscar_por_id(cid)
            if clube and clube not in reservados:
                reservados.append(clube)

        norte = {"AC", "AM", "AP", "PA", "RO", "RR", "TO"}
        nordeste = {"AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"}

        def _top_regiao(estados):
            candidatos = [
                c
                for c in participantes
                if getattr(c, "estado_federacao", "OUT") in estados and "bra_a" not in c.competicoes
            ]
            candidatos.sort(key=lambda c: rnc_atual.get(c.id, 0), reverse=True)
            return candidatos[0] if candidatos else None

        for clube in (_top_regiao(norte), _top_regiao(nordeste)):
            if clube and clube not in reservados:
                reservados.append(clube)

        if len(reservados) < 4:
            candidatos = [c for c in participantes if c not in reservados and "bra_a" not in c.competicoes]
            candidatos.sort(key=lambda c: rnc_atual.get(c.id, 0), reverse=True)
            for clube in candidatos:
                reservados.append(clube)
                if len(reservados) >= 4:
                    break

        return reservados[:4]

    def _preparar_clubes_para_temporada(self, clubes_paulistao, clubes_paulistao_a2=None, clubes_cariocao=None):
        todos = set(self.liga.clubes)
        if clubes_paulistao:
            todos.update(clubes_paulistao)
        if clubes_paulistao_a2:
            todos.update(clubes_paulistao_a2)
        if clubes_cariocao:
            todos.update(clubes_cariocao)
        processados = set()
        for clube in todos:
            if clube.id in processados:
                continue
            processados.add(clube.id)
            crise = getattr(clube, "status_financeiro", "estavel") == "crise"
            if hasattr(clube, "processar_transicao_base"):
                relatorio_base = clube.processar_transicao_base(inicio_temporada=True, crise_financeira=crise) or {}
                if self.clube_usuario and clube.id == self.clube_usuario.id:
                    novos = relatorio_base.get("novos", [])
                    promovidos = relatorio_base.get("promovidos", [])
                    if novos or promovidos:
                        partes = []
                        if novos:
                            partes.append(f"{len(novos)} novos gerados na base")
                        if promovidos:
                            partes.append(f"{len(promovidos)} promovidos ao elenco")
                        corpo = "Relatório da base: " + ", ".join(partes) + "."
                        mensagens.enviar_mensagem(
                            self.estado_mundo["meta"]["temporada_atual"],
                            "Comissão Técnica",
                            "Relatório da base",
                            corpo,
                            prioridade=1,
                        )
                    if crise:
                        mensagens.enviar_mensagem(
                            self.estado_mundo["meta"]["temporada_atual"],
                            "Diretoria",
                            "Alerta financeiro",
                            "O clube iniciou a temporada em crise financeira. Ajustes no orçamento podem ser necessários.",
                            prioridade=2,
                        )

    def simular_proxima_rodada(self):
        if self.rodada_atual >= len(self.calendario_completo):
            print("\n🏁 A temporada já terminou.\n")
            return False

        mostrou_evento = False
        while self.rodada_atual < len(self.calendario_completo):
            evento = self.calendario_completo[self.rodada_atual]
            mostrar_evento = self._deve_exibir_evento(evento)
            fim_temporada = self._processar_evento_calendario(evento, mostrar_evento=mostrar_evento)
            if fim_temporada:
                return False if not mostrou_evento else True

            if mostrar_evento:
                mostrou_evento = True
                return True
        return False

    def simular_ate_evento(self, competicao, data_iso, rodada=None, fase=None):
        if self.rodada_atual >= len(self.calendario_completo):
            print("\n🏁 A temporada já terminou.\n")
            return False

        while self.rodada_atual < len(self.calendario_completo):
            evento = self.calendario_completo[self.rodada_atual]
            eh_alvo = self._evento_equivale(evento, competicao, data_iso, rodada=rodada, fase=fase)
            fim_temporada = self._processar_evento_calendario(
                evento,
                mostrar_evento=eh_alvo and self._deve_exibir_evento(evento),
            )
            if eh_alvo:
                return True
            if fim_temporada:
                return False
        return False

    def avancar_dia(self, dias=1, auto_simular=True):
        if not hasattr(self, "data_atual"):
            self._inicializar_data_atual()
        total_simulados = 0
        passos = max(1, int(dias))
        for _ in range(passos):
            self.data_atual = self.data_atual + timedelta(days=1)
            self.estado_mundo["meta"]["data_atual"] = self.data_atual.isoformat()
            triggers.processar_triggers_diarios(self)
            if not auto_simular:
                continue
            while self.rodada_atual < len(self.calendario_completo):
                evento = self.calendario_completo[self.rodada_atual]
                if evento["data"].date() <= self.data_atual:
                    self.simular_proxima_rodada()
                    total_simulados += 1
                else:
                    break
        return total_simulados

    def avancar_ate_data(self, data_alvo, auto_simular=True, limite_dias=550):
        if not hasattr(self, "data_atual"):
            self._inicializar_data_atual()
        if data_alvo <= self.data_atual:
            return {"dias_avancados": 0, "rodadas_processadas": 0}
        dias_avancados = 0
        rodadas_processadas = 0
        while self.data_atual < data_alvo and dias_avancados < limite_dias:
            rodadas_processadas += self.avancar_dia(1, auto_simular=auto_simular)
            dias_avancados += 1
            if self.rodada_atual >= len(self.calendario_completo):
                break
        return {
            "dias_avancados": dias_avancados,
            "rodadas_processadas": rodadas_processadas,
        }

    def proximo_evento(self):
        if self.rodada_atual >= len(self.calendario_completo):
            return None
        return self.calendario_completo[self.rodada_atual]

    def eventos_por_data_mes(self, ano, mes):
        agenda = {}
        for evento in self.calendario_completo:
            data_evento = evento["data"]
            if data_evento.year != ano or data_evento.month != mes:
                continue
            dia = data_evento.day
            itens = agenda.setdefault(dia, [])
            comp = evento.get("competicao", "")
            detalhe = {
                "competicao": comp,
                "competicao_nome": comp.upper(),
                "rodada": evento.get("rodada"),
                "adversario": None,
                "mandante": None,
                "horario": data_evento.strftime("%H:%M"),
                "fase": evento.get("fase"),
            }
            if self.clube_usuario and "partidas" in evento:
                for casa, fora in evento["partidas"]:
                    if casa.id == self.clube_usuario.id:
                        detalhe["adversario"] = fora.nome
                        detalhe["mandante"] = True
                        break
                    if fora.id == self.clube_usuario.id:
                        detalhe["adversario"] = casa.nome
                        detalhe["mandante"] = False
                        break
            itens.append(detalhe)
        return agenda

    def jogar_temporada_completa(self):
        print(f"\n🏁 Início da temporada — {self.liga.nome}\n")
        while self.simular_proxima_rodada():
            pass

    def virada_de_ano(self):
        if self.rodada_atual < len(self.calendario_completo):
            return False
        self.exibir_fechamento_temporada()
        return True

    def _jogar_rodada(self, evento, mostrar_evento=True):
        if "partidas" not in evento:
            if evento.get("competicao") == "paulistao_a1" and evento.get("fase"):
                self._simular_fase_paulistao(evento["fase"])
                return
            fase = evento.get("fase")
            if fase and fase.startswith("paulistao_a2"):
                self._simular_fase_paulistao_a2(fase, evento)
                return
            if fase and fase.startswith("cariocao"):
                self._simular_fase_cariocao(fase)
                return
            if fase and fase.startswith("cdb_"):
                self._simular_fase_copa_brasil(fase)
                return
            if fase and fase.startswith("serie_c"):
                self._simular_fase_serie_c(fase, evento)
                return
            if fase and fase.startswith("serie_d"):
                self._simular_fase_serie_d(fase, evento)
                return
            return

        resultados_rodada = []
        comp = evento["competicao"]
        for casa, fora in evento["partidas"]:
            self._aplicar_efeitos_pre_partida(casa)
            self._aplicar_efeitos_pre_partida(fora)
            pre_lesoes_casa = sum(1 for j in casa.elenco if j.lesao_dias > 0)
            pre_lesoes_fora = sum(1 for j in fora.elenco if j.lesao_dias > 0)
            venda_mando = casa.deve_vender_mando(fora) if hasattr(casa, "deve_vender_mando") else False
            if hasattr(casa, "calcular_bilheteria"):
                fase_vitorias = self.tabelas.get(comp, {}).get(casa, {}).get("vitorias", 0)
                receita = casa.calcular_bilheteria(
                    capacidade_estadio=casa.capacidade_estadio if hasattr(casa, "capacidade_estadio") else None,
                    fase_vitorias=fase_vitorias,
                    vender_mando=venda_mando,
                    adversario_tier=fora.reputacao_tier,
                )
                casa.financas += receita
            gols_casa, gols_fora = simular_partida(casa, fora, venda_mando=venda_mando)
            self._registrar_partida(
                comp,
                casa,
                fora,
                gols_casa,
                gols_fora,
                rodada=evento.get("rodada"),
                data_partida=evento.get("data"),
            )
            triggers.registrar_resultado_partida(self, comp, casa, fora, gols_casa, gols_fora)
            casa.aplicar_partida()
            fora.aplicar_partida()
            resultados_rodada.append({"casa": casa, "fora": fora, "gols_casa": gols_casa, "gols_fora": gols_fora})

            if self.clube_usuario:
                if casa.id == self.clube_usuario.id:
                    novas = sum(1 for j in casa.elenco if j.lesao_dias > 0) - pre_lesoes_casa
                    if novas > 0:
                        mensagens.enviar_mensagem(
                            self.estado_mundo["meta"]["temporada_atual"],
                            "Departamento Médico",
                            "Novas lesões detectadas",
                            f"{novas} jogador(es) do {casa.nome} saíram lesionados após a rodada.",
                            prioridade=2,
                        )
                if fora.id == self.clube_usuario.id:
                    novas = sum(1 for j in fora.elenco if j.lesao_dias > 0) - pre_lesoes_fora
                    if novas > 0:
                        mensagens.enviar_mensagem(
                            self.estado_mundo["meta"]["temporada_atual"],
                            "Departamento Médico",
                            "Novas lesões detectadas",
                            f"{novas} jogador(es) do {fora.nome} saíram lesionados após a rodada.",
                            prioridade=2,
                        )
            if mostrar_evento:
                print(f"  {casa.nome:>12} {gols_casa} x {gols_fora} {fora.nome:<12}")

        try:
            noticias.processar_rodada(
                resultados_rodada,
                self.estado_mundo["meta"]["temporada_atual"],
                evento.get("rodada"),
            )
        except Exception:
            pass

    def _processar_evento_calendario(self, evento, mostrar_evento):
        data_txt = evento["data"].strftime("%d/%m/%Y %H:%M")
        if hasattr(self, "data_atual") and evento["data"].date() > self.data_atual:
            self.data_atual = evento["data"].date()
            self.estado_mundo["meta"]["data_atual"] = self.data_atual.isoformat()

        if mostrar_evento:
            nome_evento = evento.get("competicao", "PAUSA NO CALENDÁRIO").upper()
            rodada_str = f" — Rodada {evento['rodada']}" if "rodada" in evento else ""
            print(f"\n🕒 {nome_evento}{rodada_str} — {data_txt}")

        if self.rodada_atual > 0:
            dias = (evento["data"].date() - self.calendario_completo[self.rodada_atual - 1]["data"].date()).days
            todos = {c for e in self.calendario_completo if "partidas" in e for p in e["partidas"] for c in p}
            for clube in todos:
                clube.recuperar_elenco(max(1, dias))

        self._jogar_rodada(evento, mostrar_evento=mostrar_evento)
        self.rodada_atual += 1

        if self.rodada_atual == len(self.calendario_completo):
            self.exibir_fechamento_temporada()
            return True
        return False

    @staticmethod
    def _evento_equivale(evento, competicao, data_iso, rodada=None, fase=None):
        if evento.get("competicao") != competicao:
            return False
        if evento.get("data").isoformat() != data_iso:
            return False
        if evento.get("rodada") != rodada:
            return False
        if evento.get("fase") != fase:
            return False
        return True

    def _aplicar_efeitos_pre_partida(self, clube):
        meta = self.estado_mundo.setdefault("meta", {})
        efeitos = meta.setdefault("efeitos_ativos", [])
        restantes = []
        boost_total = 0.0
        for efeito in efeitos:
            if efeito.get("clube_id") == clube.id and efeito.get("tipo") == "moral_proxima_partida":
                boost_total += float(efeito.get("valor", 0.0))
            else:
                restantes.append(efeito)

        if boost_total > 0:
            for jogador in clube.escalar_titulares():
                jogador.atualizar_forma(boost_total)
            if self.clube_usuario and clube.id == self.clube_usuario.id:
                print(f"  Bonus de moral aplicado ao {clube.nome} (+{boost_total:.2f} forma nos titulares).")
        meta["efeitos_ativos"] = restantes

    def _deve_exibir_evento(self, evento):
        if not self.clube_usuario:
            return True
        comp = evento.get("competicao")
        if not comp:
            return True
        if comp.startswith("bra_d_g") or comp in ("bra_c_grupo_a", "bra_c_grupo_b"):
            return self._clube_na_competicao(comp, self.clube_usuario)
        return True

    def _clube_na_competicao(self, competicao, clube):
        tabela = self.tabelas.get(competicao, {})
        return any(c.id == clube.id for c in tabela.keys())

    def _registrar_partida(self, competicao, casa, fora, gols_casa, gols_fora, rodada=None, data_partida=None):
        usa_liga = isinstance(self.liga, Liga) and competicao == self.liga.competicao_id
        if usa_liga:
            self.liga.registrar_resultado(casa, fora, gols_casa, gols_fora)
        else:
            t_casa = self.tabelas[competicao][casa]
            t_fora = self.tabelas[competicao][fora]
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

        if gols_casa > gols_fora:
            casa.atualizar_desenvolvimento("V")
            fora.atualizar_desenvolvimento("D")
        elif gols_fora > gols_casa:
            fora.atualizar_desenvolvimento("V")
            casa.atualizar_desenvolvimento("D")
        else:
            casa.atualizar_desenvolvimento("E")
            fora.atualizar_desenvolvimento("E")

        try:
            db_manager.registrar_partida(
                competicao,
                self.estado_mundo["meta"]["temporada_atual"],
                rodada,
                casa.id,
                fora.id,
                gols_casa,
                gols_fora,
                data_partida=data_partida,
            )
        except Exception:
            pass

    def classificacao(self, competicao):
        if isinstance(self.liga, Liga) and competicao == self.liga.competicao_id:
            return self.liga.classificacao()
        tabela = self.tabelas.get(competicao, {})
        return sorted(
            tabela.items(),
            key=lambda item: (item[1]["pontos"], item[1]["gols_pro"] - item[1]["gols_contra"], item[1]["gols_pro"]),
            reverse=True,
        )

    def _marcador_tabela(self, competicao, pos, total):
        if competicao == "bra_a":
            if pos == 1:
                return "🟢"
            if 2 <= pos <= 4:
                return "🟡"
            if pos == 5:
                return "🟠"
            if 6 <= pos <= 11:
                return "🔵"
            if pos > total - 4:
                return "🔴"
        if competicao == "bra_b":
            if pos <= 2:
                return "🟢"
            if 3 <= pos <= 6:
                return "🟡"
            if pos > total - 4:
                return "🔴"
        if competicao == "paulistao_a1":
            if pos <= 8:
                return "🟢"
        if competicao == "bra_c_fase1":
            regras = self._regras_serie_c(self.estado_mundo["meta"]["temporada_atual"])
            if pos <= 8:
                return "🟢"
            if pos > total - regras["rebaixados"]:
                return "🔴"
        if competicao in ("bra_c_grupo_a", "bra_c_grupo_b"):
            if pos <= 2:
                return "🟢"
        if competicao.startswith("bra_d_g"):
            if pos <= SERIE_D_FORMATO["classificados_por_grupo"]:
                return "🟢"
        return ""

    def exibir_tabela(self, competicao):
        classificacao_final = self.classificacao(competicao)
        print(f"\n🏆 CLASSIFICAÇÃO — {competicao.upper()}")
        print("=" * 70)
        print(f"{'POS':<4} {'CLUBE':<18} {'PTS':<4} {'V':<3} {'E':<3} {'D':<3} {'SG':<4} {'GP':<3} {'TAG':<3}")
        print("-" * 70)
        total = len(classificacao_final)
        for pos, (clube, dados) in enumerate(classificacao_final, start=1):
            saldo = dados["gols_pro"] - dados["gols_contra"]
            tag = self._marcador_tabela(competicao, pos, total)
            print(
                f"{pos:>2}º  {clube.nome:<18} {dados['pontos']:>3}  {dados['vitorias']:>2}  "
                f"{dados['empates']:>2}  {dados['derrotas']:>2}  {saldo:>3}  {dados['gols_pro']:>2}  {tag:<3}"
            )
        if competicao == "bra_a":
            print("\n🟢 Campeão  🟡 Libertadores  🟠 Pré-Libertadores  🔵 Sul-Americana  🔴 Rebaixamento")
        if competicao == "bra_b":
            print("\n🟢 Acesso direto  🟡 Playoffs  🔴 Rebaixamento")
        if competicao == "paulistao_a1":
            print("\n🟢 Classificados ao mata-mata (top-8)")
        if competicao == "bra_c_fase1":
            regras = self._regras_serie_c(self.estado_mundo["meta"]["temporada_atual"])
            print(f"\n🟢 Avanço (top-8)  🔴 Rebaixamento (bottom-{regras['rebaixados']})")
        if competicao in ("bra_c_grupo_a", "bra_c_grupo_b"):
            print("\n🟢 Acesso (top-2)")
        if competicao.startswith("bra_d_g"):
            print("\n🟢 Classificados ao mata-mata (top-4)")

    def exibir_grupos_serie_d(self):
        grupos = sorted([k for k in self.tabelas.keys() if k.startswith("bra_d_g")])
        for comp in grupos:
            print(f"\n=== GRUPO {comp[-2:]} ===")
            self.exibir_tabela(comp)

    def exibir_grupo_serie_d_usuario(self):
        if not self.clube_usuario:
            print("\nNenhum clube do usuário definido.")
            return
        comp = self._competicao_grupo_usuario_serie_d()
        if not comp:
            print("\nGrupo da Série D do usuário ainda não está disponível.")
            return
        print(f"\n=== MEU GRUPO ({comp[-2:]}) ===")
        self.exibir_tabela(comp)

    def exibir_grupos_serie_d_outros(self):
        if not self.clube_usuario:
            self.exibir_grupos_serie_d()
            return
        comp_usuario = self._competicao_grupo_usuario_serie_d()
        grupos = sorted([k for k in self.tabelas.keys() if k.startswith("bra_d_g") and k != comp_usuario])
        if not grupos:
            print("\nNenhum outro grupo disponível.")
            return
        for comp in grupos:
            print(f"\n=== GRUPO {comp[-2:]} ===")
            self.exibir_tabela(comp)

    def exibir_resultados_competicao(self, competicao_id, rodada=None):
        temporada_ano = self.estado_mundo["meta"]["temporada_atual"]
        rodada = rodada or db_manager.ultima_rodada_finalizada(competicao_id, temporada_ano)
        if rodada is None:
            print("\nNenhuma rodada finalizada registrada.")
            return
        partidas = db_manager.listar_partidas_competicao(competicao_id, temporada_ano, rodada=rodada)
        if not partidas:
            print("\nNenhuma partida encontrada para essa rodada.")
            return
        print(f"\n🧾 RESULTADOS — {competicao_id.upper()} — Rodada {rodada}")
        for partida in partidas:
            print(
                f"  {partida['casa_nome']:>12} {partida['gols_casa']} x {partida['gols_fora']} {partida['fora_nome']:<12}"
            )

    def exibir_resultados_serie_d_grupo_usuario(self):
        comp = self._competicao_grupo_usuario_serie_d()
        if not comp:
            print("\nGrupo da Série D do usuário ainda não está disponível.")
            return
        self.exibir_resultados_competicao(comp)

    def exibir_resultados_serie_d_grupos_outros(self):
        comp_usuario = self._competicao_grupo_usuario_serie_d()
        grupos = sorted([k for k in self.tabelas.keys() if k.startswith("bra_d_g") and k != comp_usuario])
        if not grupos:
            print("\nNenhum outro grupo disponível.")
            return
        for comp in grupos:
            self.exibir_resultados_competicao(comp)

    def _competicao_grupo_usuario_serie_d(self):
        for comp in self.tabelas.keys():
            if comp.startswith("bra_d_g") and self._clube_na_competicao(comp, self.clube_usuario):
                return comp
        return None

    def exibir_grupo_serie_c_usuario(self):
        if not self.clube_usuario:
            print("\nNenhum clube do usuário definido.")
            return
        comp = self._competicao_grupo_usuario_serie_c()
        if not comp:
            print("\nGrupo da Série C do usuário ainda não está disponível.")
            return
        print(f"\n=== MEU GRUPO ({'A' if comp.endswith('a') else 'B'}) ===")
        self.exibir_tabela(comp)

    def exibir_grupos_serie_c_outros(self):
        if not self.clube_usuario:
            for comp in ("bra_c_grupo_a", "bra_c_grupo_b"):
                if comp in self.tabelas:
                    self.exibir_tabela(comp)
            return
        comp_usuario = self._competicao_grupo_usuario_serie_c()
        grupos = [c for c in ("bra_c_grupo_a", "bra_c_grupo_b") if c in self.tabelas and c != comp_usuario]
        if not grupos:
            print("\nNenhum outro grupo disponível.")
            return
        for comp in grupos:
            self.exibir_tabela(comp)

    def exibir_resultados_serie_c_grupo_usuario(self):
        comp = self._competicao_grupo_usuario_serie_c()
        if not comp:
            print("\nGrupo da Série C do usuário ainda não está disponível.")
            return
        self.exibir_resultados_competicao(comp)

    def exibir_resultados_serie_c_grupos_outros(self):
        comp_usuario = self._competicao_grupo_usuario_serie_c()
        grupos = [c for c in ("bra_c_grupo_a", "bra_c_grupo_b") if c in self.tabelas and c != comp_usuario]
        if not grupos:
            print("\nNenhum outro grupo disponível.")
            return
        for comp in grupos:
            self.exibir_resultados_competicao(comp)

    def _competicao_grupo_usuario_serie_c(self):
        for comp in ("bra_c_grupo_a", "bra_c_grupo_b"):
            if comp in self.tabelas and self._clube_na_competicao(comp, self.clube_usuario):
                return comp
        return None

    def _avaliar_objetivos(self):
        if not self.clube_usuario:
            return []
        resultados = []
        pos_paul = self._posicao_clube("paulistao_a1")
        pos_paul_a2 = self._posicao_clube("paulistao_a2")
        pos_cariocao = self._posicao_clube("cariocao_a1")
        pos_liga = self._posicao_clube(self._competicao_liga_clube(self.clube_usuario))
        base_ok = len([j for j in self.clube_usuario.elenco if getattr(j, "origem_base", False) and j.jogos_temporada >= 5]) >= 3
        fase_copa = self.copa_brasil_estado.get("fase_por_clube", {}).get(self.clube_usuario.id)

        for obj in self.objetivos:
            cumprido = False
            if obj["id"] == "paulistao_semifinal":
                cumprido = pos_paul is not None and pos_paul <= 4
            elif obj["id"] == "paulistao_quartas":
                cumprido = pos_paul is not None and pos_paul <= 8
            elif obj["id"] == "paulistao_a2_acesso":
                acessos = {c.id for c in self.paulistao_a2_estado.get("acessos", [])}
                cumprido = self.clube_usuario.id in acessos
            elif obj["id"] == "paulistao_a2_top4":
                cumprido = pos_paul_a2 is not None and pos_paul_a2 <= 4
            elif obj["id"] == "cariocao_semis":
                semifinalistas = {c.id for c in self.cariocao_estado.get("semifinalistas", [])}
                cumprido = self.clube_usuario.id in semifinalistas
            elif obj["id"] == "cariocao_quartas":
                grupos = self.cariocao_estado.get("grupos") or {}
                grupo = None
                if self.clube_usuario in grupos.get("A", []):
                    grupo = grupos.get("A", [])
                elif self.clube_usuario in grupos.get("B", []):
                    grupo = grupos.get("B", [])
                if grupo:
                    classif_grupo = self._classificacao_grupo("cariocao_a1", grupo)
                    pos_grupo = next((i for i, (c, _) in enumerate(classif_grupo, start=1) if c.id == self.clube_usuario.id), None)
                    cumprido = pos_grupo is not None and pos_grupo <= 4
            elif obj["id"] == "liga_top":
                if "bra_a" in self.clube_usuario.competicoes:
                    limite = 8 if self.clube_usuario.reputacao_tier >= 9 else 12
                    cumprido = pos_liga is not None and pos_liga <= limite
                else:
                    limite = 6 if self.clube_usuario.reputacao_tier >= 5 else 10
                    cumprido = pos_liga is not None and pos_liga <= limite
            elif obj["id"] == "copa_brasil_fase3":
                fases = {"f3", "f4", "f5", "f6", "f7", "f8", "final"}
                cumprido = fase_copa in fases
            elif obj["id"] == "copa_brasil_fase5":
                fases = {"f5", "f6", "f7", "f8", "final"}
                cumprido = fase_copa in fases
            elif obj["id"] == "financeiro_folha":
                limite = int(obj.get("limite", 0))
                folha = sum(int(getattr(j, "salario", 0) or 0) for j in self.clube_usuario.elenco)
                cumprido = folha <= limite if limite > 0 else True
            elif obj["id"] == "base_revelar_70":
                cumprido = any(
                    getattr(j, "origem_base", False) and int(getattr(j, "overall", 0)) >= 70 and int(getattr(j, "jogos_temporada", 0)) >= 3
                    for j in self.clube_usuario.elenco
                )
            elif obj["id"] == "base":
                cumprido = base_ok
            resultados.append({"texto": obj["texto"], "cumprido": cumprido})
        return resultados

    def avaliar_objetivos_atuais(self):
        resultados = self._avaliar_objetivos()
        temporada_encerrada = self.rodada_atual >= len(self.calendario_completo)
        saida = []
        for item in resultados:
            status = "cumprido" if item["cumprido"] else ("falhado" if temporada_encerrada else "em_andamento")
            saida.append(
                {
                    "texto": item["texto"],
                    "cumprido": item["cumprido"],
                    "status": status,
                }
            )
        return saida

    def _aplicar_consequencias_objetivos(self, resultados):
        if not self.clube_usuario:
            return
        falhos = [r for r in resultados if not r["cumprido"]]
        if not falhos:
            self.clube_usuario.job_security = {
                "risco": "baixo",
                "demissao_imediata": False,
                "objetivo": "Manter desempenho com consistencia",
            }
            return

        falhas_criticas = [r for r in falhos if "base" in r["texto"].lower() or "folha" in r["texto"].lower()]
        risco = "alto" if falhas_criticas else "moderado"
        self.clube_usuario.job_security = {
            "risco": risco,
            "demissao_imediata": False,
            "objetivo": "Recuperar confianca da diretoria",
        }
        self.clube_usuario.torcida_expectativa = max(10, int(self.clube_usuario.torcida_expectativa) - (8 if falhas_criticas else 4))

    def _competicao_liga_clube(self, clube):
        if "bra_a" in clube.competicoes:
            return "bra_a"
        if "bra_b" in clube.competicoes:
            return "bra_b"
        if "bra_c" in clube.competicoes:
            return "bra_c_fase1"
        if "bra_d" in clube.competicoes:
            for comp in self.tabelas.keys():
                if comp.startswith("bra_d_g") and any(c.id == clube.id for c, _ in self.classificacao(comp)):
                    return comp
        return "bra_b"

    def _posicao_clube(self, competicao):
        for i, (clube, _) in enumerate(self.classificacao(competicao), start=1):
            if self.clube_usuario and clube.id == self.clube_usuario.id:
                return i
        return None

    def _simular_mata_mata_paulistao(self):
        classif = self.classificacao("paulistao_a1")
        if not classif:
            return

        print("\n🏆 INÍCIO DO MATA-MATA — PAULISTÃO A1")
        vagas = [c[0] for c in classif[:8]]

        def confrontos(times, fase_nome):
            print(f"\n🎯 {fase_nome}")
            vencedores = []
            for i in range(len(times) // 2):
                casa, fora = times[i], times[-(i + 1)]
                g_c, g_f, venc, pen_str = self._simular_jogo_mata_mata(casa, fora)
                pen_txt = f" {pen_str}" if pen_str else ""
                print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {venc.nome}{pen_txt}")
                vencedores.append(venc)
            return vencedores

        quartas = confrontos(vagas, "QUARTAS DE FINAL")
        semis = confrontos(quartas, "SEMIFINAIS")
        campeao = confrontos(semis, "GRANDE FINAL")[0]

        ano_temporada = self.estado_mundo.get("meta", {}).get("temporada_atual", 2026)
        print(f"\n🎊 ¡{campeao.nome.upper()} É O CAMPEÃO PAULISTA DE {ano_temporada}! 🎊")
        self.paulistao_mata_mata_simulado = True

    def _prob_penalti(self, time, bonus_casa=False):
        forca = time.forca_titular() if hasattr(time, "forca_titular") else 60
        tier = getattr(time, "reputacao_tier", 6)
        base = 0.74
        ajuste = (forca - 70) * 0.004 + (tier - 8) * 0.01
        if bonus_casa:
            ajuste += 0.02
        return max(0.62, min(0.9, base + ajuste))

    def _simular_disputa_penaltis(self, casa, fora):
        prob_casa = self._prob_penalti(casa, bonus_casa=True)
        prob_fora = self._prob_penalti(fora, bonus_casa=False)
        gols_casa = 0
        gols_fora = 0

        for i in range(5):
            if random.random() < prob_casa:
                gols_casa += 1
            if random.random() < prob_fora:
                gols_fora += 1
            restantes = 4 - i
            if gols_casa > gols_fora + restantes:
                return gols_casa, gols_fora
            if gols_fora > gols_casa + restantes:
                return gols_casa, gols_fora

        while gols_casa == gols_fora:
            if random.random() < prob_casa:
                gols_casa += 1
            if random.random() < prob_fora:
                gols_fora += 1
        return gols_casa, gols_fora

    def _simular_jogo_mata_mata(self, casa, fora, derby=False, permitir_penaltis=True):
        venda_mando = casa.deve_vender_mando(fora) if hasattr(casa, "deve_vender_mando") else False
        if hasattr(casa, "calcular_bilheteria"):
            receita = casa.calcular_bilheteria(
                capacidade_estadio=casa.capacidade_estadio if hasattr(casa, "capacidade_estadio") else None,
                vender_mando=venda_mando,
                adversario_tier=fora.reputacao_tier,
            )
            casa.financas += receita
        gols_casa, gols_fora = simular_partida(casa, fora, derby=derby, venda_mando=venda_mando)
        pen_str = None
        if gols_casa == gols_fora and permitir_penaltis:
            pen_c, pen_f = self._simular_disputa_penaltis(casa, fora)
            vencedor = casa if pen_c > pen_f else fora
            pen_str = f"pen ({pen_c}x{pen_f})"
        else:
            vencedor = casa if gols_casa >= gols_fora else fora

        if vencedor == casa:
            casa.atualizar_desenvolvimento("V")
            fora.atualizar_desenvolvimento("D")
        else:
            fora.atualizar_desenvolvimento("V")
            casa.atualizar_desenvolvimento("D")
        casa.aplicar_partida()
        fora.aplicar_partida()
        return gols_casa, gols_fora, vencedor, pen_str

    def _simular_fase_paulistao(self, fase):
        if fase == "grupo":
            return

        if fase == "quartas":
            classif = self.classificacao("paulistao_a1")
            if not classif:
                return
            vagas = [c[0] for c in classif[:8]]
            confrontos = [(vagas[0], vagas[7]), (vagas[1], vagas[6]), (vagas[2], vagas[5]), (vagas[3], vagas[4])]
            print("\n🏆 QUARTAS DE FINAL — PAULISTÃO A1")
            vencedores = []
            for casa, fora in confrontos:
                g_c, g_f, vencedor, pen_str = self._simular_jogo_mata_mata(casa, fora)
                pen_txt = f" {pen_str}" if pen_str else ""
                print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {vencedor.nome}{pen_txt}")
                vencedores.append(vencedor)
            self.paulistao_bracket["quartas"] = vencedores
            return

        if fase == "semis":
            if not self.paulistao_bracket.get("quartas"):
                self._simular_fase_paulistao("quartas")
            vencedores_quartas = self.paulistao_bracket.get("quartas") or []
            if len(vencedores_quartas) < 4:
                return
            confrontos = [
                (vencedores_quartas[0], vencedores_quartas[3]),
                (vencedores_quartas[1], vencedores_quartas[2]),
            ]
            print("\n🏆 SEMIFINAIS — PAULISTÃO A1")
            vencedores = []
            for casa, fora in confrontos:
                g_c, g_f, vencedor, pen_str = self._simular_jogo_mata_mata(casa, fora)
                pen_txt = f" {pen_str}" if pen_str else ""
                print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {vencedor.nome}{pen_txt}")
                vencedores.append(vencedor)
            self.paulistao_bracket["semis"] = vencedores
            self.paulistao_bracket["finalistas"] = vencedores
            return

        if fase == "final_ida":
            if not self.paulistao_bracket.get("finalistas"):
                self._simular_fase_paulistao("semis")
            finalistas = self.paulistao_bracket.get("finalistas") or []
            if len(finalistas) < 2:
                return
            casa, fora = finalistas[0], finalistas[1]
            print("\n🏆 FINAL — IDA — PAULISTÃO A1")
            g_c, g_f, _, _ = self._simular_jogo_mata_mata(casa, fora, permitir_penaltis=False)
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12}")
            self.paulistao_bracket["final_ida"] = (casa, fora, g_c, g_f)
            return

        if fase == "final_volta":
            if not self.paulistao_bracket.get("final_ida"):
                self._simular_fase_paulistao("final_ida")
            final_ida = self.paulistao_bracket.get("final_ida")
            if not final_ida:
                return
            casa_ida, fora_ida, g_ida_c, g_ida_f = final_ida
            casa, fora = fora_ida, casa_ida
            print("\n🏆 FINAL — VOLTA — PAULISTÃO A1")
            g_c, g_f, _, _ = self._simular_jogo_mata_mata(casa, fora, permitir_penaltis=False)
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12}")

            agg_casa_ida = g_ida_c + g_f
            agg_fora_ida = g_ida_f + g_c
            if agg_casa_ida > agg_fora_ida:
                campeao = casa_ida
            elif agg_fora_ida > agg_casa_ida:
                campeao = fora_ida
            else:
                pen_c, pen_f = self._simular_disputa_penaltis(casa, fora)
                campeao = casa if pen_c > pen_f else fora
                print(f"  Disputa de pênaltis: pen ({pen_c}x{pen_f})")
            ano_temporada = self.estado_mundo.get("meta", {}).get("temporada_atual", 2026)
            print(f"\n🎊 ¡{campeao.nome.upper()} É O CAMPEÃO PAULISTA DE {ano_temporada}! 🎊")
            self.paulistao_bracket["campeao"] = campeao
            self.paulistao_mata_mata_simulado = True
            return

    def _classificacao_grupo(self, competicao, clubes_grupo):
        tabela = self.tabelas.get(competicao, {})
        itens = []
        for clube in clubes_grupo:
            itens.append((clube, tabela.get(clube, self._init_linha())))
        return sorted(
            itens,
            key=lambda item: (item[1]["pontos"], item[1]["gols_pro"] - item[1]["gols_contra"], item[1]["gols_pro"]),
            reverse=True,
        )

    def _simular_fase_paulistao_a2(self, fase, evento):
        if fase == "paulistao_a2_quadrangulares":
            if self.paulistao_a2_estado.get("grupos_gerados"):
                return
            classif = self.classificacao("paulistao_a2")
            if len(classif) < 8:
                return
            top8 = [c[0] for c in classif[:8]]
            grupo_2 = [top8[i] for i in [0, 3, 4, 7]]
            grupo_3 = [top8[i] for i in [1, 2, 5, 6]]
            self.paulistao_a2_estado["grupos"] = {"G2": grupo_2, "G3": grupo_3}

            from engine import calendario as cal_mod

            rodadas_g2 = cal_mod._gerar_rodadas_pontos_corridos(grupo_2)
            rodadas_g3 = cal_mod._gerar_rodadas_pontos_corridos(grupo_3)

            novos_eventos = []
            data_inicio = evento["data"].date()
            for idx, rodada in enumerate(rodadas_g2, start=1):
                data_jogo = datetime(data_inicio.year, data_inicio.month, data_inicio.day, 20, 0) + timedelta(days=7 * (idx - 1))
                novos_eventos.append({"rodada": idx, "competicao": "paulistao_a2_g2", "data": data_jogo, "partidas": rodada})
                novos_eventos.append({"rodada": idx, "competicao": "paulistao_a2_g3", "data": data_jogo, "partidas": rodadas_g3[idx - 1]})

            data_final = novos_eventos[-1]["data"] if novos_eventos else evento["data"]
            novos_eventos.append(
                {
                    "competicao": "paulistao_a2",
                    "data": data_final + timedelta(days=7),
                    "fase": "paulistao_a2_semifinal_grupos",
                }
            )

            insert_idx = self.rodada_atual + 1
            self.calendario_completo[insert_idx:insert_idx] = novos_eventos
            for ev in novos_eventos:
                if "partidas" not in ev:
                    continue
                for casa, fora in ev["partidas"]:
                    self.tabelas[ev["competicao"]].setdefault(casa, self._init_linha())
                    self.tabelas[ev["competicao"]].setdefault(fora, self._init_linha())
            self.paulistao_a2_estado["grupos_gerados"] = True
            return

        if fase == "paulistao_a2_semifinal_grupos":
            if self.paulistao_a2_estado.get("semi_gerados"):
                return
            classif_g2 = self.classificacao("paulistao_a2_g2")
            classif_g3 = self.classificacao("paulistao_a2_g3")
            if len(classif_g2) < 2 or len(classif_g3) < 2:
                return
            g2_1, g2_2 = classif_g2[0][0], classif_g2[1][0]
            g3_1, g3_2 = classif_g3[0][0], classif_g3[1][0]
            grupo_1 = [g2_1, g3_2]
            grupo_2 = [g3_1, g2_2]
            self.paulistao_a2_estado["semi_grupos"] = {"S1": grupo_1, "S2": grupo_2}

            from engine import calendario as cal_mod

            rodadas_s1 = cal_mod._gerar_rodadas_pontos_corridos(grupo_1)
            rodadas_s2 = cal_mod._gerar_rodadas_pontos_corridos(grupo_2)

            novos_eventos = []
            data_inicio = evento["data"].date()
            for idx, rodada in enumerate(rodadas_s1, start=1):
                data_jogo = datetime(data_inicio.year, data_inicio.month, data_inicio.day, 20, 0) + timedelta(days=7 * (idx - 1))
                novos_eventos.append({"rodada": idx, "competicao": "paulistao_a2_sf_g1", "data": data_jogo, "partidas": rodada})
                novos_eventos.append({"rodada": idx, "competicao": "paulistao_a2_sf_g2", "data": data_jogo, "partidas": rodadas_s2[idx - 1]})

            data_final = novos_eventos[-1]["data"] if novos_eventos else evento["data"]
            novos_eventos.append(
                {
                    "competicao": "paulistao_a2",
                    "data": data_final + timedelta(days=7),
                    "fase": "paulistao_a2_final",
                }
            )

            insert_idx = self.rodada_atual + 1
            self.calendario_completo[insert_idx:insert_idx] = novos_eventos
            for ev in novos_eventos:
                if "partidas" not in ev:
                    continue
                for casa, fora in ev["partidas"]:
                    self.tabelas[ev["competicao"]].setdefault(casa, self._init_linha())
                    self.tabelas[ev["competicao"]].setdefault(fora, self._init_linha())
            self.paulistao_a2_estado["semi_gerados"] = True
            return

        if fase == "paulistao_a2_final":
            classif_s1 = self.classificacao("paulistao_a2_sf_g1")
            classif_s2 = self.classificacao("paulistao_a2_sf_g2")
            if len(classif_s1) < 1 or len(classif_s2) < 1:
                return
            vencedor_s1 = classif_s1[0][0]
            vencedor_s2 = classif_s2[0][0]
            self.paulistao_a2_estado["acessos"] = [vencedor_s1, vencedor_s2]

            print("\n🏆 FINAL — PAULISTAO A2")
            g_c, g_f, campeao, pen_str = self._simular_jogo_mata_mata(vencedor_s1, vencedor_s2)
            pen_txt = f" {pen_str}" if pen_str else ""
            print(f"  {vencedor_s1.nome:>12} {g_c} x {g_f} {vencedor_s2.nome:<12} -> Campeao: {campeao.nome}{pen_txt}")
            self.paulistao_a2_estado["campeao"] = campeao
            if self.clube_usuario and self.clube_usuario.id in {vencedor_s1.id, vencedor_s2.id}:
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Acesso conquistado",
                    "O clube garantiu o acesso ao Paulistao A1.",
                    prioridade=3,
                )
            if self.clube_usuario and campeao.id == self.clube_usuario.id:
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Titulo estadual",
                    "Parabens! O clube foi campeao do Paulistao A2.",
                    prioridade=2,
                )
            return

    def _simular_fase_cariocao(self, fase):
        if fase != "cariocao_quartas":
            return
        grupos = self.cariocao_estado.get("grupos") or {}
        if not grupos:
            return
        grupo_a = grupos.get("A", [])
        grupo_b = grupos.get("B", [])
        classif_a = self._classificacao_grupo("cariocao_a1", grupo_a)[:4]
        classif_b = self._classificacao_grupo("cariocao_a1", grupo_b)[:4]
        if len(classif_a) < 4 or len(classif_b) < 4:
            return

        a1, a2, a3, a4 = [c[0] for c in classif_a]
        b1, b2, b3, b4 = [c[0] for c in classif_b]
        confrontos = [(a1, b4), (a2, b3), (b1, a4), (b2, a3)]

        print("\n🏆 QUARTAS DE FINAL — CARIOCAO")
        vencedores = []
        for casa, fora in confrontos:
            g_c, g_f, vencedor, pen_str = self._simular_jogo_mata_mata(casa, fora)
            pen_txt = f" {pen_str}" if pen_str else ""
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {vencedor.nome}{pen_txt}")
            vencedores.append(vencedor)

        if len(vencedores) < 4:
            return
        self.cariocao_estado["semifinalistas"] = vencedores
        semi_1 = (vencedores[0], vencedores[3])
        semi_2 = (vencedores[1], vencedores[2])
        print("\n🏆 SEMIFINAIS — CARIOCAO")
        finais = []
        for casa, fora in (semi_1, semi_2):
            g_c, g_f, vencedor, pen_str = self._simular_jogo_mata_mata(casa, fora)
            pen_txt = f" {pen_str}" if pen_str else ""
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {vencedor.nome}{pen_txt}")
            finais.append(vencedor)

        if len(finais) < 2:
            return
        self.cariocao_estado["finalistas"] = finais
        casa, fora = finais[0], finais[1]
        print("\n🏆 FINAL — CARIOCAO")
        g_c, g_f, campeao, pen_str = self._simular_jogo_mata_mata(casa, fora)
        pen_txt = f" {pen_str}" if pen_str else ""
        print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Campeao: {campeao.nome}{pen_txt}")
        campeao.financas += 1_000_000
        self.cariocao_estado["campeao"] = campeao
        if self.clube_usuario and campeao.id == self.clube_usuario.id:
            mensagens.enviar_mensagem(
                self.estado_mundo["meta"]["temporada_atual"],
                "Diretoria",
                "Titulo estadual",
                "Parabens! O clube conquistou o Cariocao e o premio estadual.",
                prioridade=3,
            )
        return

    def _ordenar_por_rnc(self, clubes):
        rnc_atual = self.estado_mundo["meta"].get("rnc_atual", {})
        return rankings.ordenar_clubes_por_rnc(clubes, rnc_atual)

    def _pares_seeded(self, clubes):
        ordenados = self._ordenar_por_rnc(clubes)
        pares = []
        total = len(ordenados)
        for i in range(total // 2):
            pares.append((ordenados[i], ordenados[-1 - i]))
        return pares

    def _premiar_copa_brasil(self, clube, fase):
        grupo = rankings.grupo_copa_brasil(clube)
        if fase in ("f1", "f2", "f3", "f4"):
            total = COPA_BRASIL_PREMIACAO_2026["grupos"][grupo][fase]
            pago = self.copa_brasil_estado["premio_fase"].get(clube.id, 0)
            delta = max(0, total - pago)
            if delta > 0:
                clube.financas += delta
                self.copa_brasil_estado["premio_fase"][clube.id] = total
            return
        clube.financas += COPA_BRASIL_PREMIACAO_2026["fase_unificada"]

    def _simular_copa_jogo_unico(self, clubes, fase, titulo):
        pares = self._pares_seeded(clubes)
        vencedores = []
        print(f"\n🏆 {titulo.upper()} — COPA DO BRASIL")
        for casa, fora in pares:
            self._premiar_copa_brasil(casa, fase)
            self._premiar_copa_brasil(fora, fase)
            self.copa_brasil_estado["fase_por_clube"][casa.id] = fase
            self.copa_brasil_estado["fase_por_clube"][fora.id] = fase
            g_c, g_f, vencedor, pen_str = self._simular_jogo_mata_mata(casa, fora)
            pen_txt = f" {pen_str}" if pen_str else ""
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Passa: {vencedor.nome}{pen_txt}")
            vencedores.append(vencedor)
        return vencedores

    def _simular_copa_ida_volta(self, clubes, fase, titulo):
        ordenados = []
        for casa, fora in self._pares_seeded(clubes):
            ordenados.extend([casa, fora])
        for clube in clubes:
            self._premiar_copa_brasil(clube, fase)
            self.copa_brasil_estado["fase_por_clube"][clube.id] = fase
        vencedores, perdedores = self._rodada_ida_volta(ordenados, titulo)
        return vencedores, perdedores

    def _simular_fase_copa_brasil(self, fase):
        participantes = self.copa_brasil_estado.get("participantes", {})

        if fase == "cdb_f1":
            if self.copa_brasil_estado.get("f1_vencedores") is not None:
                return
            vencedores = self._simular_copa_jogo_unico(participantes.get("f1", []), "f1", "1a fase")
            self.copa_brasil_estado["f1_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para a 2a fase da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f2":
            if self.copa_brasil_estado.get("f2_vencedores") is not None:
                return
            clubes = (self.copa_brasil_estado.get("f1_vencedores") or []) + participantes.get("f2_novos", [])
            vencedores = self._simular_copa_jogo_unico(clubes, "f2", "2a fase")
            self.copa_brasil_estado["f2_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para a 3a fase da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f3":
            if self.copa_brasil_estado.get("f3_vencedores") is not None:
                return
            clubes = (self.copa_brasil_estado.get("f2_vencedores") or []) + participantes.get("f3_novos", [])
            vencedores = self._simular_copa_jogo_unico(clubes, "f3", "3a fase")
            self.copa_brasil_estado["f3_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para a 4a fase da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f4":
            if self.copa_brasil_estado.get("f4_vencedores") is not None:
                return
            clubes = self.copa_brasil_estado.get("f3_vencedores") or []
            vencedores = self._simular_copa_jogo_unico(clubes, "f4", "4a fase")
            self.copa_brasil_estado["f4_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para a fase de ida e volta (5a fase).",
                    prioridade=2,
                )
            return

        if fase == "cdb_f5_ida":
            if self.copa_brasil_estado.get("f5_vencedores") is not None:
                return
            clubes = (self.copa_brasil_estado.get("f4_vencedores") or []) + participantes.get("f5_serie_a", [])
            vencedores, _ = self._simular_copa_ida_volta(clubes, "f5", "5a fase")
            self.copa_brasil_estado["f5_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para as oitavas da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f6_ida":
            if self.copa_brasil_estado.get("f6_vencedores") is not None:
                return
            clubes = self.copa_brasil_estado.get("f5_vencedores") or []
            vencedores, _ = self._simular_copa_ida_volta(clubes, "f6", "oitavas")
            self.copa_brasil_estado["f6_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para as quartas da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f7_ida":
            if self.copa_brasil_estado.get("f7_vencedores") is not None:
                return
            clubes = self.copa_brasil_estado.get("f6_vencedores") or []
            vencedores, _ = self._simular_copa_ida_volta(clubes, "f7", "quartas")
            self.copa_brasil_estado["f7_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para as semifinais da Copa do Brasil.",
                    prioridade=2,
                )
            return

        if fase == "cdb_f8_ida":
            if self.copa_brasil_estado.get("f8_vencedores") is not None:
                return
            clubes = self.copa_brasil_estado.get("f7_vencedores") or []
            vencedores, _ = self._simular_copa_ida_volta(clubes, "f8", "semis")
            self.copa_brasil_estado["f8_vencedores"] = vencedores
            if self.clube_usuario and any(c.id == self.clube_usuario.id for c in vencedores):
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube avancou para a final da Copa do Brasil.",
                    prioridade=3,
                )
            return

        if fase == "cdb_final":
            if self.copa_brasil_estado.get("campeao_id") is not None:
                return
            finalistas = self.copa_brasil_estado.get("f8_vencedores") or []
            if len(finalistas) < 2:
                return
            casa, fora = finalistas[0], finalistas[1]
            self._premiar_copa_brasil(casa, "final")
            self._premiar_copa_brasil(fora, "final")
            print("\n🏆 FINAL — COPA DO BRASIL")
            g_c, g_f, campeao, pen_str = self._simular_jogo_mata_mata(casa, fora)
            pen_txt = f" {pen_str}" if pen_str else ""
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12} -> Campeao: {campeao.nome}{pen_txt}")
            campeao.financas += COPA_BRASIL_PREMIACAO_2026["premio_titulo"]
            self.copa_brasil_estado["campeao_id"] = campeao.id
            self.copa_brasil_estado["fase_por_clube"][casa.id] = "final"
            self.copa_brasil_estado["fase_por_clube"][fora.id] = "final"
            if self.clube_usuario and campeao.id == self.clube_usuario.id:
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Copa do Brasil",
                    "O clube conquistou a Copa do Brasil e o maior premio da temporada.",
                    prioridade=3,
                )
            return

    def _simular_fase_serie_c(self, fase, evento):
        if fase == "serie_c_grupos":
            if self.serie_c_estado.get("grupos_gerados"):
                return
            classif = self.classificacao("bra_c_fase1")
            if len(classif) < 8:
                return
            top8 = [c[0] for c in classif[:8]]
            grupo_a = [top8[i] for i in [0, 3, 4, 7]]
            grupo_b = [top8[i] for i in [1, 2, 5, 6]]
            self.serie_c_estado["grupos"] = {"A": grupo_a, "B": grupo_b}

            from engine import calendario as cal_mod
            rodadas_a = cal_mod._gerar_rodadas_pontos_corridos(grupo_a)
            rodadas_b = cal_mod._gerar_rodadas_pontos_corridos(grupo_b)

            novos_eventos = []
            data_inicio = evento["data"].date()
            for idx, rodada in enumerate(rodadas_a, start=1):
                data_jogo = datetime(data_inicio.year, data_inicio.month, data_inicio.day, 20, 0) + timedelta(days=7 * (idx - 1))
                novos_eventos.append({"rodada": idx, "competicao": "bra_c_grupo_a", "data": data_jogo, "partidas": rodada})
                novos_eventos.append({"rodada": idx, "competicao": "bra_c_grupo_b", "data": data_jogo, "partidas": rodadas_b[idx - 1]})

            data_final = novos_eventos[-1]["data"]
            finais = [
                {"competicao": "bra_c", "data": data_final + timedelta(days=7), "fase": "serie_c_final_ida"},
                {"competicao": "bra_c", "data": data_final + timedelta(days=14), "fase": "serie_c_final_volta"},
            ]

            insert_idx = self.rodada_atual + 1
            self.calendario_completo[insert_idx:insert_idx] = novos_eventos + finais
            for ev in novos_eventos:
                for casa, fora in ev["partidas"]:
                    self.tabelas[ev["competicao"]].setdefault(casa, self._init_linha())
                    self.tabelas[ev["competicao"]].setdefault(fora, self._init_linha())
            self.serie_c_estado["grupos_gerados"] = True
            return

        if fase == "serie_c_final_ida":
            grupo_a = self.serie_c_estado.get("grupos", {}).get("A", [])
            grupo_b = self.serie_c_estado.get("grupos", {}).get("B", [])
            if not grupo_a or not grupo_b:
                return
            lider_a = self.classificacao("bra_c_grupo_a")[0][0]
            lider_b = self.classificacao("bra_c_grupo_b")[0][0]
            casa, fora = lider_a, lider_b
            print("\n🏆 FINAL — IDA — SÉRIE C")
            g_c, g_f, _, _ = self._simular_jogo_mata_mata(casa, fora, permitir_penaltis=False)
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12}")
            self.serie_c_estado["final_ida"] = (casa, fora, g_c, g_f)
            return

        if fase == "serie_c_final_volta":
            if not self.serie_c_estado.get("final_ida"):
                self._simular_fase_serie_c("serie_c_final_ida", evento)
            final_ida = self.serie_c_estado.get("final_ida")
            if not final_ida:
                return
            casa_ida, fora_ida, g_ida_c, g_ida_f = final_ida
            casa, fora = fora_ida, casa_ida
            print("\n🏆 FINAL — VOLTA — SÉRIE C")
            g_c, g_f, _, _ = self._simular_jogo_mata_mata(casa, fora, permitir_penaltis=False)
            print(f"  {casa.nome:>12} {g_c} x {g_f} {fora.nome:<12}")

            agg_casa_ida = g_ida_c + g_f
            agg_fora_ida = g_ida_f + g_c
            if agg_casa_ida > agg_fora_ida:
                campeao = casa_ida
            elif agg_fora_ida > agg_casa_ida:
                campeao = fora_ida
            else:
                pen_c, pen_f = self._simular_disputa_penaltis(casa, fora)
                campeao = casa if pen_c > pen_f else fora
                print(f"  Disputa de pênaltis: pen ({pen_c}x{pen_f})")
            print(f"\n🎊 {campeao.nome.upper()} É O CAMPEÃO DA SÉRIE C! 🎊")
            self.serie_c_estado["campeao"] = campeao
            return

    def _simular_fase_serie_d(self, fase, evento):
        if fase != "serie_d_mata_mata":
            return
        if self.serie_d_estado.get("mata_mata_gerado"):
            return

        classificados = self._classificados_serie_d()
        total_esperado = SERIE_D_FORMATO["grupos"] * SERIE_D_FORMATO["classificados_por_grupo"]

        if len(classificados) < 2:
            print("\n⚠️ Não foi possível montar o mata-mata da Série D (classificados insuficientes).")
            return

        if len(classificados) < total_esperado:
            print(
                f"\n⚠️ Mata-mata da Série D com {len(classificados)} classificados (esperado: {total_esperado})."
            )

        if len(classificados) % 2 == 1:
            print("\n⚠️ Número ímpar de classificados na Série D; ajustando chaves automaticamente.")
            classificados = classificados[:-1]

        random.shuffle(classificados)
        print("\n🏆 INÍCIO DO MATA-MATA — SÉRIE D")
        v32, _ = self._rodada_ida_volta(classificados, "32 avos")
        v16, _ = self._rodada_ida_volta(v32, "16 avos")
        v8, _ = self._rodada_ida_volta(v16, "oitavas")
        v4, perdedores_quartas = self._rodada_ida_volta(v8, "quartas")
        v2, _ = self._rodada_ida_volta(v4, "semis")
        campeao, _ = self._rodada_ida_volta(v2, "final")

        random.shuffle(perdedores_quartas)
        playoff_winners, _ = self._rodada_ida_volta(perdedores_quartas, "playoff acesso")
        acessos = v4 + playoff_winners
        self.serie_d_estado["acessos"] = acessos
        self.serie_d_estado["campeao"] = campeao[0] if campeao else None
        self.serie_d_estado["mata_mata_gerado"] = True

        if self.clube_usuario and any(c.id == self.clube_usuario.id for c in acessos):
            mensagens.enviar_mensagem(
                self.estado_mundo["meta"]["temporada_atual"],
                "Diretoria",
                "Acesso garantido!",
                f"O {self.clube_usuario.nome} conquistou o acesso à Série C.",
                prioridade=3,
            )

    def _classificados_serie_d(self):
        grupos_ids = sorted([k for k in self.tabelas.keys() if k.startswith("bra_d_g")])
        classificados = []
        for gid in grupos_ids:
            classif = self.classificacao(gid)
            classificados.extend([c[0] for c in classif[:SERIE_D_FORMATO["classificados_por_grupo"]]])

        vistos = set()
        unicos = []
        for clube in classificados:
            if clube.id in vistos:
                continue
            vistos.add(clube.id)
            unicos.append(clube)
        return unicos

    def _rodada_ida_volta(self, times, fase_nome, mostrar=True):
        times = list(times)
        if len(times) < 2:
            return [], []
        if len(times) % 2 == 1:
            times = times[:-1]

        vencedores = []
        perdedores = []
        if mostrar:
            print(f"\n🎯 {fase_nome.upper()}")
        for i in range(0, len(times), 2):
            casa = times[i]
            fora = times[i + 1]
            g1_c, g1_f, _, _ = self._simular_jogo_mata_mata(casa, fora, permitir_penaltis=False)
            g2_c, g2_f, _, _ = self._simular_jogo_mata_mata(fora, casa, permitir_penaltis=False)
            agg_c = g1_c + g2_f
            agg_f = g1_f + g2_c
            if agg_c > agg_f:
                vencedor, perdedor = casa, fora
                pen_txt = ""
            elif agg_f > agg_c:
                vencedor, perdedor = fora, casa
                pen_txt = ""
            else:
                pen_c, pen_f = self._simular_disputa_penaltis(casa, fora)
                vencedor = casa if pen_c > pen_f else fora
                perdedor = fora if vencedor == casa else casa
                pen_txt = f" pen ({pen_c}x{pen_f})"
            if mostrar:
                print(
                    f"  {casa.nome:>12} {g1_c} x {g1_f} {fora.nome:<12}  /  "
                    f"{fora.nome:>12} {g2_c} x {g2_f} {casa.nome:<12}  -> Passa: {vencedor.nome} (agg {agg_c}x{agg_f}{pen_txt})"
                )
            vencedores.append(vencedor)
            perdedores.append(perdedor)
        return vencedores, perdedores

    def _simular_playoffs_serie_b(self):
        classif = self.classificacao("bra_b")
        terceiro, quarto, quinto, sexto = classif[2][0], classif[3][0], classif[4][0], classif[5][0]

        def jogo_unico(mandante, visitante):
            venda_mando = mandante.deve_vender_mando(visitante) if hasattr(mandante, "deve_vender_mando") else False
            g_m, g_v = simular_partida(mandante, visitante, venda_mando=venda_mando)
            if g_m == g_v:
                g_m += 1
            return mandante if g_m > g_v else visitante, g_m, g_v

        v1, g1, g2 = jogo_unico(terceiro, sexto)
        v2, g3, g4 = jogo_unico(quarto, quinto)

        print("\n🎯 PLAYOFFS DE ACESSO — SÉRIE B")
        print(f"{terceiro.nome} {g1} x {g2} {sexto.nome}  -> classificado: {v1.nome}")
        print(f"{quarto.nome} {g3} x {g4} {quinto.nome}  -> classificado: {v2.nome}")
        return [v1.nome, v2.nome]

    def exibir_fechamento_temporada(self):
        print("\n🏁 Fim da temporada")
        if "paulistao_a1" in self.tabelas:
            self.exibir_tabela("paulistao_a1")
            if not self.paulistao_mata_mata_simulado:
                self._simular_mata_mata_paulistao()
        if "paulistao_a2" in self.tabelas:
            self.exibir_tabela("paulistao_a2")
            if self.paulistao_a2_estado.get("campeao") is None:
                self._simular_fase_paulistao_a2("paulistao_a2_quadrangulares", {"data": datetime.now()})
        if "cariocao_a1" in self.tabelas:
            self.exibir_tabela("cariocao_a1")
            if self.cariocao_estado.get("campeao") is None:
                self._simular_fase_cariocao("cariocao_quartas")
        if "bra_a" in self.tabelas:
            self.exibir_tabela("bra_a")
            self._mostrar_regra_a()
        if "bra_b" in self.tabelas:
            self.exibir_tabela("bra_b")
            self._mostrar_regra_b()
        if "bra_c_fase1" in self.tabelas:
            self.exibir_tabela("bra_c_fase1")
            if "bra_c_grupo_a" in self.tabelas:
                self.exibir_tabela("bra_c_grupo_a")
            if "bra_c_grupo_b" in self.tabelas:
                self.exibir_tabela("bra_c_grupo_b")
            self._mostrar_regra_c()
        if any(k.startswith("bra_d_g") for k in self.tabelas.keys()):
            self._mostrar_regra_d()

        resultados = self._avaliar_objetivos()
        mensagem_resultado_objetivos(resultados)
        self._aplicar_consequencias_objetivos(resultados)
        if self.clube_usuario:
            pendentes = [r["texto"] for r in resultados if not r["cumprido"]]
            if pendentes:
                corpo = "Objetivos não cumpridos: " + "; ".join(pendentes) + "."
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Balanço da temporada",
                    corpo,
                    prioridade=2,
                )
            else:
                mensagens.enviar_mensagem(
                    self.estado_mundo["meta"]["temporada_atual"],
                    "Diretoria",
                    "Balanço da temporada",
                    "Todos os objetivos foram cumpridos. A diretoria está satisfeita.",
                    prioridade=1,
                )
        self._atualizar_estado_mundo(resultados)

    def _mostrar_regra_a(self):
        classif = self.classificacao("bra_a")
        rebaixados = [c.nome for c, _ in classif[-4:]]
        print(f"\n⬇️ Rebaixados Série A: {', '.join(rebaixados)}")

    def _mostrar_regra_b(self):
        classif = self.classificacao("bra_b")
        diretos = [c.nome for c, _ in classif[:2]]
        playoff = [c.nome for c, _ in classif[2:6]]
        print(f"\n⬆️ Acesso direto Série B: {', '.join(diretos)}")
        print(f"🎯 Playoffs: {playoff[0]} x {playoff[3]} e {playoff[1]} x {playoff[2]} (jogo único)")
        vencedores = self._simular_playoffs_serie_b()
        print(f"✅ Vagas via playoff: {', '.join(vencedores)}")
        print(f"⬇️ Rebaixados Série B: {', '.join([c.nome for c, _ in classif[-4:]])}")

    def _calcular_resultados_serie_c(self):
        ano = self.estado_mundo["meta"]["temporada_atual"]
        regras = self._regras_serie_c(ano)
        classif_fase1 = self.classificacao("bra_c_fase1")
        rebaixados = [c[0] for c in classif_fase1[-regras["rebaixados"] :]] if classif_fase1 else []
        acessos = []
        if "bra_c_grupo_a" in self.tabelas and "bra_c_grupo_b" in self.tabelas:
            grupo_a = self.classificacao("bra_c_grupo_a")
            grupo_b = self.classificacao("bra_c_grupo_b")
            if len(grupo_a) >= 2 and len(grupo_b) >= 2:
                acessos = [grupo_a[0][0], grupo_a[1][0], grupo_b[0][0], grupo_b[1][0]]
        self.serie_c_estado["acessos"] = acessos
        self.serie_c_estado["rebaixados"] = rebaixados
        return acessos, rebaixados

    def _mostrar_regra_c(self):
        acessos, rebaixados = self._calcular_resultados_serie_c()
        if acessos:
            print(f"\n⬆️ Acesso Série C: {', '.join([c.nome for c in acessos])}")
        if rebaixados:
            print(f"⬇️ Rebaixados Série C: {', '.join([c.nome for c in rebaixados])}")

    def _mostrar_regra_d(self):
        if not self.serie_d_estado.get("mata_mata_gerado"):
            self._simular_fase_serie_d("serie_d_mata_mata", {"fase": "serie_d_mata_mata"})
        acessos = self.serie_d_estado.get("acessos", [])
        campeao = self.serie_d_estado.get("campeao")
        if acessos:
            print(f"\n⬆️ Acesso Série D: {', '.join([c.nome for c in acessos])}")
        if campeao:
            print(f"🏆 Campeão Série D: {campeao.nome} (entra na 3ª fase da Copa do Brasil no próximo ano)")

    @staticmethod
    def _normalizar_competicoes_clube(competicoes):
        nacionais = ("bra_a", "bra_b", "bra_c", "bra_d")
        unicos = []
        for comp in competicoes:
            if comp not in unicos:
                unicos.append(comp)
        nacionais_encontradas = [c for c in unicos if c in nacionais]
        if len(nacionais_encontradas) <= 1:
            return unicos
        principal = nacionais_encontradas[0]
        return [c for c in unicos if c not in nacionais or c == principal]

    def _atualizar_estado_mundo(self, resultados_objetivos):
        estado = self.estado_mundo
        mapa_estado = {c["id"]: c for c in estado.get("clubes", [])}
        ano_atual = estado["meta"].get("temporada_atual", 2026)

        acessos_c, rebaixados_c = ([], [])
        if "bra_c_fase1" in self.tabelas:
            acessos_c, rebaixados_c = self._calcular_resultados_serie_c()
        acessos_d = self.serie_d_estado.get("acessos", [])
        campeao_d = self.serie_d_estado.get("campeao")
        campeao_c = self.serie_c_estado.get("campeao")
        acessos_a2 = {c.id for c in self.paulistao_a2_estado.get("acessos", [])}

        ids_acesso_c = {c.id for c in acessos_c}
        ids_rebaix_c = {c.id for c in rebaixados_c}
        ids_acesso_d = {c.id for c in acessos_d}

        campeoes = {}
        for comp in self.tabelas:
            classif_comp = self.classificacao(comp)
            if classif_comp:
                campeoes[comp] = classif_comp[0][0]
        if self.copa_brasil_estado.get("campeao_id"):
            campeao_copa = next(
                (c for c in self.todos_clubes.values() if c.id == self.copa_brasil_estado["campeao_id"]),
                None,
            )
            if campeao_copa:
                campeoes["copa_brasil"] = campeao_copa

        todos_clubes = list(self.todos_clubes.values())
        for clube in todos_clubes:
            titulos = sum(1 for camp in campeoes.values() if camp.id == clube.id)
            pos_bra_a = next(
                (i for i, (c, _) in enumerate(self.classificacao("bra_a"), start=1) if c.id == clube.id),
                None,
            )
            elite_assiduo = pos_bra_a is not None and pos_bra_a <= 16
            permaneceu_elite = elite_assiduo

            clube.atualizar_reputacao_financas_fim_ano(
                titulos=titulos,
                elite_assiduo=elite_assiduo,
                permaneceu_elite=permaneceu_elite,
            )

            competicoes = list(clube.competicoes)
            if clube.id in ids_acesso_c and "bra_c" in competicoes:
                competicoes = [c for c in competicoes if c != "bra_c"]
                competicoes.append("bra_b")
            if clube.id in ids_rebaix_c and "bra_c" in competicoes:
                competicoes = [c for c in competicoes if c != "bra_c"]
                competicoes.append("bra_d")
            if clube.id in ids_acesso_d and "bra_d" in competicoes:
                competicoes = [c for c in competicoes if c != "bra_d"]
                competicoes.append("bra_c")
            if clube.id in acessos_a2:
                competicoes = [c for c in competicoes if c != "paulistao_a2"]
                if "paulistao_a1" not in competicoes:
                    competicoes.append("paulistao_a1")
            clube.competicoes = self._normalizar_competicoes_clube(competicoes)

            estado_vaga_anterior = getattr(clube, "estado_vaga", "sem_divisao")
            clube.estado_vaga = clube._estado_vaga_por_competicoes()
            if estado_vaga_anterior != "sem_divisao" and clube.estado_vaga == "sem_divisao":
                clube.patrocinio_penalizado = True
                if self.clube_usuario and clube.id == self.clube_usuario.id:
                    mensagens.enviar_mensagem(
                        ano_atual,
                        "Diretoria",
                        "Alerta financeiro grave",
                        "O clube perdeu a divisao nacional e pode sofrer ate 60% de queda em patrocinio.",
                        prioridade=3,
                    )
            elif clube.estado_vaga != "sem_divisao":
                clube.patrocinio_penalizado = False

        classificacoes = {}
        if "bra_a" in self.tabelas:
            classificacoes["bra_a"] = self.classificacao("bra_a")
        if "bra_b" in self.tabelas:
            classificacoes["bra_b"] = self.classificacao("bra_b")
        if "bra_c_fase1" in self.tabelas:
            classificacoes["bra_c"] = self.classificacao("bra_c_fase1")

        pontos_ano = rankings.calcular_pontos_temporada(todos_clubes, classificacoes, self.copa_brasil_estado)
        historico = rankings.atualizar_historico_rnc(estado["meta"].get("rnc_historico"), ano_atual, pontos_ano)
        rnc_atual = rankings.calcular_rnc_atual(historico, ano_atual)
        ordenados = rankings.ordenar_clubes_por_rnc(todos_clubes, rnc_atual)
        rankings.aplicar_rnc_em_clubes(ordenados, rnc_atual)
        rnf_atual = rankings.calcular_rnf(rnc_atual, todos_clubes)

        for clube in todos_clubes:
            mapa_estado[clube.id] = clube.to_dict()

        estado["clubes"] = list(mapa_estado.values())
        estado["meta"]["rnc_historico"] = historico
        estado["meta"]["rnc_atual"] = rnc_atual
        estado["meta"]["rnf_atual"] = rnf_atual
        estado["meta"]["temporada_atual"] = ano_atual + 1
        if campeao_d:
            estado["meta"]["copa_brasil_fase3"] = campeao_d.id
        if campeao_c:
            estado["meta"]["serie_c_campeao"] = campeao_c.id
        if self.copa_brasil_estado.get("campeao_id"):
            estado["meta"]["copa_brasil_campeao"] = self.copa_brasil_estado["campeao_id"]
        estado["meta"].pop("data_atual", None)
        estado["meta"].pop("season_runtime", None)
        self.estado_mundo = estado

    def obter_estado_mundo(self):
        meta = self.estado_mundo.setdefault("meta", {})
        self._persistir_classificacoes_no_banco()
        if self.rodada_atual < len(self.calendario_completo):
            meta["season_runtime"] = self._snapshot_runtime_temporada()
        else:
            meta.pop("season_runtime", None)
        return self.estado_mundo
