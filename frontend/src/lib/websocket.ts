/**
 * WebSocket clients for live game state updates.
 *
 * Classic variant  endpoint: ws://host:8000/ws/games/{game_id}
 * Logistics Wars   endpoint: ws://host:8001/ws/sessions/{session_id}
 *
 * Both protocols: server sends raw JSON (GameState / GameSession) on every
 * state change — no wrapper envelope.
 */

import type { GameState, GameSession } from './types';

const WS_BASE = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000';
const LW_WS_BASE = import.meta.env.VITE_LW_WS_URL ?? 'ws://localhost:8001';

/**
 * Open a WebSocket connection for the given game.
 *
 * @param gameId  - the game to subscribe to
 * @param onUpdate - callback invoked with the new GameState on each update
 * @returns cleanup function — call it to close the socket
 */
export function connectToGame(
	gameId: string,
	onUpdate: (state: GameState) => void,
): () => void {
	const url = `${WS_BASE}/ws/games/${gameId}`;
	const socket = new WebSocket(url);

	socket.onmessage = (event: MessageEvent) => {
		try {
			const state = JSON.parse(event.data as string) as GameState;
			onUpdate(state);
		} catch {
			console.error('[ws] failed to parse message', event.data);
		}
	};

	socket.onerror = (event) => {
		console.error('[ws] connection error', event);
	};

	return () => {
		if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
			socket.close();
		}
	};
}

// ── Logistics Wars session WebSocket ─────────────────────────────────────────

/**
 * Open a WebSocket connection for a Logistics Wars session.
 *
 * @param sessionId - the session to subscribe to
 * @param onUpdate  - callback invoked with the new GameSession on each push
 * @returns cleanup function — call it to close the socket
 */
export function connectToSession(
	sessionId: string,
	onUpdate: (session: GameSession) => void,
): () => void {
	const url = `${LW_WS_BASE}/ws/sessions/${sessionId}`;
	const socket = new WebSocket(url);

	socket.onmessage = (event: MessageEvent) => {
		try {
			const session = JSON.parse(event.data as string) as GameSession;
			onUpdate(session);
		} catch {
			console.error('[ws:lw] failed to parse message', event.data);
		}
	};

	socket.onerror = (event) => {
		console.error('[ws:lw] connection error', event);
	};

	return () => {
		if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
			socket.close();
		}
	};
}
