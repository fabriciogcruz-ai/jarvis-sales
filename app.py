from flask import Flask, render_template, request, Response, stream_with_context
from openai import OpenAI
from dotenv import load_dotenv
from scraper.linkedin_scraper import scrape_profile_and_company
import os
import markdown
import time
import queue

load_dotenv()
app = Flask(__name__)
message_queue = queue.Queue()

def get_gpt_insights(profile_text: str, model: str = "gpt-4o") -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    system_prompt = (
        "Você é um especialista em pré-vendas ERP da Benner (Consulte o site benner.com.br para saber mais sobre a vertical). "
        "Seu papel é analisar o perfil de um decisor e sua empresa para gerar insights de prospecção com base em desafios reais do setor, "
        "oportunidades estratégicas e o portfólio da Benner. Use linguagem consultiva, objetiva e de impacto. "
        "\n\nDivida a resposta em seções numeradas:\n"
        "1. Pontos de conexão\n"
        "2. Abordagem inicial (prospecção estilo SPIN)\n"
        "3. Diagnóstico estratégico (desafios, como o ERP ajuda)\n"
        "4. Tópicos para perguntas (consultoria)\n"
        "5. Tom recomendado\n"
        "Evite generalidades. Seja direto, consultivo e estratégico."
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Perfil LinkedIn extraído:\n---\n{profile_text}\n---"},
        ],
        max_tokens=800,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def format_insights(text: str):
    sections, current_title, current_body = [], "", []
    for line in text.splitlines():
        line = line.strip()
        if line and any(line.startswith(f"{i}.") for i in range(1, 10)):
            if current_title:
                sections.append((current_title, current_body))
                current_body = []
            current_title = line[line.find('.') + 1:].strip().strip("*_")
        elif line:
            current_body.append(line)
    if current_title:
        sections.append((current_title, current_body))
    if not sections and text.strip():
        sections.append(("Análise Geral", text.strip().split("\n")))

    converted = []
    for title, body in sections:
        title_clean = markdown.markdown(title)
        html_lines = [markdown.markdown(line, extensions=["nl2br"]) for line in body]
        converted.append((title_clean, html_lines))
    return converted

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    login_mode = request.form.get("login_mode")
    cookie = request.form.get("cookie")
    email = request.form.get("email")
    password = request.form.get("password")
    profile_url = request.form.get("profile")
    company_url = request.form.get("company")

    if not profile_url or (login_mode == "cookie" and not cookie) or (login_mode == "credenciais" and (not email or not password)):
        return render_template("index.html", error="Preencha todos os campos obrigatórios.")

    try:
        if login_mode == "cookie":
            message_queue.put("🔐 Fazendo login e extraindo dados com cookie...")
            time.sleep(0.2)
            scraped_text, nome_pessoa, nome_empresa = scrape_profile_and_company(
                cookie=cookie, profile_url=profile_url, company_url=company_url)
        else:
            message_queue.put("🔐 Fazendo login e extraindo dados com e-mail e senha...")
            time.sleep(0.2)
            scraped_text, nome_pessoa, nome_empresa = scrape_profile_and_company(
                email=email, password=password, profile_url=profile_url, company_url=company_url)

        if not scraped_text:
            return render_template("index.html", error="Não foi possível coletar os dados do LinkedIn.")

        message_queue.put("📄 Gerando insights com o Jarvis do Sr. Fabrício...")
        time.sleep(0.3)
        gpt_response = get_gpt_insights(scraped_text)
        insights = format_insights(gpt_response)

        if not insights:
            return render_template("index.html", error="Não foi possível gerar insights estruturados.")

        return render_template("index.html", insights=insights, nome_pessoa=nome_pessoa, nome_empresa=nome_empresa)

    except Exception as e:
        return render_template("index.html", error=str(e))

@app.route("/progress")
def progress():
    def event_stream():
        while True:
            try:
                message = message_queue.get(timeout=30)
                yield f"data: {message}\n\n"
            except queue.Empty:
                break
    return Response(stream_with_context(event_stream()), content_type="text/event-stream")

if __name__ == "__main__":
    app.run()
