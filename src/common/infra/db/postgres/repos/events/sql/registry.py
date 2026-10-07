from sqlalchemy import text

from src.common.infra.db.postgres.repos.common.sql_reader import sql_reader


class SQL:
    ADD_MANY = text(sql_reader("add_many.sql", __file__))
    GET_ALL = text(sql_reader("get_all.sql", __file__))
