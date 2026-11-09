
import mysql.connector
from mysql.connector import Error

def conectar():
    try:
        conexao = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="sige"
        )

        if conexao.is_connected():
            print("Conectado ao banco SIGE!")
            return conexao

    except Error as erro:
        print(f"Erro ao conectar ao MySQL: {erro}")

    return None

