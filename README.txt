ARTTUBE - COMO EXECUTAR

1. Instale Python 3.10 ou superior.
2. Abra o terminal na pasta ArtTube.
3. Crie um ambiente virtual (recomendado):
   python -m venv .venv

   Windows:
   .venv\Scripts\activate

   macOS/Linux:
   source .venv/bin/activate

4. Instale as dependências:
   pip install -r requirements.txt

5. Defina uma chave secreta própria antes de usar fora de testes:
   Windows PowerShell:
   $env:SECRET_KEY="uma-chave-longa-e-aleatoria"

   macOS/Linux:
   export SECRET_KEY="uma-chave-longa-e-aleatoria"

6. Execute:
   python app.py

7. Abra no navegador:
   http://127.0.0.1:5000

O banco SQLite será criado automaticamente na primeira execução.
As imagens e vídeos enviados ficarão em static/uploads.

IMPORTANTE:
- Este projeto é uma base de desenvolvimento, não está pronto para produção.
- Antes de publicar na internet, implemente proteção CSRF, validação real do tipo/MIME
  e tamanho dos arquivos, moderação, limitação de requisições, política de privacidade,
  HTTPS e armazenamento seguro.
- Para alterações futuras no esquema do banco, use Flask-Migrate. db.create_all()
  cria tabelas ausentes, mas não altera tabelas já existentes.
- O servidor de desenvolvimento debug=True não deve ser usado em produção.
- As mensagens privadas desta versão não possuem criptografia ponta a ponta.
