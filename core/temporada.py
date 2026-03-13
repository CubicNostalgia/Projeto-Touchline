from collections import defaultdict
from datetime import date
import random

from engine.calendario import gerar_calendario_brasileirao, gerar_calendario_paulistao
from engine.simulador import simular_partida
from ui.mensagens import mensagem_resultado_objetivos


class Temporada:
    def __init__(self, liga, clube_usuario=None, clubes_paulistao=None, objetivos=None, estado_mundo_inicial=None):
        self.liga = liga
        self.clube_usuario = clube_usuario
        self.objetivos = objetivos or []
        self.rodada_atual = 0
        self.estado_mundo = estado_mundo_inicial or {"meta": {"temporada_atual": 2026}, "clubes": []}
        self.paulistao_bracket = {"quartas": None, "semis": None, "finalistas": None, "final_ida": None, "campeao": None}
        self.paulistao_mata_mata_simulado = False

        self.calendario_completo = []
        if clubes_paulistao:
            self.calendario_completo.extend(gerar_calendario_paulistao(clubes_paulistao))
        comp_nacional = "bra_a" if "Série A" in liga.nome else "bra_b"
        inicio_nacional = date(2026, 3, 29) if clubes_paulistao else date(2026, 1, 31)
        self.calendario_completo.extend(gerar_calendario_brasileirao(liga.clubes, comp_nacional, inicio_override=inicio_nacional))
        self.calendario_completo.sort(key=lambda x: x["data"])

        self.tabelas = defaultdict(dict)
        for evento in self.calendario_completo:
            if "partidas" not in evento:
                continue

            comp = evento["competicao"]
            for casa, fora in evento["partidas"]:
                self.tabelas[comp].setdefault(casa, self._init_linha())
                self.tabelas[comp].setdefault(fora, self._init_linha())

        self._preparar_clubes_para_temporada(clubes_paulistao)

    @staticmethod
    def _init_linha():
        return {"pontos": 0, "vitorias": 0, "empates": 0, "derrotas": 0, "gols_pro": 0, "gols_contra": 0}

    def _preparar_clubes_para_temporada(self, clubes_paulistao):
        todos = set(self.liga.clubes)
        if clubes_paulistao:
            todos.update(clubes_paulistao)
        for clube in todos:
            crise = getattr(clube, "status_financeiro", "estavel") == "crise"
            if hasattr(clube, "processar_transicao_base"):
                clube.processar_transicao_base(inicio_temporada=True, crise_financeira=crise)

    def simular_proxima_rodada(self):
        if self.rodada_atual >= len(self.calendario_completo):
            print("\n🏁 A temporada já terminou.\n")
            return False

        evento = self.calendario_completo[self.rodada_atual]
        data_txt = evento["data"].strftime("%d/%m/%Y %H:%M")

        nome_evento = evento.get("competicao", "PAUSA NO CALENDÁRIO").upper()
        rodada_str = f" — Rodada {evento['rodada']}" if "rodada" in evento else ""

        print(f"\n🕒 {nome_evento}{rodada_str} — {data_txt}")

        if self.rodada_atual > 0:
            dias = (evento["data"].date() - self.calendario_completo[self.rodada_atual - 1]["data"].date()).days
            todos = {c for e in self.calendario_completo if "partidas" in e for p in e["partidas"] for c in p}
            for clube in todos:
                clube.recuperar_elenco(max(1, dias))

        self._jogar_rodada(evento)
        self.rodada_atual += 1

        if self.rodada_atual == len(self.calendario_completo):
            self.exibir_fechamento_temporada()
        return True

    def jogar_temporada_completa(self):
        print(f"\n🏁 Início da temporada — {self.liga.nome}\n")
        while self.simular_proxima_rodada():
            pass

    def _jogar_rodada(self, evento):
        if "partidas" not in evento:
            if evento.get("competicao") == "paulistao_a1" and evento.get("fase"):
                self._simular_fase_paulistao(evento["fase"])
            return

        comp = evento["competicao"]
        for casa, fora in evento["partidas"]:
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
            self._registrar_partida(comp, casa, fora, gols_casa, gols_fora)
            casa.aplicar_partida()
            fora.aplicar_partida()
            print(f"  {casa.nome:>12} {gols_casa} x {gols_fora} {fora.nome:<12}")

    def _registrar_partida(self, competicao, casa, fora, gols_casa, gols_fora):
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
            casa.atualizar_desenvolvimento("V")
            fora.atualizar_desenvolvimento("D")
        elif gols_fora > gols_casa:
            t_fora["vitorias"] += 1
            t_fora["pontos"] += 3
            t_casa["derrotas"] += 1
            fora.atualizar_desenvolvimento("V")
            casa.atualizar_desenvolvimento("D")
        else:
            t_casa["empates"] += 1
            t_fora["empates"] += 1
            t_casa["pontos"] += 1
            t_fora["pontos"] += 1
            casa.atualizar_desenvolvimento("E")
            fora.atualizar_desenvolvimento("E")

    def classificacao(self, competicao):
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

    def _avaliar_objetivos(self):
        if not self.clube_usuario:
            return []
        resultados = []
        pos_paul = self._posicao_clube("paulistao_a1")
        pos_liga = self._posicao_clube("bra_a" if "bra_a" in self.clube_usuario.competicoes else "bra_b")
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

        resultados = self._avaliar_objetivos()
        mensagem_resultado_objetivos(resultados)
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

    def _atualizar_estado_mundo(self, resultados_objetivos):
        estado = self.estado_mundo
        mapa_estado = {c["id"]: c for c in estado.get("clubes", [])}

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
            mapa_estado[clube.id] = clube.to_dict()

        estado["clubes"] = list(mapa_estado.values())
        estado["meta"]["temporada_atual"] = estado["meta"].get("temporada_atual", 2026) + 1
        self.estado_mundo = estado

    def obter_estado_mundo(self):
        return self.estado_mundo
