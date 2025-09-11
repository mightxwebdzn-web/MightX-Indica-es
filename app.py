import json
import os
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

DB_FILE = 'codigos.json'

EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECEIVER = 'mightxwebdzn@gmail.com'

def load_codes():
    """Carrega os códigos e dados de indicação do arquivo JSON."""
    if not os.path.exists(DB_FILE):
        return []
    
    with open(DB_FILE, 'r') as f:
        data = json.load(f)

    # Garante que a lista de reivindicadores existe para cada código
    for code_data in data:
        if 'reivindicadores_usados' not in code_data:
            code_data['reivindicadores_usados'] = []
    
    return data

def save_codes(codes):
    """Salva os códigos e dados de indicação no arquivo JSON."""
    with open(DB_FILE, 'w') as f:
        json.dump(codes, f, indent=4)

def send_email_notification(codigo, dono_codigo, indicado):
    """Envia uma notificação por e-mail sobre um código validado."""
    try:
        msg = MIMEText(f'O código {codigo} de @{dono_codigo} foi utilizado por @{indicado}.')
        msg['Subject'] = f'Novo código de indicação usado por @{indicado}'
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECEIVER

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
            print("✅ E-mail de notificação enviado com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar o e-mail: {e}")
        return False

@app.route('/registrar', methods=['POST'])
def registrar_codigo():
    """
    Rota para registrar um novo código de indicação.
    Recebe: JSON com 'nome', 'instagram' e 'codigo'.
    Retorna: Mensagem de sucesso ou erro.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Dados não enviados."}), 400

    nome = data.get('nome')
    insta = data.get('instagram', '').lower()
    codigo = data.get('codigo')

    if not nome or not insta or not codigo:
        return jsonify({"success": False, "message": "Preencha todos os campos."}), 400

    codes = load_codes()
    if any(c['insta'] == insta for c in codes):
        return jsonify({"success": False, "message": "Você já possui um código gerado."}), 409

    codes.append({
        "nome": nome,
        "insta": insta,
        "codigo": codigo,
        "reivindicadores_usados": [] # Nova lista para registrar quem usou o código
    })
    save_codes(codes)

    return jsonify({"success": True, "message": "Código registrado com sucesso!"}), 201

@app.route('/reivindicar', methods=['POST'])
def reivindicar_codigo():
    """
    Rota para reivindicar um código de indicação.
    Permite que o mesmo código seja usado por diferentes pessoas, mas
    impede que a mesma pessoa o use mais de uma vez.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Dados não enviados."}), 400

    codigo = data.get('codigo', '').upper()
    insta_reivindicador = data.get('instagramReivindicador', '').lower()

    if not codigo or not insta_reivindicador:
        return jsonify({"success": False, "message": "Preencha todos os campos."}), 400

    codes = load_codes()
    encontrado = next((c for c in codes if c['codigo'] == codigo), None)

    if not encontrado:
        return jsonify({"success": False, "message": "Código inválido."}), 404
    
    # Impede que o usuário use seu próprio código
    if encontrado['insta'] == insta_reivindicador:
        return jsonify({"success": False, "message": "Você não pode usar seu próprio código."}), 403

    # NOVO: Verifica se o reivindicador já usou este código
    if insta_reivindicador in encontrado.get('reivindicadores_usados', []):
        return jsonify({"success": False, "message": "Você já utilizou este código."}), 409

    # Adiciona o Instagram do novo reivindicador à lista
    encontrado['reivindicadores_usados'].append(insta_reivindicador)
    save_codes(codes)

    # Envia a notificação por e-mail
    send_email_notification(codigo, encontrado['insta'], insta_reivindicador)

    return jsonify({"success": True, "message": "Código validado com sucesso! E-mail de confirmação enviado."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001, debug=True)
