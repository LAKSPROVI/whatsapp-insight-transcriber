#!/usr/bin/env python3
"""
Script de inicialização e desenvolvimento do backend
"""
import subprocess
import sys
import os

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Copiar .env.example para .env se não existir
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        import shutil
        shutil.copy(".env.example", ".env")
        print("⚠️  .env criado a partir de .env.example. Configure sua ANTHROPIC_API_KEY!")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info",
    ]
    
    print("🚀 Iniciando WhatsApp Insight Transcriber Backend...")
    print("📡 API disponível em: http://localhost:8000")
    print("📚 Docs disponíveis em: http://localhost:8000/api/docs")
    print("")
    
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
