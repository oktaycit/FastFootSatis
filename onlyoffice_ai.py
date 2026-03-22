#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OnlyOffice AI Proxy - Alibaba Cloud Qwen Entegrasyonu
OnlyOffice AI Assistant için proxy sunucusu
"""

import os
import json
import logging
import requests
from flask import Flask, request, jsonify
from functools import wraps

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Konfigürasyon
ONLYOFFICE_AI_PORT = int(os.getenv('ONLYOFFICE_AI_PORT', '5557'))
ALIBABA_API_KEY = os.getenv('ALIBABA_API_KEY', '')
ALIBABA_MODEL = os.getenv('ALIBABA_MODEL', 'qwen-turbo')
ALIBABA_ENDPOINT = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation'

# OnlyOffice AI komutları ve sistem promptları
AI_COMMANDS = {
    'continue': 'Metni devam ettir',
    'summarize': 'Özetle',
    'expand': 'Genişlet',
    'shorten': 'Kısalt',
    'simplify': 'Basitleştir',
    'formalize': 'Resmileştir',
    'fixGrammar': 'Dilbilgisi düzelt',
    'changeTone': 'Ton değiştir',
    'translate': 'Çevir',
    'generate': 'Üret',
    'chat': 'Sohbet'
}

SYSTEM_PROMPTS = {
    'continue': 'Aşağıdaki metni doğal bir şekilde devam ettir. Sadece devamını yaz, açıklama ekleme.',
    'summarize': 'Aşağıdaki metni özetle. Ana noktaları vurgula.',
    'expand': 'Aşağıdaki metni genişlet, daha detaylı hale getir.',
    'shorten': 'Aşağıdaki metni kısalt, öz hale getir.',
    'simplify': 'Aşağıdaki metni daha basit bir dille yeniden yaz.',
    'formalize': 'Aşağıdaki metni resmi bir dille yeniden yaz.',
    'fixGrammar': 'Aşağıdaki metnin dilbilgisi hatalarını düzelt.',
    'changeTone': 'Aşağıdaki metnin tonunu değiştir. Daha profesyonel yap.',
    'translate': 'Aşağıdaki metni Türkçe\'ye çevir.',
    'generate': 'Aşağıdaki konu hakkında kısa bir metin üret.',
    'chat': 'Kullanıcıya yardımcı ol. Kısa ve öz cevaplar ver.'
}


def call_alibaba_api(prompt, system_prompt=None, max_tokens=1024, temperature=0.7):
    """Alibaba Cloud Qwen API'yi çağır"""
    if not ALIBABA_API_KEY:
        logger.error("ALIBABA_API_KEY ayarlanmamış!")
        return None, "API anahtarı yapılandırılmamış"
    
    headers = {
        'Authorization': f'Bearer {ALIBABA_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Qwen API formatı
    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})
    
    payload = {
        'model': ALIBABA_MODEL,
        'input': {
            'messages': messages
        },
        'parameters': {
            'max_tokens': max_tokens,
            'temperature': temperature,
            'result_format': 'message'
        }
    }
    
    try:
        response = requests.post(ALIBABA_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Qwen response parse
        if 'output' in result and 'choices' in result['output']:
            choice = result['output']['choices'][0]
            message = choice.get('message', {})
            content = message.get('content', '')
            return content, None
        elif 'output' in result and 'text' in result['output']:
            return result['output']['text'], None
        else:
            logger.error(f"Beklenmeyen Qwen response: {result}")
            return None, f"API response hatası: {result}"
            
    except requests.exceptions.RequestException as e:
        logger.error(f"API request hatası: {e}")
        return None, f"Bağlantı hatası: {str(e)}"
    except Exception as e:
        logger.error(f"Genel hata: {e}")
        return None, f"Hata: {str(e)}"


@app.route('/health', methods=['GET'])
def health_check():
    """Sağlık kontrolü endpoint"""
    return jsonify({
        'status': 'ok',
        'model': ALIBABA_MODEL,
        'configured': bool(ALIBABA_API_KEY)
    })


@app.route('/api/v1/ai/status', methods=['GET'])
def ai_status():
    """OnlyOffice AI durumu"""
    return jsonify({
        'models': [
            {
                'id': ALIBABA_MODEL,
                'name': f'Alibaba Cloud - {ALIBABA_MODEL}',
                'type': 'text-generation'
            }
        ]
    })


@app.route('/api/v1/ai/chat', methods=['POST'])
def ai_chat():
    """
    OnlyOffice AI Chat endpoint
    OnlyOffice 9.x formatı
    """
    try:
        data = request.json
        logger.info(f"AI Chat request: {data}")
        
        # OnlyOffice request format
        prompt = data.get('prompt', '')
        command = data.get('command', 'chat')
        model = data.get('model', ALIBABA_MODEL)
        
        # Sistem promptunu al
        system_prompt = SYSTEM_PROMPTS.get(command, SYSTEM_PROMPTS['chat'])
        
        # Alibaba API'yi çağır
        response_text, error = call_alibaba_api(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=data.get('maxTokens', 1024),
            temperature=data.get('temperature', 0.7)
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify({
            'success': True,
            'result': response_text,
            'model': model
        })
        
    except Exception as e:
        logger.error(f"Chat endpoint hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/ai/complete', methods=['POST'])
def ai_complete():
    """
    OnlyOffice AI Completion endpoint
    Metin tamamlama için
    """
    try:
        data = request.json
        logger.info(f"AI Complete request: {data}")
        
        prompt = data.get('prompt', '')
        model = data.get('model', ALIBABA_MODEL)
        
        system_prompt = "Sen profesyonel bir metin asistanısın. Kullanıcının metnini tamamlamaya yardım et."
        
        response_text, error = call_alibaba_api(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=data.get('maxTokens', 512),
            temperature=data.get('temperature', 0.7)
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify({
            'success': True,
            'result': response_text,
            'model': model
        })
        
    except Exception as e:
        logger.error(f"Complete endpoint hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/ai/translate', methods=['POST'])
def ai_translate():
    """
    OnlyOffice AI Translate endpoint
    Metin çeviri için
    """
    try:
        data = request.json
        logger.info(f"AI Translate request: {data}")
        
        text = data.get('text', '')
        source_lang = data.get('sourceLanguage', 'en')
        target_lang = data.get('targetLanguage', 'tr')
        
        prompt = f"Translate the following text from {source_lang} to {target_lang}:\n\n{text}"
        
        response_text, error = call_alibaba_api(
            prompt=prompt,
            system_prompt="Sen profesyonel bir çevirmensin. Sadece çeviriyi ver, açıklama ekleme.",
            max_tokens=2048,
            temperature=0.3
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify({
            'success': True,
            'result': response_text,
            'sourceLanguage': source_lang,
            'targetLanguage': target_lang
        })
        
    except Exception as e:
        logger.error(f"Translate endpoint hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/ai/command', methods=['POST'])
def ai_command():
    """
    OnlyOffice AI Command endpoint
    Özetleme, genişletme, kısaltma vb. komutlar için
    """
    try:
        data = request.json
        logger.info(f"AI Command request: {data}")
        
        command = data.get('command', 'summarize')
        text = data.get('text', '')
        model = data.get('model', ALIBABA_MODEL)
        
        # Komut için sistem promptunu al
        system_prompt = SYSTEM_PROMPTS.get(command, SYSTEM_PROMPTS['chat'])
        
        prompt = f"Lütfen aşağıdaki metni işle:\n\n{text}"
        
        response_text, error = call_alibaba_api(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=data.get('maxTokens', 1024),
            temperature=data.get('temperature', 0.7)
        )
        
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 500
        
        return jsonify({
            'success': True,
            'result': response_text,
            'command': command
        })
        
    except Exception as e:
        logger.error(f"Command endpoint hatası: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/ai/models', methods=['GET'])
def list_models():
    """Kullanılabilir modelleri listele"""
    return jsonify({
        'models': [
            {
                'id': ALIBABA_MODEL,
                'name': f'Alibaba Qwen - {ALIBABA_MODEL}',
                'type': 'text-generation',
                'capabilities': ['chat', 'complete', 'translate', 'summarize', 'expand', 'shorten']
            }
        ]
    })


def run_server():
    """Sunucuyu başlat"""
    logger.info(f"OnlyOffice AI Proxy başlatılıyor...")
    logger.info(f"Port: {ONLYOFFICE_AI_PORT}")
    logger.info(f"Model: {ALIBABA_MODEL}")
    logger.info(f"API Key configured: {bool(ALIBABA_API_KEY)}")
    
    app.run(host='0.0.0.0', port=ONLYOFFICE_AI_PORT, debug=False)


if __name__ == '__main__':
    run_server()