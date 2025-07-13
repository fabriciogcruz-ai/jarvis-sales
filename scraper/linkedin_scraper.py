from linkedin_scraper import Person, Company, actions
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from typing import List, Tuple

def scrape_profile_and_company(
    profile_url: str,
    company_url: str | None = None,
    email: str | None = None,
    password: str | None = None,
    cookie: str | None = None
) -> Tuple[str, str, str]:

    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )

    try:
        if cookie:
            driver.get("https://www.linkedin.com/")
            driver.add_cookie({"name": "li_at", "value": cookie, "domain": ".linkedin.com", "path": "/"})
            driver.refresh()
        else:
            if not email or not password:
                raise ValueError("Email e senha são obrigatórios se o cookie não for fornecido.")
            actions.login(driver, email, password)

        person = Person(profile_url, driver=driver, scrape=True, close_on_complete=False)

        lines: List[str] = [
            f"Nome: {person.name}",
            f"Localização: {getattr(person, 'location', '')}",
            f"Open to Work: {'Sim' if getattr(person, 'open_to_work', False) else 'Não'}",
            "\nSobre:",
            person.about or "-",
            "\nExperiências:"
        ]

        for exp in person.experiences:
            lines.append(
                f"  • {exp.position_title} em {exp.institution_name} ({exp.from_date} – {exp.to_date or 'Presente'}) | {exp.location}"
            )

        lines.append("\nEducação:")
        for edu in person.educations:
            lines.append(
                f"  • {edu.degree or ''} em {edu.institution_name} ({edu.from_date} – {edu.to_date or 'Presente'})"
            )

        lines.append("\nInteresses:")
        for it in person.interests:
            lines.append(f"  • {it.title}")

        lines.append("\nConquistas:")
        for acc in person.accomplishments:
            lines.append(f"  • {acc.category}: {acc.title}")

        if company_url and "linkedin.com/company/" in company_url:
            try:
                company = Company(company_url, driver=driver, get_employees=False, scrape=True)
                lines.append("\n========== DADOS DA EMPRESA ==========")
                lines.extend([
                    f"Empresa: {getattr(company, 'name', '-')}",
                    f"Setor: {getattr(company, 'industry', '-')}",
                    f"Tamanho: {getattr(company, 'size', '-')}",
                    f"Tipo: {getattr(company, 'company_type', '-')}",
                    f"Localização: {getattr(company, 'headquarters', '-')}",
                    f"Especialidades: {', '.join(getattr(company, 'specialties', []) or [])}",
                    f"\nDescrição:\n{getattr(company, 'about', '-')}",
                ])
                nome_empresa = getattr(company, 'name', '')
            except Exception as e:
                lines.append(f"\n⚠️ Erro ao coletar dados da empresa: {e}")
                nome_empresa = ''
        else:
            nome_empresa = ''

        return "\n".join(lines), person.name or "Contato", nome_empresa

    finally:
        driver.quit()
