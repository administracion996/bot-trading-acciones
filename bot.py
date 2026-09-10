name: Bot de Trading Acciones

on:
  schedule:
    # Ejecuta a las 14:00, 16:00, 18:00 y 20:00 UTC (16:00, 18:00, 20:00 y 22:00 hora de España)
    # Solo de lunes a viernes (1-5)
    - cron: '0 14,16,18,20 * * 1-5'
  workflow_dispatch:

jobs:
  run-trading-bot:
    runs-on: ubuntu-latest

    steps:
    - name: Descargar repositorio
      uses: actions/checkout@v4

    - name: Configurar Python 3.10
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: Instalar dependencias
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Ejecutar Bot de Trading
      env:
        GH_PAT: ${{ secrets.GH_PAT }}
        GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
      run: python bot.py
