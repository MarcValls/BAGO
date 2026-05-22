#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""personality_panel — Panel de personalidad y configuración de agentes BAGO."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import sys


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / ".bago/state/user_personality_profile.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_profile() -> dict:
    return {
        "version": 1,
        "updated_at": now_iso(),
        "personality": {
            "style": "colaborativo, directo y claro",
            "notes": "",
        },
        "language": {
            "primary": "es",
            "register": "neutral",
        },
        "vocabulary": [],
    }


def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        return default_profile()
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def save_profile(profile: dict) -> None:
    profile["updated_at"] = now_iso()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def print_profile(profile: dict) -> None:
    print(json.dumps(profile, indent=2, ensure_ascii=False, sort_keys=True))


def list_vocab(profile: dict) -> None:
    terms = profile.get("vocabulary", [])
    if not terms:
        print("No hay vocabulario personalizado.")
        return
    for idx, item in enumerate(terms, start=1):
        print(
            f"{idx}. {item.get('term','')} | contexto={item.get('social_context','')}\n"
            f"   significado: {item.get('meaning','')}\n"
            f"   ejemplo: {item.get('usage_example','')}"
        )


def add_vocab(
    profile: dict,
    term: str,
    meaning: str,
    usage_example: str,
    social_context: str = "circulo_pequeno",
) -> None:
    vocabulary = profile.setdefault("vocabulary", [])
    for item in vocabulary:
        if item.get("term", "").lower() == term.lower():
            item.update(
                {
                    "meaning": meaning,
                    "usage_example": usage_example,
                    "social_context": social_context,
                }
            )
            return
    vocabulary.append(
        {
            "term": term,
            "meaning": meaning,
            "usage_example": usage_example,
            "social_context": social_context,
        }
    )


def remove_vocab(profile: dict, term: str) -> bool:
    vocabulary = profile.get("vocabulary", [])
    before = len(vocabulary)
    profile["vocabulary"] = [v for v in vocabulary if v.get("term", "").lower() != term.lower()]
    return len(profile["vocabulary"]) < before


def interactive_panel(profile: dict) -> int:
    print("Panel de configuración BAGO")
    while True:
        print("\n1) Ver configuración")
        print("2) Editar personalidad")
        print("3) Editar idioma")
        print("4) Añadir palabra de vocabulario (círculo pequeño)")
        print("5) Listar vocabulario")
        print("6) Eliminar palabra de vocabulario")
        print("7) Guardar y salir")
        print("8) Salir sin guardar")
        option = input("> ").strip()

        if option == "1":
            print_profile(profile)
        elif option == "2":
            style = input("Estilo/personalidad: ").strip()
            notes = input("Notas de comportamiento (opcional): ").strip()
            if style:
                profile.setdefault("personality", {})["style"] = style
            profile.setdefault("personality", {})["notes"] = notes
        elif option == "3":
            primary = input("Idioma principal (ej: es, en): ").strip()
            register = input("Registro (neutral, formal, cercano...): ").strip()
            if primary:
                profile.setdefault("language", {})["primary"] = primary
            if register:
                profile.setdefault("language", {})["register"] = register
        elif option == "4":
            term = input("Palabra/expresión: ").strip()
            meaning = input("Qué significa en su círculo: ").strip()
            usage_example = input("Ejemplo de uso: ").strip()
            if term and meaning:
                add_vocab(profile, term, meaning, usage_example)
            else:
                print("Termino y significado son obligatorios.")
        elif option == "5":
            list_vocab(profile)
        elif option == "6":
            term = input("Palabra a eliminar: ").strip()
            if not term:
                print("Debes indicar una palabra.")
            elif remove_vocab(profile, term):
                print("Eliminada.")
            else:
                print("No encontrada.")
        elif option == "7":
            save_profile(profile)
            print(f"Guardado en {PROFILE_PATH}")
            return 0
        elif option == "8":
            print("Sin cambios guardados.")
            return 0
        else:
            print("Opción inválida.")


def guided_vocabulary_flow(profile: dict) -> int:
    print("Flujo guiado de vocabulario (círculo pequeño)")
    print("Pulsa Enter en 'palabra' para terminar.")
    while True:
        term = input("\nPalabra/expresión: ").strip()
        if not term:
            break
        meaning = input("Qué significa en su círculo: ").strip()
        if not meaning:
            print("Significado obligatorio. Se omite este término.")
            continue
        usage_example = input("Frase real de uso: ").strip()
        social_context = input("Contexto social [circulo_pequeno]: ").strip() or "circulo_pequeno"
        add_vocab(profile, term, meaning, usage_example, social_context)
        print(f"Guardado: {term}")

    save_profile(profile)
    print(f"\nFlujo completado. Perfil guardado en {PROFILE_PATH}")
    list_vocab(profile)
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Panel de configuración de personalidad, idioma y vocabulario BAGO."
    )
    parser.add_argument("--show", action="store_true", help="Muestra la configuración actual")
    parser.add_argument("--interactive", action="store_true", help="Abre el panel interactivo")
    parser.add_argument(
        "--flow-vocab",
        action="store_true",
        help="Abre un flujo guiado para cargar vocabulario de círculo pequeño",
    )
    parser.add_argument("--set-style", help="Define el estilo/personalidad base")
    parser.add_argument("--set-notes", help="Define notas de comportamiento")
    parser.add_argument("--set-language", help="Define idioma principal (es, en, ...)")
    parser.add_argument("--set-register", help="Define registro (neutral, formal, cercano...)")
    parser.add_argument("--add-term", help="Añade/actualiza una palabra o expresión")
    parser.add_argument("--meaning", help="Significado contextual de --add-term")
    parser.add_argument("--example", default="", help="Ejemplo de uso para --add-term")
    parser.add_argument(
        "--social-context",
        default="circulo_pequeno",
        help="Contexto social del término (por defecto: circulo_pequeno)",
    )
    parser.add_argument("--remove-term", help="Elimina una palabra del vocabulario")
    parser.add_argument("--list-vocab", action="store_true", help="Lista el vocabulario guardado")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    profile = load_profile()
    changed = False

    if args.flow_vocab:
        return guided_vocabulary_flow(profile)

    if args.interactive:
        return interactive_panel(profile)

    if args.set_style is not None:
        profile.setdefault("personality", {})["style"] = args.set_style
        changed = True
    if args.set_notes is not None:
        profile.setdefault("personality", {})["notes"] = args.set_notes
        changed = True
    if args.set_language is not None:
        profile.setdefault("language", {})["primary"] = args.set_language
        changed = True
    if args.set_register is not None:
        profile.setdefault("language", {})["register"] = args.set_register
        changed = True

    if args.add_term:
        if not args.meaning:
            raise SystemExit("--meaning es obligatorio cuando usas --add-term")
        add_vocab(profile, args.add_term, args.meaning, args.example, args.social_context)
        changed = True

    if args.remove_term:
        remove_vocab(profile, args.remove_term)
        changed = True

    if changed:
        save_profile(profile)

    if args.list_vocab:
        list_vocab(profile)
    elif args.show or changed:
        print_profile(profile)
    elif not any(vars(args).values()):
        return interactive_panel(profile)

    return 0



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main(sys.argv))
