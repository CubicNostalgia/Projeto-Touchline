import json
import sqlite3
from pathlib import Path

from core.clube import Clube
from core.jogador import Jogador
from utils.gerador_jogadores import gerar_elenco
from data import database as base_db


DB_PATH = Path("save_game.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clubes (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                reputacao INTEGER NOT NULL,
                reputacao_tier INTEGER NOT NULL,
                prestigio_acumulado INTEGER NOT NULL,
                saldo INTEGER NOT NULL,
                nivel_ct INTEGER NOT NULL,
                nivel_base INTEGER NOT NULL,
                nivel_estadio INTEGER NOT NULL,
                estadio_capacidade INTEGER NOT NULL,
                torcida_expectativa INTEGER NOT NULL,
                status_financeiro TEXT NOT NULL,
                job_security TEXT NOT NULL,
                investimento_base TEXT NOT NULL DEFAULT 'medio',
                nivel_auxiliar INTEGER NOT NULL DEFAULT 1,
                nivel_olheiro INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS jogadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clube_id TEXT NOT NULL,
                nome TEXT NOT NULL,
                posicao TEXT NOT NULL,
                idade INTEGER NOT NULL,
                overall INTEGER NOT NULL,
                potencial INTEGER NOT NULL,
                salario INTEGER NOT NULL,
                status_base TEXT NOT NULL,
                origem_base INTEGER NOT NULL,
                lesao_dias INTEGER NOT NULL,
                fadiga REAL NOT NULL,
                forma REAL NOT NULL,
                jogos_temporada INTEGER NOT NULL,
                da_base INTEGER NOT NULL,
                habilidades TEXT NOT NULL DEFAULT '[]',
                defeitos TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (clube_id) REFERENCES clubes(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS campeonatos (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                nivel TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clube_competicoes (
                clube_id TEXT NOT NULL,
                campeonato_id TEXT NOT NULL,
                temporada_ano INTEGER NOT NULL,
                PRIMARY KEY (clube_id, campeonato_id, temporada_ano),
                FOREIGN KEY (clube_id) REFERENCES clubes(id) ON DELETE RESTRICT,
                FOREIGN KEY (campeonato_id) REFERENCES campeonatos(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS partidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campeonato_id TEXT NOT NULL,
                temporada_ano INTEGER NOT NULL,
                rodada INTEGER,
                casa_id TEXT NOT NULL,
                fora_id TEXT NOT NULL,
                data TEXT NOT NULL,
                gols_casa INTEGER,
                gols_fora INTEGER,
                estado TEXT NOT NULL CHECK (estado IN ('AGENDADO','FINALIZADO')),
                FOREIGN KEY (campeonato_id) REFERENCES campeonatos(id) ON DELETE RESTRICT,
                FOREIGN KEY (casa_id) REFERENCES clubes(id) ON DELETE RESTRICT,
                FOREIGN KEY (fora_id) REFERENCES clubes(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS noticias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_ano INTEGER NOT NULL,
                rodada INTEGER,
                tipo TEXT NOT NULL,
                prioridade INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                corpo TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                temporada_ano INTEGER NOT NULL,
                data TEXT NOT NULL,
                remetente TEXT NOT NULL,
                prioridade INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                corpo TEXT NOT NULL,
                lido INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        _ensure_column(conn, "clubes", "investimento_base", "TEXT NOT NULL DEFAULT 'medio'")
        _ensure_column(conn, "clubes", "nivel_auxiliar", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "clubes", "nivel_olheiro", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "jogadores", "habilidades", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(conn, "jogadores", "defeitos", "TEXT NOT NULL DEFAULT '[]'")


def _ensure_column(conn, tabela, coluna, definicao):
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({tabela})")}
    if coluna not in cols:
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def save_exists():
    return DB_PATH.exists()


def _normalizar_reputacao(valor):
    return valor if valor > 15 else max(1, min(100, valor * 15))


def _clubes_base():
    return (
        base_db.CLUBES_SERIE_A
        + base_db.CLUBES_SERIE_B_2026
        + base_db.CLUBES_SERIE_C_2026
        + base_db.CLUBES_SERIE_D_2026
    )


def seed_database_if_needed():
    init_db()
    with _connect() as conn:
        existentes = {row["id"] for row in conn.execute("SELECT id FROM clubes").fetchall()}

    base = _clubes_base()
    faltantes = [c for c in base if c["id"] not in existentes]
    if not faltantes and existentes:
        return

    temporada_ano = 2026
    clubes = []
    for c in faltantes if existentes else base:
        reputacao = _normalizar_reputacao(c.get("reputacao", 50))
        clube = Clube(
            id=c["id"],
            nome=c["nome"],
            elenco=gerar_elenco(c["forca_base"]),
            reputacao=reputacao,
            competicoes=c.get("competicoes", []),
        )
        clubes.append(clube)

    if clubes:
        salvar_clubes(clubes, temporada_ano=temporada_ano)
    salvar_meta_temporada(temporada_ano)
    _sincronizar_competicoes_base(temporada_ano, base)


def _sincronizar_competicoes_base(temporada_ano, base=None):
    base = base or _clubes_base()
    init_db()
    with _connect() as conn:
        for c in base:
            for comp in c.get("competicoes", []):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO campeonatos (id, nome, nivel)
                    VALUES (?, ?, ?)
                    """,
                    (
                        comp,
                        base_db.COMPETICOES.get(comp, {}).get("nome", comp),
                        base_db.COMPETICOES.get(comp, {}).get("nivel", "nacional"),
                    ),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO clube_competicoes (clube_id, campeonato_id, temporada_ano)
                    VALUES (?, ?, ?)
                    """,
                    (c["id"], comp, temporada_ano),
                )


def salvar_meta_temporada(temporada_ano):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO meta (chave, valor) VALUES ('temporada_atual', ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (str(temporada_ano),),
        )


def carregar_meta_temporada(default=2026):
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT valor FROM meta WHERE chave='temporada_atual'").fetchone()
        return int(row["valor"]) if row else default


def salvar_clubes(clubes, temporada_ano):
    init_db()
    with _connect() as conn:
        for clube in clubes:
            job_security = json.dumps(clube.job_security, ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO clubes (
                    id, nome, reputacao, reputacao_tier, prestigio_acumulado, saldo,
                    nivel_ct, nivel_base, nivel_estadio, estadio_capacidade,
                    torcida_expectativa, status_financeiro, job_security,
                    investimento_base, nivel_auxiliar, nivel_olheiro
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nome=excluded.nome,
                    reputacao=excluded.reputacao,
                    reputacao_tier=excluded.reputacao_tier,
                    prestigio_acumulado=excluded.prestigio_acumulado,
                    saldo=excluded.saldo,
                    nivel_ct=excluded.nivel_ct,
                    nivel_base=excluded.nivel_base,
                    nivel_estadio=excluded.nivel_estadio,
                    estadio_capacidade=excluded.estadio_capacidade,
                    torcida_expectativa=excluded.torcida_expectativa,
                    status_financeiro=excluded.status_financeiro,
                    job_security=excluded.job_security,
                    investimento_base=excluded.investimento_base,
                    nivel_auxiliar=excluded.nivel_auxiliar,
                    nivel_olheiro=excluded.nivel_olheiro
                """,
                (
                    clube.id,
                    clube.nome,
                    clube.reputacao,
                    clube.reputacao_tier,
                    clube.prestigio_acumulado,
                    clube.financas,
                    clube.nivel_ct,
                    clube.nivel_base,
                    clube.nivel_estadio,
                    clube.capacidade_estadio,
                    clube.torcida_expectativa,
                    clube.status_financeiro,
                    job_security,
                    clube.investimento_base,
                    clube.nivel_auxiliar,
                    clube.nivel_olheiro,
                ),
            )

            conn.execute("DELETE FROM jogadores WHERE clube_id = ?", (clube.id,))
            jogadores = []
            for jogador in clube.elenco:
                jogadores.append(_jogador_row(clube.id, jogador, da_base=0))
            for jogador in clube.base_jovens:
                jogadores.append(_jogador_row(clube.id, jogador, da_base=1))
            conn.executemany(
                """
                INSERT INTO jogadores (
                    clube_id, nome, posicao, idade, overall, potencial, salario,
                    status_base, origem_base, lesao_dias, fadiga, forma, jogos_temporada, da_base,
                    habilidades, defeitos
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                jogadores,
            )

            conn.execute(
                "DELETE FROM clube_competicoes WHERE clube_id = ? AND temporada_ano = ?",
                (clube.id, temporada_ano),
            )
            for comp in clube.competicoes:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO campeonatos (id, nome, nivel)
                    VALUES (?, ?, ?)
                    """,
                    (
                        comp,
                        base_db.COMPETICOES.get(comp, {}).get("nome", comp),
                        base_db.COMPETICOES.get(comp, {}).get("nivel", "nacional"),
                    ),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO clube_competicoes (clube_id, campeonato_id, temporada_ano)
                    VALUES (?, ?, ?)
                    """,
                    (clube.id, comp, temporada_ano),
                )


def _jogador_row(clube_id, jogador, da_base):
    return (
        clube_id,
        jogador.nome,
        jogador.posicao,
        jogador.idade,
        jogador.overall,
        jogador.potencial,
        getattr(jogador, "salario", 0),
        jogador.status_base,
        1 if jogador.origem_base else 0,
        jogador.lesao_dias,
        jogador.fadiga,
        jogador.forma,
        jogador.jogos_temporada,
        da_base,
        json.dumps(getattr(jogador, "habilidades", []), ensure_ascii=False),
        json.dumps(getattr(jogador, "defeitos", []), ensure_ascii=False),
    )


def carregar_estado_mundo():
    init_db()
    temporada_ano = carregar_meta_temporada()
    clubes = []
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM clubes").fetchall()
        for row in rows:
            jogadores = conn.execute(
                "SELECT * FROM jogadores WHERE clube_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            base_jovens = [j for j in jogadores if j["da_base"] == 1]
            elenco = [j for j in jogadores if j["da_base"] == 0]

            infra = {
                "ct": row["nivel_ct"],
                "base": row["nivel_base"],
                "estadio_nivel": row["nivel_estadio"],
                "estadio_capacidade": row["estadio_capacidade"],
            }
            job_security = json.loads(row["job_security"])
            competicoes = [
                c["campeonato_id"]
                for c in conn.execute(
                    "SELECT campeonato_id FROM clube_competicoes WHERE clube_id = ? AND temporada_ano = ?",
                    (row["id"], temporada_ano),
                ).fetchall()
            ]
            clubes.append(
                {
                    "id": row["id"],
                    "nome": row["nome"],
                    "reputacao": row["reputacao"],
                    "reputacao_tier": row["reputacao_tier"],
                    "prestigio_acumulado": row["prestigio_acumulado"],
                    "financas": row["saldo"],
                    "infraestrutura": infra,
                    "torcida_expectativa": row["torcida_expectativa"],
                    "job_security": job_security,
                    "status_financeiro": row["status_financeiro"],
                    "investimento_base": row["investimento_base"],
                    "nivel_auxiliar": row["nivel_auxiliar"],
                    "nivel_olheiro": row["nivel_olheiro"],
                    "base_jovens": [_row_to_jogador_dict(j) for j in base_jovens],
                    "elenco": [_row_to_jogador_dict(j) for j in elenco],
                    "competicoes": competicoes,
                }
            )
    return {"meta": {"temporada_atual": temporada_ano}, "clubes": clubes}


def _row_to_jogador_dict(row):
    try:
        habilidades = json.loads(row["habilidades"]) if row["habilidades"] else []
    except Exception:
        habilidades = []
    try:
        defeitos = json.loads(row["defeitos"]) if row["defeitos"] else []
    except Exception:
        defeitos = []
    return {
        "nome": row["nome"],
        "overall": row["overall"],
        "posicao": row["posicao"],
        "idade": row["idade"],
        "potencial": row["potencial"],
        "salario": row["salario"],
        "status_base": row["status_base"],
        "origem_base": bool(row["origem_base"]),
        "fadiga": row["fadiga"],
        "forma": row["forma"],
        "jogos_temporada": row["jogos_temporada"],
        "lesao_dias": row["lesao_dias"],
        "habilidades": habilidades,
        "defeitos": defeitos,
    }


def carregar_clubes_por_competicao(competicao_id, temporada_ano=None):
    init_db()
    temporada_ano = temporada_ano or carregar_meta_temporada()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*
            FROM clubes c
            JOIN clube_competicoes cc ON cc.clube_id = c.id
            WHERE cc.campeonato_id = ? AND cc.temporada_ano = ?
            ORDER BY c.nome
            """,
            (competicao_id, temporada_ano),
        ).fetchall()

        clubes = []
        for row in rows:
            jogadores = conn.execute(
                "SELECT * FROM jogadores WHERE clube_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            base_jovens = [j for j in jogadores if j["da_base"] == 1]
            elenco = [Jogador.from_dict(_row_to_jogador_dict(j)) for j in jogadores if j["da_base"] == 0]

            dados_iniciais = {
                "reputacao": row["reputacao"],
                "reputacao_tier": row["reputacao_tier"],
                "prestigio_acumulado": row["prestigio_acumulado"],
                "financas": row["saldo"],
                "infraestrutura": {
                    "ct": row["nivel_ct"],
                    "base": row["nivel_base"],
                    "estadio_nivel": row["nivel_estadio"],
                    "estadio_capacidade": row["estadio_capacidade"],
                },
                "torcida_expectativa": row["torcida_expectativa"],
                "job_security": json.loads(row["job_security"]),
                "status_financeiro": row["status_financeiro"],
                "investimento_base": row["investimento_base"],
                "nivel_auxiliar": row["nivel_auxiliar"],
                "nivel_olheiro": row["nivel_olheiro"],
                "base_jovens": [_row_to_jogador_dict(j) for j in base_jovens],
            }
            competicoes = [
                c["campeonato_id"]
                for c in conn.execute(
                    "SELECT campeonato_id FROM clube_competicoes WHERE clube_id = ? AND temporada_ano = ?",
                    (row["id"], temporada_ano),
                ).fetchall()
            ]
            clubes.append(
                Clube(
                    id=row["id"],
                    nome=row["nome"],
                    elenco=elenco,
                    reputacao=row["reputacao"],
                    competicoes=competicoes,
                    dados_iniciais=dados_iniciais,
                )
            )
        return clubes


def carregar_clube_por_id(clube_id, temporada_ano=None):
    init_db()
    temporada_ano = temporada_ano or carregar_meta_temporada()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM clubes WHERE id = ?", (clube_id,)).fetchone()
        if not row:
            return None
        jogadores = conn.execute(
            "SELECT * FROM jogadores WHERE clube_id = ? ORDER BY id",
            (row["id"],),
        ).fetchall()
        base_jovens = [j for j in jogadores if j["da_base"] == 1]
        elenco = [Jogador.from_dict(_row_to_jogador_dict(j)) for j in jogadores if j["da_base"] == 0]
        dados_iniciais = {
            "reputacao": row["reputacao"],
            "reputacao_tier": row["reputacao_tier"],
            "prestigio_acumulado": row["prestigio_acumulado"],
            "financas": row["saldo"],
            "infraestrutura": {
                "ct": row["nivel_ct"],
                "base": row["nivel_base"],
                "estadio_nivel": row["nivel_estadio"],
                "estadio_capacidade": row["estadio_capacidade"],
            },
            "torcida_expectativa": row["torcida_expectativa"],
            "job_security": json.loads(row["job_security"]),
            "status_financeiro": row["status_financeiro"],
            "investimento_base": row["investimento_base"],
            "nivel_auxiliar": row["nivel_auxiliar"],
            "nivel_olheiro": row["nivel_olheiro"],
            "base_jovens": [_row_to_jogador_dict(j) for j in base_jovens],
        }
        competicoes = [
            c["campeonato_id"]
            for c in conn.execute(
                "SELECT campeonato_id FROM clube_competicoes WHERE clube_id = ? AND temporada_ano = ?",
                (row["id"], temporada_ano),
            ).fetchall()
        ]
        return Clube(
            id=row["id"],
            nome=row["nome"],
            elenco=elenco,
            reputacao=row["reputacao"],
            competicoes=competicoes,
            dados_iniciais=dados_iniciais,
        )


def salvar_calendario(competicao_id, temporada_ano, eventos):
    init_db()
    with _connect() as conn:
        for evento in eventos:
            if "partidas" not in evento:
                continue
            comp_evento = evento.get("competicao", competicao_id)
            conn.execute(
                """
                INSERT OR IGNORE INTO campeonatos (id, nome, nivel)
                VALUES (?, ?, ?)
                """,
                (
                    comp_evento,
                    base_db.COMPETICOES.get(comp_evento, {}).get("nome", comp_evento),
                    base_db.COMPETICOES.get(comp_evento, {}).get("nivel", "nacional"),
                ),
            )
            for casa, fora in evento["partidas"]:
                data_txt = evento["data"].isoformat()
                conn.execute(
                    """
                    INSERT INTO partidas (
                        campeonato_id, temporada_ano, rodada, casa_id, fora_id, data, estado
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'AGENDADO')
                    """,
                    (comp_evento, temporada_ano, evento.get("rodada"), casa.id, fora.id, data_txt),
                )


def registrar_partida(competicao_id, temporada_ano, rodada, casa_id, fora_id, gols_casa, gols_fora):
    init_db()
    with _connect() as conn:
        if rodada is None:
            conn.execute(
                """
                UPDATE partidas
                SET gols_casa = ?, gols_fora = ?, estado = 'FINALIZADO'
                WHERE campeonato_id = ? AND temporada_ano = ? AND casa_id = ? AND fora_id = ?
                """,
                (gols_casa, gols_fora, competicao_id, temporada_ano, casa_id, fora_id),
            )
        else:
            conn.execute(
                """
                UPDATE partidas
                SET gols_casa = ?, gols_fora = ?, estado = 'FINALIZADO'
                WHERE campeonato_id = ? AND temporada_ano = ? AND rodada = ? AND casa_id = ? AND fora_id = ?
                """,
                (gols_casa, gols_fora, competicao_id, temporada_ano, rodada, casa_id, fora_id),
            )


def filtrar_jogadores_por_faixa_salario(min_salario=None, max_salario=None):
    init_db()
    min_salario = 0 if min_salario is None else min_salario
    max_salario = 10**9 if max_salario is None else max_salario
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM jogadores
            WHERE salario BETWEEN ? AND ?
            ORDER BY salario DESC
            """,
            (min_salario, max_salario),
        ).fetchall()


def filtrar_jogadores_por_ovr_pot(min_ovr=None, max_ovr=None, min_pot=None, max_pot=None):
    init_db()
    min_ovr = 0 if min_ovr is None else min_ovr
    max_ovr = 100 if max_ovr is None else max_ovr
    min_pot = 0 if min_pot is None else min_pot
    max_pot = 100 if max_pot is None else max_pot
    with _connect() as conn:
        return conn.execute(
            """
            SELECT * FROM jogadores
            WHERE overall BETWEEN ? AND ?
              AND potencial BETWEEN ? AND ?
            ORDER BY overall DESC, potencial DESC
            """,
            (min_ovr, max_ovr, min_pot, max_pot),
        ).fetchall()


def inserir_noticia(temporada_ano, rodada, tipo, prioridade, titulo, corpo, criado_em=None):
    from datetime import datetime

    init_db()
    criado_em = criado_em or datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO noticias (temporada_ano, rodada, tipo, prioridade, titulo, corpo, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (temporada_ano, rodada, tipo, int(prioridade), titulo, corpo, criado_em),
        )


def listar_noticias(temporada_ano=None, limite=20):
    init_db()
    with _connect() as conn:
        if temporada_ano is None:
            return conn.execute(
                """
                SELECT * FROM noticias
                ORDER BY criado_em DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return conn.execute(
            """
            SELECT * FROM noticias
            WHERE temporada_ano = ?
            ORDER BY criado_em DESC
            LIMIT ?
            """,
            (temporada_ano, limite),
        ).fetchall()


def inserir_mensagem(temporada_ano, data, remetente, prioridade, titulo, corpo, lido=0):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO mensagens (temporada_ano, data, remetente, prioridade, titulo, corpo, lido)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (temporada_ano, data, remetente, int(prioridade), titulo, corpo, int(lido)),
        )


def listar_mensagens(temporada_ano=None, apenas_nao_lidas=False, limite=50):
    init_db()
    with _connect() as conn:
        if temporada_ano is None:
            filtro = "WHERE lido = 0" if apenas_nao_lidas else ""
            return conn.execute(
                f"""
                SELECT * FROM mensagens
                {filtro}
                ORDER BY data DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        filtro = "AND lido = 0" if apenas_nao_lidas else ""
        return conn.execute(
            f"""
            SELECT * FROM mensagens
            WHERE temporada_ano = ?
            {filtro}
            ORDER BY data DESC
            LIMIT ?
            """,
            (temporada_ano, limite),
        ).fetchall()


def contar_mensagens_nao_lidas(temporada_ano=None):
    init_db()
    with _connect() as conn:
        if temporada_ano is None:
            return conn.execute("SELECT COUNT(*) FROM mensagens WHERE lido = 0").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM mensagens WHERE temporada_ano = ? AND lido = 0",
            (temporada_ano,),
        ).fetchone()[0]


def marcar_mensagem_lida(mensagem_id):
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE mensagens SET lido = 1 WHERE id = ?",
            (mensagem_id,),
        )


def ultima_rodada_finalizada(competicao_id, temporada_ano):
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT MAX(rodada) as rodada
            FROM partidas
            WHERE campeonato_id = ? AND temporada_ano = ? AND estado = 'FINALIZADO'
            """,
            (competicao_id, temporada_ano),
        ).fetchone()
        return row["rodada"] if row and row["rodada"] is not None else None


def listar_partidas_competicao(competicao_id, temporada_ano, rodada=None):
    init_db()
    with _connect() as conn:
        if rodada is None:
            return conn.execute(
                """
                SELECT p.rodada, p.gols_casa, p.gols_fora,
                       c1.nome as casa_nome, c2.nome as fora_nome
                FROM partidas p
                JOIN clubes c1 ON c1.id = p.casa_id
                JOIN clubes c2 ON c2.id = p.fora_id
                WHERE p.campeonato_id = ? AND p.temporada_ano = ? AND p.estado = 'FINALIZADO'
                ORDER BY p.data
                """,
                (competicao_id, temporada_ano),
            ).fetchall()
        return conn.execute(
            """
            SELECT p.rodada, p.gols_casa, p.gols_fora,
                   c1.nome as casa_nome, c2.nome as fora_nome
            FROM partidas p
            JOIN clubes c1 ON c1.id = p.casa_id
            JOIN clubes c2 ON c2.id = p.fora_id
            WHERE p.campeonato_id = ? AND p.temporada_ano = ?
              AND p.estado = 'FINALIZADO' AND p.rodada = ?
            ORDER BY p.data
            """,
            (competicao_id, temporada_ano, rodada),
        ).fetchall()
