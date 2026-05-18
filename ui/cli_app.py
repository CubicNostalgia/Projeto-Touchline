import io
import sys

import db_manager
from core.carreira_service import (
    carregar_clubes_nacionais,
    criar_temporada,
    iniciar_proxima_temporada,
    listar_ligas_jogaveis,
)
from core.clube import FORMACOES
from core.objetivos import mensagem_boas_vindas_objetivos
from data.database import COMPETICOES, HIERARQUIA_COMPETICOES
from engine import mensagens, noticias
from save_manager import carregar_save, save_exists, salvar_save
from ui.exibir_elenco import exibir_elenco


def configurar_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def escolher_liga(estado_mundo=None):
    ligas = listar_ligas_jogaveis()
    print("\nEscolha a competicao nacional jogavel:")
    for idx, (_, nome) in enumerate(ligas, start=1):
        print(f"{idx}. {nome}")
    while True:
        opcao = input("Opcao: ").strip()
        if opcao.isdigit() and 1 <= int(opcao) <= len(ligas):
            comp_id, nome_liga = ligas[int(opcao) - 1]
            clubes_nacionais = carregar_clubes_nacionais(comp_id, estado_mundo=estado_mundo)
            return comp_id, clubes_nacionais, nome_liga


def escolher_clube(clubes):
    print("\nEscolha seu clube:\n")
    for i, clube in enumerate(clubes, start=1):
        print(f"{i}. {clube.nome}")
    while True:
        escolha = input("\nNumero do clube: ")
        if escolha.isdigit() and 1 <= int(escolha) <= len(clubes):
            return clubes[int(escolha) - 1]


def personalizar_escalacao(clube):
    print("\nPersonalizacao de escalacao")
    formacoes = list(FORMACOES.keys())
    for i, form in enumerate(formacoes, start=1):
        print(f"[{i}] {form}")
    opcao_formacao = input("Formacao: ").strip()
    if opcao_formacao.isdigit() and 1 <= int(opcao_formacao) <= len(formacoes):
        clube.definir_formacao(formacoes[int(opcao_formacao) - 1])

    custom = input("Deseja escolher manualmente os titulares? (s/n): ").lower().strip()
    if custom != "s":
        return

    for idx, jogador in enumerate(clube.elenco):
        print(f"[{idx}] {jogador.nome} - {jogador.posicao} OVR {jogador.overall}")
    ids = input("Digite EXATAMENTE 11 indices separados por virgula: ").split(",")
    try:
        sucesso = clube.definir_titulares([int(x.strip()) for x in ids])
        if not sucesso:
            print("Escalacao invalida: precisam ser 11 jogadores unicos.")
        else:
            print("Titulares definidos com sucesso.")
    except ValueError:
        print("Entrada invalida. Escalacao automatica mantida.")


def exibir_tabelas_disponiveis(temporada):
    competicoes = list(temporada.tabelas.keys())
    tem_grupos_d = any(c.startswith("bra_d_g") for c in competicoes)
    tem_grupos_c = any(c in ("bra_c_grupo_a", "bra_c_grupo_b") for c in competicoes)

    competicoes = [c for c in competicoes if not c.startswith("bra_d_g")]
    competicoes = [c for c in competicoes if c not in ("bra_c_grupo_a", "bra_c_grupo_b")]
    competicoes = [
        c
        for c in competicoes
        if c not in ("paulistao_a2_g2", "paulistao_a2_g3", "paulistao_a2_sf_g1", "paulistao_a2_sf_g2")
    ]

    if tem_grupos_d:
        competicoes.append("bra_d_grupo_usuario")
        competicoes.append("bra_d_grupos_outros")
    if tem_grupos_c:
        competicoes.append("bra_c_grupo_usuario")
        competicoes.append("bra_c_grupos_outros")

    if not competicoes:
        print("\nNenhuma tabela disponivel no momento.")
        return

    print("\nTabelas disponiveis")
    for i, comp in enumerate(competicoes, start=1):
        if comp == "bra_d_grupo_usuario":
            nome = "Serie D: Meu Grupo"
        elif comp == "bra_d_grupos_outros":
            nome = "Serie D: Outros Grupos"
        elif comp == "bra_c_grupo_usuario":
            nome = "Serie C: Meu Grupo"
        elif comp == "bra_c_grupos_outros":
            nome = "Serie C: Outros Grupos"
        else:
            nome = COMPETICOES.get(comp, {}).get("nome", comp.upper())
        print(f"[{i}] {nome}")
    print("[0] Voltar")

    escolha = input("\nEscolha: ").strip()
    if escolha.isdigit():
        idx = int(escolha)
        if idx == 0:
            return
        if 1 <= idx <= len(competicoes):
            comp = competicoes[idx - 1]
            if comp == "bra_d_grupo_usuario":
                temporada.exibir_grupo_serie_d_usuario()
                if input("Mostrar resultados da ultima rodada? (s/n): ").strip().lower() == "s":
                    temporada.exibir_resultados_serie_d_grupo_usuario()
            elif comp == "bra_d_grupos_outros":
                temporada.exibir_grupos_serie_d_outros()
                if input("Mostrar resultados da ultima rodada? (s/n): ").strip().lower() == "s":
                    temporada.exibir_resultados_serie_d_grupos_outros()
            elif comp == "bra_c_grupo_usuario":
                temporada.exibir_grupo_serie_c_usuario()
                if input("Mostrar resultados da ultima rodada? (s/n): ").strip().lower() == "s":
                    temporada.exibir_resultados_serie_c_grupo_usuario()
            elif comp == "bra_c_grupos_outros":
                temporada.exibir_grupos_serie_c_outros()
                if input("Mostrar resultados da ultima rodada? (s/n): ").strip().lower() == "s":
                    temporada.exibir_resultados_serie_c_grupos_outros()
            else:
                temporada.exibir_tabela(comp)


