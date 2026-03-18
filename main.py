import io
import sys

from data.clubes import (
    carregar_clubes_serie_a,
    carregar_clubes_serie_b_2026,
    carregar_clubes_serie_c_2026,
    carregar_clubes_serie_d_2026,
    carregar_clubes_paulistao,
)
from core.clube import FORMACOES
from core.liga import Liga
from core.temporada import Temporada
from save_manager import save_exists, carregar_save, iniciar_novo_save, salvar_save
from ui.exibir_elenco import exibir_elenco
from ui.mensagens import mensagem_boas_vindas_objetivos, gerar_objetivos_por_clube
from data.database import HIERARQUIA_COMPETICOES, COMPETICOES
from engine import mensagens
from engine import noticias
import db_manager

CARREGADORES_COMP = {
    "bra_a": carregar_clubes_serie_a,
    "bra_b": carregar_clubes_serie_b_2026,
    "bra_c": carregar_clubes_serie_c_2026,
    "bra_d": carregar_clubes_serie_d_2026,
}


def configurar_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def escolher_liga(estado_mundo=None):
    print("\nEscolha a competição nacional jogável:")
    print("1. Campeonato Brasileiro Série A")
    print("2. Campeonato Brasileiro Série B")
    print("3. Campeonato Brasileiro Série C")
    print("4. Campeonato Brasileiro Série D")
    while True:
        op = input("Opção: ").strip()
        if op == "1":
            return "bra_a", carregar_clubes_serie_a(estado_mundo=estado_mundo), "Campeonato Brasileiro Série A"
        if op == "2":
            return "bra_b", carregar_clubes_serie_b_2026(estado_mundo=estado_mundo), "Campeonato Brasileiro Série B"
        if op == "3":
            return "bra_c", carregar_clubes_serie_c_2026(estado_mundo=estado_mundo), "Campeonato Brasileiro  Série C"
        if op == "4":
            return "bra_d", carregar_clubes_serie_d_2026(estado_mundo=estado_mundo), "Campeonato Brasileiro Série D"


def _competicao_principal(clube):
    if "bra_a" in clube.competicoes:
        return "bra_a"
    if "bra_b" in clube.competicoes:
        return "bra_b"
    if "bra_c" in clube.competicoes:
        return "bra_c"
    if "bra_d" in clube.competicoes:
        return "bra_d"
    return "bra_b"


def _nome_liga(comp_id):
    return COMPETICOES.get(comp_id, {}).get("nome", comp_id.upper())


def iniciar_proxima_temporada(estado_mundo, clube_id):
    clube_db = db_manager.carregar_clube_por_id(clube_id, temporada_ano=estado_mundo["meta"]["temporada_atual"])
    if not clube_db:
        return None, None, None
    comp_id = _competicao_principal(clube_db)
    clubes_nacionais = CARREGADORES_COMP.get(comp_id, carregar_clubes_serie_b_2026)(estado_mundo=estado_mundo)
    clube_usuario = next((c for c in clubes_nacionais if c.id == clube_id), clube_db)

    clubes_paulistao = carregar_clubes_paulistao(clubes_nacionais, estado_mundo=estado_mundo) if "paulistao_a1" in clube_usuario.competicoes else []
    if clubes_paulistao:
        mapa = {c.id: c for c in clubes_nacionais}
        clubes_paulistao = [mapa.get(c.id, c) for c in clubes_paulistao]
    if clubes_paulistao:
        mapa = {c.id: c for c in clubes_nacionais}
        clubes_paulistao = [mapa.get(c.id, c) for c in clubes_paulistao]

    objetivos = gerar_objetivos_por_clube(clube_usuario)
    liga = Liga(_nome_liga(comp_id), clubes_nacionais)
    temporada = Temporada(
        liga,
        clube_usuario=clube_usuario,
        clubes_paulistao=clubes_paulistao,
        objetivos=objetivos,
        estado_mundo_inicial=estado_mundo,
        competicao_id=comp_id,
    )
    return temporada, clube_usuario, comp_id


def escolher_clube(clubes):
    print("\nEscolha seu clube:\n")
    for i, clube in enumerate(clubes, start=1):
        print(f"{i}. {clube.nome}")
    while True:
        escolha = input("\nNúmero do clube: ")
        if escolha.isdigit() and 1 <= int(escolha) <= len(clubes):
            return clubes[int(escolha) - 1]


