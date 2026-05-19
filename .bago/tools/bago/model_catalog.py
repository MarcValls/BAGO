"""
BAGO Model Catalog — lista curada de modelos locales Ollama.

Cada entrada describe un modelo disponible para instalar/usar localmente.
Los marcados con  gem=True  son "joyas ocultas": excelente rendimiento,
poca adopción comercial — los auténticos campeones del open-source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ─── Tipos de especialidad ────────────────────────────────────────────────────
SPECIALTIES = {
    "coding":        "💻 Código",
    "reasoning":     "🧠 Razonamiento",
    "general":       "🌐 General",
    "multilingual":  "🗺  Multilingüe",
    "small":         "🪶 Ultra-ligero",
    "vision":        "👁  Visión",
    "rag":           "🔍 RAG / búsqueda",
    "uncensored":    "🔓 Sin censura",
    "math":          "📐 Matemáticas",
    "embeddings":    "📊 Embeddings",
}


@dataclass
class ModelEntry:
    ollama_tag: str           # tag exacto para `ollama pull`
    label: str                # nombre bonito
    maker: str                # organización creadora
    size_gb: float            # tamaño aproximado en GB (modelo Q4)
    specialty: list[str]      # claves de SPECIALTIES
    description: str          # descripción corta en español
    context_k: int = 4        # ventana de contexto en miles de tokens
    benchmark: str = ""       # puntos de referencia breves
    gem: bool = False         # ¿joya oculta?
    gem_reason: str = ""      # por qué es una joya
    url: str = ""             # página/paper de referencia
    installed: bool = False   # se rellena en runtime


# ─── Catálogo ─────────────────────────────────────────────────────────────────

CATALOG: list[ModelEntry] = [

    # ════════════════════════════════════════════════════════════════════════
    # JOYAS OCULTAS — buena reputación, bajo perfil comercial
    # ════════════════════════════════════════════════════════════════════════

    ModelEntry(
        ollama_tag   = "phi4:14b",
        label        = "Phi-4 14B",
        maker        = "Microsoft Research",
        size_gb      = 8.5,
        specialty    = ["reasoning", "coding", "math"],
        description  = (
            "El modelo pequeño más sorprendente de 2025. 14B parámetros "
            "pero supera a modelos de 70B en razonamiento y matemáticas. "
            "Microsoft casi no lo promocionó — lo lanzó calladamente en Ollama."
        ),
        context_k    = 16,
        benchmark    = "MMLU 84.8 · HumanEval 82.6 · GSM8K 91.0",
        gem          = True,
        gem_reason   = "Supera a Llama-3.1-70B en muchos benchmarks siendo 5× más pequeño",
        url          = "https://ollama.com/library/phi4",
    ),

    ModelEntry(
        ollama_tag   = "deepseek-r1:8b",
        label        = "DeepSeek-R1 8B (distilado)",
        maker        = "DeepSeek AI",
        size_gb      = 5.0,
        specialty    = ["reasoning", "math", "coding"],
        description  = (
            "Destilado del modelo de razonamiento DeepSeek-R1 completo. "
            "Piensa en voz alta (chain-of-thought nativo). Para su tamaño, "
            "el mejor modelo de razonamiento que existe — prácticamente desconocido en occidente."
        ),
        context_k    = 128,
        benchmark    = "MATH 83.0 · AIME 50.0 · HumanEval 79.3",
        gem          = True,
        gem_reason   = "Razonamiento de nivel GPT-o1 mini a 5GB. Casi nadie lo usa fuera de Asia",
        url          = "https://ollama.com/library/deepseek-r1",
    ),

    ModelEntry(
        ollama_tag   = "granite3.2:8b",
        label        = "IBM Granite 3.2 8B",
        maker        = "IBM Research",
        size_gb      = 4.9,
        specialty    = ["coding", "reasoning", "rag"],
        description  = (
            "El modelo enterprise más infravalorado. IBM lo entrena con datos "
            "verificados y curados, sin contenido de dudosa procedencia. "
            "Excelente para RAG, function calling y código de producción."
        ),
        context_k    = 128,
        benchmark    = "MMLU 73.5 · IFEval 76.8 · HumanEval 68.4",
        gem          = True,
        gem_reason   = "Entrenado éticamente, licencia Apache-2.0, IBM no sabe hacer marketing",
        url          = "https://ollama.com/library/granite3.2",
    ),

    ModelEntry(
        ollama_tag   = "internlm2:7b",
        label        = "InternLM 2.5 7B",
        maker        = "Shanghai AI Lab",
        size_gb      = 4.5,
        specialty    = ["coding", "multilingual", "reasoning"],
        description  = (
            "Modelo del laboratorio de IA más activo de China, prácticamente "
            "desconocido en Europa. Excelente en chino, inglés y español. "
            "Su capacidad de código rivaliza con CodeLlama en la mitad del tamaño."
        ),
        context_k    = 32,
        benchmark    = "MMLU 72.8 · HumanEval 73.2 · GSM8K 86.0",
        gem          = True,
        gem_reason   = "El modelo chino que avergüenza a modelos occidentales de 13B",
        url          = "https://ollama.com/library/internlm2",
    ),

    ModelEntry(
        ollama_tag   = "falcon3:7b",
        label        = "Falcon 3 7B",
        maker        = "TII — Technology Innovation Institute (Abu Dabi)",
        size_gb      = 4.4,
        specialty    = ["general", "multilingual", "reasoning"],
        description  = (
            "Lanzado en diciembre 2024, Falcon 3 supera a Llama-3.1-8B en "
            "todos los benchmarks. El TII recibe apenas el 10% de la atención "
            "de Meta. Licencia Apache-2.0 real, sin restricciones comerciales."
        ),
        context_k    = 32,
        benchmark    = "MMLU 78.2 · Arc-C 64.1",
        gem          = True,
        gem_reason   = "Mejor que Llama 3.1 8B, casi nadie lo sabe",
        url          = "https://ollama.com/library/falcon3",
    ),

    ModelEntry(
        ollama_tag   = "smollm2:1.7b",
        label        = "SmolLM2 1.7B",
        maker        = "Hugging Face",
        size_gb      = 1.1,
        specialty    = ["small", "coding", "general"],
        description  = (
            "El modelo más pequeño que todavía es útil. 1.7B parámetros que "
            "caben en un teléfono. Para tasks simples: resumir, completar, "
            "generar funciones cortas. Ideal para edge, IoT, sin GPU."
        ),
        context_k    = 8,
        benchmark    = "GSM8K 31.0 · MMLU 51.9",
        gem          = True,
        gem_reason   = "1GB y todavía sirve para código. Ideal para máquinas sin GPU o muy limitadas",
        url          = "https://ollama.com/library/smollm2",
    ),

    ModelEntry(
        ollama_tag   = "nous-hermes3:8b",
        label        = "Nous Hermes 3 8B",
        maker        = "Nous Research (community)",
        size_gb      = 4.9,
        specialty    = ["general", "uncensored", "reasoning"],
        description  = (
            "Fine-tune artesanal de la comunidad sobre Llama 3.1 8B. "
            "Sin restricciones artificiales, seguimiento de instrucciones "
            "mucho más fiel que el modelo base. Favorito de los power users."
        ),
        context_k    = 128,
        benchmark    = "MT-Bench estimado: 8.1",
        gem          = True,
        gem_reason   = "La comunidad vs los corporativos. Sigue instrucciones mejor que el Llama base",
        url          = "https://ollama.com/library/nous-hermes3",
    ),

    ModelEntry(
        ollama_tag   = "solar:10.7b",
        label        = "Solar Pro 10.7B",
        maker        = "Upstage (Corea del Sur)",
        size_gb      = 6.2,
        specialty    = ["general", "reasoning", "multilingual"],
        description  = (
            "Arquitectura nueva (Depth Up-Scaling) que logra rendimiento de "
            "13B con solo 10.7B parámetros. Startup coreana que la rompe en "
            "benchmarks pero apenas tiene presencia fuera de Asia."
        ),
        context_k    = 4,
        benchmark    = "MMLU 74.2 · MT-Bench 7.58",
        gem          = True,
        gem_reason   = "Técnica DUS innovadora, rompe la relación tamaño/calidad",
        url          = "https://ollama.com/library/solar",
    ),

    # ════════════════════════════════════════════════════════════════════════
    # ESTÁNDAR DE ORO — los más usados y fiables
    # ════════════════════════════════════════════════════════════════════════

    ModelEntry(
        ollama_tag   = "qwen2.5-coder:7b",
        label        = "Qwen2.5-Coder 7B",
        maker        = "Alibaba",
        size_gb      = 4.7,
        specialty    = ["coding"],
        description  = "El mejor modelo de código a menos de 10GB. Motor por defecto de BAGO.",
        context_k    = 128,
        benchmark    = "HumanEval 88.4 · MultiPL-E 73.2",
        url          = "https://ollama.com/library/qwen2.5-coder",
    ),

    ModelEntry(
        ollama_tag   = "qwen2.5-coder:14b",
        label        = "Qwen2.5-Coder 14B",
        maker        = "Alibaba",
        size_gb      = 9.0,
        specialty    = ["coding"],
        description  = "Versión grande del coder de BAGO. Contexto 1M tokens.",
        context_k    = 1000,
        benchmark    = "HumanEval 91.2 · MBPP 80.4",
        url          = "https://ollama.com/library/qwen2.5-coder",
    ),

    ModelEntry(
        ollama_tag   = "qwen2.5:7b",
        label        = "Qwen2.5 7B",
        maker        = "Alibaba",
        size_gb      = 4.7,
        specialty    = ["general", "multilingual"],
        description  = "Propósito general multilingüe (29 idiomas). Excelente en español.",
        context_k    = 128,
        benchmark    = "MMLU 74.2",
        url          = "https://ollama.com/library/qwen2.5",
    ),

    ModelEntry(
        ollama_tag   = "llama3.2:3b",
        label        = "Llama 3.2 3B",
        maker        = "Meta",
        size_gb      = 2.0,
        specialty    = ["general", "small"],
        description  = "El equilibrio perfecto de Meta: 3B muy capaz, 2GB RAM. Ideal como fallback.",
        context_k    = 128,
        benchmark    = "MMLU 58.0",
        url          = "https://ollama.com/library/llama3.2",
    ),

    ModelEntry(
        ollama_tag   = "llama3.1:8b",
        label        = "Llama 3.1 8B",
        maker        = "Meta",
        size_gb      = 4.9,
        specialty    = ["general", "multilingual"],
        description  = "El modelo open-source más adoptado del mundo. 128K contexto.",
        context_k    = 128,
        benchmark    = "MMLU 73.0 · HumanEval 72.6",
        url          = "https://ollama.com/library/llama3.1",
    ),

    ModelEntry(
        ollama_tag   = "mistral:7b",
        label        = "Mistral 7B v0.3",
        maker        = "Mistral AI",
        size_gb      = 4.1,
        specialty    = ["general", "coding"],
        description  = "Compacto, rápido, eficiente. El pionero de los modelos europeos.",
        context_k    = 32,
        benchmark    = "MMLU 62.5 · HumanEval 60.0",
        url          = "https://ollama.com/library/mistral",
    ),

    ModelEntry(
        ollama_tag   = "mistral-nemo:12b",
        label        = "Mistral NeMo 12B",
        maker        = "Mistral AI + NVIDIA",
        size_gb      = 7.1,
        specialty    = ["general", "multilingual", "coding"],
        description  = "Colaboración Mistral-NVIDIA. 128K contexto, excelente en producción.",
        context_k    = 128,
        benchmark    = "MMLU 68.0",
        url          = "https://ollama.com/library/mistral-nemo",
    ),

    ModelEntry(
        ollama_tag   = "gemma3:12b",
        label        = "Gemma 3 12B",
        maker        = "Google DeepMind",
        size_gb      = 8.1,
        specialty    = ["general", "vision", "multilingual"],
        description  = "Google open-source con soporte multimodal. 140 idiomas.",
        context_k    = 128,
        benchmark    = "MMLU 74.5",
        url          = "https://ollama.com/library/gemma3",
    ),

    ModelEntry(
        ollama_tag   = "gemma3:4b",
        label        = "Gemma 3 4B",
        maker        = "Google DeepMind",
        size_gb      = 3.3,
        specialty    = ["general", "vision", "small"],
        description  = "Versión compacta de Gemma con visión. Muy equilibrado.",
        context_k    = 128,
        benchmark    = "MMLU 59.6",
        url          = "https://ollama.com/library/gemma3",
    ),

    ModelEntry(
        ollama_tag   = "phi3.5:3.8b",
        label        = "Phi-3.5 mini 3.8B",
        maker        = "Microsoft Research",
        size_gb      = 2.2,
        specialty    = ["coding", "small", "reasoning"],
        description  = "El SLM de Microsoft. 3.8B que rinde como un 7B en código.",
        context_k    = 128,
        benchmark    = "MMLU 69.0 · HumanEval 62.8",
        url          = "https://ollama.com/library/phi3.5",
    ),

    ModelEntry(
        ollama_tag   = "codellama:13b",
        label        = "CodeLlama 13B",
        maker        = "Meta",
        size_gb      = 7.4,
        specialty    = ["coding"],
        description  = "Especialista en código de Meta. FIM nativo (fill-in-the-middle).",
        context_k    = 16,
        benchmark    = "HumanEval 62.0 · MBPP 62.4",
        url          = "https://ollama.com/library/codellama",
    ),

    ModelEntry(
        ollama_tag   = "starcoder2:7b",
        label        = "StarCoder2 7B",
        maker        = "BigCode (HuggingFace + ServiceNow)",
        size_gb      = 4.0,
        specialty    = ["coding"],
        description  = "619 lenguajes de programación, 80K contexto. Trained on The Stack v2.",
        context_k    = 80,
        benchmark    = "HumanEval 46.3 · MultiPL-E 48.0",
        url          = "https://ollama.com/library/starcoder2",
    ),

    ModelEntry(
        ollama_tag   = "dolphin-mistral:7b",
        label        = "Dolphin Mistral 7B",
        maker        = "Cognitive Computations (Eric Hartford)",
        size_gb      = 4.1,
        specialty    = ["general", "uncensored"],
        description  = (
            "Fine-tune sin filtros sobre Mistral 7B. Para investigación "
            "o tareas que los modelos censurados rechazan injustificadamente."
        ),
        context_k    = 32,
        benchmark    = "MT-Bench estimado: 7.5",
        url          = "https://ollama.com/library/dolphin-mistral",
    ),

    ModelEntry(
        ollama_tag   = "nomic-embed-text:latest",
        label        = "Nomic Embed Text",
        maker        = "Nomic AI",
        size_gb      = 0.3,
        specialty    = ["embeddings", "rag"],
        description  = "El mejor modelo de embeddings locales para RAG. 137M params, 8192 tokens.",
        context_k    = 8,
        benchmark    = "MTEB 62.4 (mejor que OpenAI ada-002)",
        gem          = True,
        gem_reason   = "Embeddings locales que superan a OpenAI text-embedding-ada-002. 300MB.",
        url          = "https://ollama.com/library/nomic-embed-text",
    ),

    ModelEntry(
        ollama_tag   = "deepseek-coder:6.7b",
        label        = "DeepSeek Coder 6.7B",
        maker        = "DeepSeek AI",
        size_gb      = 3.9,
        specialty    = ["coding"],
        description  = "Especialista en código de DeepSeek. Project-level code completion.",
        context_k    = 16,
        benchmark    = "HumanEval 78.6 · MBPP 74.9",
        url          = "https://ollama.com/library/deepseek-coder",
    ),
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_gems() -> list[ModelEntry]:
    """Devuelve solo las joyas ocultas."""
    return [m for m in CATALOG if m.gem]


def get_by_specialty(spec: str) -> list[ModelEntry]:
    """Filtra modelos por especialidad."""
    return [m for m in CATALOG if spec in m.specialty]


def enrich_with_installed(installed_tags: list[str]) -> None:
    """Marca los modelos del catálogo que ya están instalados en Ollama.

    installed_tags: lista de tags que devuelve ollama_probe() → models
    """
    # Normaliza: "qwen2.5-coder:7b" y "qwen2.5-coder" ambos matchean
    installed_normalized = {t.split(":")[0] for t in installed_tags} | set(installed_tags)
    for entry in CATALOG:
        tag_base = entry.ollama_tag.split(":")[0]
        entry.installed = (
            entry.ollama_tag in installed_normalized
            or tag_base in installed_normalized
        )


def by_tag(tag: str) -> Optional[ModelEntry]:
    """Busca entrada por ollama_tag exacto o base (sin versión)."""
    tag_base = tag.split(":")[0]
    for m in CATALOG:
        if m.ollama_tag == tag or m.ollama_tag.split(":")[0] == tag_base:
            return m
    return None
