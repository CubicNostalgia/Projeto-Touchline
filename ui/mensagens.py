def gerar_objetivos_por_clube(clube):
    objetivos = []
    comps = set(clube.competicoes)

    if "paulistao_a1" in comps:
        if clube.forca >= 75 or clube.reputacao_tier >= 9:
            objetivos.append({"id": "paulistao_semifinal", "texto": "Alcançar a semifinal do Paulistão A1"})
        else:
            objetivos.append({"id": "paulistao_quartas", "texto": "Alcançar as quartas do Paulistão A1"})

    if "bra_a" in comps:
        meta = "Terminar no top-8 da Série A" if clube.reputacao_tier >= 9 else "Terminar no top-12 da Série A"
        objetivos.append({"id": "liga_top", "texto": meta})
    elif "bra_b" in comps:
        meta = "Disputar acesso (top-6 da Série B)" if clube.reputacao_tier >= 5 else "Terminar no top-10 da Série B"
        objetivos.append({"id": "liga_top", "texto": meta})

    objetivos.append({"id": "base", "texto": "Utilizar pelo menos 3 jogadores da Academia de Base"})
    return objetivos


def mensagem_boas_vindas_objetivos(clube, objetivos):
    print(f"\n🏢 A diretoria lhe dá as boas-vindas ao {clube.nome}!")
    print("Seus objetivos pros primeiros meses de trabalho são:")
    for objetivo in objetivos:
        print(f"- {objetivo['texto']}")


def mensagem_resultado_objetivos(resultados):
    print("\n📋 Balanço de objetivos da diretoria")
    for item in resultados:
        status = "✅" if item["cumprido"] else "❌"
        print(f"{status} {item['texto']}")