/**
 * API client for the BeerGame backend.
 *
 * Classic variant  (port 8000):
 *   POST   /api/games                          → create game
 *   GET    /api/games/{game_id}                → get game state
 *   POST   /api/games/{game_id}/orders         → submit orders for this round
 *
 * Logistics Wars variant  (port 8001):
 *   POST   /api/sessions                       → create session
 *   POST   /api/sessions/{code}/join           → join session
 *   POST   /api/sessions/{id}/start            → start session
 *   GET    /api/sessions/{id}                  → get session
 *   POST   /api/sessions/{id}/orders           → place order / ship goods
 *   GET    /api/sessions/{id}/leaderboard      → leaderboard
 *   GET    /api/map                            → city + route data
 */

import type {
	GameState,
	Role,
	SubmitOrdersRequest,
	GameSession,
	Company,
	Shipment,
	TransportMode,
	LeaderboardEntry,
	MapData,
} from './types';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/** Logistics Wars backend runs on a separate port */
const LW_API_BASE = import.meta.env.VITE_LW_API_URL ?? 'http://localhost:8001';

async function handleResponse<T>(res: Response): Promise<T> {
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = (await res.json()) as { detail?: string };
			if (body.detail) detail = body.detail;
		} catch {
			// ignore parse errors — keep statusText
		}
		throw new Error(`API error ${res.status}: ${detail}`);
	}
	return res.json() as Promise<T>;
}

/**
 * Create a new Classic Beer Game.
 * @param humanRoles - list of roles controlled by a human player
 */
export async function createGame(humanRoles: Role[]): Promise<GameState> {
	const res = await fetch(`${API_BASE}/api/games`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ human_roles: humanRoles }),
	});
	return handleResponse<GameState>(res);
}

/**
 * Fetch the current state of a game.
 */
export async function getGame(gameId: string): Promise<GameState> {
	const res = await fetch(`${API_BASE}/api/games/${gameId}`);
	return handleResponse<GameState>(res);
}

/**
 * Submit orders for the current round.
 * @param gameId - the game to act on
 * @param orders - map of role → order quantity
 */
export async function submitOrders(
	gameId: string,
	orders: Record<string, number>,
): Promise<GameState> {
	const body: SubmitOrdersRequest = { orders };
	const res = await fetch(`${API_BASE}/api/games/${gameId}/orders`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	return handleResponse<GameState>(res);
}

// ── Logistics Wars API ───────────────────────────────────────────────────────

/**
 * Create a new Logistics Wars session.
 */
export async function createSession(durationMinutes = 30): Promise<GameSession> {
	const res = await fetch(`${LW_API_BASE}/api/sessions`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ duration_minutes: durationMinutes }),
	});
	return handleResponse<GameSession>(res);
}

/**
 * Join an existing session by room code, registering a player and claiming a city+role.
 * Returns the Company record for this player.
 */
export async function joinSession(
	roomCode: string,
	playerName: string,
	role: string,
	cityId: string,
): Promise<Company> {
	const res = await fetch(`${LW_API_BASE}/api/sessions/${roomCode}/join`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ player_name: playerName, role, city_id: cityId }),
	});
	return handleResponse<Company>(res);
}

/**
 * Start a session (moves it from 'lobby' → 'active').
 */
export async function startSession(sessionId: string): Promise<GameSession> {
	const res = await fetch(`${LW_API_BASE}/api/sessions/${sessionId}/start`, {
		method: 'POST',
	});
	return handleResponse<GameSession>(res);
}

/**
 * Fetch the current state of a Logistics Wars session.
 */
export async function getSession(sessionId: string): Promise<GameSession> {
	const res = await fetch(`${LW_API_BASE}/api/sessions/${sessionId}`);
	return handleResponse<GameSession>(res);
}

/**
 * Place a goods order / initiate a shipment.
 */
export async function placeOrder(
	sessionId: string,
	buyerCompanyId: string,
	sellerCompanyId: string,
	quantity: number,
	transportMode: TransportMode,
): Promise<{ session: GameSession; shipment: Shipment }> {
	const res = await fetch(`${LW_API_BASE}/api/sessions/${sessionId}/orders`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			buyer_company_id: buyerCompanyId,
			seller_company_id: sellerCompanyId,
			quantity,
			transport_mode: transportMode,
		}),
	});
	return handleResponse<{ session: GameSession; shipment: Shipment }>(res);
}

/**
 * Fetch the leaderboard for a session.
 */
export async function getLeaderboard(sessionId: string): Promise<LeaderboardEntry[]> {
	const res = await fetch(`${LW_API_BASE}/api/sessions/${sessionId}/leaderboard`);
	return handleResponse<LeaderboardEntry[]>(res);
}

/**
 * Fetch city and route map data.
 */
export async function getMapData(): Promise<MapData> {
	const res = await fetch(`${LW_API_BASE}/api/map`);
	return handleResponse<MapData>(res);
}
