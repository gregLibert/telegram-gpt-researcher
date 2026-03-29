"""Telegram bot: allowlisted users, GPT Researcher HTTP API, Markdown + PDF delivery."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx
from telegram import Bot, BufferedInputFile, Message, Update, User
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults

from bot.allowlist import parse_allowed_user_ids
from bot.filename_sanitize import sanitize_download_basename
from bot.gptr_client import generate_report
from bot.pdf_export import markdown_to_basic_pdf_bytes
from bot.research_parse import ParsedResearchCommand, parse_research_command

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("telegram_bot")


def _load_allowed_ids_from_env() -> set[int]:
    """
    Read ``TELEGRAM_ALLOWED_USER_IDS`` and parse it into a set of integer user IDs.

    Raises:
        RuntimeError: If the variable is missing or empty after stripping whitespace.
    """
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
    if not raw:
        raise RuntimeError(
            "TELEGRAM_ALLOWED_USER_IDS must list at least one Telegram user id."
        )
    return parse_allowed_user_ids(raw)


def _check_authorization(user_id: int, allowed_ids: set[int]) -> bool:
    """Return True if ``user_id`` is present in the configured allowlist."""
    return user_id in allowed_ids


def _user_and_message(update: Update) -> tuple[User, Message] | None:
    """
    Extract the acting user and the message from an update, if both exist.

    Returns:
        A ``(user, message)`` pair, or ``None`` when the update has no user or no message.
    """
    if update.effective_user is None or update.message is None:
        return None
    return update.effective_user, update.message


def _markdown_report_or_none(data: dict[str, object]) -> str | None:
    """
    Return the Markdown report string from a GPT Researcher JSON payload, if valid.

    Returns:
        Non-empty stripped Markdown, or ``None`` if ``report`` is missing or not a non-empty string.
    """
    report_md = data.get("report")
    if not isinstance(report_md, str) or not report_md.strip():
        return None
    return report_md


def _prepare_artifact_paths(base: str) -> tuple[Path, Path]:
    """
    Resolve absolute paths for the Markdown and PDF artifacts under ``BOT_ARTIFACT_DIR``.

    Creates the artifact directory if it does not exist.
    """
    tmpdir = Path(os.environ.get("BOT_ARTIFACT_DIR", "/tmp/bot-artifacts"))
    tmpdir.mkdir(parents=True, exist_ok=True)
    return tmpdir / f"{base}.md", tmpdir / f"{base}.pdf"


def _write_markdown_and_pdf(md_path: Path, pdf_path: Path, report_md: str) -> None:
    """Persist Markdown to disk and render a basic PDF next to it."""
    md_path.write_text(report_md, encoding="utf-8")
    pdf_path.write_bytes(markdown_to_basic_pdf_bytes(report_md))


def _unlink_quiet(paths: tuple[Path, ...]) -> None:
    """Best-effort deletion of files; ignores missing paths and OS errors."""
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


async def _send_artifacts(
    bot: Bot,
    chat_id: int,
    *,
    base: str,
    md_path: Path,
    pdf_path: Path,
) -> None:
    """Send the Markdown and PDF files to the given Telegram chat as documents."""
    md_bytes = md_path.read_bytes()
    pdf_bytes = pdf_path.read_bytes()
    await bot.send_document(
        chat_id=chat_id,
        document=BufferedInputFile(md_bytes, filename=f"{base}.md"),
        caption="Rapport (Markdown)",
    )
    await bot.send_document(
        chat_id=chat_id,
        document=BufferedInputFile(pdf_bytes, filename=f"{base}.pdf"),
        caption="Rapport (PDF basique)",
    )


async def _process_research_task(
    application: Application,
    chat_id: int,
    parsed: ParsedResearchCommand,
) -> None:
    """
    Background job: call GPT Researcher, write artifacts, send them, and clean up files.

    Network I/O (``generate_report``) runs outside the artifact ``try``/``finally`` so cleanup
    never references ``md_path`` / ``pdf_path`` before assignment.
    """
    bot = application.bot
    status = await bot.send_message(chat_id, "Génération du rapport en cours…")

    try:
        data = await generate_report(parsed.query, report_type=parsed.report_type)
    except httpx.HTTPStatusError as exc:
        logger.exception("GPT Researcher HTTP error")
        await status.edit_text(f"Erreur API GPT Researcher : {exc.response.status_code}")
        return
    except Exception as exc:
        logger.exception("GPT Researcher request failed")
        await status.edit_text(f"Échec : {exc!s}")
        return

    report_md = _markdown_report_or_none(data)
    if report_md is None:
        await status.edit_text("Réponse sans rapport Markdown.")
        return

    research_id = data.get("research_id", "report")
    base = sanitize_download_basename(str(research_id))
    md_path, pdf_path = _prepare_artifact_paths(base)

    try:
        _write_markdown_and_pdf(md_path, pdf_path, report_md)
        await status.edit_text("Envoi des fichiers…")
        await _send_artifacts(bot, chat_id, base=base, md_path=md_path, pdf_path=pdf_path)
        await status.edit_text("Terminé.")
    except Exception:
        logger.exception("Unexpected failure while building or sending research artifacts")
        try:
            await status.edit_text("Une erreur inattendue s’est produite.")
        except Exception:
            pass
    finally:
        _unlink_quiet((md_path, pdf_path))


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start with a short French usage hint."""
    if update.message is None:
        return
    await update.message.reply_text(
        "Assistant de recherche.\n"
        "Utilisez : /research <votre question>\n"
        "Vous recevrez un fichier .md et un .pdf."
    )


async def cmd_research(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /research: enforce allowlist, parse argv, acknowledge immediately, and schedule work.

    Long-running work runs in ``asyncio.create_task`` so the handler returns quickly.
    """
    pair = _user_and_message(update)
    if pair is None:
        return
    user, message = pair
    allowed_ids: set[int] = context.application.bot_data["allowed_ids"]
    if not _check_authorization(user.id, allowed_ids):
        await message.reply_text("Accès refusé.")
        return

    parsed = parse_research_command(list(context.args or []))
    if parsed is None:
        await message.reply_text(
            "Usage : /research [options] <question>\n"
            "Options : --deep (-d), --detailed, --outline, --resource"
        )
        return

    await message.reply_chat_action(action="typing")
    await message.reply_text("Recherche lancée…")
    asyncio.create_task(
        _process_research_task(context.application, message.chat_id, parsed),
        name=f"research-{user.id}-{message.message_id}",
    )


def main() -> None:
    """Build the Telegram ``Application``, register handlers, and start long polling."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")

    allowed_ids = _load_allowed_ids_from_env()
    defaults = Defaults(parse_mode=None)

    app = (
        Application.builder()
        .token(token)
        .defaults(defaults)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.bot_data["allowed_ids"] = allowed_ids

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("research", cmd_research))

    logger.info("Starting bot (long polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