def exibir_noticias(temporada):
    temporada_ano = temporada.estado_mundo["meta"]["temporada_atual"]
    itens = noticias.listar_noticias(temporada_ano=temporada_ano, limite=20)
    if not itens:
        print("\nNenhuma noticia no momento.")
        return
    print("\nNoticias")
    for item in itens:
        print(f"- {item['titulo']}")
        print(f"  {item['corpo']}")


def exibir_mensagens(temporada):
    temporada_ano = temporada.estado_mundo["meta"]["temporada_atual"]
    msgs = mensagens.listar_mensagens(temporada_ano=temporada_ano, limite=50)
    if not msgs:
        print("\nNenhuma mensagem no momento.")
        return

    print("\nMensagens")
    for msg in msgs:
        status = "NOVA" if msg["lido"] == 0 else "lida"
        print(f"[{msg['id']}] ({status}) {msg['remetente']}: {msg['titulo']}")
        print(f"    {msg['corpo']}")
    for msg in msgs:
        if msg["lido"] == 0:
            mensagens.marcar_lida(msg["id"])


def run_cli():
    configurar_stdout_utf8()
    print("TOUCHLINE - Football Manager (Alpha)\n")
    print("Hierarquia de competicoes:", " < ".join(HIERARQUIA_COMPETICOES))

    db_manager.seed_database_if_needed()
    estado_mundo = carregar_save() if save_exists() else None
    meta = (estado_mundo or {}).get("meta", {})
    comp_salvo = meta.get("comp_usuario_id")
    clube_salvo = meta.get("clube_usuario_id")
    retomado_save = False
    if comp_salvo and clube_salvo:
        comp_id = comp_salvo
        clubes_nacionais = carregar_clubes_nacionais(comp_id, estado_mundo=estado_mundo)
        clube_usuario = next((c for c in clubes_nacionais if c.id == clube_salvo), None)
        if clube_usuario:
            print(f"Save encontrado: retomando carreira com {clube_usuario.nome}.")
            retomado_save = True
        else:
            comp_id, clubes_nacionais, _ = escolher_liga(estado_mundo=estado_mundo)
            clube_usuario = escolher_clube(clubes_nacionais)
    else:
        comp_id, clubes_nacionais, _ = escolher_liga(estado_mundo=estado_mundo)
        clube_usuario = escolher_clube(clubes_nacionais)

    temporada, objetivos = criar_temporada(
        comp_id=comp_id,
        clubes_nacionais=clubes_nacionais,
        clube_usuario=clube_usuario,
        estado_mundo=estado_mundo,
    )
    if not retomado_save:
        mensagem_boas_vindas_objetivos(clube_usuario, objetivos)
        objetivos_semanais = temporada.estado_mundo.get("meta", {}).get("objetivos_semanais", [])
        if objetivos_semanais:
            print("\nObjetivos semanais em foco:")
            for obj in objetivos_semanais[:5]:
                print(f"- {obj}")
        personalizar_escalacao(clube_usuario)

    while True:
        nao_lidas = mensagens.contar_nao_lidas(temporada.estado_mundo["meta"]["temporada_atual"])
        badge_msg = f" ({nao_lidas})" if nao_lidas else ""
        print("\nMenu")
        print("[1] Exibir elenco")
        print("[2] Simular proxima rodada")
        print("[3] Simular temporada inteira")
        print("[4] Ajustar formacao/titulares")
        print("[5] Ver tabelas")
        print(f"[6] Mensagens{badge_msg}")
        print("[7] Noticias")
        print("[0] Sair")

        opcao = input("\nEscolha: ")
        if opcao == "1":
            exibir_elenco(clube_usuario)
        elif opcao == "2":
            avancou = temporada.simular_proxima_rodada()
            salvar_save(temporada.obter_estado_mundo())
            if not avancou:
                nova_temp = iniciar_proxima_temporada(temporada.obter_estado_mundo(), clube_usuario.id)
                if nova_temp[0]:
                    temporada, clube_usuario, comp_id, _ = nova_temp
        elif opcao == "3":
            temporada.jogar_temporada_completa()
            salvar_save(temporada.obter_estado_mundo())
            nova_temp = iniciar_proxima_temporada(temporada.obter_estado_mundo(), clube_usuario.id)
            if nova_temp[0]:
                temporada, clube_usuario, comp_id, _ = nova_temp
        elif opcao == "4":
            personalizar_escalacao(clube_usuario)
        elif opcao == "5":
            exibir_tabelas_disponiveis(temporada)
        elif opcao == "6":
            exibir_mensagens(temporada)
        elif opcao == "7":
            exibir_noticias(temporada)
        elif opcao == "0":
            print("\nSaindo do jogo...")
            break
