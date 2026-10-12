import os
import re
import io
import json
import time
import uuid
import zipfile
import threading
from urllib.parse import quote

from flask import (
    Flask,
    request,
    render_template_string,
    send_file,
    abort,
    url_for,
)
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL", "gemini-3.8-flash"
).strip()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = "allabiely-bit/genius-app-ai"
GITHUB_WORKFLOW = "build-android.yml"
GITHUB_BRANCH = "main"

MAX_FILES = 40
MAX_TOTAL_SIZE = 1_500_000
MAX_DESCRIPTION_LENGTH = 5000

# Les archives sont conservées temporairement en mémoire.
PROJECTS = {}
PROJECTS_LOCK = threading.Lock()
PROJECT_TTL = 1800

PAGE = r"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0a0820">
<title>GENIUS APP AI</title>
<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 20px 14px;
  background: #0a0820;
  color: white;
  font-family: Arial, sans-serif;
}
.container { max-width: 760px; margin: auto; }
header { text-align: center; padding: 24px 8px; }
.logo { font-size: 42px; }
h1 { color: #c5a3ff; font-size: 29px; margin: 12px 0; }
.subtitle, .note { color: #c4bddb; line-height: 1.7; }
.card {
  background: #191537;
  border: 1px solid #37305e;
  border-radius: 18px;
  padding: 20px;
  margin: 18px 0;
}
label { display: block; margin: 18px 0 9px; font-weight: bold; }
textarea, select {
  width: 100%;
  border: 1px solid #554786;
  border-radius: 10px;
  padding: 14px;
  background: #0e0b29;
  color: white;
  font-size: 16px;
}
textarea { min-height: 160px; resize: vertical; }
button, .download {
  display: block;
  width: 100%;
  border: 0;
  border-radius: 12px;
  padding: 16px 12px;
  margin-top: 20px;
  background: #7c00ff;
  color: white;
  font-size: 16px;
  font-weight: bold;
  text-align: center;
  text-decoration: none;
  cursor: pointer;
}
button:disabled { opacity: .6; }
.note { font-size: 13px; }
.result { overflow-wrap: anywhere; line-height: 1.7; }
.success { color: #83ffd0; }
.error { color: #ffaaa9; }
footer { text-align: center; color: #aaa1ca; font-size: 12px; padding: 20px; }
</style>
</head>
<body>
<div class="container">
<header>
<div class="logo">🧠</div>
<h1>GENIUS APP AI</h1>
<p class="subtitle">
Décris ton idée. Prépare ton projet avec l'intelligence artificielle.
</p>
</header>

<section class="card">
<form method="POST" action="/"
onsubmit="document.getElementById('submit').disabled=true;
document.getElementById('submit').textContent='⏳ PRÉPARATION DU PROJET...';">

<label for="description">✍️ Décris l'application que tu veux créer</label>
<textarea id="description" name="description" maxlength="5000"
required placeholder="Exemple : crée une application de gestion de budget avec un écran d'accueil, des dépenses et un historique.">{{ description }}</textarea>

<label for="platform">📱 Choisis la plateforme</label>
<select id="platform" name="platform">
<option value="Android" {% if platform == "Android" %}selected{% endif %}>
Application Android (APK)
</option>
<option value="Web" {% if platform == "Web" %}selected{% endif %}>
Application Web
</option>
</select>

<button id="submit" type="submit">🚀 CRÉER MON PROJET</button>
</form>

<p class="note">
La génération utilise la clé Gemini configurée sur le serveur.
La compilation Android nécessite un projet compatible.
</p>
</section>

{% if message %}
<section class="card">
<h2 class="{{ 'success' if success else 'error' }}">{{ heading }}</h2>
<div class="result">{{ message }}</div>
{% if zip_url %}
<a class="download" href="{{ zip_url }}">📦 Télécharger le projet ZIP</a>
{% endif %}
</section>
{% endif %}

<footer>GENIUS APP AI · Version expérimentale</footer>
</div>
</body>
</html>
"""


def render_page(
    description="",
    platform="Android",
    heading="",
    message="",
    success=False,
    zip_url=None,
    status=200,
):
    return (
        render_template_string(
            PAGE,
            description=description,
            platform=platform,
            heading=heading,
            message=message,
            success=success,
            zip_url=zip_url,
        ),
        status,
    )


def call_gemini(description, platform):
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "La variable GEMINI_API_KEY est absente de Render."
        )

    if platform == "Android":
        requirements = """
Tu dois générer un projet Android natif minimal et compilable.
Utilise Kotlin, le plugin Android Gradle 8.7.3,
Kotlin Gradle Plugin 2.0.21, Java 17 et compileSdk 35.
Le projet doit inclure :
- settings.gradle.kts
- build.gradle.kts à la racine
- gradle.properties
- app/build.gradle.kts
- app/src/main/AndroidManifest.xml
- app/src/main/java/com/genius/generated/MainActivity.kt

L'application doit avoir une interface fonctionnelle correspondant
à la demande. MainActivity doit utiliser Android SDK natif.
Évite toute dépendance externe inutile.
Le projet doit permettre gradle assembleDebug.
"""
    else:
        requirements = """
Génère une petite application Web fonctionnelle.
Inclue index.html, style.css et script.js.
Utilise uniquement HTML, CSS et JavaScript standards.
"""

    prompt = f"""
Tu es un ingénieur logiciel expérimenté.
Crée un projet complet répondant à la demande de l'utilisateur.

PLATEFORME : {platform}

DEMANDE :
{description}

CONTRAINTES :
{requirements}

Réponds uniquement avec un objet JSON valide de cette forme :
{{
  "project_name": "nom-du-projet",
  "files": [
    {{
      "path": "chemin/du/fichier",
      "content": "contenu complet du fichier"
    }}
  ]
}}

Règles :
- Fournis le contenu intégral de chaque fichier.
- N'inclus aucun Markdown ni texte avant ou après le JSON.
- Pas de chemin absolu.
- Pas de '..' dans les chemins.
- Maximum {MAX_FILES} fichiers.
- N'inclus aucun secret, jeton ou clé API.
"""

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + quote(GEMINI_MODEL, safe="")
        + ":generateContent?key="
        + quote(GEMINI_API_KEY, safe="")
    )

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    req = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            raise RuntimeError(
                "Quota Gemini atteint. Réessaie après la réinitialisation."
            )
        raise RuntimeError(
            f"Erreur Gemini HTTP {exc.code}. Vérifie le modèle et le quota."
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Impossible de contacter Gemini. Réessaie plus tard."
        ) from exc

    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Gemini n'a pas renvoyé un projet JSON valide."
        ) from exc

    files = data.get("files")
    if not isinstance(files, list) or not files:
        raise RuntimeError("Le projet généré ne contient aucun fichier.")

    if len(files) > MAX_FILES:
        raise RuntimeError("Le projet contient trop de fichiers.")

    cleaned = []
    total_size = 0
    seen = set()

    for item in files:
        if not isinstance(item, dict):
            continue

        path = str(item.get("path", "")).replace("\\", "/").strip()
        content = item.get("content", "")

        if not path or not isinstance(content, str):
            continue

        parts = path.split("/")

        if (
            path.startswith("/")
            or "\\" in path
            or any(part in ("", ".", "..") for part in parts)
            or ":" in parts[0]
        ):
            raise RuntimeError("Un chemin de fichier dangereux a été rejeté.")

        if path in seen:
            raise RuntimeError("Le projet contient des chemins en double.")

        seen.add(path)
        total_size += len(content.encode("utf-8"))

        if total_size > MAX_TOTAL_SIZE:
            raise RuntimeError("Le projet généré est trop volumineux.")

        cleaned.append({"path": path, "content": content})

    if not cleaned:
        raise RuntimeError("Aucun fichier valide n'a été généré.")

    if platform == "Android":
        paths = {item["path"] for item in cleaned}
        required = {
            "settings.gradle.kts",
            "build.gradle.kts",
            "app/build.gradle.kts",
            "app/src/main/AndroidManifest.xml",
        }
        if not required.issubset(paths):
            raise RuntimeError(
                "Le projet Android est incomplet : des fichiers Gradle "
                "ou le manifeste sont manquants. Réessaie avec une demande "
                "plus simple."
            )

    return cleaned


def clean_old_projects():
    now = time.time()
    with PROJECTS_LOCK:
        expired = [
            key for key, item in PROJECTS.items()
            if now - item["created"] > PROJECT_TTL
        ]
        for key in expired:
            PROJECTS.pop(key, None)


def make_zip(files):
    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for item in files:
            archive.writestr(item["path"], item["content"])

    buffer.seek(0)
    return buffer.getvalue()


@app.get("/health")
def health():
    return {
        "application": "GENIUS APP AI",
        "status": "ok",
        "gemini_configured": bool(GEMINI_API_KEY),
        "github_configured": bool(GITHUB_TOKEN),
    }


@app.get("/download/<project_id>")
def download_project(project_id):
    clean_old_projects()

    with PROJECTS_LOCK:
        project = PROJECTS.get(project_id)

    if not project:
        abort(404, "Le ZIP a expiré. Génère à nouveau le projet.")

    return send_file(
        io.BytesIO(project["zip"]),
        mimetype="application/zip",
        as_attachment=True,
        download_name=project["filename"],
    )


def trigger_github_build(zip_url):
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN est absent de Render."
        )

    api_url = (
        "https://api.github.com/repos/"
        + GITHUB_REPOSITORY
        + "/actions/workflows/"
        + GITHUB_WORKFLOW
        + "/dispatches"
    )

    payload = {
        "ref": GITHUB_BRANCH,
        "inputs": {
            "project_zip_url": zip_url
        },
    }

    req = Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + GITHUB_TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "GENIUS-APP-AI",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(
                    "GitHub n'a pas accepté la demande de compilation."
                )
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise RuntimeError(
                "Le jeton GitHub est invalide ou expiré."
            ) from exc
        if exc.code == 403:
            raise RuntimeError(
                "GitHub refuse l'accès. Vérifie la permission Actions "
                "Read and write du jeton."
            ) from exc
        if exc.code == 404:
            raise RuntimeError(
                "Workflow introuvable. Vérifie build-android.yml "
                "sur la branche main."
            ) from exc
        raise RuntimeError(
            f"Erreur GitHub HTTP {exc.code}. Vérifie la configuration."
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Impossible de joindre GitHub Actions."
        ) from exc


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return render_page()

    description = request.form.get("description", "").strip()
    platform = request.form.get("platform", "Android").strip()

    if platform not in ("Android", "Web"):
        platform = "Android"

    if not description:
        return render_page(
            platform=platform,
            heading="Description manquante",
            message="Décris l'application que tu souhaites créer.",
            status=400,
        )

    if len(description) > MAX_DESCRIPTION_LENGTH:
        return render_page(
            description=description[:MAX_DESCRIPTION_LENGTH],
            platform=platform,
            heading="Description trop longue",
            message="Raccourcis la description et réessaie.",
            status=400,
        )

    try:
        files = call_gemini(description, platform)
        archive = make_zip(files)

        project_id = uuid.uuid4().hex
        filename = "GENIUS-APP-AI-PROJECT.zip"

        with PROJECTS_LOCK:
            PROJECTS[project_id] = {
                "zip": archive,
                "filename": filename,
                "created": time.time(),
            }

        zip_url = url_for(
            "download_project",
            project_id=project_id,
            _external=True,
        )

        if platform == "Android":
            trigger_github_build(zip_url)
            message = (
                f"Projet généré avec {len(files)} fichiers. "
                "La demande de compilation a été envoyée à GitHub Actions. "
                "La compilation peut encore échouer si le projet généré "
                "ou son environnement Gradle est incompatible. "
                "Tu peux télécharger le ZIP ci-dessous."
            )
            heading = "Projet créé — compilation demandée"
        else:
            message = (
                f"Projet Web généré avec {len(files)} fichiers. "
                "Télécharge l'archive ZIP ci-dessous."
            )
            heading = "Projet Web créé"

        return render_page(
            description=description,
            platform=platform,
            heading=heading,
            message=message,
            success=True,
            zip_url=zip_url,
        )

    except RuntimeError as exc:
        return render_page(
            description=description,
            platform=platform,
            heading="Impossible de terminer",
            message=str(exc),
            success=False,
            status=400,
        )
    except Exception:
        app.logger.exception("Erreur inattendue")
        return render_page(
            description=description,
            platform=platform,
            heading="Erreur inattendue",
            message=(
                "Une erreur est survenue. Consulte les journaux Render "
                "pour identifier le problème. Ne partage aucune clé secrète."
            ),
            success=False,
            status=500,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
