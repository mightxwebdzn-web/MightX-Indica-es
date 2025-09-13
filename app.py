import json
import os
import requests  # Added for Mailgun API
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

DB_FILE = 'codigos.json'

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
    try:
        API_KEY = "822243467f8e5e9023bfd1cef6a4a8e2-fbceb7cb-7496d9da"
        DOMAIN = "sandboxf9a7a3a6584a43d2a8c1019020eb838f.mailgun.org"
        
        # Cria a mensagem com o formato desejado
        email_body = (
            f"Novo código validado! Confere aí no painel.\n"
            f"Criador do código: @{dono_codigo}\n"
            f"Código usado por: @{indicado}"
        )
        
        requests.post(
            f"https://api.mailgun.net/v3/{DOMAIN}/messages",
            auth=("api", API_KEY),
            data={
                "from": f"Notificador MightX <mailgun@{DOMAIN}>",
                "to": ["miguelitoadventures@gmail.com"],
                "subject": f"Novo código de indicação usado por @{indicado}",
                "text": email_body,
            }
        )
        print("✅ E-mail de notificação enviado com sucesso via Mailgun!")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar o e-mail com Mailgun: {e}")
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

    # Verifica se o reivindicador já usou este código
    if insta_reivindicador in encontrado.get('reivindicadores_usados', []):
        return jsonify({"success": False, "message": "Você já utilizou este código."}), 409

    # Adiciona o Instagram do novo reivindicador à lista (corrigido o nome do campo)
    encontrado['reivindicadores_usados'].append(insta_reivindicador)
    save_codes(codes)

    # Envia a notificação por e-mail
    send_email_notification(codigo, encontrado['insta'], insta_reivindicador)

    return jsonify({"success": True, "message": "Código validado com sucesso! E-mail de confirmação enviado."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
