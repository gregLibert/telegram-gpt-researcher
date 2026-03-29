"""Telegram bot: allowlisted users, GPT Researcher HTTP API, PDF report delivery."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx
from telegram import Bot, Message, Update, User
from telegram.ext import Application, CommandHandler, ContextTypes, Defaults

from bot.allowlist import parse_allowed_user_ids
from bot.filename_sanitize import sanitize_download_basename
from bot.gptr_client import (
    ResearchDeliveryMeta,
    format_delivery_summary,
    generate_report,
    parse_research_delivery_meta,
)
from bot.markdown_heading import extract_first_markdown_heading_title
from bot.pdf_export import markdown_to_pdf_bytes
from bot.research_parse import ParsedResearchCommand, parse_research_command

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("telegram_bot")


def _research_concurrency_limit() -> int:
    """
    Max concurrent GPT Researcher jobs (1–2). Parsed from ``RESEARCH_MAX_CONCURRENT`` (default 1).

    Limits parallel ``_process_research_task`` runs to reduce RAM pressure on small hosts (e.g. ARM SBCs).
    """
    raw = os.environ.get("RESEARCH_MAX_CONCURRENT", "1").strip()
    try:
        n = int(raw)
    except ValueError:
        return 1
    return max(1, min(2, n))


async def _process_research_task_guarded(
    application: Application,
    chat_id: int,
    parsed: ParsedResearchCommand,
) -> None:
    """Acquire the global research slot, then run :func:`_process_research_task` (queued if busy)."""
    semaphore: asyncio.Semaphore = application.bot_data["research_semaphore"]
    async with semaphore:
        await _process_research_task(application, chat_id, parsed)


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


def _artifact_basename(report_md: str, fallback_id: str) -> str:
    """Prefer the first Markdown H1/H2 title; otherwise fall back to the research id string."""
    title = extract_first_markdown_heading_title(report_md)
    raw = title if title else fallback_id
    return sanitize_download_basename(raw)


def _truncate_caption(text: str, max_len: int = 1024) -> str:
    """Trim text to Telegram's caption limit."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _compose_document_caption(kind_label: str, summary_line: str) -> str:
    """Merge a French file label with an optional English metrics line."""
    summary_line = summary_line.strip()
    if not summary_line:
        return kind_label
    return _truncate_caption(f"{kind_label}\n{summary_line}")


def _write_markdown_and_pdf(md_path: Path, pdf_path: Path, report_md: str) -> None:
    """Persist Markdown to disk and render a formatted PDF next to it."""
    md_path.write_text(report_md, encoding="utf-8")
    pdf_path.write_bytes(markdown_to_pdf_bytes(report_md))


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
    pdf_path: Path,
    meta: ResearchDeliveryMeta,
) -> None:
    """Send the PDF with a caption that includes cost and URL metrics when available."""
    summary = format_delivery_summary(meta)
    pdf_caption = _compose_document_caption("Rapport (PDF)", summary)
    pdf_bytes = pdf_path.read_bytes()
    await bot.send_document(
        chat_id=chat_id,
        document=pdf_bytes,
        filename=f"{base}.pdf",
        caption=pdf_caption,
    )


