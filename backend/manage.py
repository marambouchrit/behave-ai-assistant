"""
manage.py
=========
Gestion des comptes en ligne de commande (depuis la racine du projet).

    python -m backend.manage create-user --username alice --role admin
    python -m backend.manage reset-password --username alice
    python -m backend.manage set-role --username alice --role user

Les mots de passe sont saisis au clavier (saisie masquée, confirmation), jamais
passés en argument : ils n'apparaissent ni dans l'historique du shell ni dans
la liste des processus.
"""

import argparse
import getpass
import sys

from pydantic import ValidationError

from backend.database.connection import SessionLocal
from backend.database.crud import create_user, get_user_by_username, set_user_password, set_user_role
from backend.database.models import User, UserRole
from backend.schemas import UserRegisterRequest


class CommandError(Exception):
    """Erreur affichable à l'utilisateur du script."""


_FIELD_LABELS = {"username": "Nom d'utilisateur", "password": "Mot de passe"}


def _validation_message(exc: ValidationError) -> str:
    messages = []
    for error in exc.errors():
        field = _FIELD_LABELS.get(str(error["loc"][0]), str(error["loc"][0]))
        ctx   = error.get("ctx", {})
        if error["type"] == "string_too_short":
            messages.append(f"{field} : {ctx['min_length']} caractères minimum")
        elif error["type"] == "string_too_long":
            messages.append(f"{field} : {ctx['max_length']} caractères maximum")
        else:
            messages.append(f"{field} : {error['msg']}")
    return "; ".join(messages)


def _prompt_password() -> str:
    password = getpass.getpass("Mot de passe : ")
    if password != getpass.getpass("Confirmer le mot de passe : "):
        raise CommandError("Les mots de passe ne correspondent pas.")
    return password


def _validated_credentials(username: str, password: str) -> UserRegisterRequest:
    """Mêmes règles que l'inscription par l'API (longueurs du username et du mot de passe)."""
    try:
        return UserRegisterRequest(username=username, password=password)
    except ValidationError as exc:
        raise CommandError(_validation_message(exc)) from exc


def _get_user_or_fail(db, username: str) -> User:
    user = get_user_by_username(db, username)
    if user is None:
        raise CommandError(f"Utilisateur introuvable : {username}")
    return user


def create_user_command(username: str, role: str) -> None:
    with SessionLocal() as db:
        if get_user_by_username(db, username):
            raise CommandError(f"Le nom d'utilisateur '{username}' est déjà pris.")
        credentials = _validated_credentials(username, _prompt_password())
        create_user(db, credentials.username, credentials.password, role=UserRole(role))
    print(f"Compte créé : {username} (rôle {role}).")


def reset_password_command(username: str) -> None:
    with SessionLocal() as db:
        user = _get_user_or_fail(db, username)
        credentials = _validated_credentials(username, _prompt_password())
        set_user_password(db, user, credentials.password)
    print(f"Mot de passe réinitialisé pour {username}.")


def set_role_command(username: str, role: str) -> None:
    new_role = UserRole(role)
    with SessionLocal() as db:
        user = _get_user_or_fail(db, username)
        if user.role == new_role:
            print(f"{username} a déjà le rôle {role}.")
            return
        if user.role == UserRole.admin:
            admins = db.query(User).filter(User.role == UserRole.admin).count()
            if admins <= 1:
                raise CommandError("Impossible de rétrograder le dernier administrateur.")
        set_user_role(db, user, new_role)
    print(f"Rôle de {username} : {role}.")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m backend.manage",
        description="Gestion des comptes BeHave Assistant.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    roles = [r.value for r in UserRole]

    create = commands.add_parser("create-user", help="Créer un compte (le mot de passe est demandé au clavier).")
    create.add_argument("--username", required=True)
    create.add_argument("--role", choices=roles, default=UserRole.user.value)

    reset = commands.add_parser("reset-password", help="Définir un nouveau mot de passe.")
    reset.add_argument("--username", required=True)

    set_role = commands.add_parser("set-role", help="Changer le rôle d'un compte.")
    set_role.add_argument("--username", required=True)
    set_role.add_argument("--role", choices=roles, required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "create-user":
            create_user_command(args.username, args.role)
        elif args.command == "reset-password":
            reset_password_command(args.username)
        elif args.command == "set-role":
            set_role_command(args.username, args.role)
    except CommandError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAnnulé.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
