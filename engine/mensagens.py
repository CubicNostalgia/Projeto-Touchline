from datetime import datetime

import db_manager


def enviar_mensagem(temporada_ano, remetente, titulo, corpo, prioridade=1):
    data = datetime.now().isoformat()
    db_manager.inserir_mensagem(temporada_ano, data, remetente, prioridade, titulo, corpo, lido=0)


def listar_mensagens(temporada_ano=None, apenas_nao_lidas=False, limite=50):
    return db_manager.listar_mensagens(temporada_ano=temporada_ano, apenas_nao_lidas=apenas_nao_lidas, limite=limite)


def contar_nao_lidas(temporada_ano=None):
    return db_manager.contar_mensagens_nao_lidas(temporada_ano=temporada_ano)


def marcar_lida(mensagem_id):
    db_manager.marcar_mensagem_lida(mensagem_id)