async def _process_research_task(
    application: Application,
    chat_id: int,
    parsed: ParsedResearchCommand,
) -> None:
    """
    Background job: call GPT Researcher, write artifacts, send them, and clean up files.

    Initial Telegram status and ``generate_report`` share one ``try`` so a failed
    ``send_message`` is logged without assuming ``status`` exists. Markdown/PDF work
    uses ``asyncio.to_thread`` so WeasyPrint does not block the event loop. The
    artifact ``try``/``finally`` keeps cleanup from referencing ``md_path`` /
    ``pdf_path`` before assignment.
    """
    bot = application.bot
    status: Message | None = None
    try:
        status = await bot.send_message(chat_id, "Génération du rapport en cours…")
        data = await generate_report(parsed.query, report_type=parsed.report_type)
    except httpx.HTTPStatusError as exc:
        logger.exception("GPT Researcher HTTP error")
        if status is not None:
            await status.edit_text(f"Erreur API GPT Researcher : {exc.response.status_code}")
        return
    except httpx.RequestError as exc:
        logger.exception("Network error while contacting GPT Researcher")
        if status is not None:
            await status.edit_text(f"Erreur réseau avec GPT Researcher : {exc!s}")
        return
    except Exception as exc:
        if status is None:
            logger.exception(
                "Telegram error while sending initial status for research task"
            )
        else:
            logger.exception("GPT Researcher request failed")
            try:
                await status.edit_text(f"Échec : {exc!s}")
            except Exception:
                pass
        return

    report_md = _markdown_report_or_none(data)
    if report_md is None:
        await status.edit_text("Réponse sans rapport Markdown.")
        return

    meta = parse_research_delivery_meta(data)
    fallback_id = str(data.get("research_id", "report"))
    base = _artifact_basename(report_md, fallback_id)
    md_path, pdf_path = _prepare_artifact_paths(base)

    try:
        await asyncio.to_thread(_write_markdown_and_pdf, md_path, pdf_path, report_md)
        await status.edit_text("Envoi des fichiers…")
        await _send_artifacts(
            bot,
            chat_id,
            base=base,
            pdf_path=pdf_path,
            meta=meta,
        )
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
    """Handle /start with a short French usage hint and a pointer to /help."""
    if update.message is None:
        return
    await update.message.reply_text(
        "Assistant de recherche automatisé (GPT Researcher).\n\n"
        "Posez une question avec : /research <votre sujet>\n"
        "Vous recevrez le rapport au format PDF.\n\n"
        "Pour les modes avancés (--deep, plan détaillé, etc.), utilisez /help."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /help: explain /research syntax and optional report modes (French user text).

    Intended to make advanced flags discoverable without reading the source code.
    """
    if update.message is None:
        return
    await update.message.reply_text(
        "📖 Aide — commande /research\n\n"
        "Syntaxe :\n"
        "/research [options…] <votre question ou sujet>\n\n"
        "Vous pouvez enchaîner plusieurs options ; la dernière indiquée "
        "prévaut pour le type de rapport.\n\n"
        "Options disponibles :\n"
        "• --deep ou -d — recherche approfondie (mode « deep »), plus exhaustive, "
        "souvent plus long.\n"
        "• --detailed — rapport détaillé, avec une analyse plus poussée.\n"
        "• --outline — plan structuré (sommaire / outline) plutôt qu’un texte linéaire.\n"
        "• --resource — rapport centré sur les ressources et références utiles.\n\n"
        "Exemples :\n"
        "/research Qu’est-ce que Docker ?\n"
        "/research --deep historique du protocole HTTP\n"
        "/research --outline --detailed veille sur l’IA en 2025\n\n"
        "Astuce : les mots du type « deep learning » ne sont pas interprétés comme "
        "l’option --deep ; utilisez bien le flag --deep devant la question."
    )


async def cmd_research(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /research: enforce allowlist, parse argv, acknowledge immediately, and schedule work.

    Long-running work runs in ``asyncio.create_task`` so the handler returns quickly.
    Concurrent jobs are capped by :func:`_research_concurrency_limit` via a semaphore.
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
            "Options : --deep (-d), --detailed, --outline, --resource\n"
            "Tapez /help pour une description détaillée de chaque mode."
        )
        return

    await message.reply_chat_action(action="typing")
    await message.reply_text("Recherche lancée…")
    asyncio.create_task(
        _process_research_task_guarded(context.application, message.chat_id, parsed),
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
    app.bot_data["research_semaphore"] = asyncio.Semaphore(_research_concurrency_limit())

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("research", cmd_research))

    logger.info("Starting bot (long polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
