name: Bot de Trading Acciones

on:
  schedule:
    # Ejecuta a las 15:47, 17:47, 19:47 y 21:47 (Hora de España) de Lunes a Viernes
    - cron: '47 13,15,17,19 * * 1-5'
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
