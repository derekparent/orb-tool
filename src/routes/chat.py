"""
Chat Blueprint — LLM-powered manuals assistant endpoints.

Provides the chat UI and SSE streaming endpoint.
"""

import json

from flask import (
    Blueprint,
    Response,
    current_app,
    render_template,
    request,
    jsonify,
    stream_with_context,
)
from flask_login import login_required, current_user

from sqlalchemy.exc import SQLAlchemyError

from app import limiter
from security import SecurityConfig
from models import db, ChatSession
from services.chat_service import (
    stream_chat_response,
    get_fallback_results,
    ChatServiceError,
)
from services.llm_service import get_llm_service
from services.web_search_service import get_web_search_service

chat_bp = Blueprint("chat", __name__, url_prefix="/manuals/chat")


@chat_bp.route("/")
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def chat_page():
    """Chat interface."""
    llm_available = get_llm_service() is not None
    web_search_enabled = get_web_search_service() is not None
    return render_template("manuals/chat.html", llm_available=llm_available, web_search_enabled=web_search_enabled)


@chat_bp.route("/api/message", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@login_required
def send_message():
    """Send a chat message and get a streamed SSE response.

    Request JSON:
        query: str — the user's question
        session_id: int|null — existing session ID, or null for new
        equipment: str|null — optional equipment filter

    Response: SSE stream with events:
        data: {"type": "token", "content": "..."} — streaming text deltas
        data: {"type": "done", "session_id": 123} — stream complete
        data: {"type": "error", "message": "..."} — error occurred
        data: {"type": "fallback", "results": [...]} — FTS5 fallback results
    """
    data = request.get_json(silent=True)
    if not data or not data.get("query", "").strip():
        return jsonify({"error": "Query is required"}), 400

    query = data["query"].strip()
    session_id = data.get("session_id")
    equipment = data.get("equipment")

    # Load or create session
    session = None
    history = []
    if session_id:
        session = ChatSession.query.filter_by(
            id=session_id, user_id=current_user.id
        ).first()
        if session:
            history = session.get_messages()

    def generate():
        nonlocal session

        full_response = []

        try:
            for token in stream_chat_response(
                query=query,
                history=history,
                equipment=equipment,
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Save to session
            response_text = "".join(full_response)
            new_messages = history + [
                {"role": "user", "content": query},
                {"role": "assistant", "content": response_text},
            ]

            if session:
                session.set_messages(new_messages)
            else:
                session = ChatSession(user_id=current_user.id)
                session.set_messages(new_messages)
                db.session.add(session)

            db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'session_id': session.id})}\n\n"

        except ChatServiceError as e:
            current_app.logger_instance.error(f"Chat error: {e}")

            # Fallback: return FTS5 search results
            fallback = get_fallback_results(query, equipment=equipment)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            if fallback:
                yield f"data: {json.dumps({'type': 'fallback', 'results': fallback})}\n\n"

        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger_instance.exception(f"Database error during chat: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Database error saving conversation'})}\n\n"

        except (ConnectionError, TimeoutError) as e:
            current_app.logger_instance.error(f"LLM connection error: {e}")
            fallback = get_fallback_results(query, equipment=equipment)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Connection to AI service timed out'})}\n\n"
            if fallback:
                yield f"data: {json.dumps({'type': 'fallback', 'results': fallback})}\n\n"

        except Exception as e:  # Safety net — SSE generators must not crash silently
            current_app.logger_instance.exception(f"Unexpected chat error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An unexpected error occurred'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/api/sessions", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def list_sessions():
    """List user's chat sessions."""
    sessions = ChatSession.query.filter_by(
        user_id=current_user.id
    ).order_by(ChatSession.updated_at.desc()).limit(20).all()

    return jsonify([
        {
            "id": s.id,
            "preview": _session_preview(s),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ])


@chat_bp.route("/api/sessions/<int:session_id>", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def get_session(session_id: int):
    """Get a specific chat session."""
    session = ChatSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict())


@chat_bp.route("/api/sessions/<int:session_id>", methods=["DELETE"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@login_required
def delete_session(session_id: int):
    """Delete a chat session."""
    session = ChatSession.query.filter_by(
        id=session_id, user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "Session not found"}), 404

    db.session.delete(session)
    db.session.commit()

    return jsonify({"status": "ok"})


def _session_preview(session: ChatSession) -> str:
    """Get a short preview of the session's first message."""
    messages = session.get_messages()
    if messages:
        first_user_msg = next(
            (m["content"] for m in messages if m["role"] == "user"), ""
        )
        return first_user_msg[:80] + ("..." if len(first_user_msg) > 80 else "")
    return "Empty conversation"
