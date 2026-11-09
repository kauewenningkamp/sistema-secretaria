from conexao import conectar
banco = conectar()

if banco:
    banco.close()
    print('Teste foi concluido com sucesso')
else:
    print('nao foi possivel conectar')