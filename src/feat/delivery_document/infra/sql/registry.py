from sqlalchemy import text

from src.common.infra.db.postgres.repos.common.sql_reader import sql_reader


class SQL:
    GET_CLIENT_HISTORY = text(sql_reader("get_client_history.sql", __file__))
    GET_HISTORY = text(sql_reader("get_history.sql", __file__))
    GET_DELIVERY_DAYS = text(sql_reader("get_delivery_days.sql", __file__))
    GET_DAY_DOCUMENTS = text(sql_reader("get_day_documents.sql", __file__))
    GET_SALES_REPORT = text(sql_reader("get_sales_report.sql", __file__))
