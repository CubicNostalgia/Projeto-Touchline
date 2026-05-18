import contextlib
import io
import calendar as pycalendar
from datetime import date, datetime, timedelta

import customtkinter as ctk

from core.carreira_service import (
    carregar_clubes_nacionais,
    criar_temporada,
    iniciar_proxima_temporada,
    listar_ligas_jogaveis,
    nome_competicao,
)
from core.clube import FORMACOES
from data.database import COMPETICOES
from engine import mensagens, noticias
from save_manager import carregar_save, save_exists, salvar_save
import db_manager

ESTADOS_ESTADUAIS = {
    "SP": {"nome": "Sao Paulo", "competicoes": ["paulistao_a1", "paulistao_a2", "paulistao_a3"]},
    "RJ": {"nome": "Rio de Janeiro", "competicoes": ["cariocao_a1"]},
}


class TheTouchlineApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("The Touchline - Seasonal Engine")
        self.geometry("1200x720")
        self.minsize(1100, 660)

        self.colors = {
            "bg": "#0f1419",
            "panel": "#151b22",
            "panel_soft": "#1d2430",
            "accent": "#00c48c",
            "accent_soft": "#0b8a62",
            "text_dim": "#a8b3c4",
        }
        self.configure(fg_color=self.colors["bg"])

        self.font_title = ("Bahnschrift", 26, "bold")
        self.font_sub = ("Bahnschrift", 14, "bold")
        self.font_body = ("Bahnschrift", 13)

        self.estado_mundo = None
        self.temporada = None
        self.clube_usuario = None
        self.comp_id = None
        self.clubes_nacionais = []
        self.nome_liga = ""
        self.estilo_jogo = "Equilibrado"
        self.objetivos = []
        self._tooltip = None
        self._fluxo_partida = None
        self._calendario_cursor = None
        self._drag_data = None
        self._slot_widgets = {}
        self._tactical_slot_order = []

        db_manager.seed_database_if_needed()
        self._tela_inicial()

    def limpar_tela(self):
        for widget in self.winfo_children():
            widget.destroy()

    def _tela_inicial(self):
        self.limpar_tela()
        topo = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        topo.pack(fill="both", expand=True)

        ctk.CTkLabel(topo, text="THE TOUCHLINE", font=self.font_title).pack(pady=(60, 10))
        ctk.CTkLabel(
            topo,
            text="Career Hub",
            font=self.font_body,
            text_color=self.colors["text_dim"],
        ).pack(pady=(0, 30))

        btn_frame = ctk.CTkFrame(topo, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="NOVO JOGO",
            width=260,
            height=46,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._novo_jogo,
        ).pack(pady=8)

        ctk.CTkButton(
            btn_frame,
            text="CONTINUAR",
            width=260,
            height=46,
            command=self._continuar_jogo,
        ).pack(pady=8)

    def _novo_jogo(self):
        self.estado_mundo = None
        self._tela_selecao_liga()

    def _continuar_jogo(self):
        self.estado_mundo = carregar_save() if save_exists() else None
        if not self.estado_mundo:
            self._tela_selecao_liga()
            return

        meta = self.estado_mundo.get("meta", {})
        comp_id = meta.get("comp_usuario_id")
        clube_id = meta.get("clube_usuario_id")
        if not comp_id or not clube_id:
            self._tela_selecao_liga()
            return

        self.comp_id = comp_id
        self.clubes_nacionais = carregar_clubes_nacionais(comp_id, estado_mundo=self.estado_mundo)
        self.nome_liga = nome_competicao(comp_id)
        self.clube_usuario = next((c for c in self.clubes_nacionais if c.id == clube_id), None)
        if not self.clube_usuario:
            self._tela_selecao_liga()
            return
        self.temporada, self.objetivos = criar_temporada(
            comp_id=self.comp_id,
            clubes_nacionais=self.clubes_nacionais,
            clube_usuario=self.clube_usuario,
            estado_mundo=self.estado_mundo,
        )
        self.estado_mundo = self.temporada.obter_estado_mundo()
        self._tela_menu_principal()

    def _tela_selecao_liga(self):
        self.limpar_tela()
        container = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        container.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(container, text="SELECIONE A LIGA", font=self.font_title).pack(pady=(20, 20))

        ligas = listar_ligas_jogaveis()

        btns = ctk.CTkFrame(container, fg_color="transparent")
        btns.pack(pady=10)
        for comp_id, nome in ligas:
            ctk.CTkButton(
                btns,
                text=nome,
                width=420,
                height=48,
                command=lambda c=comp_id: self._selecionar_liga(c),
            ).pack(pady=8)

        ctk.CTkButton(container, text="VOLTAR", command=self._tela_inicial).pack(pady=20)

    def _selecionar_liga(self, comp_id):
        self.comp_id = comp_id
        self.clubes_nacionais = carregar_clubes_nacionais(comp_id, estado_mundo=self.estado_mundo)
        self.nome_liga = nome_competicao(comp_id)
        self._tela_selecao_clube()

    def _tela_selecao_clube(self):
        self.limpar_tela()
        container = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(container, text=self.nome_liga, font=self.font_sub, text_color=self.colors["text_dim"]).pack(pady=(10, 0))
        ctk.CTkLabel(container, text="ESCOLHA SEU CLUBE", font=self.font_title).pack(pady=(8, 18))

        grid = ctk.CTkScrollableFrame(container, fg_color=self.colors["panel"])
        grid.pack(fill="both", expand=True, padx=12, pady=12)

        cols = 4
        for i, clube in enumerate(self.clubes_nacionais):
            btn = ctk.CTkButton(
                grid,
                text=clube.nome,
                width=200,
                height=40,
                command=lambda c=clube: self._selecionar_clube(c),
            )
            btn.grid(row=i // cols, column=i % cols, padx=8, pady=8, sticky="ew")
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1)

        ctk.CTkButton(container, text="VOLTAR", command=self._tela_selecao_liga).pack(pady=10)

    def _selecionar_clube(self, clube):
        self.clube_usuario = clube
        self._iniciar_temporada(aplicar_tatica=False)

    def _tela_tatica(self):
        self.limpar_tela()
        container = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        container.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(container, text=f"GESTAO TATICA - {self.clube_usuario.nome}", font=self.font_title).pack(pady=(10, 20))

        painel = ctk.CTkFrame(container, fg_color=self.colors["panel"])
        painel.pack(fill="both", expand=True, padx=10, pady=10)

        opcoes = ctk.CTkFrame(painel, fg_color=self.colors["panel_soft"])
        opcoes.pack(side="left", fill="y", padx=12, pady=12)

        ctk.CTkLabel(opcoes, text="FORMACAO", font=self.font_sub).pack(pady=(12, 6))
        formacoes = list(FORMACOES.keys())
        self._tactical_slots = {}
        self._tooltip = None
        self.formacao_var = ctk.StringVar(value=self.clube_usuario.formacao)
        ctk.CTkOptionMenu(
            opcoes,
            values=formacoes,
            variable=self.formacao_var,
            command=lambda _: self._render_campinho_tatico(),
        ).pack(pady=(0, 18))

        ctk.CTkLabel(opcoes, text="ESTILO DE JOGO", font=self.font_sub).pack(pady=(8, 6))
        self.estilo_var = ctk.StringVar(value=self.estilo_jogo)
        ctk.CTkSegmentedButton(opcoes, values=["Ofensivo", "Equilibrado", "Retranca"], variable=self.estilo_var).pack(pady=(0, 18))

        self.campo_tatico = ctk.CTkFrame(painel, fg_color="#1f5f43")
        self.campo_tatico.pack(side="right", fill="both", expand=True, padx=12, pady=12)
        self._render_campinho_tatico()

        botoes = ctk.CTkFrame(container, fg_color="transparent")
        botoes.pack(pady=10)
        ctk.CTkButton(
            botoes,
            text="INICIAR CARREIRA",
            width=260,
            height=46,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._iniciar_temporada,
        ).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="VOLTAR", width=140, command=self._tela_selecao_clube).pack(side="left", padx=8)

    def _iniciar_temporada(self, aplicar_tatica=True):
        if aplicar_tatica:
            self._aplicar_escalacao_tatica_manual()
            if hasattr(self, "formacao_var"):
                self.clube_usuario.definir_formacao(self.formacao_var.get())
            if hasattr(self, "estilo_var"):
                self.estilo_jogo = self.estilo_var.get()

        self.temporada, self.objetivos = criar_temporada(
            comp_id=self.comp_id,
            clubes_nacionais=self.clubes_nacionais,
            clube_usuario=self.clube_usuario,
            estado_mundo=self.estado_mundo,
        )
        self.estado_mundo = self.temporada.obter_estado_mundo()
        self._tela_menu_principal()

    def _render_campinho_tatico(self):
        for w in self.campo_tatico.winfo_children():
            w.destroy()

        ctk.CTkLabel(
            self.campo_tatico,
            text="Arraste cards do banco para o campo ou troque titulares entre si.",
            font=self.font_body,
            text_color="white",
        ).pack(anchor="w", padx=14, pady=(12, 6))

        superficie = ctk.CTkFrame(self.campo_tatico, fg_color="transparent")
        superficie.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._drag_surface = superficie

        campo = ctk.CTkFrame(superficie, fg_color="#1f5f43", corner_radius=18)
        campo.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._campo_visual = campo

        lateral = ctk.CTkFrame(superficie, fg_color=self.colors["panel"], width=280, corner_radius=18)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)

        ctk.CTkLabel(lateral, text="Banco e rotacao", font=self.font_sub).pack(anchor="w", padx=12, pady=(12, 4))
        ctk.CTkLabel(
            lateral,
            text="Reserve com profundidade. Um drop substitui o titular do slot.",
            text_color=self.colors["text_dim"],
            justify="left",
            wraplength=240,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        lista_reservas = ctk.CTkScrollableFrame(lateral, fg_color=self.colors["panel_soft"], width=252)
        lista_reservas.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        jogadores_base = self._jogadores_taticos_render()
        self._tactical_slots = {}
        self._slot_widgets = {}
        self._tactical_slot_order = []

        for idx, (pos, (x, y)) in enumerate(self._layout_slots_formacao()):
            slot_id = f"{pos}_{idx}"
            jogador = jogadores_base[idx] if idx < len(jogadores_base) else None
            self._tactical_slot_order.append(slot_id)
            self._tactical_slots[slot_id] = {"pos": pos, "jogador": jogador}

            card = ctk.CTkFrame(
                campo,
                fg_color="#143d2f",
                corner_radius=16,
                border_width=1,
                border_color=self._cor_posicao(pos),
                width=156,
                height=86,
            )
            card.place(relx=x, rely=y, anchor="center")
            card.pack_propagate(False)

            topo = ctk.CTkFrame(card, fg_color="transparent")
            topo.pack(fill="x", padx=8, pady=(8, 2))
            ctk.CTkLabel(
                topo,
                text=pos,
                width=42,
                fg_color=self._cor_posicao(pos),
                corner_radius=10,
                font=self.font_sub,
            ).pack(side="left")
            ctk.CTkLabel(
                topo,
                text=f"OVR {getattr(jogador, 'overall', '--')}",
                text_color=self.colors["text_dim"],
            ).pack(side="right")

            ctk.CTkLabel(
                card,
                text=jogador.nome if jogador else "Slot vazio",
                font=self.font_sub,
                justify="left",
                wraplength=130,
            ).pack(anchor="w", padx=10, pady=(2, 1))
            ctk.CTkLabel(
                card,
                text=self._resumo_status_jogador(jogador) if jogador else "Solte um jogador aqui",
                text_color=self.colors["text_dim"],
                justify="left",
                wraplength=130,
            ).pack(anchor="w", padx=10, pady=(0, 8))

            self._slot_widgets[slot_id] = card
            self._vincular_drag_card(card, ("slot", slot_id), tooltip_slot=slot_id)

        for jogador in self._reservas_taticas():
            card = ctk.CTkFrame(lista_reservas, fg_color=self.colors["panel"], corner_radius=14)
            card.pack(fill="x", padx=4, pady=5)
            topo = ctk.CTkFrame(card, fg_color="transparent")
            topo.pack(fill="x", padx=8, pady=(8, 4))
            ctk.CTkLabel(
                topo,
                text=jogador.posicao,
                width=42,
                fg_color=self._cor_posicao(jogador.posicao),
                corner_radius=10,
                font=self.font_sub,
            ).pack(side="left")
            ctk.CTkLabel(topo, text=f"OVR {jogador.overall}", text_color=self.colors["text_dim"]).pack(side="right")
            ctk.CTkLabel(card, text=jogador.nome, font=self.font_sub, justify="left", wraplength=220).pack(
                anchor="w", padx=10
            )
            ctk.CTkLabel(
                card,
                text=f"{jogador.idade} anos | {self._resumo_status_jogador(jogador)}",
                text_color=self.colors["text_dim"],
                justify="left",
                wraplength=220,
            ).pack(anchor="w", padx=10, pady=(0, 8))
            self._vincular_drag_card(card, ("bench", jogador))

    def _aplicar_escalacao_tatica_manual(self):
        if not self._tactical_slots:
            return
        jogadores = [
            self._tactical_slots.get(slot_id, {}).get("jogador")
            for slot_id in self._tactical_slot_order
            if self._tactical_slots.get(slot_id, {}).get("jogador")
        ]
        if len(jogadores) != 11:
            return
        indices = []
        for jogador in jogadores:
            try:
                indices.append(self.clube_usuario.elenco.index(jogador))
            except ValueError:
                continue
        if len(indices) == 11:
            self.clube_usuario.definir_titulares(indices)

    def _layout_slots_formacao(self):
        formacao = FORMACOES.get(self.formacao_var.get(), FORMACOES["4-3-3"])
        posicoes = []
        for pos, qtd in formacao.items():
            posicoes.extend([pos] * qtd)

        def _espalhar_posicoes(qtd):
            if qtd <= 0:
                return []
            if qtd == 1:
                return [0.50]
            margem = 0.14
            passo = (1.0 - (2 * margem)) / (qtd - 1)
            return [round(margem + (passo * i), 3) for i in range(qtd)]

        defesa = [p for p in posicoes if p in ("LE", "LD", "ZAG")]
        volantes = [p for p in posicoes if p == "VOL"]
        meias = [p for p in posicoes if p in ("MC", "MEI")]
        pontas = [p for p in posicoes if p in ("PE", "PD")]
        atacantes = [p for p in posicoes if p == "ATA"]

        linhas = [
            (defesa, 0.78),
            (volantes, 0.64),
            (meias, 0.50),
            (pontas, 0.36),
            (atacantes, 0.24),
        ]
        slot_layout = [("GOL", (0.50, 0.90))]
        for grupo, eixo_y in linhas:
            xs = _espalhar_posicoes(len(grupo))
            for idx, pos in enumerate(grupo):
                slot_layout.append((pos, (xs[idx], eixo_y)))
        return slot_layout[:11]

    def _jogadores_taticos_render(self):
        jogadores = []
        if getattr(self, "_tactical_slots", None):
            for slot_id in getattr(self, "_tactical_slot_order", []):
                jogador = self._tactical_slots.get(slot_id, {}).get("jogador")
                if jogador and jogador in self.clube_usuario.elenco and jogador not in jogadores:
                    jogadores.append(jogador)
        if len(jogadores) != 11:
            jogadores = list(self.clube_usuario.escalar_titulares())
        return jogadores[:11]

    def _reservas_taticas(self):
        ordem = {"GOL": 0, "ZAG": 1, "LD": 2, "LE": 3, "VOL": 4, "MC": 5, "MEI": 6, "PE": 7, "PD": 8, "ATA": 9}
        titulares = {info.get("jogador") for info in self._tactical_slots.values() if info.get("jogador")}
        return sorted(
            [j for j in self.clube_usuario.elenco if j not in titulares],
            key=lambda j: (ordem.get(j.posicao, 99), -j.overall, j.nome),
        )

    def _vincular_drag_card(self, widget, origem, tooltip_slot=None):
        alvos = [widget]
        fila = list(widget.winfo_children())
        while fila:
            atual = fila.pop(0)
            alvos.append(atual)
            fila.extend(atual.winfo_children())
        for alvo in alvos:
            alvo.bind("<Button-1>", lambda event, src=origem: self._iniciar_drag_tatico(event, src))
            alvo.bind("<B1-Motion>", self._mover_drag_tatico)
            alvo.bind("<ButtonRelease-1>", self._soltar_drag_tatico)
            if tooltip_slot:
                alvo.bind("<Enter>", lambda event, sid=tooltip_slot: self._mostrar_tooltip_jogador(sid, event))
                alvo.bind("<Leave>", lambda event: self._ocultar_tooltip_jogador())

    def _iniciar_drag_tatico(self, event, origem):
        if origem[0] == "slot":
            jogador = self._tactical_slots.get(origem[1], {}).get("jogador")
            posicao = self._tactical_slots.get(origem[1], {}).get("pos", "")
        else:
            jogador = origem[1]
            posicao = getattr(jogador, "posicao", "")
        if not jogador:
            return

        self._ocultar_tooltip_jogador()
        self._limpar_drag_tatico()
        ghost = ctk.CTkFrame(
            self._drag_surface,
            fg_color=self.colors["panel"],
            corner_radius=14,
            border_width=1,
            border_color=self._cor_posicao(posicao),
            width=180,
            height=74,
        )
        ghost.pack_propagate(False)
        topo = ctk.CTkFrame(ghost, fg_color="transparent")
        topo.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(
            topo,
            text=posicao,
            width=42,
            fg_color=self._cor_posicao(posicao),
            corner_radius=10,
            font=self.font_sub,
        ).pack(side="left")
        ctk.CTkLabel(topo, text=f"OVR {jogador.overall}", text_color=self.colors["text_dim"]).pack(side="right")
        ctk.CTkLabel(ghost, text=jogador.nome, font=self.font_sub, wraplength=150).pack(anchor="w", padx=10, pady=(2, 8))

        self._drag_data = {"origem": origem, "ghost": ghost}
        self._atualizar_drag_tatico(event.x_root, event.y_root)

    def _mover_drag_tatico(self, event):
        if not self._drag_data:
            return
        self._atualizar_drag_tatico(event.x_root, event.y_root)

    def _atualizar_drag_tatico(self, x_root, y_root):
        if not self._drag_data:
            return
        x_local = x_root - self._drag_surface.winfo_rootx()
        y_local = y_root - self._drag_surface.winfo_rooty()
        self._drag_data["ghost"].place(x=x_local, y=y_local, anchor="center")

    def _soltar_drag_tatico(self, event):
        if not self._drag_data:
            return
        origem = self._drag_data["origem"]
        slot_destino = self._slot_tatico_por_coordenada(event.x_root, event.y_root)
        houve_mudanca = False
        if slot_destino:
            if origem[0] == "slot":
                houve_mudanca = self._trocar_slots_taticos(origem[1], slot_destino)
            else:
                houve_mudanca = self._substituir_slot_por_reserva(origem[1], slot_destino)
        self._limpar_drag_tatico()
        if houve_mudanca:
            self._render_campinho_tatico()

    def _slot_tatico_por_coordenada(self, x_root, y_root):
        for slot_id, widget in self._slot_widgets.items():
            x0 = widget.winfo_rootx()
            y0 = widget.winfo_rooty()
            x1 = x0 + widget.winfo_width()
            y1 = y0 + widget.winfo_height()
            if x0 <= x_root <= x1 and y0 <= y_root <= y1:
                return slot_id
        return None

    def _trocar_slots_taticos(self, origem_id, destino_id):
        if origem_id == destino_id:
            return False
        slot_origem = self._tactical_slots.get(origem_id)
        slot_destino = self._tactical_slots.get(destino_id)
        if not slot_origem or not slot_destino:
            return False
        slot_origem["jogador"], slot_destino["jogador"] = slot_destino.get("jogador"), slot_origem.get("jogador")
        return True

    def _substituir_slot_por_reserva(self, jogador, destino_id):
        slot_destino = self._tactical_slots.get(destino_id)
        if not slot_destino or not jogador or slot_destino.get("jogador") == jogador:
            return False
        slot_destino["jogador"] = jogador
        return True

    def _limpar_drag_tatico(self):
        if self._drag_data and self._drag_data.get("ghost") is not None:
            try:
                self._drag_data["ghost"].destroy()
            except Exception:
                pass
        self._drag_data = None

    def _resumo_atributos(self, jogador):
        ovr = int(getattr(jogador, "overall", 60))
        pos = getattr(jogador, "posicao", "MC")
        ataque = min(99, ovr + (8 if pos in ("ATA", "PE", "PD", "MEI") else -2))
        defesa = min(99, ovr + (8 if pos in ("ZAG", "LD", "LE", "VOL", "GOL") else -4))
        fisico = min(99, ovr + (4 if pos in ("VOL", "ZAG", "ATA") else 0))
        tecnica = min(99, ovr + (5 if pos in ("MC", "MEI", "PE", "PD") else 1))
        mental = min(99, int(ovr * 0.9) + 5)
        return {
            "Ataque": max(35, ataque),
            "Defesa": max(35, defesa),
            "Fisico": max(35, fisico),
            "Tecnica": max(35, tecnica),
            "Mental": max(35, mental),
        }

    def _mostrar_tooltip_jogador(self, slot_id, event):
        slot = self._tactical_slots.get(slot_id)
        jogador = slot.get("jogador") if slot else None
        if not jogador:
            return
        self._ocultar_tooltip_jogador()
        self._tooltip = ctk.CTkToplevel(self)
        self._tooltip.overrideredirect(True)
        self._tooltip.geometry(f"220x170+{event.x_root + 12}+{event.y_root + 12}")
        card = ctk.CTkFrame(self._tooltip, fg_color=self.colors["panel"])
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(card, text=jogador.nome, font=self.font_sub).pack(pady=(8, 4))
        atributos = self._resumo_atributos(jogador)
        for nome, valor in atributos.items():
            ctk.CTkLabel(card, text=f"{nome}: {valor}", font=self.font_body).pack(anchor="w", padx=12)

    def _ocultar_tooltip_jogador(self):
        if self._tooltip is not None:
            try:
                self._tooltip.destroy()
            except Exception:
                pass
            self._tooltip = None

    def _tela_menu_principal(self):
        self.limpar_tela()
        root = ctk.CTkFrame(self, fg_color=self.colors["bg"])
        root.pack(fill="both", expand=True)

        nav = ctk.CTkFrame(root, fg_color=self.colors["panel"], width=220)
        nav.pack(side="left", fill="y")

        ctk.CTkLabel(nav, text="THE TOUCHLINE", font=self.font_sub).pack(pady=(16, 10))

        btns = [
            ("Dashboard", self._mostrar_dashboard),
            ("Calendario", self._mostrar_calendario_completo),
            ("Elenco", self._mostrar_elenco),
            ("Financeiro", self._mostrar_financeiro),
            ("Tabelas", self._mostrar_tabelas),
            ("Mensagens", self._mostrar_mensagens),
            ("Noticias", self._mostrar_noticias),
            ("Ajuda", self._mostrar_basicos_jogo),
        ]
        for texto, cmd in btns:
            ctk.CTkButton(nav, text=texto, command=cmd, height=40).pack(fill="x", padx=12, pady=6)

        ctk.CTkButton(nav, text="Sair", command=self._tela_inicial, height=40).pack(fill="x", padx=12, pady=(20, 10))

        self.content = ctk.CTkFrame(root, fg_color=self.colors["bg"])
        self.content.pack(side="right", fill="both", expand=True)
        self._mostrar_dashboard()

    def _clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _mostrar_dashboard(self):
        self._clear_content()
        dashboard_root = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        dashboard_root.pack(fill="both", expand=True, padx=8, pady=4)

        header = ctk.CTkFrame(dashboard_root, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=12, pady=(12, 10))

        titulo = f"{self.clube_usuario.nome} | {self.nome_liga}"
        ctk.CTkLabel(header, text=titulo, font=self.font_title).pack(side="left", padx=16, pady=12)

        self.lbl_data = ctk.CTkLabel(header, text="", font=self.font_sub, text_color=self.colors["text_dim"])
        self.lbl_data.pack(side="right", padx=16)

        progresso_frame = ctk.CTkFrame(dashboard_root, fg_color=self.colors["panel_soft"])
        progresso_frame.pack(fill="x", padx=12, pady=(0, 10))
        nivel_reputacao, percentual = self._status_reputacao_barra(self.clube_usuario)
        ctk.CTkLabel(
            progresso_frame,
            text=f"Reputacao: {nivel_reputacao}",
            font=self.font_body,
            text_color=self.colors["text_dim"],
        ).pack(anchor="w", padx=12, pady=(8, 2))
        barra = ctk.CTkProgressBar(progresso_frame, progress_color=self.colors["accent"])
        barra.pack(fill="x", padx=12, pady=(0, 10))
        barra.set(percentual)

        info = ctk.CTkFrame(dashboard_root, fg_color="transparent")
        info.pack(fill="x", padx=12, pady=(0, 10))

        self.lbl_proximo = ctk.CTkLabel(info, text="", font=self.font_body, text_color=self.colors["text_dim"])
        self.lbl_proximo.pack(anchor="w")

        linha_superior = ctk.CTkFrame(dashboard_root, fg_color="transparent")
        linha_superior.pack(fill="x", padx=12, pady=(0, 10))
        self._render_calendario_mensal(linha_superior)
        self._render_mural_objetivos(linha_superior)

        widgets = ctk.CTkFrame(dashboard_root, fg_color="transparent")
        widgets.pack(fill="x", padx=12, pady=(0, 10))
        self._render_widget_top5(widgets)
        self._render_widget_noticias(widgets)

        cards = ctk.CTkFrame(dashboard_root, fg_color="transparent")
        cards.pack(fill="x", padx=12, pady=(10, 10))

        ctk.CTkButton(
            cards,
            text="Ajuda do Jogo",
            width=180,
            height=46,
            command=self._mostrar_basicos_jogo,
        ).grid(row=0, column=0, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Calendario Completo",
            width=200,
            height=46,
            command=self._mostrar_calendario_completo,
        ).grid(row=0, column=1, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Avancar 1 Dia",
            width=180,
            height=46,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._acao_avancar_dia,
        ).grid(row=0, column=2, padx=8, pady=6)

        self.entry_data_alvo = ctk.CTkEntry(cards, width=140, placeholder_text="AAAA-MM-DD")
        self.entry_data_alvo.grid(row=0, column=3, padx=8, pady=6)
        ctk.CTkButton(
            cards,
            text="Avancar Ate",
            width=140,
            height=46,
            command=self._acao_avancar_ate_data,
        ).grid(row=0, column=4, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Avancar ate a Proxima Partida",
            width=260,
            height=46,
            command=self._acao_fluxo_proxima_partida,
        ).grid(row=1, column=0, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Financeiro",
            width=180,
            height=46,
            command=self._mostrar_financeiro,
        ).grid(row=1, column=1, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Salvar",
            width=120,
            height=46,
            command=self._acao_salvar,
        ).grid(row=1, column=2, padx=8, pady=6)

        ctk.CTkButton(
            cards,
            text="Simular Temporada",
            width=180,
            height=46,
            command=self._acao_simular_temporada,
        ).grid(row=1, column=3, padx=8, pady=6)

        self.log_box = ctk.CTkTextbox(dashboard_root, height=280, fg_color=self.colors["panel"])
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(10, 20))
        self._append_log("Bem-vindo ao modo carreira.")
        if self.objetivos:
            self._append_log("Objetivos da diretoria:")
            for obj in self.objetivos:
                self._append_log(f"- {obj.get('texto', '')}")
        objetivos_semanais = self.temporada.estado_mundo.get("meta", {}).get("objetivos_semanais", [])
        if objetivos_semanais:
            self._append_log("Objetivos semanais:")
            for obj in objetivos_semanais[:5]:
                self._append_log(f"- {obj}")

        self._atualizar_header()

    @staticmethod
    def _status_reputacao_barra(clube):
        tier = int(getattr(clube, "reputacao_tier", 1))
        if tier <= 3:
            nivel = "Local"
        elif tier <= 6:
            nivel = "Regional"
        elif tier <= 10:
            nivel = "Nacional"
        elif tier <= 13:
            nivel = "Continental"
        else:
            nivel = "Mundial"
        return f"{nivel} (Tier {tier}/15)", max(0.05, min(1.0, tier / 15))

    def _confianca_diretoria(self):
        base = int(getattr(self.clube_usuario, "torcida_expectativa", 50))
        risco = (getattr(self.clube_usuario, "job_security", {}) or {}).get("risco", "estavel")
        ajuste = {"baixo": 8, "estavel": 5, "moderado": -5, "alto": -12, "critico": -20}.get(risco, 0)
        return max(0, min(100, base + ajuste))

    @staticmethod
    def _categoria_posicao(posicao):
        if posicao in ("ATA", "PE", "PD"):
            return "ataque"
        if posicao in ("MC", "MEI", "VOL"):
            return "meio"
        if posicao in ("ZAG", "LD", "LE"):
            return "defesa"
        return "gol"

    def _cor_posicao(self, posicao):
        categoria = self._categoria_posicao(posicao)
        return {
            "ataque": "#ef4444",
            "meio": "#22c55e",
            "defesa": "#3b82f6",
            "gol": "#facc15",
        }.get(categoria, self.colors["accent"])

    @staticmethod
    def _mes_nome_pt(mes):
        nomes = [
            "Janeiro",
            "Fevereiro",
            "Marco",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        return nomes[max(1, min(12, mes)) - 1]

    @staticmethod
    def _resumo_status_jogador(jogador):
        if jogador.lesao_dias > 0:
            return f"Lesao {jogador.lesao_dias}d"
        if jogador.fadiga >= 70:
            return "Muito cansado"
        if jogador.fadiga >= 40:
            return "Cansado"
        if jogador.forma >= 2.5:
            return "Em alta"
        if jogador.forma <= -2.5:
            return "Em queda"
        return "Disponivel"

    def _folha_salarial(self, incluir_base=True):
        elenco = list(getattr(self.clube_usuario, "elenco", []))
        if incluir_base:
            elenco += list(getattr(self.clube_usuario, "base_jovens", []))
        return sum(int(getattr(j, "salario", 0) or 0) for j in elenco)

    def _valor_mercado_jogador(self, jogador):
        valor_base = (jogador.overall * 42_000) + (jogador.potencial * 18_000) + max(0, 28 - jogador.idade) * 14_000
        return int(self.clube_usuario.calcular_valor_venda(valor_base))

    @staticmethod
    def _formatar_dinheiro(valor):
        inteiro = int(valor or 0)
        texto = f"{inteiro:,}".replace(",", ".")
        return f"R$ {texto}"

    def _proximo_evento_usuario(self):
        if not self.temporada:
            return None
        for evento in self.temporada.calendario_completo[self.temporada.rodada_atual :]:
            if self.temporada._deve_exibir_evento(evento):
                return evento
        return self.temporada.proximo_evento()

    def _proxima_rodada_jogavel(self):
        if not self.temporada:
            return None
        for evento in self.temporada.calendario_completo[self.temporada.rodada_atual :]:
            if "partidas" not in evento:
                continue
            if self.temporada._deve_exibir_evento(evento):
                return evento
        return None

    def _partida_usuario_no_evento(self, evento):
        if not evento or "partidas" not in evento:
            return None
        for casa, fora in evento["partidas"]:
            if casa.id == self.clube_usuario.id or fora.id == self.clube_usuario.id:
                return casa, fora
        return evento["partidas"][0] if evento["partidas"] else None

    def _avancar_mes_cursor(self, base, delta):
        mes = base.month + delta
        ano = base.year
        while mes < 1:
            mes += 12
            ano -= 1
        while mes > 12:
            mes -= 12
            ano += 1
        return date(ano, mes, 1)

    def _render_calendario_mensal(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        data_ref = self.temporada.data_atual if self.temporada else date.today()
        topo = ctk.CTkFrame(card, fg_color="transparent")
        topo.pack(fill="x", padx=12, pady=(8, 6))
        ctk.CTkLabel(
            topo,
            text=f"Calendario - {self._mes_nome_pt(data_ref.month)} {data_ref.year}",
            font=self.font_sub,
        ).pack(side="left")
        ctk.CTkButton(
            topo,
            text="Abrir",
            width=90,
            height=28,
            command=self._mostrar_calendario_completo,
        ).pack(side="right")

        grade = ctk.CTkFrame(card, fg_color=self.colors["panel_soft"])
        grade.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for i, nome in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]):
            ctk.CTkLabel(grade, text=nome, text_color=self.colors["text_dim"]).grid(row=0, column=i, padx=2, pady=2)
            grade.grid_columnconfigure(i, weight=1)

        agenda = self.temporada.eventos_por_data_mes(data_ref.year, data_ref.month) if self.temporada else {}
        _, ultimo_dia = pycalendar.monthrange(data_ref.year, data_ref.month)
        primeiro_dia = date(data_ref.year, data_ref.month, 1).weekday()
        for dia in range(1, ultimo_dia + 1):
            idx = primeiro_dia + (dia - 1)
            linha = (idx // 7) + 1
            coluna = idx % 7
            cel = ctk.CTkFrame(grade, fg_color=self.colors["panel"], corner_radius=6)
            cel.grid(row=linha, column=coluna, sticky="nsew", padx=2, pady=2)
            grade.grid_rowconfigure(linha, weight=1)
            ctk.CTkLabel(cel, text=str(dia), font=("Bahnschrift", 11, "bold")).pack(anchor="nw", padx=4, pady=2)
            eventos = agenda.get(dia, [])
            if eventos:
                ev = eventos[0]
                comp = self._nome_competicao_ui(ev.get("competicao", ""))[:12]
                adv = ev.get("adversario")
                marcador = comp
                if adv:
                    marcador += f" vs {adv[:8]}"
                ctk.CTkLabel(cel, text=marcador, font=("Bahnschrift", 10), text_color=self.colors["accent"]).pack(
                    anchor="w", padx=4, pady=(0, 2)
                )

    def _render_mural_objetivos(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(card, text="Mural de Objetivos", font=self.font_sub).pack(anchor="w", padx=12, pady=(8, 4))

        confianca = self._confianca_diretoria()
        ctk.CTkLabel(card, text=f"Confianca da diretoria: {confianca}%", text_color=self.colors["text_dim"]).pack(
            anchor="w", padx=12
        )
        barra = ctk.CTkProgressBar(card, progress_color=self.colors["accent"])
        barra.pack(fill="x", padx=12, pady=(2, 8))
        barra.set(confianca / 100)

        box = ctk.CTkTextbox(card, height=170, fg_color=self.colors["panel_soft"])
        box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        resultados = self.temporada.avaliar_objetivos_atuais() if self.temporada else []
        if not resultados:
            box.insert("end", "Sem objetivos ativos.")
        else:
            icones = {"cumprido": "[OK]", "falhado": "[X]", "em_andamento": "[...]"}
            for item in resultados[:8]:
                icon = icones.get(item.get("status"), "[...]")
                box.insert("end", f"{icon} {item['texto']}\n")
        box.configure(state="disabled")

    def _competicao_tabela_principal(self):
        if self.comp_id == "bra_c":
            return "bra_c_fase1"
        if self.comp_id == "bra_d":
            for comp in sorted(self.temporada.tabelas.keys()):
                if comp.startswith("bra_d_g") and any(c.id == self.clube_usuario.id for c in self.temporada.tabelas.get(comp, {})):
                    return comp
        return self.comp_id or "bra_b"

    def _render_widget_top5(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        card.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(card, text="Top 5 da Liga", font=self.font_sub).pack(anchor="w", padx=12, pady=(8, 4))

        box = ctk.CTkTextbox(card, height=120, fg_color=self.colors["panel_soft"])
        box.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        comp = self._competicao_tabela_principal()
        classif = self.temporada.classificacao(comp)[:5] if self.temporada else []
        if not classif:
            box.insert("end", "Tabela ainda sem dados.")
        else:
            for i, (clube, stats) in enumerate(classif, start=1):
                pts = stats.get("pontos", 0)
                box.insert("end", f"{i}. {clube.nome} - {pts} pts\n")
        box.configure(state="disabled")

    def _render_widget_noticias(self, parent):
        card = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        card.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(card, text="Ultimas Manchetes", font=self.font_sub).pack(anchor="w", padx=12, pady=(8, 4))
        lista = ctk.CTkFrame(card, fg_color=self.colors["panel_soft"])
        lista.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        itens = noticias.listar_noticias(temporada_ano=temporada_ano, limite=3)
        if not itens:
            ctk.CTkLabel(lista, text="Sem noticias recentes.", text_color=self.colors["text_dim"]).pack(
                anchor="w", padx=10, pady=10
            )
        else:
            for item in itens:
                bloco = ctk.CTkFrame(lista, fg_color=self.colors["panel"], corner_radius=10)
                bloco.pack(fill="x", padx=8, pady=6)
                ctk.CTkLabel(
                    bloco,
                    text=item["titulo"],
                    font=self.font_body,
                    anchor="w",
                    justify="left",
                    wraplength=340,
                ).pack(fill="x", padx=10, pady=(8, 3))
                ctk.CTkLabel(
                    bloco,
                    text=item.get("corpo", ""),
                    text_color=self.colors["text_dim"],
                    anchor="w",
                    justify="left",
                    wraplength=340,
                ).pack(fill="x", padx=10, pady=(0, 8))

    def _append_log(self, texto):
        self.log_box.configure(state="normal")
        if texto:
            self.log_box.insert("end", texto + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _run_with_log(self, func, *args, **kwargs):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            resultado = func(*args, **kwargs)
        output = buf.getvalue().strip()
        if output:
            self._append_log(output)
        return resultado

    def _atualizar_header(self):
        data_iso = self.temporada.estado_mundo.get("meta", {}).get("data_atual")
        data_txt = data_iso
        try:
            data_txt = datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
        except Exception:
            pass
        if hasattr(self, "lbl_data") and self.lbl_data.winfo_exists():
            self.lbl_data.configure(text=f"DATA: {data_txt}")

        evento = self._proximo_evento_usuario()
        if not evento:
            if hasattr(self, "lbl_proximo") and self.lbl_proximo.winfo_exists():
                self.lbl_proximo.configure(text="Proximo evento: temporada encerrada.")
        else:
            comp_nome = self._nome_competicao_ui(evento.get("competicao"))
            dia = evento["data"].strftime("%d/%m/%Y")
            hora = evento["data"].strftime("%H:%M")
            rodada = f" - Rodada {evento['rodada']}" if "rodada" in evento else ""
            if hasattr(self, "lbl_proximo") and self.lbl_proximo.winfo_exists():
                self.lbl_proximo.configure(text=f"Proximo evento: {comp_nome}{rodada} | {dia} {hora}")

    def _pos_simulacao(self, avancou, auto_iniciar_proxima_temporada=True):
        salvar_save(self.temporada.obter_estado_mundo())
        fim_temporada = self.temporada.rodada_atual >= len(self.temporada.calendario_completo)
        if auto_iniciar_proxima_temporada and (not avancou or fim_temporada):
            nova_temp = iniciar_proxima_temporada(self.temporada.obter_estado_mundo(), self.clube_usuario.id)
            if nova_temp[0]:
                self.temporada, self.clube_usuario, self.comp_id, self.objetivos = nova_temp
                self.nome_liga = nome_competicao(self.comp_id)
        self._atualizar_header()

    def _acao_avancar_dia(self):
        self._append_log("-> Avancando 1 dia...")
        self._run_with_log(self.temporada.avancar_dia, 1)
        self._pos_simulacao(True)

    def _acao_avancar_ate_data(self):
        alvo_txt = (self.entry_data_alvo.get() or "").strip()
        if not alvo_txt:
            self._append_log("-> Informe uma data alvo no formato AAAA-MM-DD.")
            return
        try:
            alvo = date.fromisoformat(alvo_txt)
        except ValueError:
            self._append_log("-> Data invalida. Use AAAA-MM-DD.")
            return
        self._append_log(f"-> Avancando ate {alvo_txt}...")
        resultado = self.temporada.avancar_ate_data(alvo, auto_simular=True)
        self._append_log(
            f"-> {resultado['dias_avancados']} dias avancados | {resultado['rodadas_processadas']} rodadas processadas."
        )
        self._pos_simulacao(True)

    def _acao_fluxo_proxima_partida(self):
        evento = self._proxima_rodada_jogavel()
        if not evento:
            self._append_log("-> Nao ha mais eventos disponiveis nesta temporada.")
            return

        if hasattr(self.temporada, "data_atual") and evento["data"].date() > self.temporada.data_atual:
            self.temporada.avancar_ate_data(evento["data"].date(), auto_simular=False)

        self._fluxo_partida = {
            "stage": "agenda",
            "competicao": evento.get("competicao"),
            "rodada": evento.get("rodada"),
            "fase": evento.get("fase"),
            "data": evento["data"].isoformat(),
            "fim_temporada": False,
        }
        self._mostrar_central_rodada()

    def _acao_simular_temporada(self):
        self._append_log("-> Simulando temporada completa...")
        self._run_with_log(self.temporada.jogar_temporada_completa)
        self._pos_simulacao(False)

    def _evento_fluxo_partida(self):
        if not self._fluxo_partida:
            return None
        comp_alvo = self._fluxo_partida.get("competicao")
        rodada_alvo = self._fluxo_partida.get("rodada")
        fase_alvo = self._fluxo_partida.get("fase")
        data_alvo = self._fluxo_partida.get("data")
        for evento in self.temporada.calendario_completo:
            if evento.get("competicao") != comp_alvo:
                continue
            if evento.get("rodada") != rodada_alvo:
                continue
            if evento.get("fase") != fase_alvo:
                continue
            if evento.get("data").isoformat() != data_alvo:
                continue
            return evento
        return None

    def _mostrar_central_rodada(self):
        if not self._fluxo_partida:
            self._mostrar_dashboard()
            return

        evento = self._evento_fluxo_partida()
        self._clear_content()
        root = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=8, pady=8)

        header = ctk.CTkFrame(root, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=12, pady=(12, 10))
        ctk.CTkLabel(header, text="CENTRAL DA RODADA", font=self.font_title).pack(side="left", padx=16, pady=12)

        stage = self._fluxo_partida.get("stage", "agenda")
        subtitulo = {
            "agenda": "1. Jogos da rodada",
            "escalacoes": "2. Escalacoes e preparacao",
            "pos_jogo": "3. Resultados e tabela",
        }.get(stage, "Rodada")
        ctk.CTkLabel(header, text=subtitulo, font=self.font_sub, text_color=self.colors["text_dim"]).pack(
            side="right", padx=16
        )

        if not evento:
            ctk.CTkLabel(root, text="A rodada selecionada nao esta mais disponivel.", text_color=self.colors["text_dim"]).pack(
                padx=12, pady=20
            )
            ctk.CTkButton(root, text="Voltar ao Dashboard", command=self._finalizar_fluxo_partida).pack(pady=(0, 20))
            return

        faixa = ctk.CTkFrame(root, fg_color=self.colors["panel_soft"])
        faixa.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            faixa,
            text=f"{self._nome_competicao_ui(evento.get('competicao'))} | {evento['data'].strftime('%d/%m/%Y %H:%M')}",
            font=self.font_body,
        ).pack(anchor="w", padx=12, pady=10)

        if stage == "agenda":
            self._render_partidas_evento(root, evento)
        elif stage == "escalacoes":
            self._render_escalacoes_evento(root, evento)
        else:
            self._render_pos_jogo_evento(root, evento)

    def _render_partidas_evento(self, parent, evento):
        lista = ctk.CTkFrame(parent, fg_color="transparent")
        lista.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        ctk.CTkLabel(
            lista,
            text="A rodada que vem ai",
            font=self.font_sub,
        ).pack(anchor="w", pady=(0, 8))

        for casa, fora in evento.get("partidas", []):
            card = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
            card.pack(fill="x", pady=5)
            destaque = casa.id == self.clube_usuario.id or fora.id == self.clube_usuario.id
            if destaque:
                ctk.CTkFrame(card, fg_color=self.colors["accent"], width=6, height=56).pack(
                    side="left", padx=(0, 8), pady=2
                )
            else:
                ctk.CTkFrame(card, fg_color=self.colors["panel_soft"], width=6, height=56).pack(
                    side="left", padx=(0, 8), pady=2
                )
            ctk.CTkLabel(card, text=casa.nome, width=240, anchor="e").pack(side="left", padx=6, pady=14)
            ctk.CTkLabel(card, text="vs", width=70, font=self.font_sub).pack(side="left", padx=6)
            ctk.CTkLabel(card, text=fora.nome, width=240, anchor="w").pack(side="left", padx=6, pady=14)

        botoes = ctk.CTkFrame(parent, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=(6, 16))
        ctk.CTkButton(
            botoes,
            text="Voltar ao Dashboard",
            width=180,
            height=42,
            command=self._finalizar_fluxo_partida,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            botoes,
            text="Avancar para Escalacoes",
            width=220,
            height=42,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._avancar_fluxo_partida,
        ).pack(side="left", padx=8)

    def _render_escalacoes_evento(self, parent, evento):
        partida = self._partida_usuario_no_evento(evento)
        if not partida:
            ctk.CTkLabel(parent, text="Nao foi possivel localizar a partida principal desta rodada.").pack(pady=20)
            return

        casa, fora = partida
        titulo = ctk.CTkFrame(parent, fg_color="transparent")
        titulo.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            titulo,
            text=f"{casa.nome} x {fora.nome}",
            font=self.font_sub,
        ).pack(anchor="w")

        conteudo = ctk.CTkFrame(parent, fg_color="transparent")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        for indice, clube in enumerate((casa, fora)):
            coluna = ctk.CTkFrame(conteudo, fg_color=self.colors["panel"])
            coluna.pack(side="left", fill="both", expand=True, padx=(0, 6) if indice == 0 else (6, 0))
            ctk.CTkLabel(coluna, text=clube.nome, font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(
                coluna,
                text=f"OVR titular: {clube.forca_titular():.1f}",
                text_color=self.colors["text_dim"],
            ).pack(anchor="w", padx=12, pady=(0, 8))

            lista = ctk.CTkScrollableFrame(coluna, fg_color=self.colors["panel_soft"], height=360)
            lista.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            for jogador in clube.escalar_titulares():
                linha = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
                linha.pack(fill="x", pady=3)
                ctk.CTkLabel(
                    linha,
                    text=jogador.posicao,
                    width=52,
                    fg_color=self._cor_posicao(jogador.posicao),
                    corner_radius=8,
                ).pack(side="left", padx=8, pady=6)
                ctk.CTkLabel(linha, text=jogador.nome, anchor="w").pack(side="left", padx=4, pady=6)
                ctk.CTkLabel(linha, text=f"OVR {jogador.over_match}", width=90).pack(side="right", padx=8, pady=6)

        botoes = ctk.CTkFrame(parent, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=(6, 16))
        if casa.id == self.clube_usuario.id or fora.id == self.clube_usuario.id:
            ctk.CTkButton(
                botoes,
                text="Ajustar Escalacao",
                width=180,
                height=42,
                command=self._mostrar_gestao_tatica,
            ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            botoes,
            text="Voltar",
            width=140,
            height=42,
            command=lambda: self._alterar_stage_fluxo("agenda"),
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            botoes,
            text="Simular Rodada",
            width=180,
            height=42,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._avancar_fluxo_partida,
        ).pack(side="left", padx=8)

    def _render_pos_jogo_evento(self, parent, evento):
        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        rodada = self._fluxo_partida.get("rodada")
        competicao = self._fluxo_partida.get("competicao")

        bloco_resultados = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        bloco_resultados.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        ctk.CTkLabel(bloco_resultados, text="Resultados da rodada", font=self.font_sub).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        self._render_resultados_visual(bloco_resultados, competicao)

        bloco_tabela = ctk.CTkFrame(parent, fg_color=self.colors["panel"])
        bloco_tabela.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        ctk.CTkLabel(bloco_tabela, text="Tabela apos os jogos", font=self.font_sub).pack(
            anchor="w", padx=12, pady=(10, 6)
        )
        self.tabela_rodada_var = ctk.StringVar(value=str(rodada) if rodada is not None else "-")
        self._render_classificacao_visual(bloco_tabela, competicao)

        botoes = ctk.CTkFrame(parent, fg_color="transparent")
        botoes.pack(fill="x", padx=12, pady=(6, 16))
        ctk.CTkButton(
            botoes,
            text="Concluir Rodada",
            width=180,
            height=42,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._finalizar_fluxo_partida,
        ).pack(side="left")

    def _alterar_stage_fluxo(self, stage):
        if not self._fluxo_partida:
            return
        self._fluxo_partida["stage"] = stage
        self._mostrar_central_rodada()

    def _avancar_fluxo_partida(self):
        if not self._fluxo_partida:
            return
        stage = self._fluxo_partida.get("stage")
        if stage == "agenda":
            self._fluxo_partida["stage"] = "escalacoes"
            self._mostrar_central_rodada()
            return
        if stage == "escalacoes":
            self._append_log("-> Rodada em andamento...")
            avancou = self._run_with_log(
                self.temporada.simular_ate_evento,
                self._fluxo_partida.get("competicao"),
                self._fluxo_partida.get("data"),
                rodada=self._fluxo_partida.get("rodada"),
                fase=self._fluxo_partida.get("fase"),
            )
            self._fluxo_partida["stage"] = "pos_jogo"
            self._fluxo_partida["fim_temporada"] = self.temporada.rodada_atual >= len(self.temporada.calendario_completo)
            self._pos_simulacao(avancou, auto_iniciar_proxima_temporada=False)
            self._mostrar_central_rodada()
            return
        self._finalizar_fluxo_partida()

    def _finalizar_fluxo_partida(self):
        if self._fluxo_partida and self._fluxo_partida.get("stage") == "pos_jogo":
            self._pos_simulacao(True, auto_iniciar_proxima_temporada=True)
        self._fluxo_partida = None
        self._mostrar_dashboard()

    def _acao_salvar(self):
        salvar_save(self.temporada.obter_estado_mundo())
        self._append_log("-> Jogo salvo com sucesso.")

    def _mostrar_basicos_jogo(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="AJUDA DO JOGO", font=self.font_title).pack(side="left", padx=16, pady=12)

        root = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        secoes = [
            (
                "Como o fluxo da rodada funciona",
                "Use 'Avancar ate a Proxima Partida' no Dashboard. O jogo passa por agenda da rodada, escalacoes e depois resultados com tabela atualizada.",
            ),
            (
                "Calendario",
                "O calendario completo mostra o mes inteiro e permite navegar entre meses para ver todos os compromissos da temporada.",
            ),
            (
                "Elenco",
                "A tela de elenco mostra titulares, reservas e jovens com cor por setor. Clique em qualquer jogador para ver detalhes, treino e opcoes de mercado.",
            ),
            (
                "Financeiro e estruturas",
                "Na aba Financeiro voce controla investimento na base, staff e melhorias de CT, academia e estadio. Crise financeira pode deteriorar essas estruturas com o tempo.",
            ),
            (
                "Mensagens e noticias",
                "Mensagens trazem recados da diretoria e do staff. Noticias destacam resultados, zebras e movimentacoes do mundo do jogo.",
            ),
            (
                "Tabelas",
                "Use as setas para navegar entre competicoes e grupos. Em 'Resultados' voce consegue passear por cada rodada ja encerrada.",
            ),
        ]

        for titulo, corpo in secoes:
            card = ctk.CTkFrame(root, fg_color=self.colors["panel"])
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(card, text=titulo, font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(
                card,
                text=corpo,
                font=self.font_body,
                text_color=self.colors["text_dim"],
                justify="left",
                wraplength=880,
            ).pack(anchor="w", padx=12, pady=(0, 10))

        acoes = ctk.CTkFrame(root, fg_color="transparent")
        acoes.pack(fill="x", pady=(8, 4))
        ctk.CTkButton(acoes, text="Gestao Tatica", width=220, height=44, command=self._mostrar_gestao_tatica).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(acoes, text="Elenco Completo", width=220, height=44, command=self._mostrar_elenco).pack(
            side="left", padx=8
        )

    def _mostrar_gestao_tatica(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text=f"GESTAO TATICA - {self.clube_usuario.nome}", font=self.font_title).pack(
            side="left", padx=16, pady=12
        )

        painel = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        painel.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        opcoes = ctk.CTkFrame(painel, fg_color=self.colors["panel_soft"], width=250)
        opcoes.pack(side="left", fill="y", padx=12, pady=12)
        opcoes.pack_propagate(False)

        self._tactical_slots = {}
        self._tooltip = None
        self.formacao_var = ctk.StringVar(value=self.clube_usuario.formacao)
        self.estilo_var = ctk.StringVar(value=self.estilo_jogo)

        ctk.CTkLabel(opcoes, text="FORMACAO", font=self.font_sub).pack(pady=(14, 6))
        ctk.CTkOptionMenu(
            opcoes,
            values=list(FORMACOES.keys()),
            variable=self.formacao_var,
            command=lambda _: self._render_campinho_tatico(),
        ).pack(padx=10, pady=(0, 18))

        ctk.CTkLabel(opcoes, text="ESTILO DE JOGO", font=self.font_sub).pack(pady=(8, 6))
        ctk.CTkSegmentedButton(
            opcoes,
            values=["Ofensivo", "Equilibrado", "Retranca"],
            variable=self.estilo_var,
        ).pack(padx=10, pady=(0, 18))

        self.lbl_feedback_tatico = ctk.CTkLabel(opcoes, text="", font=self.font_body, text_color=self.colors["accent"])
        self.lbl_feedback_tatico.pack(pady=(6, 8))

        self.campo_tatico = ctk.CTkFrame(painel, fg_color="#1f5f43")
        self.campo_tatico.pack(side="right", fill="both", expand=True, padx=12, pady=12)
        self._render_campinho_tatico()

        botoes = ctk.CTkFrame(self.content, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(
            botoes,
            text="Salvar Ajustes Taticos",
            width=240,
            height=44,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_soft"],
            command=self._salvar_ajustes_taticos,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            botoes,
            text="Voltar a Central" if self._fluxo_partida else "Voltar a Ajuda",
            width=200,
            height=44,
            command=self._mostrar_central_rodada if self._fluxo_partida else self._mostrar_basicos_jogo,
        ).pack(side="left", padx=8)

    def _salvar_ajustes_taticos(self):
        self._aplicar_escalacao_tatica_manual()
        self.clube_usuario.definir_formacao(self.formacao_var.get())
        self.estilo_jogo = self.estilo_var.get()
        salvar_save(self.temporada.obter_estado_mundo())
        if hasattr(self, "lbl_feedback_tatico"):
            self.lbl_feedback_tatico.configure(text="Ajustes salvos para os proximos jogos.")

    def _mostrar_elenco(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="ELENCO", font=self.font_title).pack(side="left", padx=16, pady=12)
        resumo = ctk.CTkFrame(self.content, fg_color=self.colors["panel_soft"])
        resumo.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(
            resumo,
            text=f"Titulares: {len(self.clube_usuario.escalar_titulares())} | Base: {len(self.clube_usuario.base_jovens)} | Folha: {self._formatar_dinheiro(self._folha_salarial())}",
            text_color=self.colors["text_dim"],
        ).pack(anchor="w", padx=12, pady=10)

        lista = ctk.CTkScrollableFrame(self.content, fg_color=self.colors["panel"])
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ordem = {"GOL": 0, "ZAG": 1, "LD": 2, "LE": 3, "VOL": 4, "MC": 5, "MEI": 6, "PE": 7, "PD": 8, "ATA": 9}
        titulares = set(self.clube_usuario.escalar_titulares())
        elenco_ordenado = sorted(
            self.clube_usuario.elenco,
            key=lambda j: (ordem.get(j.posicao, 99), -j.overall, j.nome),
        )
        if self.clube_usuario.base_jovens:
            elenco_ordenado += sorted(
                self.clube_usuario.base_jovens,
                key=lambda j: (ordem.get(j.posicao, 99), -j.potencial, j.nome),
            )

        for jogador in elenco_ordenado:
            base = jogador in getattr(self.clube_usuario, "base_jovens", [])
            card = ctk.CTkFrame(lista, fg_color=self.colors["panel_soft"], corner_radius=12)
            card.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(
                card,
                text=jogador.posicao,
                width=52,
                fg_color=self._cor_posicao(jogador.posicao),
                corner_radius=10,
            ).pack(side="left", padx=10, pady=10)
            nome = jogador.nome + (" [Base]" if base else " [Tit]" if jogador in titulares else "")
            texto = ctk.CTkFrame(card, fg_color="transparent")
            texto.pack(side="left", fill="x", expand=True, padx=4, pady=8)
            ctk.CTkLabel(texto, text=nome, font=self.font_body, anchor="w").pack(anchor="w")
            ctk.CTkLabel(
                texto,
                text=self._resumo_status_jogador(jogador),
                text_color=self.colors["text_dim"],
                anchor="w",
            ).pack(anchor="w")
            meta = ctk.CTkFrame(card, fg_color="transparent")
            meta.pack(side="left", padx=6)
            ctk.CTkLabel(meta, text=f"OVR {jogador.overall}", font=self.font_sub).pack(anchor="w")
            ctk.CTkLabel(meta, text=f"{jogador.idade} anos", text_color=self.colors["text_dim"]).pack(anchor="w")
            if jogador.lesao_dias > 0:
                ctk.CTkLabel(card, text=f"{jogador.lesao_dias}d", text_color="#f87171").pack(side="left", padx=10)
            ctk.CTkButton(
                card,
                text="Detalhes",
                width=110,
                command=lambda j=jogador: self._abrir_detalhe_jogador(j),
            ).pack(side="right", padx=10, pady=10)

    def _abrir_detalhe_jogador(self, jogador):
        topo = ctk.CTkToplevel(self)
        topo.title(jogador.nome)
        topo.geometry("560x640")

        card = ctk.CTkFrame(topo, fg_color=self.colors["bg"])
        card.pack(fill="both", expand=True, padx=14, pady=14)

        cabecalho = ctk.CTkFrame(card, fg_color=self.colors["panel"])
        cabecalho.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(cabecalho, text=jogador.nome, font=self.font_title).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            cabecalho,
            text=f"{jogador.posicao} | OVR {jogador.overall} | Potencial {jogador.potencial} | {jogador.idade} anos",
            text_color=self.colors["text_dim"],
        ).pack(anchor="w", padx=14, pady=(0, 12))

        stats = ctk.CTkFrame(card, fg_color=self.colors["panel"])
        stats.pack(fill="x", pady=(0, 10))
        campos = [
            ("Forma", f"{jogador.forma:.1f}"),
            ("Fadiga", f"{jogador.fadiga:.1f}"),
            ("Jogos", str(jogador.jogos_temporada)),
            ("Salario", self._formatar_dinheiro(jogador.salario)),
            ("Mercado", self._formatar_dinheiro(self._valor_mercado_jogador(jogador))),
            ("Status", self._resumo_status_jogador(jogador)),
        ]
        for texto, valor in campos:
            linha = ctk.CTkFrame(stats, fg_color="transparent")
            linha.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(linha, text=texto, width=120, anchor="w", text_color=self.colors["text_dim"]).pack(side="left")
            ctk.CTkLabel(linha, text=valor, anchor="w").pack(side="left")

        extras = ctk.CTkFrame(card, fg_color=self.colors["panel"])
        extras.pack(fill="both", expand=True, pady=(0, 10))
        ctk.CTkLabel(extras, text="Perfil do jogador", font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 6))
        habilidades = ", ".join(jogador.habilidades) if jogador.habilidades else "Nenhuma habilidade especial"
        defeitos = ", ".join(jogador.defeitos) if jogador.defeitos else "Nenhum defeito relevante"
        origem = "Formado na base" if jogador.origem_base else "Contratado"
        for texto in (
            f"Origem: {origem}",
            f"Habilidades: {habilidades}",
            f"Defeitos: {defeitos}",
        ):
            ctk.CTkLabel(
                extras,
                text=texto,
                justify="left",
                wraplength=500,
                text_color=self.colors["text_dim"],
            ).pack(anchor="w", padx=12, pady=4)

        feedback = ctk.CTkLabel(card, text="", text_color=self.colors["accent"])
        feedback.pack(anchor="w", pady=(0, 8))

        botoes = ctk.CTkFrame(card, fg_color="transparent")
        botoes.pack(fill="x")
        ctk.CTkButton(
            botoes,
            text="Treino Individual",
            width=180,
            command=lambda: self._aplicar_treino_jogador(jogador, feedback),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            botoes,
            text="Colocar a Venda",
            width=180,
            command=lambda: self._vender_jogador(jogador, topo),
        ).pack(side="left", padx=8)
        if jogador in getattr(self.clube_usuario, "base_jovens", []):
            ctk.CTkButton(
                botoes,
                text="Promover",
                width=120,
                command=lambda: self._promover_jovem_da_base(jogador, topo),
            ).pack(side="left", padx=8)

    def _aplicar_treino_jogador(self, jogador, feedback_label):
        custo = 8_000 + (jogador.overall * 120)
        if self.clube_usuario.financas < custo:
            feedback_label.configure(text="Caixa insuficiente para esse treino.")
            return
        self.clube_usuario.financas -= custo
        jogador.atualizar_forma(0.8)
        jogador.evoluir(bonus_ct=0.08 + (self.clube_usuario.nivel_ct / 220))
        feedback_label.configure(text=f"Treino concluido. Custo: {self._formatar_dinheiro(custo)}")
        salvar_save(self.temporada.obter_estado_mundo())

    def _vender_jogador(self, jogador, janela):
        valor = self._valor_mercado_jogador(jogador)
        if jogador in self.clube_usuario.elenco:
            self.clube_usuario.elenco.remove(jogador)
        elif jogador in getattr(self.clube_usuario, "base_jovens", []):
            self.clube_usuario.base_jovens.remove(jogador)
        else:
            return
        self.clube_usuario.financas += valor
        salvar_save(self.temporada.obter_estado_mundo())
        janela.destroy()
        self._mostrar_elenco()
        self._append_log(f"-> {jogador.nome} foi vendido por {self._formatar_dinheiro(valor)}.")

    def _promover_jovem_da_base(self, jogador, janela):
        self.clube_usuario.promover_jovem(jogador, definitivo=True)
        salvar_save(self.temporada.obter_estado_mundo())
        janela.destroy()
        self._mostrar_elenco()
        self._append_log(f"-> {jogador.nome} foi promovido ao elenco principal.")

    def _custo_upgrade_infra(self, chave):
        base = {"ct": 180_000, "base": 150_000, "estadio": 260_000}.get(chave, 100_000)
        nivel = {
            "ct": self.clube_usuario.nivel_ct,
            "base": self.clube_usuario.nivel_base,
            "estadio": self.clube_usuario.nivel_estadio,
        }.get(chave, 0)
        return int(base * (1 + (nivel * 0.18)))

    def _melhorar_estrutura(self, chave):
        custo = self._custo_upgrade_infra(chave)
        if self.clube_usuario.financas < custo:
            self._append_log("-> Caixa insuficiente para essa melhoria.")
            return

        self.clube_usuario.financas -= custo
        if chave == "ct":
            self.clube_usuario.infraestrutura["ct"] = min(30, self.clube_usuario.nivel_ct + 1)
        elif chave == "base":
            self.clube_usuario.infraestrutura["base"] = min(30, self.clube_usuario.nivel_base + 1)
        elif chave == "estadio":
            self.clube_usuario.infraestrutura["estadio_nivel"] = min(30, self.clube_usuario.nivel_estadio + 1)
            self.clube_usuario.infraestrutura["estadio_capacidade"] = min(
                80_000, self.clube_usuario.capacidade_estadio + 2_500
            )
        salvar_save(self.temporada.obter_estado_mundo())
        self._append_log(f"-> Estrutura melhorada ({chave}) por {self._formatar_dinheiro(custo)}.")
        self._mostrar_financeiro()

    def _atualizar_staff_financeiro(self, campo, valor):
        valor = int(valor)
        if campo == "auxiliar":
            self.clube_usuario.definir_nivel_auxiliar(valor)
        else:
            self.clube_usuario.definir_nivel_olheiro(valor)
        salvar_save(self.temporada.obter_estado_mundo())
        self._mostrar_financeiro()

    def _atualizar_investimento_base_ui(self, valor):
        self.clube_usuario.investimento_base = valor
        salvar_save(self.temporada.obter_estado_mundo())
        self._mostrar_financeiro()

    def _mostrar_financeiro(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="FINANCEIRO E ESTRUTURAS", font=self.font_title).pack(
            side="left", padx=16, pady=12
        )

        root = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        cards = ctk.CTkFrame(root, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 10))
        dados = [
            ("Saldo", self._formatar_dinheiro(self.clube_usuario.financas)),
            ("Folha salarial", self._formatar_dinheiro(self._folha_salarial())),
            ("Manutencao infra", self._formatar_dinheiro(self.clube_usuario.custo_manutencao_infra_mensal())),
            ("Staff mensal", self._formatar_dinheiro(self.clube_usuario.custo_staff_mensal())),
        ]
        for titulo, valor in dados:
            bloco = ctk.CTkFrame(cards, fg_color=self.colors["panel"])
            bloco.pack(side="left", fill="both", expand=True, padx=6)
            ctk.CTkLabel(bloco, text=titulo, font=self.font_body, text_color=self.colors["text_dim"]).pack(
                anchor="w", padx=12, pady=(10, 4)
            )
            ctk.CTkLabel(bloco, text=valor, font=self.font_sub).pack(anchor="w", padx=12, pady=(0, 12))

        gestao = ctk.CTkFrame(root, fg_color=self.colors["panel"])
        gestao.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(gestao, text="Politicas do clube", font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 6))

        linha = ctk.CTkFrame(gestao, fg_color="transparent")
        linha.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(linha, text="Investimento na base", width=180, anchor="w").pack(side="left")
        invest_var = ctk.StringVar(value=self.clube_usuario.investimento_base)
        ctk.CTkSegmentedButton(
            linha,
            values=["baixo", "medio", "alto"],
            variable=invest_var,
            command=self._atualizar_investimento_base_ui,
        ).pack(side="left", padx=8)

        linha_staff = ctk.CTkFrame(gestao, fg_color="transparent")
        linha_staff.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(linha_staff, text="Auxiliar", width=180, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(
            linha_staff,
            values=[str(i) for i in range(1, 8)],
            command=lambda valor: self._atualizar_staff_financeiro("auxiliar", valor),
            variable=ctk.StringVar(value=str(self.clube_usuario.nivel_auxiliar)),
            width=100,
        ).pack(side="left", padx=8)
        ctk.CTkLabel(linha_staff, text="Olheiro", width=100, anchor="w").pack(side="left", padx=(20, 0))
        ctk.CTkOptionMenu(
            linha_staff,
            values=[str(i) for i in range(1, 8)],
            command=lambda valor: self._atualizar_staff_financeiro("olheiro", valor),
            variable=ctk.StringVar(value=str(self.clube_usuario.nivel_olheiro)),
            width=100,
        ).pack(side="left", padx=8)

        infra = ctk.CTkFrame(root, fg_color="transparent")
        infra.pack(fill="x", pady=(0, 10))
        estruturas = [
            ("Centro de Treinamento", "ct", self.clube_usuario.nivel_ct, f"Nivel {self.clube_usuario.nivel_ct}/30"),
            ("Academia de Base", "base", self.clube_usuario.nivel_base, f"Nivel {self.clube_usuario.nivel_base}/30"),
            (
                "Estadio",
                "estadio",
                self.clube_usuario.nivel_estadio,
                f"Nivel {self.clube_usuario.nivel_estadio}/30 | Capacidade {self.clube_usuario.capacidade_estadio}",
            ),
        ]
        for titulo, chave, _, subtitulo in estruturas:
            bloco = ctk.CTkFrame(infra, fg_color=self.colors["panel"])
            bloco.pack(fill="x", pady=6)
            ctk.CTkLabel(bloco, text=titulo, font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 4))
            ctk.CTkLabel(bloco, text=subtitulo, text_color=self.colors["text_dim"]).pack(
                anchor="w", padx=12, pady=(0, 6)
            )
            ctk.CTkButton(
                bloco,
                text=f"Melhorar por {self._formatar_dinheiro(self._custo_upgrade_infra(chave))}",
                width=240,
                command=lambda c=chave: self._melhorar_estrutura(c),
            ).pack(anchor="w", padx=12, pady=(0, 12))

    def _mostrar_calendario_completo(self):
        self._clear_content()
        if self._calendario_cursor is None:
            base = self.temporada.data_atual if self.temporada else date.today()
            self._calendario_cursor = date(base.year, base.month, 1)
            self._calendario_dia_selecionado = base.day

        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="CALENDARIO COMPLETO", font=self.font_title).pack(side="left", padx=16, pady=12)

        nav = ctk.CTkFrame(self.content, fg_color="transparent")
        nav.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkButton(nav, text="<", width=40, command=lambda: self._mudar_mes_calendario(-1)).pack(side="left", padx=4)
        ctk.CTkLabel(
            nav,
            text=f"{self._mes_nome_pt(self._calendario_cursor.month)} {self._calendario_cursor.year}",
            font=self.font_sub,
        ).pack(side="left", padx=12)
        ctk.CTkButton(nav, text=">", width=40, command=lambda: self._mudar_mes_calendario(1)).pack(side="left", padx=4)
        ctk.CTkButton(nav, text="Voltar ao mes atual", command=self._resetar_mes_calendario).pack(side="right", padx=4)

        corpo = ctk.CTkFrame(self.content, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        grade = ctk.CTkFrame(corpo, fg_color=self.colors["panel"])
        grade.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._render_grade_calendario(grade)

        lateral = ctk.CTkFrame(corpo, fg_color=self.colors["panel"], width=320)
        lateral.pack(side="left", fill="y", padx=(8, 0))
        lateral.pack_propagate(False)
        self._render_eventos_calendario(lateral)

    def _mudar_mes_calendario(self, delta):
        self._calendario_cursor = self._avancar_mes_cursor(self._calendario_cursor, delta)
        self._calendario_dia_selecionado = 1
        self._mostrar_calendario_completo()

    def _resetar_mes_calendario(self):
        base = self.temporada.data_atual if self.temporada else date.today()
        self._calendario_cursor = date(base.year, base.month, 1)
        self._calendario_dia_selecionado = base.day
        self._mostrar_calendario_completo()

    def _selecionar_dia_calendario(self, dia):
        self._calendario_dia_selecionado = dia
        self._mostrar_calendario_completo()

    def _render_grade_calendario(self, parent):
        for widget in parent.winfo_children():
            widget.destroy()
        for i, nome in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]):
            ctk.CTkLabel(parent, text=nome, text_color=self.colors["text_dim"]).grid(row=0, column=i, padx=4, pady=4)
            parent.grid_columnconfigure(i, weight=1)

        ano = self._calendario_cursor.year
        mes = self._calendario_cursor.month
        agenda = self.temporada.eventos_por_data_mes(ano, mes) if self.temporada else {}
        _, ultimo_dia = pycalendar.monthrange(ano, mes)
        primeiro_dia = date(ano, mes, 1).weekday()
        for dia in range(1, ultimo_dia + 1):
            idx = primeiro_dia + (dia - 1)
            linha = (idx // 7) + 1
            coluna = idx % 7
            eventos = agenda.get(dia, [])
            fg = self.colors["accent_soft"] if dia == getattr(self, "_calendario_dia_selecionado", 1) else self.colors["panel_soft"]
            botao = ctk.CTkButton(
                parent,
                text=str(dia) if not eventos else f"{dia}\n{len(eventos)} jogo(s)",
                fg_color=fg,
                hover_color=self.colors["accent"],
                height=72,
                command=lambda d=dia: self._selecionar_dia_calendario(d),
            )
            botao.grid(row=linha, column=coluna, sticky="nsew", padx=4, pady=4)
            parent.grid_rowconfigure(linha, weight=1)

    def _render_eventos_calendario(self, parent):
        for widget in parent.winfo_children():
            widget.destroy()
        dia = getattr(self, "_calendario_dia_selecionado", 1)
        ano = self._calendario_cursor.year
        mes = self._calendario_cursor.month
        agenda = self.temporada.eventos_por_data_mes(ano, mes) if self.temporada else {}
        eventos = agenda.get(dia, [])

        ctk.CTkLabel(parent, text=f"Dia {dia}", font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 6))
        if not eventos:
            ctk.CTkLabel(parent, text="Nenhum evento agendado.", text_color=self.colors["text_dim"]).pack(
                anchor="w", padx=12, pady=12
            )
            return
        lista = ctk.CTkScrollableFrame(parent, fg_color=self.colors["panel_soft"])
        lista.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for evento in eventos:
            bloco = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
            bloco.pack(fill="x", pady=5)
            ctk.CTkLabel(bloco, text=self._nome_competicao_ui(evento.get("competicao", "")), font=self.font_body).pack(
                anchor="w", padx=10, pady=(8, 3)
            )
            if evento.get("adversario"):
                ctk.CTkLabel(
                    bloco,
                    text=f"vs {evento['adversario']} | {evento['horario']}",
                    text_color=self.colors["text_dim"],
                ).pack(anchor="w", padx=10, pady=(0, 8))
            else:
                ctk.CTkLabel(
                    bloco,
                    text=f"Evento de fase | {evento['horario']}",
                    text_color=self.colors["text_dim"],
                ).pack(anchor="w", padx=10, pady=(0, 8))

    @staticmethod
    def _sigla_clube(nome):
        partes = [p for p in nome.split() if p]
        if len(partes) >= 2:
            return (partes[0][:1] + partes[1][:1]).upper()
        return nome[:2].upper()

    def _mostrar_resultados_rodada(self):
        self._mostrar_tabelas(modo_inicial="Resultados")

    @staticmethod
    def _nome_competicao_ui(comp_id):
        mapa = {
            "bra_a": "Brasileirao A",
            "bra_b": "Brasileirao B",
            "bra_c": "Brasileirao C",
            "bra_d": "Brasileirao D",
            "bra_c_fase1": "Brasileirao C - Fase Inicial",
            "copa_brasil": "Copa do Brasil",
            "paulistao_a1": "Paulistao A1",
            "paulistao_a2": "Paulistao A2",
            "paulistao_a3": "Paulistao A3",
            "cariocao_a1": "Cariocao A1",
        }
        if comp_id in mapa:
            return mapa[comp_id]
        if comp_id.startswith("bra_d_g"):
            try:
                numero = int(comp_id.replace("bra_d_g", ""))
            except ValueError:
                numero = comp_id.replace("bra_d_g", "")
            return f"Brasileirao D - Grupo {numero}"
        if comp_id.startswith("bra_c_grupo_"):
            sufixo = comp_id.split("_")[-1].upper()
            return f"Brasileirao C - Grupo {sufixo}"
        if comp_id.startswith("paulistao_a2_g"):
            return f"Paulistao A2 - Grupo {comp_id.split('g')[-1]}"
        if comp_id.startswith("paulistao_a2_sf_g"):
            return f"Paulistao A2 - Semi Grupo {comp_id.split('g')[-1]}"
        if comp_id in COMPETICOES:
            return COMPETICOES[comp_id].get("nome", comp_id.upper())
        return comp_id.replace("_", " ").title()

    @staticmethod
    def _normalizar_base_tabela(comp):
        if comp.startswith("bra_d_g"):
            return "bra_d"
        if comp.startswith("bra_c_"):
            return "bra_c"
        if comp.startswith("paulistao_a2_"):
            return "paulistao_a2"
        return comp

    def _categoria_tabela_atual(self):
        return self.tabela_categoria_var.get() if hasattr(self, "tabela_categoria_var") else "Meu Time"

    def _competicoes_base_tabelas(self):
        categoria = self._categoria_tabela_atual()
        if categoria == "Estaduais":
            return list(ESTADOS_ESTADUAIS.keys())

        bases = []
        if categoria == "Meu Time":
            fonte = list(dict.fromkeys(getattr(self.clube_usuario, "competicoes", []) + [self.comp_id]))
        elif categoria == "Nacionais":
            fonte = [comp_id for comp_id, meta in COMPETICOES.items() if meta.get("nivel") == "nacional"]
        else:
            fonte = [
                comp_id
                for comp_id, meta in COMPETICOES.items()
                if meta.get("nivel") in ("internacional", "intercontinental", "mundial")
            ]

        for comp in fonte:
            base = self._normalizar_base_tabela(comp)
            if base not in bases:
                bases.append(base)

        for comp in sorted(self.temporada.tabelas.keys()):
            base = self._normalizar_base_tabela(comp)
            nivel = COMPETICOES.get(base, {}).get("nivel")
            if categoria == "Meu Time" and any(base == self._normalizar_base_tabela(c) for c in self.clube_usuario.competicoes):
                if base not in bases:
                    bases.append(base)
            elif categoria == "Nacionais" and nivel == "nacional" and base not in bases:
                bases.append(base)
            elif categoria == "Internacionais" and nivel in ("internacional", "intercontinental", "mundial") and base not in bases:
                bases.append(base)
        return bases

    def _variantes_competicao_tabela(self, base, comps):
        if base == "bra_c":
            fase1 = [c for c in comps if c == "bra_c_fase1"]
            grupos = [c for c in comps if c.startswith("bra_c_grupo_")]
            return fase1 + grupos if (fase1 or grupos) else [base]
        if base == "bra_d":
            grupos = [c for c in comps if c.startswith("bra_d_g")]
            return grupos if grupos else [base]
        if base == "paulistao_a2":
            principal = [c for c in comps if c == "paulistao_a2"]
            extras = [c for c in comps if c.startswith("paulistao_a2_")]
            return principal + extras if (principal or extras) else [base]
        if base in comps or base in COMPETICOES:
            return [base]
        variantes = [c for c in comps if c.startswith(base)]
        return variantes or [base]

    def _competicoes_por_base(self, base):
        comps = sorted(self.temporada.tabelas.keys())
        if self._categoria_tabela_atual() == "Estaduais":
            grupos = []
            for comp_id in ESTADOS_ESTADUAIS.get(base, {}).get("competicoes", []):
                grupos.extend(self._variantes_competicao_tabela(comp_id, comps))
            return grupos
        return self._variantes_competicao_tabela(base, comps)

    def _descricao_base_tabela(self, base):
        if not base:
            return "Sem dados"
        if self._categoria_tabela_atual() == "Estaduais":
            return ESTADOS_ESTADUAIS.get(base, {}).get("nome", base)
        return self._nome_competicao_ui(base)

    def _descricao_grupo_tabela(self, competicao):
        if not competicao:
            return "Sem grupo"
        return self._nome_competicao_ui(competicao)

    def _competicao_base_atual(self):
        if not getattr(self, "_bases_disponiveis", None):
            return None
        self._indice_base_tabela = max(0, min(self._indice_base_tabela, len(self._bases_disponiveis) - 1))
        return self._bases_disponiveis[self._indice_base_tabela]

    def _competicao_grupo_atual(self):
        base = self._competicao_base_atual()
        grupos = self._competicoes_por_base(base) if base else []
        self._grupos_tabela_disponiveis = grupos
        if not grupos:
            return None
        self._indice_grupo_tabela = max(0, min(self._indice_grupo_tabela, len(grupos) - 1))
        return grupos[self._indice_grupo_tabela]

    def _mudar_base_tabela(self, delta):
        if not getattr(self, "_bases_disponiveis", None):
            return
        self._indice_base_tabela = (self._indice_base_tabela + delta) % len(self._bases_disponiveis)
        self._indice_grupo_tabela = 0
        self._atualizar_painel_tabelas()

    def _mudar_grupo_tabela(self, delta):
        grupos = getattr(self, "_grupos_tabela_disponiveis", [])
        if not grupos:
            return
        self._indice_grupo_tabela = (self._indice_grupo_tabela + delta) % len(grupos)
        self._atualizar_painel_tabelas()

    def _alternar_categoria_tabela(self, _=None):
        self._indice_base_tabela = 0
        self._indice_grupo_tabela = 0
        self._bases_disponiveis = self._competicoes_base_tabelas()
        self._atualizar_painel_tabelas()

    def _rodadas_finalizadas(self, competicao_id):
        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        partidas = db_manager.listar_partidas_competicao(competicao_id, temporada_ano, rodada=None)
        return sorted({int(p["rodada"]) for p in partidas if p.get("rodada") is not None})

    def _navegar_rodada(self, delta):
        if not getattr(self, "_rodadas_disponiveis", None):
            return
        atual_txt = self.tabela_rodada_var.get()
        if not atual_txt:
            return
        try:
            atual = int(atual_txt)
        except ValueError:
            return
        if atual not in self._rodadas_disponiveis:
            return
        idx = self._rodadas_disponiveis.index(atual) + delta
        idx = max(0, min(len(self._rodadas_disponiveis) - 1, idx))
        self.tabela_rodada_var.set(str(self._rodadas_disponiveis[idx]))
        self._atualizar_painel_tabelas()

    def _cor_tag_classificacao(self, competicao, posicao, total):
        if competicao == "bra_a":
            if posicao == 1:
                return "#22c55e"
            if 2 <= posicao <= 4:
                return "#eab308"
            if posicao == 5:
                return "#fb923c"
            if 6 <= posicao <= 11:
                return "#38bdf8"
            if posicao > total - 4:
                return "#ef4444"
        if competicao == "bra_b":
            if posicao <= 2:
                return "#22c55e"
            if 3 <= posicao <= 6:
                return "#eab308"
            if posicao > total - 4:
                return "#ef4444"
        if competicao == "bra_c_fase1":
            if posicao <= 8:
                return "#22c55e"
            regras = self.temporada._regras_serie_c(self.temporada.estado_mundo["meta"]["temporada_atual"])
            if posicao > total - regras["rebaixados"]:
                return "#ef4444"
        if competicao in ("bra_c_grupo_a", "bra_c_grupo_b") and posicao <= 2:
            return "#22c55e"
        if competicao.startswith("bra_d_g") and posicao <= 4:
            return "#22c55e"
        return "#334155"

    def _render_classificacao_visual(self, parent, competicao):
        classif = self.temporada.classificacao(competicao)
        if not classif:
            ctk.CTkLabel(parent, text="Sem dados para exibir.", text_color=self.colors["text_dim"]).pack(pady=20)
            return

        cabecalho = ctk.CTkFrame(parent, fg_color=self.colors["panel_soft"])
        cabecalho.pack(fill="x", padx=10, pady=(10, 4))
        colunas = [("POS", 50), ("CLUBE", 260), ("PTS", 70), ("V", 55), ("E", 55), ("D", 55), ("GP", 60), ("GC", 60), ("SG", 60)]
        for texto, largura in colunas:
            ctk.CTkLabel(cabecalho, text=texto, width=largura, font=self.font_sub).pack(side="left", padx=3, pady=8)

        total = len(classif)
        lista = ctk.CTkScrollableFrame(parent, fg_color=self.colors["panel"])
        lista.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for idx, (clube, stats) in enumerate(classif, start=1):
            linha = ctk.CTkFrame(lista, fg_color=("#1a2435" if idx % 2 else "#16202f"))
            linha.pack(fill="x", pady=2)
            cor = self._cor_tag_classificacao(competicao, idx, total)
            ctk.CTkFrame(linha, fg_color=cor, width=6, height=34).pack(side="left", padx=(0, 8), pady=2)
            saldo = stats["gols_pro"] - stats["gols_contra"]
            valores = [
                (str(idx), 50),
                (clube.nome, 260),
                (str(stats["pontos"]), 70),
                (str(stats["vitorias"]), 55),
                (str(stats["empates"]), 55),
                (str(stats["derrotas"]), 55),
                (str(stats["gols_pro"]), 60),
                (str(stats["gols_contra"]), 60),
                (str(saldo), 60),
            ]
            for texto, largura in valores:
                ctk.CTkLabel(linha, text=texto, width=largura, anchor="w").pack(side="left", padx=3, pady=6)

    def _render_resultados_visual(self, parent, competicao):
        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        rodada_txt = self.tabela_rodada_var.get()
        if not rodada_txt:
            ctk.CTkLabel(parent, text="Ainda nao ha rodada finalizada.", text_color=self.colors["text_dim"]).pack(pady=20)
            return
        try:
            rodada = int(rodada_txt)
        except ValueError:
            ctk.CTkLabel(parent, text="Rodada invalida.", text_color=self.colors["text_dim"]).pack(pady=20)
            return

        partidas = db_manager.listar_partidas_competicao(competicao, temporada_ano, rodada=rodada)
        if not partidas:
            ctk.CTkLabel(parent, text="Sem resultados para esta rodada.", text_color=self.colors["text_dim"]).pack(pady=20)
            return

        lista = ctk.CTkScrollableFrame(parent, fg_color=self.colors["bg"])
        lista.pack(fill="both", expand=True, padx=10, pady=10)
        for jogo in partidas:
            card = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
            card.pack(fill="x", pady=6)
            casa = jogo["casa_nome"]
            fora = jogo["fora_nome"]
            gols_c = jogo["gols_casa"] if jogo["gols_casa"] is not None else "-"
            gols_f = jogo["gols_fora"] if jogo["gols_fora"] is not None else "-"

            ctk.CTkLabel(card, text=self._sigla_clube(casa), width=45).pack(side="left", padx=(8, 4), pady=10)
            ctk.CTkLabel(card, text=casa, width=200, anchor="e").pack(side="left", padx=4, pady=10)
            ctk.CTkLabel(card, text=f"{gols_c}  x  {gols_f}", font=self.font_sub, width=100).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(card, text=fora, width=200, anchor="w").pack(side="left", padx=4, pady=10)
            ctk.CTkLabel(card, text=self._sigla_clube(fora), width=45).pack(side="left", padx=(4, 8), pady=10)

    def _atualizar_controles_rodada(self, competicao):
        modo_resultados = self.tabela_modo_var.get() == "Resultados"
        self._rodadas_disponiveis = self._rodadas_finalizadas(competicao) if modo_resultados else []
        valores = [str(r) for r in self._rodadas_disponiveis] or ["-"]
        self.tabela_rodada_menu.configure(values=valores)
        if self.tabela_rodada_var.get() not in valores:
            self.tabela_rodada_var.set(valores[-1])
        estado_controles = "normal" if modo_resultados and self._rodadas_disponiveis else "disabled"
        self.btn_rodada_prev.configure(state=estado_controles)
        self.btn_rodada_next.configure(state=estado_controles)
        self.tabela_rodada_menu.configure(state=estado_controles)

    def _atualizar_painel_tabelas(self):
        self._bases_disponiveis = self._competicoes_base_tabelas()
        categoria = self._categoria_tabela_atual()
        base = self._competicao_base_atual()
        competicao = self._competicao_grupo_atual()
        if hasattr(self, "lbl_contexto_base"):
            self.lbl_contexto_base.configure(text="Estado" if categoria == "Estaduais" else "Competicao")
        if hasattr(self, "lbl_contexto_grupo"):
            self.lbl_contexto_grupo.configure(text="Divisao" if categoria == "Estaduais" else "Grupo / Fase")
        if hasattr(self, "lbl_competicao_base"):
            self.lbl_competicao_base.configure(text=self._descricao_base_tabela(base))
        if hasattr(self, "lbl_competicao_grupo"):
            self.lbl_competicao_grupo.configure(text=self._descricao_grupo_tabela(competicao))
        for widget in self.tabelas_body.winfo_children():
            widget.destroy()

        if not competicao:
            ctk.CTkLabel(self.tabelas_body, text="Nenhuma competicao disponivel nesta categoria.", text_color=self.colors["text_dim"]).pack(
                pady=24
            )
            self._rodadas_disponiveis = []
            self.tabela_rodada_menu.configure(values=["-"], state="disabled")
            self.tabela_rodada_var.set("-")
            self.btn_rodada_prev.configure(state="disabled")
            self.btn_rodada_next.configure(state="disabled")
            return

        self._atualizar_controles_rodada(competicao)

        titulo = ctk.CTkFrame(self.tabelas_body, fg_color=self.colors["panel"])
        titulo.pack(fill="x", padx=10, pady=(10, 8))
        ctk.CTkLabel(titulo, text=self._nome_competicao_ui(competicao), font=self.font_sub).pack(
            side="left", padx=12, pady=8
        )
        if competicao not in self.temporada.tabelas:
            ctk.CTkLabel(
                titulo,
                text="Ainda nao configurada nesta temporada",
                text_color=self.colors["text_dim"],
            ).pack(side="right", padx=12, pady=8)
        if self.tabela_modo_var.get() == "Classificacao":
            self._render_classificacao_visual(self.tabelas_body, competicao)
        else:
            self._render_resultados_visual(self.tabelas_body, competicao)

    def _mostrar_tabelas(self, modo_inicial="Classificacao"):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="TABELAS", font=self.font_title).pack(side="left", padx=16, pady=12)

        self.tabela_categoria_var = ctk.StringVar(value="Meu Time")
        self._bases_disponiveis = self._competicoes_base_tabelas()
        self._indice_base_tabela = 0
        self._indice_grupo_tabela = 0
        self.tabela_modo_var = ctk.StringVar(value=modo_inicial)
        self.tabela_rodada_var = ctk.StringVar(value="-")

        filtros = ctk.CTkFrame(self.content, fg_color="transparent")
        filtros.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkSegmentedButton(
            filtros,
            values=["Classificacao", "Resultados"],
            variable=self.tabela_modo_var,
            command=lambda _: self._atualizar_painel_tabelas(),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSegmentedButton(
            filtros,
            values=["Meu Time", "Nacionais", "Estaduais", "Internacionais"],
            variable=self.tabela_categoria_var,
            command=self._alternar_categoria_tabela,
        ).pack(side="left", padx=(0, 14))

        nav_comp = ctk.CTkFrame(filtros, fg_color="transparent")
        nav_comp.pack(side="left", padx=10)
        self.lbl_contexto_base = ctk.CTkLabel(nav_comp, text="Competicao", width=88, text_color=self.colors["text_dim"])
        self.lbl_contexto_base.pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav_comp, text="<", width=38, command=lambda: self._mudar_base_tabela(-1)).pack(side="left", padx=4)
        self.lbl_competicao_base = ctk.CTkLabel(nav_comp, text="", width=210, font=self.font_sub)
        self.lbl_competicao_base.pack(side="left", padx=4)
        ctk.CTkButton(nav_comp, text=">", width=38, command=lambda: self._mudar_base_tabela(1)).pack(side="left", padx=4)

        rodada_box = ctk.CTkFrame(filtros, fg_color="transparent")
        rodada_box.pack(side="right")
        self.btn_rodada_prev = ctk.CTkButton(
            rodada_box, text="<", width=38, command=lambda: self._navegar_rodada(-1)
        )
        self.btn_rodada_prev.pack(side="left", padx=4)
        self.tabela_rodada_menu = ctk.CTkOptionMenu(
            rodada_box,
            values=["-"],
            variable=self.tabela_rodada_var,
            command=lambda _: self._atualizar_painel_tabelas(),
            width=90,
        )
        self.tabela_rodada_menu.pack(side="left", padx=4)
        self.btn_rodada_next = ctk.CTkButton(
            rodada_box, text=">", width=38, command=lambda: self._navegar_rodada(1)
        )
        self.btn_rodada_next.pack(side="left", padx=4)

        self.tabelas_body = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        self.tabelas_body.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        rodape = ctk.CTkFrame(self.content, fg_color="transparent")
        rodape.pack(fill="x", padx=20, pady=(0, 20))
        nav_grupo = ctk.CTkFrame(rodape, fg_color="transparent")
        nav_grupo.pack(side="right")
        self.lbl_contexto_grupo = ctk.CTkLabel(nav_grupo, text="Grupo / Fase", width=96, text_color=self.colors["text_dim"])
        self.lbl_contexto_grupo.pack(side="left", padx=(0, 6))
        ctk.CTkButton(nav_grupo, text="<", width=38, command=lambda: self._mudar_grupo_tabela(-1)).pack(side="left", padx=4)
        self.lbl_competicao_grupo = ctk.CTkLabel(nav_grupo, text="", width=260, font=self.font_body)
        self.lbl_competicao_grupo.pack(side="left", padx=4)
        ctk.CTkButton(nav_grupo, text=">", width=38, command=lambda: self._mudar_grupo_tabela(1)).pack(side="left", padx=4)
        self._atualizar_painel_tabelas()

    def _mostrar_mensagens(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="MENSAGENS", font=self.font_title).pack(side="left", padx=16, pady=12)
        lista = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        msgs = mensagens.listar_mensagens(temporada_ano=temporada_ano, limite=50)
        if not msgs:
            ctk.CTkLabel(lista, text="Nenhuma mensagem no momento.", text_color=self.colors["text_dim"]).pack(pady=20)
        else:
            for msg in msgs:
                card = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
                card.pack(fill="x", pady=6)
                status = "NOVA" if msg["lido"] == 0 else "LIDA"
                topo = ctk.CTkFrame(card, fg_color="transparent")
                topo.pack(fill="x", padx=12, pady=(10, 2))
                ctk.CTkLabel(topo, text=msg["titulo"], font=self.font_sub).pack(side="left")
                ctk.CTkLabel(
                    topo,
                    text=status,
                    text_color=self.colors["accent"] if msg["lido"] == 0 else self.colors["text_dim"],
                ).pack(side="right")
                ctk.CTkLabel(card, text=msg["remetente"], text_color=self.colors["text_dim"]).pack(
                    anchor="w", padx=12, pady=(0, 4)
                )
                ctk.CTkLabel(
                    card,
                    text=msg["corpo"],
                    justify="left",
                    wraplength=900,
                    text_color=self.colors["text_dim"],
                ).pack(anchor="w", padx=12, pady=(0, 10))
            for msg in msgs:
                if msg["lido"] == 0:
                    mensagens.marcar_lida(msg["id"])

    def _mostrar_noticias(self):
        self._clear_content()
        header = ctk.CTkFrame(self.content, fg_color=self.colors["panel"])
        header.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(header, text="NOTICIAS", font=self.font_title).pack(side="left", padx=16, pady=12)
        lista = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        temporada_ano = self.temporada.estado_mundo["meta"]["temporada_atual"]
        itens = noticias.listar_noticias(temporada_ano=temporada_ano, limite=20)
        if not itens:
            ctk.CTkLabel(lista, text="Nenhuma noticia no momento.", text_color=self.colors["text_dim"]).pack(pady=20)
        else:
            for item in itens:
                card = ctk.CTkFrame(lista, fg_color=self.colors["panel"])
                card.pack(fill="x", pady=6)
                ctk.CTkLabel(card, text=item["titulo"], font=self.font_sub).pack(anchor="w", padx=12, pady=(10, 4))
                ctk.CTkLabel(
                    card,
                    text=item["corpo"],
                    justify="left",
                    wraplength=900,
                    text_color=self.colors["text_dim"],
                ).pack(anchor="w", padx=12, pady=(0, 10))

    def _capturar_saida(self, func):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            func()
        return buf.getvalue().strip()


def start_gui():
    app = TheTouchlineApp()
    app.mainloop()
