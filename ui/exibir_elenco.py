def _imprimir_bloco(jogadores, titulo):
    print(f"\n📋 Elenco do {titulo}")
    print("-" * 72)

    ordem = ["GOL", "LD", "ZAG", "LE", "VOL", "MC", "MEI", "PD", "PE", "ATA"]
    for posicao in ordem:
        print(f"\n{posicao}")
        print("-" * 72)
        for jogador in jogadores:
            if jogador.posicao == posicao:
                status = getattr(jogador, "status_base", "profissional")
                lesao = getattr(jogador, "lesao_dias", 0)
                estrelas = getattr(jogador, "potencial_estrelas", None)
                estrela_txt = f" POT*:{str(estrelas).ljust(2)}" if estrelas is not None else ""
                tag = "BASE" if status == "base" else ("U21" if status == "transicao" else "PRO")
                print(
                    f"{jogador.nome.ljust(22)} OVR:{str(jogador.overall).ljust(3)} "
                    f"POT:{str(jogador.potencial).ljust(3)} ID:{str(jogador.idade).ljust(2)} "
                    f"FAD:{int(jogador.fadiga):>2} LES:{int(lesao):>2} J:{jogador.jogos_temporada:>2}"
                    f"{estrela_txt} {tag}"
                )


def exibir_elenco(clube):
    print("\n[1] Elenco completo")
    print("[2] Titulares")
    print("[3] Reservas")
    print("[4] Base/Sub-21")
    opcao = input("Exibir: ").strip()

    if opcao == "2":
        jogadores = clube.escalar_titulares()
        titulo = f"{clube.nome} ({clube.formacao}) — Titulares"
        medias = clube.media_por_posicao(apenas_titulares=True)
    elif opcao == "3":
        jogadores = clube.reservas()
        titulo = f"{clube.nome} ({clube.formacao}) — Reservas"
        medias = None
    elif opcao == "4":
        base_jovens = list(getattr(clube, "base_jovens", []))
        transicao = [j for j in clube.elenco if getattr(j, "status_base", "") == "transicao"]
        jogadores = base_jovens + [j for j in transicao if j not in base_jovens]
        titulo = f"{clube.nome} — Academia de Base"
        medias = None
    else:
        jogadores = clube.elenco
        titulo = f"{clube.nome} ({clube.formacao}) — Completo"
        medias = clube.media_por_posicao(apenas_titulares=False)

    _imprimir_bloco(jogadores, titulo)

    if opcao == "4" and base_jovens:
        promover = input("\nPromover jogador da base? (s/n): ").strip().lower()
        if promover == "s":
            for idx, j in enumerate(base_jovens, start=1):
                print(f"[{idx}] {j.nome} - {j.posicao} OVR {j.overall} POT {j.potencial}")
            escolha = input("Numero do jogador: ").strip()
            if escolha.isdigit():
                idx = int(escolha) - 1
                if 0 <= idx < len(base_jovens):
                    clube.promover_jovem(base_jovens[idx], definitivo=False)
                    print("✅ Jogador promovido para o elenco (transicao).")

    if medias is not None:
        print("\n📊 Médias")
        print("-" * 20)
        media_geral = round(sum(j.overall for j in jogadores) / len(jogadores), 1) if jogadores else 0
        print(f"Média geral: {media_geral}")
        for pos, media in medias.items():
            if media > 0:
                print(f"{pos}: {media}")
