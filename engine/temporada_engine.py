from collections import defaultdict
from datetime import date, datetime, timedelta
from core.liga import Liga
import random

from engine.calendario import (
    gerar_calendario_brasileirao,
    gerar_calendario_paulistao,
    gerar_calendario_serie_c,
    gerar_calendario_serie_d,
)
from engine.simulador import simular_partida
from engine import noticias, mensagens
from ui.mensagens import mensagem_resultado_objetivos
import db_manager
from data.database import SERIE_C_EXPANSAO, SERIE_D_FORMATO


class TemporadaEngine:
    def __init__(
        self,
        liga,
        clube_usuario=None,
        clubes_paulistao=None,
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
        self.serie_c_estado = {"grupos_gerados": False, "grupos": {}}
        self.serie_d_estado = {"mata_mata_gerado": False, "quartas_perdedores": [], "acessos": []}

        self.calendario_completo = []
        if clubes_paulistao:
            self.calendario_completo.extend(gerar_calendario_paulistao(clubes_paulistao))
        comp_nacional = competicao_id or ("bra_a" if "Série A" in liga.nome else "bra_b")
        inicio_nacional = date(2026, 3, 29) if clubes_paulistao else date(2026, 1, 31)
        if comp_nacional == "bra_c":
            self.calendario_completo.extend(gerar_calendario_serie_c(liga.clubes, self.estado_mundo["meta"]["temporada_atual"]))
        elif comp_nacional == "bra_d":
            self.calendario_completo.extend(gerar_calendario_serie_d(liga.clubes, self.estado_mundo["meta"]["temporada_atual"]))
        else:
            self.calendario_completo.extend(gerar_calendario_brasileirao(liga.clubes, comp_nacional, inicio_override=inicio_nacional))
        self.calendario_completo.sort(key=lambda x: x["data"])

        try:
            db_manager.salvar_calendario(comp_nacional, self.estado_mundo["meta"]["temporada_atual"], self.calendario_completo)
        except Exception:
            pass

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

        self._preparar_clubes_para_temporada(clubes_paulistao)

    @staticmethod
    def _init_linha():
        return {"pontos": 0, "vitorias": 0, "empates": 0, "derrotas": 0, "gols_pro": 0, "gols_contra": 0}

    @staticmethod
    def _regras_serie_c(ano):
        regras = SERIE_C_EXPANSAO[0]
        for etapa in SERIE_C_EXPANSAO:
            if ano >= etapa["ano"]:
                regras = etapa
        return regras

    def _preparar_clubes_para_temporada(self, clubes_paulistao):
        todos = set(self.liga.clubes)
        if clubes_paulistao:
            todos.update(clubes_paulistao)
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
            data_txt = evento["data"].strftime("%d/%m/%Y %H:%M")

            mostrar_evento = self._deve_exibir_evento(evento)
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
                return False if not mostrou_evento else True

            if mostrar_evento:
                mostrou_evento = True
                return True
        return False

    def jogar_temporada_completa(self):
        print(f"\n🏁 Início da temporada — {self.liga.nome}\n")
        while self.simular_proxima_rodada():
            pass

    def _jogar_rodada(self, evento, mostrar_evento=True):
        if "partidas" not in evento:
            if evento.get("competicao") == "paulistao_a1" and evento.get("fase"):
                self._simular_fase_paulistao(evento["fase"])
                return
            fase = evento.get("fase")
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
            self._registrar_partida(comp, casa, fora, gols_casa, gols_fora, rodada=evento.get("rodada"))
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

    def _registrar_partida(self, competicao, casa, fora, gols_casa, gols_fora, rodada=None):
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
        pos_liga = self._posicao_clube(self._competicao_liga_clube(self.clube_usuario))
        base_ok = len([j for j in self.clube_usuario.elenco if getattr(j, "origem_base", False) and j.jogos_temporada >= 5]) >= 3

        for obj in self.objetivos:
            cumprido = False
            if obj["id"] == "paulistao_semifinal":
                cumprido = pos_paul is not None and pos_paul <= 4
            elif obj["id"] == "paulistao_quartas":
                cumprido = pos_paul is not None and pos_paul <= 8
            elif obj["id"] == "liga_top":
                if "bra_a" in self.clube_usuario.competicoes:
                    limite = 8 if self.clube_usuario.reputacao_tier >= 9 else 12
                    cumprido = pos_liga is not None and pos_liga <= limite
                else:
                    limite = 6 if self.clube_usuario.reputacao_tier >= 5 else 10
                    cumprido = pos_liga is not None and pos_liga <= limite
            elif obj["id"] == "base":
                cumprido = base_ok
            resultados.append({"texto": obj["texto"], "cumprido": cumprido})
        return resultados

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

        print(f"\n🎊 ¡{campeao.nome.upper()} É O CAMPEÃO PAULISTA DE 2026! 🎊")
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
            print(f"\n🎊 ¡{campeao.nome.upper()} É O CAMPEÃO PAULISTA DE 2026! 🎊")
            self.paulistao_bracket["campeao"] = campeao
            self.paulistao_mata_mata_simulado = True
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

    def _atualizar_estado_mundo(self, resultados_objetivos):
        estado = self.estado_mundo
        mapa_estado = {c["id"]: c for c in estado.get("clubes", [])}

        acessos_c, rebaixados_c = ([], [])
        if "bra_c_fase1" in self.tabelas:
            acessos_c, rebaixados_c = self._calcular_resultados_serie_c()
        acessos_d = self.serie_d_estado.get("acessos", [])
        campeao_d = self.serie_d_estado.get("campeao")

        ids_acesso_c = {c.id for c in acessos_c}
        ids_rebaix_c = {c.id for c in rebaixados_c}
        ids_acesso_d = {c.id for c in acessos_d}

        campeoes = {}
        for comp in self.tabelas:
            classif_comp = self.classificacao(comp)
            if classif_comp:
                campeoes[comp] = classif_comp[0][0]

        todos_clubes = {c for e in self.calendario_completo if "partidas" in e for p in e["partidas"] for c in p}
        for clube in todos_clubes:
            titulos = sum(1 for camp in campeoes.values() if camp.id == clube.id)
            pos_bra_a = next((i for i, (c, _) in enumerate(self.classificacao("bra_a"), start=1) if c.id == clube.id), None)
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
            clube.competicoes = competicoes

            mapa_estado[clube.id] = clube.to_dict()

        estado["clubes"] = list(mapa_estado.values())
        estado["meta"]["temporada_atual"] = estado["meta"].get("temporada_atual", 2026) + 1
        if campeao_d:
            estado["meta"]["copa_brasil_fase3"] = campeao_d.id
        self.estado_mundo = estado

    def obter_estado_mundo(self):
        return self.estado_mundo
