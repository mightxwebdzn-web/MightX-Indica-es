import json
import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurações através de variáveis de ambiente
DB_FILE = os.getenv('DB_FILE', 'codigos.json')
LEADS_FILE = os.getenv('LEADS_FILE', 'leads.json')
MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')
EMAIL_RECEIVER = os.getenv('EMAIL_RECEIVER')

def load_codes():
    """Carrega os códigos e dados de indicação do arquivo JSON."""
    if not os.path.exists(DB_FILE):
        return []
    
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    # Garante que a lista de reivindicadores existe para cada código
    for code_data in data:
        if 'reivindicadores_usados' not in code_data:
            code_data['reivindicadores_usados'] = []
    
    return data

def save_codes(codes):
    """Salva os códigos e dados de indicação no arquivo JSON."""
    with open(DB_FILE, 'w') as f:
        json.dump(codes, f, indent=4)

def load_leads():
    """Carrega os leads do arquivo JSON."""
    if not os.path.exists(LEADS_FILE):
        return []
    
    try:
        with open(LEADS_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    
    return data

def save_leads(leads):
    """Salva os leads no arquivo JSON."""
    with open(LEADS_FILE, 'w') as f:
        json.dump(leads, f, indent=4)

def send_email_notification(codigo, dono_codigo, indicado):
    """Envia uma notificação por e-mail sobre um código validado usando Mailgun."""
    try:
        # Verifica se as configurações do Mailgun estão definidas
        if not all([MAILGUN_API_KEY, MAILGUN_DOMAIN, EMAIL_RECEIVER]):
            print("❌ Configurações de e-mail não encontradas. Verifique suas variáveis de ambiente.")
            return False
        
        # Cria a mensagem com o formato desejado
        email_body = (
            f"Novo código validado! Confere aí no painel.\n"
            f"Criador do código: @{dono_codigo}\n"
            f"Código usado por: @{indicado}"
        )
        
        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": f"Notificador MightX <mailgun@{MAILGUN_DOMAIN}>",
                "to": [EMAIL_RECEIVER],
                "subject": f"Novo código de indicação usado por @{indicado}",
                "text": email_body,
            },
            timeout=10  # Timeout para evitar que a requisição fique travada
        )
        
        if response.status_code == 200:
            print("✅ E-mail de notificação enviado com sucesso!")
            return True
        else:
            print(f"❌ Erro ao enviar o e-mail: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro ao enviar o e-mail de verificação: {e}")
        return False

def send_lead_notification(lead_data):
    """Envia uma notificação por e-mail sobre um novo lead capturado."""
    try:
        # Verifica se as configurações do Mailgun estão definidas
        if not all([MAILGUN_API_KEY, MAILGUN_DOMAIN, EMAIL_RECEIVER]):
            print("❌ Configurações de e-mail não encontradas. Verifique suas variáveis de ambiente.")
            return False
        
        # Cria a mensagem com os dados do lead
        email_body = (
            f"Novo lead capturado no site!\n\n"
            f"Nome: {lead_data.get('name', 'Não informado')}\n"
            f"E-mail: {lead_data.get('email', 'Não informado')}\n"
            f"Telefone: {lead_data.get('phone', 'Não informado')}\n"
            f"Mensagem: {lead_data.get('message', 'Não informada')}\n\n"
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        
        response = requests.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": f"Sistema de Leads MightX <leads@{MAILGUN_DOMAIN}>",
                "to": [EMAIL_RECEIVER],
                "subject": f"Novo lead: {lead_data.get('name', 'Cliente Potencial')}",
                "text": email_body,
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Solicitação Enviada!")
            return True
        else:
            print(f"❌ Erro ao enviar o e-mail de lead: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erro ao enviar solicitação: {e}")
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
        "reivindicadores_usados": []
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

    # Adiciona o Instagram do novo reivindicador à lista
    encontrado['reivindicadores_usados'].append(insta_reivindicador)
    save_codes(codes)

    # Envia a notificação por e-mail
    send_email_notification(codigo, encontrado['insta'], insta_reivindicador)

    return jsonify({"success": True, "message": "Código validado com sucesso! E-mail de confirmação enviado."}), 200

@app.route('/leads', methods=['POST'])
def capturar_lead():
    """
    Rota para capturar leads do formulário do site.
    Recebe: JSON com 'name', 'email', 'phone' e 'message' (opcional).
    Retorna: Mensagem de sucesso ou erro.
    """
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Dados não enviados."}), 400

    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    message = data.get('message', '')

    if not name or not email or not phone:
        return jsonify({"success": False, "message": "Preencha todos os campos obrigatórios."}), 400

    # Carrega os leads existentes
    leads = load_leads()
    
    # Verifica se o e-mail já existe
    if any(lead['email'].lower() == email.lower() for lead in leads):
        return jsonify({"success": False, "message": "Este e-mail já está cadastrado."}), 409

    # Adiciona o novo lead
    new_lead = {
        "name": name,
        "email": email,
        "phone": phone,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    
    leads.append(new_lead)
    save_leads(leads)

    # Envia a notificação por e-mail
    send_lead_notification(new_lead)

    return jsonify({"success": True, "message": "Entraremos em contato em breve."}), 201

if __name__ == '__main__':
    # Verifica se as variáveis de ambiente necessárias estão definidas
    required_env_vars = ['MAILGUN_API_KEY', 'MAILGUN_DOMAIN', 'EMAIL_RECEIVER']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variáveis de ambiente ausentes: {', '.join(missing_vars)}")
        print("⚠️  Certifique-se de configurar um arquivo .env com todas as variáveis necessárias")
    
    app.run(host='0.0.0.0', port=8001, debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
