import { env } from '$env/dynamic/public';

export const API_BASE = env.PUBLIC_API_BASE ?? 'http://localhost:8000';
export const WS_BASE = env.PUBLIC_WS_BASE ?? 'ws://localhost:8000';

export interface GameState {
	game_id: string;
	phase: string;
	round: number;
	role: string;
	inventory: number;
	backlog: number;
	last_order: number;
	cumulative_cost: number;
	incoming_shipments: Array<{ quantity: number; arrives_in_rounds: number }>;
}

export async function createSession(): Promise<{ session_id: string; join_urls: Record<string, string> }> {
	const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
	if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
	return res.json();
}

export async function startGame(gameId: string): Promise<void> {
	const res = await fetch(`${API_BASE}/games/${gameId}/start`, { method: 'POST' });
	if (!res.ok) throw new Error(`Failed to start game: ${res.status}`);
}

export async function submitOrder(gameId: string, role: string, quantity: number): Promise<void> {
	const res = await fetch(`${API_BASE}/games/${gameId}/orders`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ role, quantity })
	});
	if (!res.ok) throw new Error(`Failed to submit order: ${res.status}`);
}

export async function getState(gameId: string, role: string): Promise<GameState> {
	const res = await fetch(`${API_BASE}/games/${gameId}/state?role=${role}`);
	if (!res.ok) throw new Error(`Failed to get state: ${res.status}`);
	return res.json();
}