def personalizar_escalacao(clube):
    print("\n⚙️ Personalização de escalação")
    formacoes = list(FORMACOES.keys())
    for i, form in enumerate(formacoes, start=1):
        print(f"[{i}] {form}")
    op = input("Formação: ").strip()
    if op.isdigit() and 1 <= int(op) <= len(formacoes):
        clube.definir_formacao(formacoes[int(op) - 1])

    custom = input("Deseja escolher manualmente os titulares? (s/n): ").lower().strip()
    if custom != "s":
        return

    for idx, j in enumerate(clube.elenco):
        print(f"[{idx}] {j.nome} - {j.posicao} OVR {j.overall}")
    ids = input("Digite EXATAMENTE 11 índices separados por vírgula: ").split(",")
    try:
        sucesso = clube.definir_titulares([int(x.strip()) for x in ids])
        if not sucesso:
            print("❌ Escalação inválida: precisam ser 11 jogadores únicos.")
        else:
            print("✅ Titulares definidos com sucesso.")
    except ValueError:
        print("Entrada inválida. Escalação automática mantida.")

def exibir_tabelas_disponiveis(temporada):
    competicoes = list(temporada.tabelas.keys())
    tem_grupos_d = any(c.startswith("bra_d_g") for c in competicoes)
    tem_grupos_c = any(c in ("bra_c_grupo_a", "bra_c_grupo_b") for c in competicoes)

    competicoes = [c for c in competicoes if not c.startswith("bra_d_g")]
    competicoes = [c for c in competicoes if c not in ("bra_c_grupo_a", "bra_c_grupo_b")]

    if tem_grupos_d:
        competicoes.append("bra_d_grupo_usuario")
        competicoes.append("bra_d_grupos_outros")
    if tem_grupos_c:
        competicoes.append("bra_c_grupo_usuario")
        competicoes.append("bra_c_grupos_outros")

    if not competicoes:
        print("\nNenhuma tabela disponível no momento.")
        return

    print("\nTabelas disponíveis")
    for i, comp in enumerate(competicoes, start=1):
        if comp == "bra_d_grupo_usuario":
            nome = "S?rie D: Meu Grupo"
        elif comp == "bra_d_grupos_outros":
            nome = "S?rie D: Outros Grupos"
        elif comp == "bra_c_grupo_usuario":
            nome = "S?rie C: Meu Grupo"
        elif comp == "bra_c_grupos_outros":
            nome = "S?rie C: Outros Grupos"
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
        print("\nNenhuma notícia no momento.")
        return

    print("\nNot?cias")
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


def main():
    configurar_stdout_utf8()
    print("⚽ TOUCHLINE — Football Manager (Alpha)\n")
    print("Hierarquia de competições:", " < ".join(HIERARQUIA_COMPETICOES))

    db_manager.seed_database_if_needed()
    estado_mundo = carregar_save() if save_exists() else None
    comp_id, clubes_nacionais, nome_liga = escolher_liga(estado_mundo=estado_mundo)

    if not estado_mundo:
        estado_mundo = iniciar_novo_save(clubes_nacionais)

    clube_usuario = escolher_clube(clubes_nacionais)

    clubes_paulistao = carregar_clubes_paulistao(clubes_nacionais, estado_mundo=estado_mundo) if "paulistao_a1" in clube_usuario.competicoes else []
    objetivos = gerar_objetivos_por_clube(clube_usuario)
    mensagem_boas_vindas_objetivos(clube_usuario, objetivos)
    personalizar_escalacao(clube_usuario)

    liga = Liga(nome_liga, clubes_nacionais)
    temporada = Temporada(
        liga,
        clube_usuario=clube_usuario,
        clubes_paulistao=clubes_paulistao,
        objetivos=objetivos,
        estado_mundo_inicial=estado_mundo,
        competicao_id=comp_id,
    )

    while True:
        nao_lidas = mensagens.contar_nao_lidas(temporada.estado_mundo["meta"]["temporada_atual"])
        badge_msg = f" ({nao_lidas})" if nao_lidas else ""
        print("\n📋 Menu")
        print("[1] Exibir elenco")
        print("[2] Simular próxima rodada")
        print("[3] Simular temporada inteira")
        print("[4] Ajustar formação/titulares")
        print("[5] Ver tabelas")
        print(f"[6] Mensagens{badge_msg}")
        print("[7] Notícias")
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
                    temporada, clube_usuario, comp_id = nova_temp
        elif opcao == "3":
            temporada.jogar_temporada_completa()
            salvar_save(temporada.obter_estado_mundo())
            nova_temp = iniciar_proxima_temporada(temporada.obter_estado_mundo(), clube_usuario.id)
            if nova_temp[0]:
                temporada, clube_usuario, comp_id = nova_temp
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


if __name__ == "__main__":
    main()
