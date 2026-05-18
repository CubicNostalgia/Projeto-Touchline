from core.liga import Liga
from core.objetivos import gerar_catalogo_objetivos, gerar_objetivos_por_clube, selecionar_objetivos_semanais
from core.temporada import Temporada
from data.clubes import (
    carregar_clubes_cariocao,
    carregar_clubes_paulistao,
    carregar_clubes_paulistao_a2,
    carregar_clubes_serie_a,
    carregar_clubes_serie_b_2026,
    carregar_clubes_serie_c_2026,
    carregar_clubes_serie_d_2026,
)
from data.database import COMPETICOES
from save_manager import iniciar_novo_save
import db_manager

CARREGADORES_COMP = {
    "bra_a": carregar_clubes_serie_a,
    "bra_b": carregar_clubes_serie_b_2026,
    "bra_c": carregar_clubes_serie_c_2026,
    "bra_d": carregar_clubes_serie_d_2026,
}

ORDEM_LIGAS_NACIONAIS = ("bra_a", "bra_b", "bra_c", "bra_d")


def listar_ligas_jogaveis():
    ligas = []
    for comp_id in ORDEM_LIGAS_NACIONAIS:
        ligas.append((comp_id, nome_competicao(comp_id)))
    return ligas


def nome_competicao(comp_id):
    return COMPETICOES.get(comp_id, {}).get("nome", comp_id.upper())


def carregar_clubes_nacionais(comp_id, estado_mundo=None):
    carregador = CARREGADORES_COMP.get(comp_id, carregar_clubes_serie_b_2026)
    return carregador(estado_mundo=estado_mundo)


def garantir_estado_inicial(clubes_nacionais, estado_mundo):
    if estado_mundo:
        return estado_mundo
    return iniciar_novo_save(clubes_nacionais)


def carregar_clubes_estaduais(clube_usuario, clubes_nacionais, estado_mundo):
    clubes_paulistao = (
        carregar_clubes_paulistao(clubes_nacionais, estado_mundo=estado_mundo)
        if "paulistao_a1" in clube_usuario.competicoes
        else []
    )
    clubes_paulistao_a2 = (
        carregar_clubes_paulistao_a2(clubes_nacionais, estado_mundo=estado_mundo)
        if "paulistao_a2" in clube_usuario.competicoes
        else []
    )
    clubes_cariocao = (
        carregar_clubes_cariocao(clubes_nacionais, estado_mundo=estado_mundo)
        if "cariocao_a1" in clube_usuario.competicoes
        else []
    )
    return clubes_paulistao, clubes_paulistao_a2, clubes_cariocao


def criar_temporada(comp_id, clubes_nacionais, clube_usuario, estado_mundo):
    estado_mundo = garantir_estado_inicial(clubes_nacionais, estado_mundo)
    estado_mundo.setdefault("meta", {})["clube_usuario_id"] = clube_usuario.id
    estado_mundo.setdefault("meta", {})["comp_usuario_id"] = comp_id
    clubes_paulistao, clubes_paulistao_a2, clubes_cariocao = carregar_clubes_estaduais(
        clube_usuario=clube_usuario,
        clubes_nacionais=clubes_nacionais,
        estado_mundo=estado_mundo,
    )

    objetivos = gerar_objetivos_por_clube(clube_usuario)
    estado_mundo.setdefault("meta", {})["objetivos_semanais"] = selecionar_objetivos_semanais(clube_usuario, quantidade=5)
    estado_mundo.setdefault("meta", {})["catalogo_objetivos"] = gerar_catalogo_objetivos()
    liga = Liga(nome_competicao(comp_id), clubes_nacionais)
    temporada = Temporada(
        liga,
        clube_usuario=clube_usuario,
        clubes_paulistao=clubes_paulistao,
        clubes_paulistao_a2=clubes_paulistao_a2,
        clubes_cariocao=clubes_cariocao,
        objetivos=objetivos,
        estado_mundo_inicial=estado_mundo,
        competicao_id=comp_id,
    )
    return temporada, objetivos


def competicao_principal(clube):
    for comp_id in ORDEM_LIGAS_NACIONAIS:
        if comp_id in clube.competicoes:
            return comp_id
    return "bra_b"


def iniciar_proxima_temporada(estado_mundo, clube_id):
    clube_db = db_manager.carregar_clube_por_id(
        clube_id, temporada_ano=estado_mundo["meta"]["temporada_atual"]
    )
    if not clube_db:
        return None, None, None, None

    comp_id = competicao_principal(clube_db)
    clubes_nacionais = carregar_clubes_nacionais(comp_id, estado_mundo=estado_mundo)
    clube_usuario = next((c for c in clubes_nacionais if c.id == clube_id), clube_db)

    clubes_paulistao, clubes_paulistao_a2, clubes_cariocao = carregar_clubes_estaduais(
        clube_usuario=clube_usuario,
        clubes_nacionais=clubes_nacionais,
        estado_mundo=estado_mundo,
    )

    mapa_clubes = {clube.id: clube for clube in clubes_nacionais}
    if clubes_paulistao:
        clubes_paulistao = [mapa_clubes.get(clube.id, clube) for clube in clubes_paulistao]
    if clubes_paulistao_a2:
        clubes_paulistao_a2 = [mapa_clubes.get(clube.id, clube) for clube in clubes_paulistao_a2]
    if clubes_cariocao:
        clubes_cariocao = [mapa_clubes.get(clube.id, clube) for clube in clubes_cariocao]

    objetivos = gerar_objetivos_por_clube(clube_usuario)
    estado_mundo.setdefault("meta", {})["clube_usuario_id"] = clube_usuario.id
    estado_mundo.setdefault("meta", {})["comp_usuario_id"] = comp_id
    estado_mundo.setdefault("meta", {})["objetivos_semanais"] = selecionar_objetivos_semanais(clube_usuario, quantidade=5)
    estado_mundo.setdefault("meta", {})["catalogo_objetivos"] = gerar_catalogo_objetivos()
    liga = Liga(nome_competicao(comp_id), clubes_nacionais)
    temporada = Temporada(
        liga,
        clube_usuario=clube_usuario,
        clubes_paulistao=clubes_paulistao,
        clubes_paulistao_a2=clubes_paulistao_a2,
        clubes_cariocao=clubes_cariocao,
        objetivos=objetivos,
        estado_mundo_inicial=estado_mundo,
        competicao_id=comp_id,
    )
    return temporada, clube_usuario, comp_id, objetivos
